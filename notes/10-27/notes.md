# TODO
- Add roboRIO CPU to health check, akit_26-10-27_22-13-27.wpilog shows it consistently high but the health check doesn't surface this.
- could network bandwith limiting cause issues? should this be added to the health check? if so what is the threshold? can we currently measure how much bandwith we are using?

# Vision throughput test (10-27)

Goal: find out whether we can lower decimate, raise resolution, or both, on one OV9281 per
Orange Pi 5, without losing throughput or throttling the Pi. Follow-up to the 10-24 practice log
(akit_26-10-24_14-59-06): at 800x600 / 100 fps / decimate 3 both cameras kept up (~100 results/s,
~2-4% dropped frames), but the Pi CPU/temp data wasn't logged, so headroom is unknown.

## Before testing

- [ ] Robot code deployed with `COPROCESSOR_HEALTH_LOGGING = true` (Pi CPU/temp/recorder data in the log)
- [ ] Updated recorder AND nt-publisher copied to both Pis (recorder.log startup line shows `version=2026.10.25.1+...`;
      `/OrangePi/<Pi>/CpuCorePct` shows up in AdvantageScope)
- [ ] Camera USB cables strain-relieved / secured on both cameras; Right Pi ethernet checked
- [ ] On each Pi, list the camera's modes: `v4l2-ctl -d /dev/video0 --list-formats-ext`
      (does it offer 1280x800 at 100 fps in MJPG?) — write it down here:
- [ ] 1280x800 calibration done for both cameras (needed for tests 4 and 5)
- [ ] Tags placed at ~2 m, ~4 m and ~6 m+ from the robot, robot stationary
- [ ] While test 1 runs, on one Pi: `top -H -p <photonvision pid>` — note which threads are busy and
      how many cores they use (answers "is it one core or many")

Where the numbers come from (AdvantageScope / LogBench, from the robot log):
- Results/s: `Vision/<cam>/CurrentFps`
- Dropped frames: 20 ms gaps in `Vision/<cam>/RawTimestampsSec` (camera frames PhotonVision skipped);
  `RealOutputs/Vision/<cam>/MissedResults` counts results PhotonVision sent that the robot never got
- PV processing time: `Vision/<cam>/PipelineLatenciesMs` (PhotonVision's own capture-to-publish time)
- Busiest core: `RealOutputs/OrangePi/<Pi>/CpuCoreMaxPct` (all cores: `CpuCorePct`)
- CPU clock: `CpuFreqMHz` vs `CpuFreqCapMHz` vs `CpuFreqMaxMHz` (cap below max = throttling, also `CpuThrottled`)
- Max temp: `TempMaxC` / `TempMaxZone` (all zones: `ThermalZones` + `ThermalTempC`)
- Which PV threads are busy and on which cores: `PvTopThreads`, `PvTopThreadPct`, `PvTopThreadCore`

Each test: change ONE setting in PhotonVision, enable the robot, hold ~1 minute, note the log file.
Pass = ~100 results/s, dropped frames not climbing, PV processing time well under 10 ms, CPU clock
never drops below max, temperature levels off.

## Test 1: baseline (800x600, decimate 3)
akit_26-10-27_22-13-27-bundle
swapped out battery after test

| Metric | Result |
|---|---|
| Log file | |
| Results/s (left / right) | |
| Dropped frames % | |
| PV processing time, ms (median / max) | |
| Busiest core % | |
| CPU clock, big cores (MHz) | |
| Max temp (C) | |
| Farthest tag detected (m) | |
| Stationary wobble X (cm) / heading (deg) | |

Notes:

## Test 2: 800x600, decimate 2
"fresh" test battery
akit_26-10-27_22-37-33-bundle

| Metric | Result |
|---|---|
| Log file | |
| Results/s (left / right) | |
| Dropped frames % | |
| PV processing time, ms (median / max) | |
| Busiest core % | |
| CPU clock, big cores (MHz) | |
| Max temp (C) | |
| Farthest tag detected (m) | |
| Stationary wobble X (cm) / heading (deg) | |

Notes:

## Test 3: 800x600, decimate 1
restarted robot code before running test
akit_26-10-27_22-42-57-bundle

| Metric | Result |
|---|---|
| Log file | |
| Results/s (left / right) | |
| Dropped frames % | |
| PV processing time, ms (median / max) | |
| Busiest core % | |
| CPU clock, big cores (MHz) | |
| Max temp (C) | |
| Farthest tag detected (m) | |
| Stationary wobble X (cm) / heading (deg) | |

Notes:

## Test 4: 1280x800, decimate 3 (after recalibrating)
akit_26-10-27_23-07-45-bundle

| Metric | Result |
|---|---|
| Log file | |
| Results/s (left / right) | |
| Dropped frames % | |
| PV processing time, ms (median / max) | |
| Busiest core % | |
| CPU clock, big cores (MHz) | |
| Max temp (C) | |
| Farthest tag detected (m) | |
| Stationary wobble X (cm) / heading (deg) | |

Notes:

## Test 5: 1280x800, decimate 2
akit_26-10-27_23-21-27-bundle

| Metric | Result |
|---|---|
| Log file | |
| Results/s (left / right) | |
| Dropped frames % | |
| PV processing time, ms (median / max) | |
| Busiest core % | |
| CPU clock, big cores (MHz) | |
| Max temp (C) | |
| Farthest tag detected (m) | |
| Stationary wobble X (cm) / heading (deg) | |

Notes:

## Test 5.1: more FPS? (800x600@120FPS, decimate 3)
previous 800x600 testing was @100FPS, turns out it can go higher at decimate 3
akit_26-10-27_23-27-43-bundle

## Test 6: best setting from 1-5, recorder stopped
best setting: (800x600@120FPS, decimate 3)
akit_26-10-27_23-37-01-bundle

Stop the recorder on both Pis (`sudo systemctl stop 'orangepi-vision-recorder@*'`), rerun the best
setting, then start it again. Shows how much CPU the recorder's stream costs.

Setting used:

| Metric | Result |
|---|---|
| Log file | |
| Results/s (left / right) | |
| Dropped frames % | |
| PV processing time, ms (median / max) | |
| Busiest core % | |
| CPU clock, big cores (MHz) | |
| Max temp (C) | |
| Farthest tag detected (m) | |
| Stationary wobble X (cm) / heading (deg) | |

Notes:

## Test 7: heat soak (best setting, full match length)
akit_26-10-27_23-42-41-bundle

Enable for ~2.5 minutes (or several back to back) with the best setting and the recorder running.
Watch whether temperature levels off or keeps climbing, and whether the CPU clock drops.

Setting used:

| Metric | Result |
|---|---|
| Log file | |
| Results/s at start / at end | |
| Max temp at start / at end (C) | |
| CPU clock at end, big cores (MHz) | |
| Dropped frames % at end | |

Notes:

## Conclusion

Setting we're keeping:

Why:
