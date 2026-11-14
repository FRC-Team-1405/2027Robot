# exprunner — the experiment runner

Runs an experiment from its plan file (`runs.toml`, next to the experiment's README), run by run,
and records what actually ran in `manifest.json`. Design and roadmap:
[docs/experiment-runner-plan.md](../../docs/experiment-runner-plan.md).

Two kinds of experiment:

- **Bench** (`kind = "bench"`): steps that run on the Orange Pis over SSH, with no robot. The runner
  copies a bench bundle to each Pi, runs each step, and fetches the results.
- **Robot** (`kind = "robot"`): for each run it **sets PhotonVision on the Pis, checks it took, hands
  over for an auto, notices the robot enable and disable, fetches the log through LogBench, and records
  it all** in `manifest.json`. Section below.

## A robot session in four commands

LogBench running (VS Code task `LogBench`), the laptop on the robot network, the robot code running:

```bash
python -m exprunner doctor PLAN      # is everything ready? one line per check, says what to fix
python -m exprunner run PLAN         # every run, in order; stop and resume any time
python -m exprunner finish PLAN      # put the cameras back to what they were before
python analyze.py                    # (each experiment's own) reads manifest.json
```

`run` does this per run, printing each step:

1. **Refuses to change anything while the robot is enabled.**
2. Works out each camera's full settings (the plan's `[defaults]` plus the named setting) and reads what
   each camera is set to *now* from the Pi publisher (`/OrangePi/...` over NetworkTables).
3. Sends **only the differences** to PhotonVision's web socket (`ws://<pi>:5800/websocket_data`).
4. Reads them back until every value matches. If PhotonVision can't be reached, or ignores one, it says
   exactly what to set by hand in the PhotonVision UI, waits, and carries on as soon as the Pi shows
   it. (`--manual` goes straight to that.)
5. Tells you to close PhotonVision tabs and enable the auto, notices **enable then disable** on
   `/FMSInfo/FMSControlData`, and notes the window in robot time (a log holding several runs can be split
   later). It checks the settings again afterwards and fails the run if anything changed during it.
6. Writes the run into `manifest.json`: what was asked, what was read back, the enable window (robot time).
7. **After the last run, fetches the robot log once** through LogBench, as the Fetch Bundle page does. All
   runs of a session are in one log (the robot code isn't restarted), told apart by their enable windows, so
   there is one download, not one per run. It prefers the AdvantageKit log (`akit_*`) over WPILib's
   `FRC_*.wpilog` (NetworkTables mirrored, out of time order), and does **not** download the Pis' vision
   recordings unless you pass `--with-pi` (they are large, and every session since the last log rotation
   comes along, so each download was bigger than the last).

Before the first run it records each camera's settings as a **baseline**; `finish` puts them back, so a
session never leaves the cameras on an experiment setting.

| Command | Does |
|---|---|
| `doctor PLAN` | Checks NetworkTables, the Driver Station word, each camera's publisher, PhotonVision's web socket and its camera-mode list, and LogBench |
| `run PLAN [IDS...]` | Runs the runs not done yet (or the named IDs again). `--redo`, `--keep-going` |
| `fetch PLAN` | Downloads the robot log for runs that don't have it yet (`run` does this itself at the end; use this to retry) |
| `apply PLAN ID` | Sets PhotonVision to a run's settings without running it |
| `finish PLAN` | Restores the baseline |
| `status PLAN` | Done / failed / to do, with each run's cameras, log and the baseline if cameras are still changed |
| `check PLAN` | Validates the plan; prints every run's full settings per camera |
| `pv-dump HOST` | Prints what PhotonVision's web socket sends (to debug; see below) |

Options for `run`, `apply`, `finish`, `doctor`: `--nt HOST[:PORT]` (default: team 1405; `localhost` for
the simulator), `--manual`, `--no-robot` (don't connect: nothing is checked from the Pis and you press
Enter at the start and end of each run), `--fetch end|each|none` (when to download the log: once at the end, the
default; after every run, for sessions where the robot code will restart; never), `--with-pi`, `--logbench URL`.
If the robot code **restarts** during a session, its earlier runs are in an older log: use `--fetch each`.

### If PhotonVision's web socket changes

The web socket is what the PhotonVision UI uses, not a public API (v2026.1.1), so a PhotonVision update
can break it. Everything PhotonVision-specific is in [`pv.py`](exprunner/pv.py) and
[`settings.py`](exprunner/settings.py). The runner never trusts a send, it reads each value back, so a
broken web socket shows up as "set these by hand", not as a wrong experiment. `python -m exprunner
pv-dump LeftPi.local` prints the messages PhotonVision sends (and the camera mode list it found), which
is what to look at when fixing it. **The first live session is the first test against real PhotonVision**:
the message shapes were checked against the PhotonVision v2026.1.1 source (`DataSocketHandler`, `VisionModuleChangeSubscriber`, `UIPhotonConfiguration`) and tested here against fake servers.

## Robot plan files

```toml
experiment = "VIS-2026-11-14-pv-crossover-odometry"
kind = "robot"
routine = "CircleFacingTag_Tag10"                   # the auto you'll be asked to enable
cameras = ["LeftPi/LeftCam", "RightPi/RightCam"]    # Pi/camera, as in coprocessor/robots.json

[defaults]                                          # every setting starts from these
decimate = 2
threads = 8
low_latency = false

[settings.A]
camera_mode = "800x600 MJPG @100"
[settings.B]
camera_mode = "1280x800 MJPG @100"

[[runs]]
id = "X1a"
what = "Left on A, Right on B"
use = { LeftCam = "A", RightCam = "B" }             # or  use = { all = "A" }
prompt = "Optional text shown before the run"
```

Settings you can name (see [`settings.py`](exprunner/settings.py)): `camera_mode`, `decimate`, `threads`,
`low_latency`, `multitag`, `refine_edges`, `blur`, `decision_margin`, `pose_iterations`, `hamming`,
`auto_exposure`, `exposure`, `brightness`, `gain`. A setting a plan doesn't name is left as it is.

## Use

From this folder:

```bash
python -m exprunner check  ../../docs/experiments/vision/2026-11-11-pv-frame-cost/runs.toml
python -m exprunner run    ../../docs/experiments/vision/2026-11-11-pv-frame-cost/runs.toml
python -m exprunner status ../../docs/experiments/vision/2026-11-11-pv-frame-cost/runs.toml
```

| Command | Does |
|---|---|
| `check PLAN` | Validates the plan; prints each run's prompt, boards and the exact command it runs on the Pi |
| `sync PLAN [--board B]` | Builds the bench bundle and copies it to the plan's Pis (copy only; nothing is installed) |
| `run PLAN [IDS...]` | Syncs, then runs every run not done yet, in order. Named IDs run again even if done. `--redo` reruns everything, `--board B` limits to one Pi, `--yes` skips prompts, `--keep-going` carries on after a failure, `--no-sync` skips the copy |
| `status PLAN` | Done / failed / to do, per run and board |

Stopping (Ctrl+C) or a failure is safe: run it again and it carries on from what's left. A rerun
keeps the previous attempt under `history` in the manifest.

## What it needs

- **The team SSH key** at `~/.ssh/id_ed25519_orangepi`. `coprocessor/Bootstrap-OrangePi.ps1` puts
  it there the first time it runs on a laptop.
- **OpenSSH client** (`ssh`, `scp`): built into Windows 10+, macOS and Linux.
- **WPILib installed and the robot code built once.** The bench program is compiled here, with
  WPILib's JDK, against WPILib's jars (from the WPILib install or the Gradle cache).
- Python 3.11+. Bench plans need only the standard library; **robot plans also need**
  `python -m pip install -r requirements.txt` (`pyntcore`, `websockets`, `msgpack`).
- The Pis listed in `coprocessor/robots.json`; boards are named as there.
- Robot plans: LogBench running with remote fetching configured (`tools/logbench/remote_config.json`), and the
  Pi publisher (`orangepi-nt-publisher`) running on each Pi, since that is where the runner reads settings back from.

## Plan files

See the docstring at the top of [`exprunner/plan.py`](exprunner/plan.py), and
[the frame-cost plan](../../docs/experiments/vision/2026-11-11-pv-frame-cost/runs.toml) for a full
example. In short: `experiment`, `kind = "bench"`, `boards`, optional `[defaults.<step>]` tables,
then `[[runs]]` with `id`, `step`, `what`, an optional `prompt` (the runner waits for Enter), and
`args` (passed to the step as `--key value`; lists become `1,2,3`, booleans `yes`/`no`).

The steps are those of [`coprocessor/bench/run.sh`](../../coprocessor/bench/README.md).

## Where things go

| Where | What |
|---|---|
| Pi: `~/bench/code/` | The bundle: `run.sh`, compiled `classes/`, `BUILD.txt` (commit it was built from). Replaced on every sync |
| Pi: `~/bench/frames/` | Captured frames (`<name>.mjpg`). Kept between runs; they're big, so they stay on the Pi |
| Pi: `~/bench/results/<experiment>/<run>/` | One run's output, cleared before the run |
| Laptop: `<plan folder>/data/<run>/<board>/` | That output fetched back, plus `step.log` (everything the step printed) |
| Laptop: `<plan folder>/manifest.json` | Per run and board: status, exit code, command, start/finish, git commit, Pi host |

## Tests

```bash
python -m pytest
```

The bench run loop is tested against a fake Pi. The robot run loop is tested end to end against fakes
of the robot, PhotonVision and LogBench (`tests/test_robot.py`), and against a real in-process NetworkTables
server and web socket server (`tests/test_integration.py`, including a full `run` through the CLI). `test_build.py` really compiles `FrameCost.java` when a
JDK and WPILib's jars are present, so a broken bench program shows up before it reaches a Pi.
