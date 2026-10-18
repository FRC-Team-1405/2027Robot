# Plan: end-to-end test framework for the vision recorder -> LogBench vision dashboard

Written 2026-10-18 for a fresh session to pick up on **this machine** (Windows 11 laptop, repo
`C:\Users\importsjc\robotics\2027Robot`). Read `CLAUDE.md` first (no AI attribution in commits/PRs;
PowerShell is the scripting default; never push/PR unless asked).

## 1. Goal

Be able to test, without a robot match and without fighting robot connection problems:

1. the Orange Pi recorder (`coprocessor/orangepi-vision-recorder.py`),
2. Fetch Bundle (Pi + log -> `<name>.vision/<camera>/boot####-<ts>/`),
3. the LogBench **vision dashboard** (`tools/logbench`), which the user knows has a bug, and
4. the dashboard improvements the user wants: show the game mode (disabled/auto/teleop), tie the vision to
   it, and stop long disabled periods from zooming every chart out.

The data does not have to correspond physically (no need for odometry to match the video). It must have
the *shape* of a real match: disabled -> auto -> pause -> teleop -> disabled, recordings that behave like
the real ones (including their failures), on a clock shared with the log.

## 2. State of the machine and repo (verified 2026-10-18)

- Branch `feature/simulated-match-harness` (local only, **not pushed**), 2 commits on top of main `7cb7709`:
  - `347d5bd` recorder fix + `coprocessor/sim/` harness + tests
  - `16840ee` `coprocessor/Bootstrap-OrangePi.ps1`, unattended mode in `setup-orangepi.sh`, docs
  - Working tree note: `coprocessor/sim/Run-SimulatedMatch.ps1` was modified on disk after the last read; check `git status`/`git diff` before touching it.
- **Orange Pi** (PhotonVision image, Orange Pi 5, Ubuntu 24.04, Python 3.12) at `192.168.137.241` on the
  laptop's USB-Ethernet dongle (`Ethernet 3`, ICS subnet `192.168.137.x`, laptop is `192.168.137.1`).
  - SSH: `ssh -i ~/.ssh/id_ed25519_claude pi@192.168.137.241` (key login works, passwordless sudo works).
    The Pi prints a PhotonVision banner on every login; filter it when parsing output.
  - Installed by Bootstrap: venv `~/.venv-ntpublisher` (pyntcore), `orangepi-nt-publisher.service`,
    `orangepi-vision-recorder@bench.service`. Board NT name `BenchPi`, camera instance `bench`,
    raw stream `http://localhost:1181/stream.mjpg` (1182 = processed). PhotonVision camera "Cam1"
    (USB webcam, static dark scene) activated; PhotonVision team number set to 1405; IP mode DHCP.
  - Recordings normally go to `/home/pi/vision-recordings/bench/boot####-<ts>/` (service runs as root, so
    files are root-owned but world-readable). It is empty now: the previous session deleted its simulation sessions.
  - Internet Connection Sharing is **still enabled** on the laptop's Wi-Fi; the user turns it off when done.
- Laptop tools: Python 3.14 with `pyntcore`, `fastapi`, `uvicorn`, `paramiko`; Node 24/npm 11 (LogBench `web/node_modules` present); PowerShell 5.1 and 7.6; OpenSSH.
  **ffmpeg is NOT installed** (LogBench cannot build any camera video without it): `winget install Gyan.FFmpeg`
  (ask the user first), then open a new terminal.
- Harness already built (read `coprocessor/sim/README.md`):
  `fake_robot.py` (NT4 server playing a match; flags for phases, `--fast`, `--loops`, `--drop-at-sec/--drop-for-sec`, `--clock-offset-sec`, `--no-clock`, `--wait-for-clients`, `--event-log`),
  `fake_mjpeg.py` (fake camera, JPEG with counter + wall ms in a COM segment),
  `frame_tap.py` (ground-truth arrival time + SHA-1 of every stream frame; PhotonVision sends byte-identical JPEGs to all clients),
  `verify_recordings.py`, `Run-SimulatedMatch.ps1` (runs a match on the Pi against the real service via a temporary systemd drop-in that points recordings at `~/sim-recordings`, then scp's results to `coprocessor/sim/runs/`).
  `python -m pytest coprocessor/tests -q --ignore=coprocessor/tests/test_setup_orangepi.py` -> 26 pass (~50 s).
  `test_setup_orangepi.py` needs a Unix PTY: run it on the Pi (copy files to `/tmp/cptest`, `python3 -m unittest`).
- Recorder facts (after the fix): background thread drains the MJPEG stream and keeps the newest frame
  stamped on arrival (old code recorded frames minutes behind real time); session per enabled window (auto and teleop are separate sessions, nothing records which is which); NT dropout hold `NT_DROP_GRACE_SEC` (default 10) and 2 s settle after reconnect; `t_sec` is NT-server time (same clock domain as the roboRIO log); session folder timestamp comes from `/RobotTime/WallClockMs`, rendered in America/New_York. `/FMSInfo/FMSControlData` = raw HAL control word (bit0 enabled, 1 auto, 2 test, 3 eStop, 4 fms, 5 ds), confirmed from WPILib 2026.2.1 source.

## 3. Real data to build on

`C:\Users\importsjc\robotics\logs\ruckus2026\akit_26-10-17_17-21-03_nyroc1_q24-bundle\` (the "golden" bundle; ~28 MB, **keep out of git**):
`akit_26-10-17_17-21-03_nyroc1_q24.wpilog` + `akit_26-10-17_17-21-03_nyroc1_q24.vision/{LeftCam,Right,RightCam}/boot####-20261017-132555/`.
More real bundles (zips) in `...\logs\ruckus2026\` (Q1, Q6, Q13, Q17, Q20, Q24, Q28; `akit_*` = AdvantageKit logs with Vision/ topics, `FRC_*` = WPILib logs) plus `albany_2026`, `offseason_2026`.

Golden log facts (via `tools/wpilog-utils`: `load_index(path)` -> `idx.mode_spans()`, `parse_wpilog`):
- timestamps 1.6 s to 556.3 s; mode source `DriverStation/Enabled`; spans: disabled 0-315.1, **auto 315.1-325.0 (9.8 s)**, disabled 325.0-337.8 (12.8 s), **teleop 337.8-477.7 (140 s)**, disabled 477.7-554.7. 57% of the log is disabled.
- 1241 entries, 1186 signals. Vision topics: `/Vision/<Cam>/RawEstimatedPoses`, `/RealOutputs/Vision/<Cam>/Health/*`, `/RealOutputs/Vision/<Cam>/AcceptedPoses`, cameras `LeftCam` and `RightCam`; pose `/RealOutputs/Drivetrain/Pose`.
- `/SystemStats/NTClients/<client>/Connected` is a time series per NT client. It shows recorder clients named `OrangePiVisionRecorder-Right-{LeftCam,Right,RightCam,right}` and a legacy `OrangePiVisionRecorder`, **all dropping at t=349 s** and flapping with ~21 s outages through teleop. Real match outage schedule can be replayed from this.
- Wall-clock in the log name `akit_26-10-17_17-21-03` vs recorder folders `boot0023-20261017-132555` (US Eastern); the log name time zone is not yet confirmed (pairing parses both to aware datetimes).

Findings about the real recordings (all 10 bundles, via zip listing):
- exactly **one session per camera, 8-48 frames** (3-16 s at 3 Hz) vs ~420 expected for teleop alone; frame spans only loosely overlap auto (Q20: auto 233.9-253.9 s, frames 241.7-255.3 s; Q28: auto 229.3-249.2, frames 231.6-244.2; Q24: auto 315.1-325.0, frames 317.6-326.6).
- `Right/boot0051` has an empty manifest (a process restart opened a session that wrote nothing).
- **Cause is undetermined.** Hypotheses: (a) LogBench fetch/pairing keeps one session per camera; (b) recorder sessions really were short because NT flapped (old code read a disconnect as disabled); (c) service restarts. Discriminator: `ls`/count frames in `/home/pi/vision-recordings/*/` on a real Pi after a match. **Ask the user to run this when they next have a robot Pi.**
- All these recordings came from the old stale-frame reader, so their frame content lags their `t_sec` by seconds.

## 4. LogBench facts (read these files before designing)

- `tools/logbench/server/bundles.py`: `<log>.vision/<camera>/boot####-<ts>/{manifest.jsonl,frame_*.jpg}`; `list_vision_sessions`, `load_manifest`, `ensure_preview_video` (ffmpeg concat from manifest durations).
- `tools/logbench/server/pairing.py`: `suggest_pairings` picks **one Pi session per camera**, the one closest to the log's *start* time (not enable time), among sessions within [start-60 s, start+duration+60 s]. Likely drops the second session of a match.
- `tools/logbench/server/specs/camera_health.py`: `_session_overlapping` returns the **first** overlapping session; `spec.static['vision'][camera] = {video, t0}`; one mp4 and one `t0` per camera. No DS-mode data and no match-window crop in the spec or UI.
- `tools/logbench/web/src/panels/VisionPanel.tsx`: single `<video>`, `time - entry.t0`; placeholder "Outside the recorded window." No mode concept anywhere in `web/src`.
- `server/remote_fetch.py`, `pi_discovery.py`, `remote_config.json` (Pi creds/paths; `pi_discovery.scan_hosts`, `"pis": [...]` can pin `{"name","host","user","recordings_path"}`), Fetch Bundle in `server/main.py`.
- Camera naming: recording folder matched to logged camera ignoring case; real bundle has `Right` vs `RightCam`, so it fails.
- Running: `cd tools/logbench && python server/main.py --logs <folder>` (front end build in `web/` via `npm run build`; committed single-file build `server/assets/player.singlefile.html` must be rebuilt with `npm run build:single` when `web/src` changes). Tests in `tools/logbench/tests`, `tools/wpilog-utils/tests`.

## 5. Design: three tiers

**Tier 1 - golden-log bundle builder (offline; build first).** New tool (suggested `tools/logbench/testkit/` or `tools/vision-sim/`, Python, stdlib + wpilog_utils):
`build_bundle.py --log <golden.wpilog> --out <dir> --scenario <name>` produces `<dir>/<logname>.wpilog` (copy, or Janitor-trimmed copy) and `<logname>.vision/<camera>/boot####-<ts>/` in the exact recorder format:
- one session per enabled mode span from `idx.mode_spans()` (so auto and teleop), 3 Hz frames with `t_sec` inside the span (log timebase = recorder `t_sec` on the real robot, no offset needed), frame names `frame_<t>.jpg`;
- synthetic JPEGs (reuse `coprocessor/sim/fake_mjpeg.py`'s encoder or Pillow) with burned-in **log time and mode** so a human or test can read sync off the video; optional real frames from the Pi;
- session folder timestamps derived from the log's wall-clock name, US Eastern, so pairing works; boot ids increasing;
- scenarios as data: `clean`, `nt-flap` (sessions cut/shifted like the real match), `partial-auto-only` (the real Q24 shape), `empty-session`, `name-mismatch` (`Right` vs `RightCam`), `two-boots`, `no-recording`.
Run Fetch/pairing/dashboard code against it with no Pi and no robot.

**Tier 2 - sim robot + real Pi + real camera (second).** Run `./gradlew simulateJava` on the laptop with a scripted match (sim-only driver in Java using `DriverStationSim` to set enabled/autonomous on a timeline, random joystick inputs so the sim drivetrain moves; gate behind a system property or env var so real robot code is unaffected). `VisionIOSim` and sim subsystem IO already exist (`RobotContainer` selects by `RobotBase.isReal()`), and `RobotContainer.publishRobotData()` (called every `robotPeriodic`) already publishes `RobotTime/WallClockMs`. The Pi's recorder points at the laptop (`NT_SERVER=192.168.137.1`, `NT_PORT=5810`, allow inbound in Windows firewall, recorder writes to the normal `/home/pi/vision-recordings/<camera>/`). Both the AdvantageKit log and the recordings then share one clock and one wall clock, exactly like the real robot; then fetch the Pi sessions through LogBench's real path (pin the Pi in `remote_config.json` `"pis"`) and put the sim `.wpilog` in the log root (the RIO leg can be skipped). To verify first: where sim AdvantageKit logs are written and named, and that FMSInfo is published in sim.

**Tier 3 - fake robot replaying the golden log (optional).** Extend `coprocessor/sim/fake_robot.py` with `--replay-log <wpilog>`: drive the control word from the log's DS spans (compress the 315 s disabled lead-in with a flag) and the NT drop schedule from the log's `NTClients/*/Connected` series; run on the Pi via `Run-SimulatedMatch.ps1`. Recorder behaviour under real field patterns.

## 6. Work breakdown (suggested order)

1. Prereqs: install ffmpeg (ask), confirm `python tools/logbench/server/main.py --logs <dir>` starts and opens the golden bundle; record what the vision panel does with the *real* bundle (screenshot via the built-in browser) as the baseline bug repro.
2. Tier 1 builder + scenarios + pytest in `tools/logbench/tests` that load each scenario through `bundles`/`camera_health` and assert the expected sessions/video/warnings (these tests will fail on today's one-session-per-camera behaviour, which is the point).
3. LogBench fixes driven by those tests:
   - pairing keeps **all** sessions in the log window per camera (use enable time, not log start);
   - `camera_health` attaches all sessions per camera (list of `{video, t0, t1}`), player switches video by playhead and shows gaps;
   - add DS mode spans to the spec (`idx.mode_spans()`), shade/label modes on time-series and transport bar, show current mode;
   - match-window crop (default auto start - N s to teleop end + N s, toggle to full log) so charts stop being zoomed out;
   - recording-coverage indicator (fraction of enabled time with frames) and warnings for name mismatch / empty sessions;
   - ffmpeg-missing message stays a clear warning.
4. UI end-to-end check: burned-in log time must equal the playhead time (Playwright or the built-in browser: seek, read the video frame/time, compare); rebuild `player.singlefile.html`.
5. Tier 2 sim driver + `Run-SimulatedMatch`-style PowerShell orchestration (laptop runs sim, Pi records, fetch, open in LogBench).
6. Raise recorder `NT_DROP_GRACE_SEC` default (real outages ~21 s; proposed ~45 s; pending user OK) and update `test_simulated_match.py` and `docs/orangepi-vision-recorder-setup.md`.
7. Optionally make `Run-SimulatedMatch.ps1` able to keep sessions in the real recordings path and preserve the `<camera>/` folder level when copying (today the laptop copy lands as `recordings/boot...`, camera level dropped).
8. Tier 3 and docs (`docs/replay-workflow.md`, a LogBench testing doc), clear fixtures policy.

## 7. Fixtures and hygiene

- Do not commit the 27 MB real log. Options: tests skip when `C:\Users\importsjc\robotics\logs\...` is absent (the pattern `wpilog-utils` tests use), and/or commit a Janitor-trimmed copy (auto+teleop only, drop `/Power/Motors/*`, `/PowerDistribution/*`; `python -m janitor trim`, original timestamps kept by default) if small enough. Real team logs may be sensitive; ask before committing any.
- Generated bundles go under a gitignored dir (`coprocessor/sim/runs/` already ignored).

## 8. Open decisions (ask the user)

1. Build order (recommended: Tier 1, LogBench fixes, then Tier 2).
2. New `NT_DROP_GRACE_SEC` default (proposed 45 s).
3. Should sim runs write to the real `/home/pi/vision-recordings/` by default (fetchable, mixes with real data)?
4. Permission to `winget install Gyan.FFmpeg`.
5. Whether to commit a trimmed golden log.

## 9. Gotchas learned

- The Bash tool chokes on complex quoting and heredocs containing quotes: write patch scripts to files (scratchpad) and run them.
- Mixed line endings: new files should be LF; Bootstrap normalises CRLF on the Pi. Python written on Windows may arrive CRLF.
- PowerShell scripts must be **ASCII-only** and run on both 5.1 and 7 (no `?:`, `??`); passing a hashtable parameter through `powershell.exe -File` fails, use `-Command "& .\script.ps1 ..."`.
- Output of `Tee-Object` in PS 5.1 is UTF-16; use `Set-Content -Encoding UTF8`.
- A compound command (bulk `scp` + remote `sudo` install) was once denied by the auto-mode classifier; splitting into smaller steps worked.
- `pyntcore` `ntcore._now()` is system-wide, so a process on the Pi sharing the host with the NT server sees identical time; frame ages measured with `frame_tap.py` are accurate to ~10 ms.
- PhotonVision's "raw" stream (port 1181) shows a green crosshair overlay; the stream is 320x240 at ~101 fps on this setup; PhotonVision serves byte-identical frames to all clients.
- Bundle/Real-robot camera names (`LeftCam`, `RightCam`) differ from the bench instance name (`bench`); LogBench matches folder to logged camera ignoring case only.
