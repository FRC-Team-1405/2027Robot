# 11-7 session: test what was merged into beta, then run the experiments

On 11-04 four sets of changes were merged into `beta`. **None of them has run on the robot or the
Pis yet.** The plan for Saturday: deploy, spend about 30 minutes checking that each new piece
works (part 2), then run the experiments (part 3). Write results in the "Result" columns as you go.

## What's new, and what could go wrong

| Change | What it does | Risk if it's broken |
|---|---|---|
| roboRIO stats (`RioSystemStats`, robot code) | Logs roboRIO CPU, memory and network once a second as `RIO/*` | Low. A background thread reads `/proc`; the loop only logs. Worst case: no `RIO/*` values. Switch: `RIO_SYSTEM_STATS_LOGGING` |
| PhotonVision settings logging (Pi publisher) | Puts each camera's PhotonVision settings (decimate, Low Latency Mode, threads…) and real camera mode in the log, so we stop relying on notes | **Medium. Never run on a Pi.** It reads PhotonVision's settings file. If that ever blocked PhotonVision from saving, settings changes could be lost. Check 2b covers it |
| Health Check rows | roboRIO CPU / memory, radio bandwidth, Pi network rows in LogBench | Low. Thresholds are guesses; may warn too much or too little |
| LogBench live fix (`7363770`) | LogBench live no longer subscribes to every robot topic (that stalled vision on 10-27) | Low, but not confirmed on the robot |
| LogBench download fix | Fetching a log the robot is still writing now finishes (snapshot + one catch-up pass) instead of downloading forever | Low. Not tried on the robot |

Not merged: `akit-swerve-approach-b-partial-replay`. It changes every drive command and was never
tested, so it stays on its own branch.

## Part 1: before enabling (about 15 min)

- [ ] Pull `beta` on the laptop.
- [ ] **Deploy robot code** from `beta` (`./gradlew deploy`).
- [ ] **Re-bootstrap both Pis** with `coprocessor/Bootstrap-OrangePi.ps1`. This installs the new
  publisher. Without it, check 2b has nothing to check.
- [ ] Restart LogBench (VS Code task `Logbench`) so it runs the new code.
- [ ] Close every PhotonVision browser tab before each enabled run.

## Part 2: check each new piece (about 30 min)

Do these in order. If one fails, write down what you saw, use the fallback, and keep going.

| # | Check | How | Pass if | Fallback if it fails | Result |
|---|---|---|---|---|---|
| 2a | **roboRIO stats** | AdvantageScope, live: `RealOutputs/RIO/` | `CpuPct`, `CpuCorePct`, `MemUsedPct`, `NetRxMbps`, `NetTxMbps` update about once a second | Set `RIO_SYSTEM_STATS_LOGGING = false`, redeploy | |
| 2b | **PhotonVision settings, values** | AdvantageScope, live: `/OrangePi/<Pi>/PvSettingsOk` and `/OrangePi/<Pi>/PhotonVision/<cam>/` | `PvSettingsOk` is true on both Pis. `Decimate`, `LowLatencyMode`, `Threads` match the PhotonVision UI | See 2b fallback below | |
| 2b | **PhotonVision settings, a change** | Change decimate in the UI, wait 10 s | `Decimate` updates; nothing else changes | | |
| 2b | **PhotonVision settings, camera mode** | `/OrangePi/<Pi>/Video/<videoN>/Mode`; on the Pi, `v4l2-ctl -d /dev/video0 --get-fmt-video --get-parm` | Same resolution and fps as the UI | | |
| 2b | **PhotonVision still saves** | On each Pi: `journalctl -u photonvision --since "10 min ago" \| grep -i locked` | Prints nothing. Also: change a setting, restart PhotonVision, and the change is still there | | |
| 2c | **LogBench live** | Robot code running, connect LogBench live, leave the Health Check open for 2 min, then do one `CircleFacingTag` run | No camera has a gap between results over 80 ms in that run's log | Close LogBench live during the experiments; note it | |
| 2d | **LogBench download of a log still being written** | Laptop on the **access point** (not direct ethernet), robot code running. Fetch Bundle → the newest log | Finishes in under a minute and shows a "still writing" note | Fetch over direct ethernet, as on 11-03 | |
| 2d | **…and the rest of it later** | Restart robot code, fetch the same log again | The full log downloads (bigger than the first time), no note | | |
| 2e | **Health Check rows** | Open the 2c log in LogBench → Health Check | roboRIO CPU, memory, radio bandwidth and Pi network rows have values (not "no data") | Note which rows are empty | |

**2b fallback:** on that Pi, add `PHOTONVISION_CONFIG_DB=/nonexistent` to
`/etc/default/orangepi-nt-publisher`, then `sudo systemctl restart orangepi-nt-publisher`. The
settings logging stops (`PvSettingsOk` false); everything else the publisher does keeps working.
Write the PhotonVision settings into the run tables by hand, as before.

## Part 3: experiments, in priority order

Each write-up has the full run table. Fill in the settings there **before** enabling. If 2b
passed, the log records them too, but write them anyway.

1. **Frame pacing R4–R14** (about 1 hour):
   [docs/experiments/vision/2026-10-28-pv-frame-pacing](../../docs/experiments/vision/2026-10-28-pv-frame-pacing/README.md).
   First, set **Low Latency Mode off** on every pipeline on both Pis.
   The most important runs are R6 (decimate 1) and R13 (1280x800).
2. **roboRIO loop overruns L1–L6** (about 40 min, one extra deploy):
   [docs/experiments/roborio/2026-11-03-loop-overruns](../../docs/experiments/roborio/2026-11-03-loop-overruns/README.md).
   Needs 2a to pass.
3. **Range** (about 1 hour, needs taped floor marks and one pipeline per setting), if there's time:
   [docs/experiments/vision/2026-11-03-pv-range](../../docs/experiments/vision/2026-11-03-pv-range/README.md).
   Needs R6 and R13 done first.

## Recorded

<!-- Same format as 11-03: one line per log, with what changed. -->
