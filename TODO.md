# To-do

The one open to-do list for the repo. Add to it whenever a note, experiment or PR leaves something
undone, and put the source in brackets (a note's date, a write-up, a commit) so it can be traced
back. When an item is finished, move it to **Done** with where it landed. `notes/` stays the rough
lab notebook, and `TODO(2027):` markers in code are listed in `CLAUDE.md`.

Items marked *(carried)* were copied from older notes and haven't been re-checked against the code.

## Next time on the robot

- [ ] **Deploy robot code and re-bootstrap both Orange Pis**, then check that `RIO/*` and
      `/OrangePi/*/Net*` show up in the log and in the Health Check. [10-27 notes, branch
      `vision-throughput-10-27`]
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

- [ ] **Run the 10-28 frame-pacing experiment**: decimate 2 with Low Latency Mode on vs off, then
      the other levers. [`docs/experiments/vision/2026-10-28-pv-frame-pacing/`]
- [ ] **Find each camera mode's real fps** with `v4l2-ctl --list-formats-ext`, so we know whether
      the 1280x800 runs hit the camera's limit or PhotonVision's. [10-27 open question 1]
- [ ] **Range test**: stationary at 2 / 4 / 6 / 8 m, 800x600 vs 1280x800, to see whether higher
      resolution buys anything. [10-27 open question 2]
- [ ] **Repeat the recorder on/off comparison interleaved** with no browser streams over the radio,
      and see whether the recorder can read a lower-rate stream. [10-27 open questions 3–4]
- [ ] **Make the intrinsics in `VisionConstants` match whichever resolution we settle on.** The
      1280x800 calibrations were added 10-27; the recommendation is currently 800x600.
- [ ] **Decide whether camera score dropping to 0 while moving is intended** (ADR 0001), and write
      it down. [9-5] *(carried)*
- [ ] **Try a lower fixed exposure than 86.** Auto exposure off improved quality but cost about
      15% FPS. [9-5] *(carried)*

## Logging and diagnostics

- [ ] **Log the robot's NetworkTables clients.** Record `NetworkTableInstance.getConnections()`
      (client name, IP, connect time) once a second. On 10-27 we had to work out from timing gaps
      that LogBench was reconnecting; this would have shown it directly.
- [ ] **Get the PhotonVision settings into the log**: camera mode, decimate, detector threads, Low
      Latency Mode, stream settings. On 10-27 those were only in hand-written notes, so a
      mislabelled run couldn't be caught. The Pi publisher could read them from PhotonVision and
      publish them.
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
- [ ] **Install the GitHub CLI (`gh`) on the team laptop** so PRs can be opened from the terminal.

## Done

| Item | Where it landed |
|---|---|
| roboRIO CPU in the Health Check [10-27] | `RioSystemStats`, `rio.cpu` rows (branch `vision-throughput-10-27`) |
| Bandwidth logging, rows and thresholds [10-27] | Pi `Net*` topics, `RIO/Net*`, radio bandwidth rows (same branch) |
| Periodic vision dropouts in 10-27 T1/T2 | Traced to LogBench live; fixed in `7363770`, still to confirm on the robot |
| Vision recorder manifest with a real timestamp per frame [10-17] | Manifest rows carry a UTC receipt time (`orangepi-vision-recorder.py`) |

Older finished items are in `notes/9-22/todos.md`.
