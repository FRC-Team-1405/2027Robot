# Simulated match for the Orange Pi vision recorder

Test `orangepi-vision-recorder.py` end to end without a roboRIO.

## Quickest: a whole match on a real Pi, one command

From the laptop (after `..\Bootstrap-OrangePi.ps1` has set the Pi up):

```powershell
.\Run-SimulatedMatch.ps1 -Address <pi-ip> -KeyPath $HOME\.ssh\id_ed25519_claude
# -Fast 4 for a quick run, -Extra '--drop-at-sec 30 --drop-for-sec 3' for a comms dropout,
# -Extra '--loops 2' for two matches, -Extra '--no-clock' for the unsynced-clock path
```

It points the real `orangepi-vision-recorder@<camera>.service` at a fake roboRIO running on the Pi
(a temporary systemd drop-in, always removed afterwards; recordings go to a throwaway
`~/sim-recordings`), plays pre-match, auto, pause, teleop and post-match against the live
PhotonVision stream, pulls everything back to `sim\runs\<timestamp>-<label>\` and runs
`verify_recordings.py`. Real durations take about 3.5 minutes.

The verifier checks the ground truth (`events.jsonl` from `fake_robot.py`) against what was
recorded: one session per enabled window (so auto and teleop are separate across the pause),
folder names, manifest and JPEG agreement, `t_sec` ordering, frames only inside enabled windows,
frame counts at the sample rate, valid JPEGs, nothing recorded while disabled, and **frame
freshness**. For freshness, `frame_tap.py` runs on the Pi and logs when every frame left
PhotonVision (PhotonVision sends byte-identical JPEGs to every client), so each recorded frame
is matched by hash to its true age. Exit status is 1 if any check fails.

Recorded frames carry no auto/teleop label; it is inferred from order and time only.

- `fake_robot.py` is an NT4 **server** (needs only `pyntcore`) that plays a match by publishing
  `/FMSInfo/FMSControlData` (HAL control word) and `/RobotTime/WallClockMs`.
- `fake_mjpeg.py` is a stdlib-only MJPEG server for **laptop/pytest use**: every frame is a
  valid 320x240 JPEG showing a frame counter and a millisecond wall clock, and carries the same
  numbers in a JPEG comment segment (`decode_frame_info(jpeg)` reads them back). The Pi uses
  the real PhotonVision stream instead.

The recorder reads two optional env vars for this (unset = unchanged, `setServerTeam(1405)`):
`NT_SERVER` (host/IP) and `NT_PORT` (default NT4 port 5810). `SAMPLE_HZ`, `MAX_STORAGE_BYTES` and
`NT_DROP_GRACE_SEC` are also overridable.

Files here: `fake_robot.py` (fake roboRIO), `fake_mjpeg.py` (fake camera for pytest),
`frame_tap.py` (ground-truth frame arrival log, runs on the Pi), `verify_recordings.py` (the
checks), `Run-SimulatedMatch.ps1` (orchestrates all of it against a real Pi).

## Real robot code in simulation, real Pi, real LogBench bundle

`Run-SimulatedMatch.ps1` uses a fake roboRIO and produces no AdvantageKit log. To test the whole
path to the LogBench dashboard, run the **actual robot code** in `gradlew simulateJava` on the
laptop and let the Pi record it:

```powershell
.\Run-SimRobotMatch.ps1 -Address <pi-ip> -KeyPath $HOME\.ssh\id_ed25519_claude
# -Fast 4 to compress it, -Script 'disabled:5,auto:10,disabled:4,teleop:40,disabled:6' for a custom timeline,
# -LogCameras LeftCam,RightCam,Rear for more feeds, -UseRealRecordings to write into ~/vision-recordings
```

Run it from your own PowerShell (Gradle needs normal sockets). What happens:

1. One temporary recorder instance per camera (`orangepi-vision-recorder@<camera>`, default `LeftCam,RightCam`) is started with a temporary env file pointing at the laptop (`NT_SERVER`, port 5810). The Pi has one webcam, so the **first camera records the real PhotonVision stream and every other camera records a fake one** (`fake_mjpeg.py` on the Pi: a frame counter and clock), so the two feeds look obviously different when you switch between them. The Pi's normal `@bench` service is not touched.
2. `frc.robot.sim.ScriptedMatch` (inert unless `SIM_MATCH_SCRIPT` is set) waits for the Pi to connect, then drives the simulated Driver Station through disabled, auto, pause, teleop, disabled with random stick input. `Robot` writes an AdvantageKit log named in UTC (`akit_<yy-MM-dd_HH-mm-ss>_simmatch.wpilog`) when `SIM_LOG_DIR` is set; `SIM_HEADLESS` skips the GUI.
3. The Pi's sessions are copied to `<log>.vision\<LogCamera>\` beside the log, the temporary instances and fake cameras are removed (always), and `tools\logbench\testkit\check_bundle.py` reports coverage and problems.

The log and the recordings share one NT clock and one wall clock, as on the real robot. The result
is a folder you open with `python tools\logbench\server\main.py --logs <folder>`.

Needs: inbound TCP 5810 allowed through Windows Firewall for the Java that simulateJava runs
(WPILib 2026 JDK); an elevated `New-NetFirewallRule -DisplayName 'NT4 sim' -Direction Inbound
-Protocol TCP -LocalPort 5810 -Action Allow` does it. `probe_sim_nt.py` connects to a running
simulation the way the recorder does and confirms `/FMSInfo/FMSControlData` and
`/RobotTime/WallClockMs` are published, without involving the Pi.

Environment the simulation reads (all optional): `SIM_MATCH_SCRIPT`, `SIM_MATCH_FAST`,
`SIM_MATCH_WAIT_CLIENTS`, `SIM_MATCH_SEED`, `SIM_MATCH_EXIT`, `SIM_LOG_DIR`, `SIM_HEADLESS`; see
`ScriptedMatch.java`.

## Laptop only (everything local)

```bash
python coprocessor/sim/fake_mjpeg.py --port 5921 --fps 30 &
NT_SERVER=127.0.0.1 NT_PORT=5922 CAMERA_STREAM_URL=http://127.0.0.1:5921/stream.mjpg \
  RECORDINGS_DIR=/tmp/rec CAMERA_NAME=test SAMPLE_HZ=10 \
  python coprocessor/orangepi-vision-recorder.py &
python coprocessor/sim/fake_robot.py --port 5922 --wait-for-clients 1 --fast 5 --event-log events.jsonl
```

## Real Pi, fake robot on the laptop

Run the fake robot on the laptop and point the Pi's recorder at it. PhotonVision may already use
the standard NT port 5810 on the Pi, so pick another `--port` (5811 below); the laptop firewall
must allow it inbound.

```bash
# laptop
python coprocessor/sim/fake_robot.py --port 5811 --wait-for-clients 1 --event-log events.jsonl
# Pi (stop the systemd instance first, or use a separate RECORDINGS_DIR); keeps the real camera stream
NT_SERVER=<laptop-ip> NT_PORT=5811 CAMERA_STREAM_URL=http://localhost:1181/stream.mjpg \
  RECORDINGS_DIR=/tmp/vision-sim CAMERA_NAME=left \
  ~/.venv-ntpublisher/bin/python3 orangepi-vision-recorder.py
```

The fake robot can also run on the Pi itself (`--listen 127.0.0.1 --port 5811`, recorder with
`NT_SERVER=127.0.0.1 NT_PORT=5811`). Use `--stay-up` to keep serving after the match.

## fake_robot.py flags

| Flag | Default | |
| --- | --- | --- |
| `--listen` / `--port` | `0.0.0.0` / `5810` | NT4 server address |
| `--pre-sec`, `--auto-sec`, `--pause-sec`, `--teleop-sec`, `--post-sec` | 5, 20, 3, 140, 10 | phase lengths; auto and teleop are the enabled ones |
| `--fast N` | 1 | divide every phase length by N |
| `--loops N`, `--between-matches-sec S` | 1, 5 | repeat the match; disabled gap between (also divided by `--fast`) |
| `--fms` | off | set the fmsAttached bit (control word +16) |
| `--clock-offset-sec N` | 0 | skew the published `WallClockMs` |
| `--no-clock` | off | never publish `WallClockMs` (recorder labels folders "NOT synced") |
| `--drop-at-sec T`, `--drop-for-sec D` | off, 2 | stop the NT server T s into teleop, restart D s later (comms loss). Real seconds, not divided by `--fast` |
| `--wait-for-clients N` | 0 | hold the timeline (control word 0) until N NT clients connect |
| `--event-log PATH` | none | JSONL transition log |
| `--stay-up` | off | keep serving after the last phase |

Control words: pre/pause/post/between = 32 (DS attached), auto = 35 (enabled + auto + DS),
teleop = 33; add 16 with `--fms`.

## Event log

One JSON object per line, appended at each transition (`pre_match`, `auto`, `pause`, `teleop`,
`post_match`, `between`, `done`, plus `clients_connected`, `drop_start`, `drop_end`):

```json
{"phase": "auto", "control_word": 35, "wall_ms": 1792341704539, "server_time_sec": 1792341704.539117, "mono_sec": 1.012, "match": 1}
```

`server_time_sec` is the NT server clock, the same domain as the recorder's `t_sec` (frame
file names and manifest). A frame is legitimate if its `t_sec` falls inside an `auto`/`teleop`
window, i.e. from that event's `server_time_sec` to the next phase event's. `wall_ms` is the
real UTC time (not skewed by `--clock-offset-sec`).

## pytest

`python -m pytest coprocessor/tests/test_simulated_match.py -q` (about 35 s; skipped if `ntcore`
is not installed). It starts `fake_mjpeg` in-process on a free port, runs `fake_robot.py` and the
real recorder as subprocesses on free ports (`--fast`, `SAMPLE_HZ=10`), and checks sessions,
folder names, manifests, `t_sec` against the event-log windows, frame counts, boot-id increment,
the storage cap, frame freshness (a regression test for recorded frames falling behind real
time), and NT dropouts: a short one keeps one continuous session, one longer than
`NT_DROP_GRACE_SEC` ends it.
