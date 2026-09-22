# To-do roll-up — 6/16 through 9/19

Every to-do, open question, and "still outstanding" item from `notes/`, checked against the repo
as of 9/22 (branch `logbench-migration`). Source note in brackets.

## Open

### Vision follow-ups (from the 9/22 analysis; details in `drafts/reference-vision-tuning-log.md`)
- [ ] **Check that PhotonVision decimate is back at 3 on both cameras.** The 9/19 logs run at
      ~35–40 FPS, which matches decimate 1.
- [ ] **Try a lower fixed exposure than 86.** Turning auto exposure off on 9/5 improved quality but
      cost about 15% FPS.
- [ ] **(Optional) Re-run `MULTI_TAG_PNP_ON_COPROCESSOR` on decimate 3 on the same day as an
      alternative, for a clean baseline.** The current decision is to keep coprocessor (see Done).
- [ ] **Redo the 9/5 pre/post exposure comparison with all samples and a 5 s average.** The
      screenshots only covered frames that had a tag in them. The logbench comparison is now in
      `notes/9-5/analysis/`; this item is only about the dashboard view. [9-5]
### Vision (still open)
- [ ] **Work out why camera score drops to 0 while the robot moves even though tags are still
      tracked.** It shows in `9-5/postAdjustmentAutoMetrics.png`: score follows Stillness down to 0.
      This may be intended behavior under ADR 0001; decide and write down which. [9-5]

### Tools
- [ ] **The janitor's default "Close the gap" timing breaks anything that compares log time with
      timestamps stored inside the data.** It shifts log time but not the camera capture
      timestamps in `/Vision/*/RawTimestamps`. As a result, logbench's `latency_mean_ms` reads **0**
      on those trims (found 9/22; every other metric matched exactly). The same mismatch probably
      affects `simulateJava` replay, where vision measurements get stale-looking timestamps, and
      lining up vision-recorder frames. The 9/22 trims used `--preserve` to avoid it. Fix options:
      make Keep original timestamps the default for logs with vision data, or shift stored FPGA
      timestamps along with log time. Your own
      `logs/offseason/9-19/*_MULTI_TAG_PNP_ON_RIO_trimmed.wpilog` and `_trimmed_2` were made with
      Close the gap and have this problem; `_trimmed_originalTime` is fine.
- [ ] **Vision-recorder frame names don't sort in order in Windows Explorer.** The 9/15 and 9/19
      folders show why: `frame_100.055265.jpg` sorts before `frame_36.135645.jpg`. Session folders now
      have a sortable `bootNNNN-YYYYMMDD-HHMMSS` slug (commit `d8897c0`), but frame files are
      still `frame_{t_sec:.6f}.jpg` with no padding (`orangepi-vision-recorder.py:279`). Pad the
      integer part (for example `frame_{t_sec:013.6f}.jpg`) or use a per-session frame counter. [9-15]
- [ ] **Live Pit Check crash: `Cannot read properties of null (reading 'toFixed')`.** A value came
      back null and was formatted. I haven't checked whether it's fixed. Try to reproduce in
      `tools/logbench/web/src/pit/PitCheckPage.tsx`, or in whichever panel formats a value that
      can be null. [9-12]

### Coprocessor / hardware
- [ ] **Orange Pi cooling.** It idles at 73–77 °C, and throttling starts at 85 °C. A fan is likely
      needed. [7-14]
- [ ] **Temperature source mismatch.** The NT publisher read 73 °C while PhotonVision's UI read 77 °C.
      Find which thermal zone each one reads. [7-14]
- [ ] **Driver Station wiring question.** The DS plugs into radio port **AUX 2** (not the DS port)
      through a PoE-splitter cable with its power lead cut. Is that OK? Check the Vivid Hosting
      VH-109 port documentation and ask a CSA at the next event. [9-5]
- [ ] **Re-verify that NT metrics reach the roboRIO after the 7/26 reflash.** This is probably fine,
      since the recorder and Pit Check both depend on NT, but nobody confirmed it. [7-26]

### Docs that are now stale
- [ ] **`docs/orangepi-internet-access.md` is out of date.** It still uses the `pi` user, a static
      `10.14.5.202` IP, and the "use the Pi's Wi-Fi" method. The two methods that actually worked
      aren't in it: Windows Internet Connection Sharing [7-7] and NAT through a Linux box [7-26].
      See `drafts/guide-orangepi-access.md`.
- [ ] **`docs/photonvision-camera-intrinsics-calibration.md` suggests a starting point of exposure
      100, brightness 60, gain 60.** The team's tested values are AE off, exposure 86,
      brightness 0, gain 25 [9-5]. Reconcile the two.
- [ ] **Tick off step 1b in `docs/orangepi-vision-recorder-setup.md` (`/FMSInfo` enabled bit).**
      The recorder captured frames during an enabled auto on 9/12, which is strong evidence the bit
      is right. To close it out, confirm that no session starts while the robot is disabled. [9-5/todo]

### Housekeeping
- [ ] **A home Wi-Fi SSID and password are committed in plain text** in
      `notes/6-23/sshExport.txt` (the `nmcli device wifi connect ...` line), and the notes are
      tracked in the `FRC-Team-1405/2027Robot` repo. Redact the line and change that Wi-Fi password.
      Removing the line from the current file doesn't remove it from git history.

## Done

| Item | Where it landed |
|---|---|
| Analyze the 9/15 recorder runs [9-15] | Your logbench comparisons in `notes/9-15/analysis/`, plus the 9/12→9/15 intrinsics comparison added 9/22. Decimate 1 is much worse; new intrinsics and left exposure changes are better |
| Analyze the 9/19 pose-strategy runs and pick one [9-19] | `notes/9-19/analysis/`: keep `MULTI_TAG_PNP_ON_COPROCESSOR`. On the rio, the loop overran (~32 ms); `LOWEST_AMBIGUITY` lost tags |
| 6/16 feature-switch and high-resolution tests (screenshots only until now) | `notes/6-16/analysis/`: switches slightly better, high resolution −40% FPS |
| Circle-facing-tag auto around tag 10, speed ramping to ~2 m/s [9-1] | `commands/CircleFacingTagCommand.java`; fixed start location in `aacef45` |
| Confirm the raw MJPEG stream port for the recorder [9-5/todo] | `docs/orangepi-vision-recorder-setup.md` step 1a: right `:1181`, left `:1183` |
| Write or find a ChArUco calibration guide covering distance and sample count [9-5] | `docs/photonvision-camera-intrinsics-calibration.md` |
| Deploy the 9/8 calibration intrinsics [9-8, 9-15] | `VisionConstants.java` (`efa3776`) |
| Logbench tab to pull rio logs and Pi recordings together [9-12] | logbench **Fetch bundle** page (`FetchBundlePage.tsx`) |
| Get the Orange Pi internet, update it, get PhotonVision running [6-20, 6-23, 7-7, 7-26] | Reflashed; now user `photon`, DHCP (7/26) |
| Install the NT metrics publisher (`ntcore` missing) [6-20] | Package is `pyntcore`, installed in a venv; service running (7/26) |
| Vision recorder working end to end [9-12] | `coprocessor/orangepi-vision-recorder.py` + setup doc |
| Orange Pi link flapping every ~21 s [7-26] | Root cause was power from a USB-A→C adapter; fixed with a real USB-C PD supply |
| PhotonVision camera/pipeline config after reflash [7-26] | Redone 9/5; see `drafts/reference-vision-tuning-log.md` |

## Probably obsolete (verify, then drop)
- **vision-analyzer Summary tab `IndexError` in `summary.py:145`** [6-20]. This is from the Streamlit
  tool, which is being folded into logbench. Confirm logbench's Compare page handles two logs
  with different camera sets or metric lists.
- **Robot log download hangs with no progress** [6-20]. Also from vision-analyzer. Check that
  logbench's fetch shows progress and has a timeout on large `.wpilog` files; that log listing had
  220 wpilogs on the rio.
