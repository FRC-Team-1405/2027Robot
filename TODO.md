# To-do

The one open to-do list for the repo. Add to it whenever a note, experiment or PR leaves something
undone, and put the source in brackets (a note's date, a write-up, a commit) so it can be traced
back. When an item is finished, move it to **Done** with where it landed. `notes/` stays the rough
lab notebook, and `TODO(2027):` markers in code are listed in `CLAUDE.md`.

Items marked *(carried)* were copied from older notes and haven't been re-checked against the code.

## Next time on the robot

- [ ] **11-10 (Tue): work through [notes/11-10/notes.md](notes/11-10/notes.md)** (re-bootstrap, leftover
      11-07 checks, frame-budget runs).
- [ ] **Set both cameras back to 800x600 @100** unless @120 was on purpose. They were @120 from
      19:03 on 11-07; the notes don't mention the change. [11-07, frame-pacing R12]
- [ ] **Re-bootstrap both Pis with `.\Bootstrap-OrangePi.ps1 -All`** (no typing now; boards and
      cameras come from `coprocessor/robots.json`). This also moves RightPi's recorder from
      `http://rightpi.local:1181` to `localhost:1181`, which the 11-07 bootstrap silently kept.
      First run on a laptop other than the one that made the key confirms the shared key works. [11-07]
- [ ] **Re-check "PhotonVision still saves" with `sudo journalctl -u photonvision …`.** As user
      `pi` the journal is hidden, so the 11-07 check printed nothing either way. [11-07 check 2b]
- [ ] **Open the Health Check on an 11-07 log** (from `18-22-17` on) and see whether the roboRIO
      CPU / memory, radio and Pi network rows have values. [11-07 check 2e, not done]
- [ ] **Confirm the LogBench live fix.** With robot code already running, connect LogBench live,
      leave the Health Check open, and check that no camera has a gap between results over 80 ms.
      This is the case that stalled vision on 10-27 (T1, T2). [10-27 write-up, learning 8]
- [ ] **Check why the Left Pi links at 100 Mbit/s** when the Right Pi gets 1000. Try another cable
      and radio/switch port. Not the cause of the frame-rate cliff, but it shouldn't be that way.
      [10-27 write-up]
- [ ] **Tune the new Health Check thresholds** (Pi network, roboRIO CPU and memory, radio
      bandwidth) once there's a real log with them. They're educated guesses for now.
      [`tools/logbench/server/health_checks.toml`]

## Vision experiments

- [ ] **Run the resolution crossover experiment with the experiment runner**: `doctor`, `run`, `finish`,
      then `analyze.py`. First live use of the robot-experiment runner, so also the first test of its
      PhotonVision web socket messages (`pv-dump` if they differ).
      [`docs/experiments/vision/2026-11-14-pv-crossover-odometry/`, `tools/exprunner/README.md`, 11-14]
- [ ] **Camera mounts: find a trustworthy reference for the robot centreline and heading**, then
      redo the crosshair aim check and a static truth stop; try the "robot against the wall, back
      straight off" run. Constants stay as they are for now (they match tape).
      [`docs/camera-mount-calibration-notes.md`, 11-14]
- [ ] **Run the camera auto-calibration on the robot** (hub tag pair, 2-2.5 m, other tags covered,
      "CalibrateCameras" auto), then validate once against a tape-measured calibration. Check the
      tag height, tilt, spacing and size first.
      [`docs/camera-autocal-plan.md`, 11-14]
- [ ] **Run the camera-setting crossover experiment** after the cameras are calibrated; pick
      setting B first. [`docs/experiments/vision/2026-11-14-pv-crossover-odometry/`, 11-14]

- [ ] **Frame-budget B6: 800x600 @120, decimate 2, threads 8** (~5 min, one `CircleFacingTag`
      run). Passes at ≥ 108 results/s. It missed by ~0.6 ms per frame on 11-07; threads didn't
      shorten the frame on 11-10, so expect it to still miss. B1–B5 done 11-10.
      [`docs/experiments/vision/2026-11-10-pv-frame-budget/`, 11-10]
- [ ] **Try 2 workers x 2 threads (and 3 x 1) on the frame-cost bench**: might keep most of the
      frames-in-flight throughput with less added delay per frame. Only worth it if the range
      experiment says a finer image helps. [frame-cost bench, 11-14]
- [ ] **Propose grey decode (ADR 0002 O2) upstream**: saves 1.3-2.8 ms per frame; safe whatever
      the range result. [frame-cost bench, 11-14]
- [ ] **Confirm R3 was Low Latency off** in the PhotonVision UI; the notes don't say, the data
      do. [11-03]
- [ ] **Run the range experiment** after the frame-pacing runs above (R6 and R13 done 11-07): stationary at 2 / 4 / 6 / 8 m,
      one pipeline per setting. Dec 1 and 1280x800 each cost a third of the results, so they need a
      clear range gain. [`docs/experiments/vision/2026-11-03-pv-range/`, 10-27 open question 2]
- [ ] **Log the robot program's own CPU next to `RIO/CpuPct`** (`/proc/self/stat`, plus the busiest
      other process). The roboRIO is 72–84% busy; this says whether that's us. Then two 2-minute
      runs of one setup to measure the run-to-run noise (4–20% slow loops on 11-07).
      [`docs/experiments/roborio/2026-11-03-loop-overruns/`, 11-07]
- [ ] **Repeat the recorder on/off comparison interleaved** with no browser streams over the radio,
      and see whether the recorder can read a lower-rate stream. [10-27 open questions 3–4]
- [ ] **Make the intrinsics in `VisionConstants` match whichever resolution we settle on.** The
      1280x800 calibrations were added 10-27; the recommendation is currently 800x600.
- [ ] **Decide whether camera score dropping to 0 while moving is intended** (ADR 0001), and write
      it down. [9-5] *(carried)*
- [ ] **Try a lower fixed exposure than 86.** Auto exposure off improved quality but cost about
      15% FPS. [9-5] *(carried)*

## Logging and diagnostics

- [ ] **Mark the log the robot is still writing in LogBench's Fetch Bundle list**, so it's obvious
      before the download that you'll get a snapshot. [11-03, follow-up to the download fix]

- [ ] **Log the robot's NetworkTables clients.** Record `NetworkTableInstance.getConnections()`
      (client name, IP, connect time) once a second. On 10-27 we had to work out from timing gaps
      that LogBench was reconnecting; this would have shown it directly.
- [ ] **Add a vision gap row to the Health Check**: the longest time between results per camera,
      warning over 80 ms. That would have flagged the 10-27 stalls without reading the charts.
- [ ] **Make every time on a downloaded log agree.** This covers the file name, the `.wpilog` start
      metadata, LogBench's display, the bundle and trim names, and the vision-recorder folders.
      The 10-27 logs (run about 6–8 pm EDT) are named `akit_26-10-27_22-13-27` to `23-42-41`. That is
      UTC: AdvantageKit names logs in UTC once the DS has synced the clock, and it showed up as
      "11 pm" in LogBench. The Pi has no clock battery, so its recorder times have their own
      offset. Pick one rule: store UTC and show local time with the zone. Then apply it when
      fetching from the robot (rename or add a manifest field) and wherever LogBench shows a
      time. [user, 10-28]
- [ ] **Log LogBench's own live connects and disconnects, with the reason**, in its run log. Why it
      reconnected every 2.4 s on 10-27 is still unconfirmed. [10-27 write-up, learning 8]

## LogBench

- [ ] **Experiment runner, robot runs** (bench runs built in `tools/exprunner`;
      [plan](docs/experiment-runner-plan.md), steps 1–2 first): after each run,
      fetch the newest bundle through LogBench's API and record it in a manifest; before each run,
      check `/OrangePi/*` settings against the run plan. Then steps 3–6 (apply settings over
      PhotonVision's websocket, auto-detect enable/disable, `analyze.py` reads the manifest,
      copy-only Pi sync for bench scripts). [11-11]
- [ ] **Turn experiment `analyze.py` scripts into LogBench comparisons** where it's practical, so
      the next write-up doesn't need a one-off script. [`docs/experiments/README.md`]
- [ ] **Fetch a full log and trim it in one step** (with the WPILog Janitor), and a **zip-and-download
      button** on Fetch Bundle, so a match can be pulled right after it's played. [10-17] *(carried)*
- [ ] **Click-and-drag panning on the Vision Log and Battery Insights charts.** Hard to zoom and move
      around on a laptop. [10-17] *(carried)*
- [ ] **Battery Insights: show the game mode on every chart, and a progress indicator** while a
      match is analyzed (it takes minutes). [10-17] *(carried)*
- [ ] **Live Pit Check crash, `Cannot read properties of null (reading 'toFixed')`.** Reproduce or
      close. [9-12] *(carried)*

## Coprocessor and hardware

- [ ] **Vision-recorder frame names don't sort in Windows Explorer**: `frame_{t_sec:.6f}.jpg` has
      no padding (`coprocessor/orangepi-vision-recorder.py:954`). [9-15] (still open on 10-28)
- [ ] **No teleop or auto folders in the vision recorder output** on the Pi. [10-17] *(carried)*
- [ ] **Orange Pi cooling.** Idles at 73–77 °C; throttling starts at 85 °C. [7-14] *(carried)*
- [ ] **Temperature mismatch**: the publisher read 73 °C while PhotonVision showed 77 °C. Find which
      thermal zone each reads. [7-14] *(carried)*
- [ ] **Driver Station on radio port AUX 2** through a PoE splitter with the power lead cut: check
      the VH-109 docs or ask a CSA. [9-5] *(carried)*

## Pit and process

- [ ] **Battery log sheet for the pit**: a printable table of match #, time, bumper color, battery
      and notes, so each match log can be tied to a battery. [10-17] *(carried)*

## Docs

- [ ] **`docs/orangepi-internet-access.md` is out of date** (old `pi` user, static IP). Replace with
      the methods that worked. [9-22 roll-up] *(carried)*
- [ ] **Reconcile camera settings** in `docs/photonvision-camera-intrinsics-calibration.md`
      (exposure 100 / brightness 60 / gain 60) with the tested values (AE off, exposure 86,
      brightness 0, gain 25). [9-5] *(carried)*
- [ ] **Tick off step 1b of `docs/orangepi-vision-recorder-setup.md`** (`/FMSInfo` enabled bit):
      confirm no session starts while disabled. [9-5] *(carried)*

## Housekeeping

- [ ] **A home Wi-Fi password is committed** in `notes/6-23/sshExport.txt` (the
      `nmcli device wifi connect` line), still there on 10-28. Redact it and change the password;
      it stays in git history either way. [9-22 roll-up]
- [ ] **`coprocessor/tests/test_setup_orangepi.py` fails on Windows** (needs `termios`). Skip it
      there so the coprocessor tests run cleanly on team laptops.
- [ ] **`coprocessor/tests/Test-BootstrapOrangePi.ps1` fails on Windows PowerShell 5.1** at its
      first check ("argument count: expected 7, got 1"): on 5.1 `ConvertFrom-Json` returns a JSON
      array as one object. Test bug only; it passes on PowerShell 7. [11-07]
- [ ] **Install the GitHub CLI (`gh`) on the team laptop** so PRs can be opened from the terminal.

## Done

| Item | Where it landed |
|---|---|
| Frame-budget experiment B1–B5 on 11-10 (threads 8/4/3/1, "drawing off"). Keep threads 8; drawing has no UI switch for AprilTag pipelines and runs off the main thread, so no drawing run planned. B7 = the reset run | `docs/experiments/vision/2026-11-10-pv-frame-budget/`, `notes/11-10/notes.md`. B6 stays open above |
| 11-07 robot session: deploy `beta`, re-bootstrap both Pis, checks 2a/2b, frame-pacing R5/R6/R12/R13, loop-overrun L1–L5 | `notes/11-7/notes.md`, both write-ups. Checks 2c–2e not done; they stay open above |
| Start-up wizard for the laptop-side coprocessor scripts (Bootstrap, both sim scripts): numbered choices, Enter = default, prints the equivalent command [user, 11-07] | `coprocessor/lib/Wizard.ps1` |
| Our `.wpilog` parser dropped every `string[]` entry (PhotonVision thread names, AdvantageKit Alerts) [11-07] | `tools/wpilog-utils/wpilog_utils/decode.py`, `tests/test_decode_arrays.py` |
| Bootstrap without typing names: per-robot boards/cameras in `coprocessor/robots.json`, `-All`, `-Robot`, wrong-board guard; shared Orange Pi SSH key [user, 11-07] | `coprocessor/robots.json`, `coprocessor/ssh/`, `Bootstrap-OrangePi.ps1` 2026-11-07.1 |
| LogBench download of a log the robot is still writing finishes (snapshot) [11-03] | Confirmed on 11-07: all nine bundles were such snapshots and finished |
| PhotonVision settings in the log (camera mode, decimate, threads, Low Latency, streams) [10-27] | Pi publisher, working on both Pis 11-07; caught an unnoted camera mode change the same day |
| roboRIO CPU / memory / network logging (`RIO/*`) [10-27] | Working 11-07 |
| roboRIO CPU in the Health Check [10-27] | `RioSystemStats`, `rio.cpu` rows (on `beta`, 11-04) |
| Bandwidth logging, rows and thresholds [10-27] | Pi `Net*` topics, `RIO/Net*`, radio bandwidth rows (same branch) |
| Each camera mode's real fps (`v4l2-ctl`) [10-27 open question 1] | `docs/experiments/vision/2026-10-28-pv-frame-pacing/notes.md`: 1280x800 and 800x600 both offer 100 and 120 |
| Periodic vision dropouts in 10-27 T1/T2 | Traced to LogBench live; fixed in `7363770`, still to confirm on the robot |
| Vision recorder manifest with a real timestamp per frame [10-17] | Manifest rows carry a UTC receipt time (`orangepi-vision-recorder.py`) |

Older finished items are in `notes/9-22/todos.md`.
