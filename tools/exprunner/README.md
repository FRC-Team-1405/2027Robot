# exprunner — the experiment runner

Runs an experiment from its plan file (`runs.toml`, next to the experiment's README), run by run,
and records what actually ran in `manifest.json`. Design and roadmap:
[docs/tools/experiment-runner-plan.md](../../docs/tools/experiment-runner-plan.md).

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
7. **Fetches the robot log** through LogBench, as the Fetch Bundle page does, **after every run**, so a crash or a
   dead battery later loses nothing. A log only ever grows at its end, so each fetch **resumes**: it checks the
   copy it already has is the start of the same log and downloads only what the robot wrote since (a few MB, not
   the whole log again). It prefers the AdvantageKit log (`akit_*`) over WPILib's `FRC_*.wpilog`, and does **not**
   download the Pis' vision recordings unless you pass `--with-pi` (they are large, and every session since the log
   rotation comes along, so each download was bigger than the last).

Before the first run it records each camera's settings as a **baseline**; `finish` puts them back, so a
session never leaves the cameras on an experiment setting.

| Command | Does |
|---|---|
| `doctor PLAN` | Checks NetworkTables, the Driver Station word, each camera's publisher, PhotonVision's web socket and its camera-mode list, and LogBench |
| `run PLAN [IDS...]` | Runs the runs not done yet (or the named IDs again). `--attempt NAME`, `--redo` (new attempt), `--keep-going` |
| `fetch PLAN` | Downloads the robot log for runs that don't have it yet (`run` does this itself at the end; use this to retry) |
| `apply PLAN ID` | Sets PhotonVision to a run's settings without running it |
| `finish PLAN` | Restores the baseline |
| `status PLAN` | Done / failed / to do, with each run's cameras, log and the baseline if cameras are still changed |
| `check PLAN` | Validates the plan; prints every run's full settings per camera |
| `link [--board B]` | Each Pi's Ethernet speed, duplex, errors, and what the *other end* of the cable offers (read-only, over SSH; no plan needed). Built for the [Left Pi link-speed test](../../docs/experiments/coprocessor/left-pi-link-speed/README.md) |
| `pv-dump HOST` | Prints what PhotonVision's web socket sends (to debug; see below) |

Options for `run`, `apply`, `finish`, `doctor`: `--nt HOST[:PORT]` (default: team 1405; `localhost` for
the simulator), `--manual`, `--no-robot` (don't connect: nothing is checked from the Pis and you press
Enter at the start and end of each run), `--fetch each|end|none` (when to download the log: after every run, the
default; once after the last run; never), `--with-pi`, `--logbench URL`.
If the robot code **restarts** during a session, runs from before the restart are in an older log; `each` (the
default) has already fetched them, so nothing is lost.

### If PhotonVision's web socket changes

The web socket is what the PhotonVision UI uses, not a public API (v2026.1.1), so a PhotonVision update
can break it. Everything PhotonVision-specific is in [`pv.py`](exprunner/pv.py) and
[`settings.py`](exprunner/settings.py). The runner never trusts a send, it reads each value back, so a
broken web socket shows up as "set these by hand", not as a wrong experiment. `python -m exprunner
pv-dump LeftPi.local` prints the messages PhotonVision sends (and the camera mode list it found), which
is what to look at when fixing it. **The first live session is the first test against real PhotonVision**:
the message shapes were checked against the PhotonVision v2026.1.1 source (`DataSocketHandler`, `VisionModuleChangeSubscriber`, `UIPhotonConfiguration`) and tested here against fake servers.

## Flipping robot-code switches (the common validation experiment)

A change we want to validate goes behind a switch in
[`ExperimentSwitches.java`](../../src/main/java/frc/robot/constants/ExperimentSwitches.java): an AdvantageKit
`LoggedNetworkBoolean` at `/Tuning/ExperimentSwitches/<NAME>` that can be flipped **while the robot code runs**, so
no redeploy sits between the "off" and "on" runs. The runner writes it, reads it back from the robot, and the log
records it every loop, so the analysis can check the log agrees. A plan just names it per run:

```toml
experiment = "RIO-loop-overruns-process-cpu"
kind = "robot"
routine = "Teleop, sticks untouched, for 2 minutes"       # no cameras needed: a plan can be switches only

[[runs]]
id = "OFF1"
switches = { RIO_PROCESS_CPU_LOGGING = false }

[[runs]]
id = "ON1"
switches = { RIO_PROCESS_CPU_LOGGING = true }
```

Switches and camera settings can be mixed in one run (`use = {...}` and `switches = {...}`). Per run the runner reads the
switch, writes it if it differs, waits until the robot reports the new value (or fails the run, saying so), and records
`switches_asked` and `switches_read_back`. It checks again after the run and fails it if the switch moved. The first run
records what the switches were before; `finish` puts them back. `doctor` says if the robot isn't publishing a switch
(the code on the robot doesn't have it: deploy the branch that does). It can't flip the compile-time constants in
`FeatureSwitches.java`; those need a redeploy, and the analysis can read them from the log's `Metadata/FeatureSwitches`.

**The whole pattern, in a runs.toml:** off, on, off, on (so drift hits both) with the same maneuver, then
`wpilog_utils.switches.switch_values(signals, NAME, window)` in the experiment's `analyze.py` to confirm from the log
which way each run really was. The loop-overruns experiment is the example:
[`docs/experiments/roborio/loop-overruns/`](../../docs/experiments/roborio/loop-overruns/runs.toml).

## Robot plan files

```toml
experiment = "VIS-pv-crossover-odometry"
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
A run can also set robot-code `switches` (above), with or without cameras.

## Use

From this folder:

```bash
python -m exprunner check  ../../docs/experiments/vision/pv-frame-cost/runs.toml
python -m exprunner run    ../../docs/experiments/vision/pv-frame-cost/runs.toml
python -m exprunner status ../../docs/experiments/vision/pv-frame-cost/runs.toml
```

| Command | Does |
|---|---|
| `check PLAN` | Validates the plan; prints each run's prompt, boards and the exact command it runs on the Pi |
| `sync PLAN [--board B]` | Builds the bench bundle and copies it to the plan's Pis (copy only; nothing is installed) |
| `run PLAN [IDS...]` | Syncs, then runs every run not done yet, in order. Named IDs run again even if done. each go is an *attempt* (`<plan folder>/attempts/<date>/`): it continues the latest unfinished one (under 18 h old) or starts today's; `--attempt NAME` picks one, `--redo` forces a new one; `--board B` limits to one Pi, `--yes` skips prompts, `--keep-going` carries on after a failure, `--no-sync` skips the copy |
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
[the frame-cost plan](../../docs/experiments/vision/pv-frame-cost/runs.toml) for a full
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
| Laptop: `<plan folder>/attempts/<date>/manifest.json` | Per run and board: status, exit code, command, start/finish, git commit, Pi host |

## Tests

```bash
python -m pytest
```

The bench run loop is tested against a fake Pi. The robot run loop is tested end to end against fakes
of the robot, PhotonVision and LogBench (`tests/test_robot.py`), and against a real in-process NetworkTables
server and web socket server (`tests/test_integration.py`, including a full `run` through the CLI). `test_build.py` really compiles `FrameCost.java` when a
JDK and WPILib's jars are present, so a broken bench program shows up before it reaches a Pi.
