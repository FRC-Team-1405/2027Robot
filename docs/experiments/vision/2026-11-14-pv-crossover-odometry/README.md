---
id: VIS-2026-11-14-pv-crossover-odometry
title: Does a higher camera resolution improve vision odometry enough to pay for the lost results/s? (same autonomous, settings swapped between the two cameras)
area: vision
date: 2026-11-14
status: planned               # planned | running | analyzed | decided
decision: pending
robot_code: beta @ (fill in from RealMetadata/GitSHA before the first run)
logs: logs/offseason/<date>/ (gitignored); name each run's log in runs.toml
analysis: analyze.py → results.json
raw_notes: notes/<date>/notes.md
---

# Higher resolution vs more results per second

## In short

At 800x600 (decimate 2) each camera gives 101 results per second. At 1280x800 (decimate 2) the Pis
manage about 63. The 1280x800 image has about 2.5x the pixels per tag, so each result *should* be
more precise, but there are fewer of them and each arrives about 10 ms later. This experiment asks
whether the better results make up for fewer results, **measured on the robot's own autonomous**.
The [bench test](../2026-11-11-pv-frame-cost/README.md) showed that several frames in flight could
bring 1280x800 back to full rate; this tells us whether that is worth building.

How: run the same autonomous (`CircleFacingTag`) with one setting on each camera, then swap, so camera,
mount and path differences cancel. A third kind of run, both cameras on the same setting, shows how
different the two cameras are when nothing is changed.

**Not run yet.** The analysis script works (checked on the 11-10 logs, below); the runs are the next
step.

## What we're testing

1. **Is a 1280x800 result more precise than an 800x600 one?** Compare each camera's own raw
   estimates, with the same camera on both settings. *(X1, X2)*
2. **Does the precision pay for the lost rate?** Averaging N independent results a second cuts noise by
   the square root of N, so 63/s needs results about 21% less noisy just to break even with 101/s
   (sqrt(63/101) = 0.79). We compute the noise left after one second of averaging, which weighs both.
   *(X1, X2)*
3. **Is the camera difference small compared with the setting difference?** *(AA)*

A setting **wins** if, on both cameras and in both crossover directions:

| Check | B wins if | Why |
|---|---|---|
| Noise after 1 s of averaging (`noise_per_sqrt_s_mm`) | lower than A by more than the A/A left-right gap | The number that weighs precision against rate |
| Longest gap, share of the run in gaps over 50 ms | not worse | A precise result that arrives rarely leaves odometry to drift |
| Latency | reported, not a pass/fail | B arrives ~10 ms later; the pose estimator corrects for capture time, but it is not free |

Write the numeric thresholds down **after the A/A runs and before looking at X1/X2**.

Caveats built into the numbers:

- **Jitter is not accuracy.** It measures scatter around a smooth curve, so it catches noise and
  timestamp jitter, but not a bias that depends on where the robot is (the few-cm errors seen in the
  camera calibration work; see [the notes](../../../camera-mount-calibration-notes.md)). Such a bias does not
  average away, so rate cannot buy it back. The Left-minus-Right bias and scatter are reported to
  keep an eye on it.
- **Noise-per-sqrt(s) assumes frame-to-frame noise is independent.**
- **Raw estimates, not the fused pose.** The analysis uses each camera's raw estimates, logged before
  any filtering, so the robot's trust settings do not matter. The fused-pose effect (what the robot
  actually does with them) is a second step: replay the same logs through `simulateJava` with each
  setting's samples.

### Words used here

- **Setting A / B:** A = 800x600 @100, decimate 2, threads 8 (the competition pipeline). B = 1280x800
  @100, decimate 2, threads 8.
- **Crossover:** every setting runs on every camera, so a camera's mount, angle and Pi do not get
  mistaken for the effect of the setting.
- **A/A run:** both cameras on the same setting, to measure the difference between the cameras when
  nothing is being tested.
- **Jitter:** how far each estimate is from a smooth curve through its neighbours (a quadratic over
  +-0.12 s, leave-one-out). Needs no ground truth and works while the robot moves.
- **Results/s:** pipeline results the robot received per second.

## The runs

Same maneuver every run: `CircleFacingTag_Tag10` (the fixed-start orbit). Same exposure and gain on
both cameras (the 11-10 log shows exposure 80, gain 25; set both cameras the same in PhotonVision and
check). Same battery state as far as practical. Vision corrections stay **on** so the robot behaves
as in a match; the analysis does not depend on them.

| Run | Left camera | Right camera | Status |
|---|---|---|---|
| AA1, AA2 | A | A | to do |
| X1a, X1b, X1c | A | B | to do |
| X2a, X2b, X2c | B | A | to do |

**Order** (fixed shuffle, seed 1405): X1b, X1a, AA1, X2a, X1c, AA2, X2c, X2b. The same list is in
[runs.toml](runs.toml), where each run's log is entered afterwards.

### Changing a setting (about a minute per camera)

In the PhotonVision UI of each Pi: camera **Video mode**, then **Decimate 2**, **Threads 8**,
**Low Latency Mode off**, exposure and gain unchanged. Wait for the stream to come back. The Pi
publisher logs the camera mode and pipeline settings, and `analyze.py` checks the log against the
table, so a mistake shows up as a flagged run, not a mystery.

### Before the session

- [ ] Both cameras calibrated in PhotonVision at **1280x800** and 800x600. The 11-10 log lists both
      as calibrated (`CalibratedResolutions`); check the reprojection error in the PhotonVision
      calibration page, and that fx at 1280x800 is sensible compared with 800x600 (about 690).
- [ ] Robot code on this branch deployed (it makes the pixel-offset filter use the image size
      PhotonVision is actually running; at 800x600 it changes nothing). Note the SHA.
- [ ] Both cameras start on A. Same exposure/gain on both.
- [ ] A fixed start spot taped, as `CircleFacingTag` starts from a fixed point anyway.
- [ ] After each run, copy its log name into `runs.toml`. Trim with the WPILog Janitor first.

## Pilot: checking the analysis on existing logs (not a result)

Two 11-10 runs (same autonomous, both cameras, one run at decimate 2 / 101 per s, one at decimate 1 /
68 per s, **800x600** both): jitter was higher at the lower rate, 13.0 vs 7.1 mm on the left and 9.5
vs 8.1 mm on the right; noise after one second of averaging was 123% and 44% higher. Those runs were
not matched (different speed profiles, a different day's tuning), so this is only evidence that the
script runs end to end and that the metric moves the way you would expect when the rate drops. It
also hints that finer detail alone does not reduce jitter here: timestamp jitter (about 5 mm per ms of
error at 1 m/s) is part of it, which does matter for odometry.

## Results

Not run yet.

### Verdicts

| Comparison | Verdict | Why (numbers) |
|---|---|---|
| | | |

## Next experiment

- If B wins on noise after averaging: try 2 workers x 2 threads on the bench (less added delay), then
  decide whether frames in flight are worth taking upstream.
- If B ties or loses: stay at 800x600 decimate 2; a faster pipeline would still need to beat the
  fused-pose effect, so replay first.
- Either way: a speed block (the same crossover at a higher orbit speed), where latency and rate
  matter more.
