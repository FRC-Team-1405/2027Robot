# Experiment runner — plan

A laptop tool that runs a robot experiment run by run. Before each run it sets PhotonVision on
both Pis, checks the settings took, then hands over to a person to run the auto. Afterwards it
fetches that run's log through LogBench and records what ran. The person still enables and
disables the robot. Everything else is done by the tool.

Status: **built** (`tools/exprunner`). **Bench experiments** (2026-11-11): plan files, manifest,
copy-only sync of `coprocessor/bench/` to the Pis, steps run over SSH, results fetched back; first used
by the [frame-cost bench test](experiments/vision/2026-11-11-pv-frame-cost/README.md). **Robot
experiments** (2026-11-14): build order steps 1-5 below, all built, and tested end to end against fakes
and against real in-process NetworkTables and web socket servers. **Not yet run against a live
PhotonVision**: that is the first real test of the web socket messages (`pv-dump` exists for debugging).
Nothing here needs a change to PhotonVision or the robot code. The pieces it calls already exist (see
"What already exists").

How it differs from the design below (decided while building):

- **Plan files are TOML**, like the bench plans, not YAML: `[defaults]`, `[settings.A]`, and `use = {
  LeftCam = "A", RightCam = "B" }` per run, so two cameras can differ within a run (the crossover).
- **No Main/Experiment pipelines.** The runner works on the camera's current pipeline and records each
  camera's settings as a **baseline** before the first run; `finish` restores it. That needs no manual
  pipeline setup. Named pipelines can still be added later.
- **`doctor`** checks a session is ready (NetworkTables, Driver Station word, each camera's publisher,
  PhotonVision's web socket and mode list, LogBench), and **`--manual`** exists: if the web socket fails
  the runner says what to set in the PhotonVision UI and waits for the Pi to show it.
- The settings are checked again **after** the run; a change during it fails the run.

## Why

How a session runs today (11-03, 11-07, 11-10):

1. Change settings in the PhotonVision web UI on each Pi, by hand.
2. Close every PhotonVision tab, enable the auto, disable it.
3. Write the log name and settings into the notes table.
4. After the session, fetch the bundles in LogBench. At home, type each run's log into
   `analyze.py`'s `RUNS` and run it.

That costs time at the robot and invites mistakes we've actually made:

- **11-07:** the camera was at @120 for six runs while the notes said @100. Only the settings
  logging caught it.
- **11-10:** B5's "drawing off" was done as Processed → Raw, and threads were still 1 from B4. The
  logs caught both, after the session.
- Every session: log names copied by hand, and settings re-typed into `analyze.py`.

Setting PhotonVision from a written plan, and checking it before each run, removes the first two
mistakes. Recording the log name automatically removes the third.

## What already exists

| Need | Where it is today | Notes |
|---|---|---|
| Change a PhotonVision setting from a script | PhotonVision's websocket, `ws://<pi>:5800/websocket_data` | The web UI uses it. Message (MessagePack): `{"changePipelineSetting": {"cameraUniqueName": "<cam>", "threads": 4}}`. Any pipeline field by name, plus `camera*` fields for the camera (e.g. `cameraVideoModeIndex`). PhotonVision saves it to disk. Source: `DataSocketHandler`, `VisionModuleChangeSubscriber` (v2026.1.1) |
| Switch pipeline from a script | NetworkTables `photonvision/<cam>/pipelineIndexRequest`, or the websocket's `currentPipeline` | Only to move between the Main and Experiment pipelines (below); not one pipeline per test |
| Check the settings took | Pi publisher: `/OrangePi/<Pi>/PhotonVision/<cam>/*` (Decimate, Threads, LowLatencyMode, PipelineJson, PipelineIndex) and `/OrangePi/<Pi>/Video/video0/Mode` | Read from PhotonVision's saved settings every 5 s (`PV_SETTINGS_INTERVAL_S`), and the camera's real mode. Also in the log, so analysis can check it again |
| Know when the robot is enabled | NetworkTables `/FMSInfo/FMSControlData` (enabled / auto bits) | Same bits the recorder already decodes |
| Read NetworkTables from Python | `pyntcore`, already in LogBench's requirements | LogBench's `live_nt.py` already connects |
| Fetch the newest log + the Pis' recordings, trimmed and zipped | LogBench HTTP API: `POST /api/remote/sessions/jobs` → poll `GET /api/remote/jobs/{id}` → `POST /api/remote/bundle/jobs` (`prepare_download: true`) → poll → `GET /api/remote/jobs/{id}/download` | What the Fetch Bundle page uses. Already handles a log the robot is still writing |
| Analyze a list of runs | Each experiment's `analyze.py` with a hand-typed `RUNS` list | Would read the runner's manifest instead |

## How a session would go

```
laptop> python -m exprunner run docs/experiments/vision/<experiment>/runs.yaml

B1  800x600 @100, dec 1, threads 8, drawing on
  setting LeftPi/LeftCam ... RightPi/RightCam ... ok
  checking (from /OrangePi/*): mode 800x600 MJPG @100 ✓  dec 1 ✓  threads 8 ✓  LL off ✓
  ► Close any PhotonVision tabs. Enable CircleFacingTag now; disable when it's done.
  enabled 23:15:02 … disabled 23:15:24 (21.9 s)
  fetching akit_26-11-10_23-14-41 via LogBench … ok (trimmed, 3.2 MB)
  recorded B1 → manifest.json
B2  800x600 @100, dec 1, threads 4, drawing on
  ...
```

Per run, the runner:

1. **Refuses to change anything while the robot is enabled.**
2. **Applies the run's settings** to every camera listed (websocket), only the ones that differ
   from what's there.
3. **Checks them** from the publisher's `/OrangePi/*` topics until every value matches, or stops
   after ~15 s and says which didn't. This catches a setting PhotonVision ignored, and a camera
   mode that didn't switch.
4. **Closes its own websocket** and asks the person to close PhotonVision tabs, then waits.
5. **Watches for enable → disable** on `/FMSInfo`. It notes the enable window in robot time, so a
   log holding several runs can still be split later. Pressing Enter instead also works, for
   tests that don't use the robot.
6. **Fetches the newest log** through LogBench's API, with the matching Pi recordings, trimmed
   and zipped. Same as clicking Fetch Bundle.
7. **Writes the manifest**: run ID, log name, enable window, the settings asked for, the settings
   read back, and anything that didn't match. `analyze.py` reads the manifest, so `RUNS` isn't
   typed by hand any more.

Commands: `run` (from the first run not done), `run --only B3` (redo one), `status`, and
`apply B7` (set the Experiment pipeline to a run's settings without running), and `finish`
(switch every camera back to Main and check it).

## The run plan file

One per experiment, next to its README. Defaults first, then what each run changes, so "change
one thing per run" is visible at a glance:

```yaml
experiment: VIS-2026-11-10-pv-frame-budget
cameras: [LeftPi/LeftCam, RightPi/RightCam]   # Pi/camera, as in robots.json
routine: CircleFacingTag
defaults:
  camera_mode: 800x600 MJPG @100
  decimate: 1
  threads: 8
  low_latency: false          # PhotonVision's blockForFrames
runs:
  - {id: B1, note: baseline}
  - {id: B2, threads: 4}
  - {id: B3, threads: 3}
  - {id: B4, threads: 1}
  - {id: B6, camera_mode: 800x600 MJPG @120, decimate: 2}
```

Friendly names map to PhotonVision fields in one table in the runner (`low_latency` →
`blockForFrames`, `camera_mode` → `cameraVideoModeIndex`, ...). The PhotonVision-specific parts
stay in one place.

## Open details to settle while building

- **Camera mode by name.** PhotonVision sets the mode by index into that camera's mode list, and
  the list can differ between cameras. The runner has to get each camera's list (PhotonVision
  sends it to websocket clients on connect) and pick the index whose resolution, format and fps
  match. Check this first: it's the one part the publisher can't confirm from the settings alone.
  The camera's real mode (`Video/video0/Mode`) does confirm the result.
- **Settings, not pipelines.** The runner changes settings; it never builds a pipeline per test
  case. Pipelines are for **known-good states** we've decided on, and for switching between them
  in a match if that's ever needed. A pipeline per test case would need building and cleaning up
  every experiment, and would bury the real pipelines among throwaway ones.
- **Two pipelines per camera: "Main" and "Experiment".** Same on both Pis.
  - **Main:** the setting we compete with (today 800x600 @100, decimate 2, Low Latency off,
    threads 8). The runner never edits it. Later known-good states, like a long-range setting,
    would get their own named pipelines next to it.
  - **Experiment:** one permanent pipeline, reused by every experiment. The runner switches each
    camera to it, edits only it, and switches back to Main at the end of the session (`exprunner
    finish`). A session cut short still leaves Main untouched; the next `status` or `finish`
    puts the cameras back.
  - **Each session starts from Main.** The first thing `run` does is copy Main's settings into
    Experiment, so a run plan's `defaults` change things relative to Main, and nothing is left over
    from the last experiment.
  - **Set up once by hand** (or by `exprunner setup`): duplicate Main on each camera and name the
    copy "Experiment". Camera calibration is per camera, not per pipeline, so the copy has it.
  - **Leaving a camera on Experiment by accident** is the risk. `exprunner status` shows each
    camera's pipeline and its settings against Main. At match time the robot could make sure:
    when an FMS is attached, it requests Main (`PhotonCamera.setPipelineIndex`). Robot code
    doesn't set a pipeline today.
- **If the websocket protocol changes** in a PhotonVision release, the fix goes in the runner's
  one PhotonVision module (fresh message names, or PhotonVision's settings import), not into a set
  of pipelines.
- **PhotonVision version.** The websocket messages are what the v2026.1.1 UI sends; they aren't a
  public API. The runner records PhotonVision's version (`/api/status`) in the manifest. Re-check
  the messages after every PhotonVision update.
- **LogBench must be running** (the VS Code task) for the fetch step. The runner checks first and
  says so if it isn't.
- **One log or one per run.** The runner fetches the newest log after every run either way.
  Repeated fetches of a log still being written keep growing. The enable window in the manifest
  says which part of the log belongs to which run.

## Pi-side scripts (bench tests)

Some tests run on the Pi itself, with no robot: ADR 0002's bench tests 1 and 2, for example. For
those:

- A **`coprocessor/bench/`** folder of scripts, copied to `~/bench/` on each Pi by a **copy-only
  sync**. That means a `-SyncOnly` mode for `Bootstrap-OrangePi.ps1` that runs just its file-copy
  step, not a reinstall. The old separate sync script was folded into the bootstrap wizard in
  `4bc9ae9`, so this would bring the idea back without a second script.
- The runner can then run a bench step over SSH (`python3 ~/bench/<script>.py ...`) and copy its
  results back into the experiment folder, using the team key the bootstrap already installs.
  The same run plan file and manifest apply, with `trigger: none` instead of an auto.

## Build order

Each step is useful on its own:

1. **Fetch + manifest** (no PhotonVision changes): after each run the person presses Enter, and the
   runner fetches the newest bundle through LogBench and records it. This alone removes copying
   log names and typing `RUNS`.
2. **Read-back check**: before each run, compare `/OrangePi/*` with the plan and refuse to go on
   if they differ. This would have caught 11-07's @120 and 11-10's B5 at the robot.
3. **Apply settings over the websocket**, including the camera mode by name.
4. **Auto-detect enable → disable** on `/FMSInfo`.
5. **`analyze.py` reads the manifest.** Change the frame-budget `analyze.py` first, as the
   example.
6. **Copy-only sync + bench runs over SSH.**

Where the code lives: `tools/exprunner/`, a Python package and CLI like `tools/wpilog-janitor/`.
It talks to LogBench over HTTP rather than importing it, so there's one implementation of
fetching. It needs `pyntcore`, `websockets` and `msgpack`, plus `requests` or the standard library
for HTTP.
