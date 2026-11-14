---
id: VIS-2026-11-14-pv-crossover-odometry
title: Two camera settings on the same autonomous, swapped between cameras: which gives better vision odometry?
area: vision
date: 2026-11-14
status: planned               # planned | running | analyzed | decided
decision: pending
robot_code: beta @ (fill in from RealMetadata/GitSHA before the first run)
logs: logs/ (gitignored); name each run's log in the run table
analysis: analyze.py → results.json (not written yet)
raw_notes: notes/<date>/notes.md
---

# Camera-setting crossover on the same autonomous

## In short

The [frame-cost bench test](../2026-11-11-pv-frame-cost/README.md) showed the Pis can process
about 4x the frames/s with several frames in flight, at the cost of each frame arriving ~10 ms
later. It did **not** show that this improves odometry. This experiment tests that on the robot,
without the range experiment: run the same autonomous with a different setting on each camera,
then swap the settings and run it again, so the camera, mount and path differences cancel.

**Not run yet.** It starts after the cameras are calibrated with the
[spin & drive tool](../../../camera-autocal-plan.md), because the comparison is only as good as
the camera mounts.

## What we're testing

1. **Does setting B give a better odometry signal than setting A (800x600, decimate 2)?** Compare
   each camera's own raw estimates under A and under B, in both camera positions. *(X1, X2)*
2. **How big is a difference we can trust?** Run both cameras with the *same* setting, so any
   Left-vs-Right difference is the noise floor. *(A/A)*
3. **Does speed change the answer?** Latency and rate matter more at speed than at rest. *(speed
   block, after the first block works)*

A setting **wins** if:

| Check | Wins if | Why |
|---|---|---|
| Jitter (the camera's estimate against the smooth wheel+gyro odometry, drift removed) | lower than the other setting on the same camera, by more than the A/A spread | Noise is what the filter has to average out |
| Tag uptime | not lower | A better pose that arrives less often is not better |
| Dropout length | not longer | Long gaps are where odometry drifts |
| Taped end position | closer | The one absolute check we have |

Write the thresholds from the A/A runs **before** looking at X1/X2.

### Words used here

- **Setting A / B:** a PhotonVision pipeline setting (resolution, decimate, threads). A is
  800x600 decimate 2 (the competition setting). B is the one under test (see "Open").
- **Crossover:** every setting runs on every camera, so a camera's mount, angle and Pi do not
  get mistaken for the effect of the setting.
- **A/A run:** both cameras on the same setting, to measure the difference between cameras when
  nothing is being tested.
- **Jitter:** how far a camera's estimate wanders from the smooth wheel+gyro path, after slow
  drift is removed. It needs no ground truth.

## The runs

Same maneuver every run: `CircleFacingTag` (check that it varies the distance to the tag; if it
holds one range, add a second path that does). Same starting pose (taped). Same exposure and gain
on both cameras. Vision corrections stay **on** in the robot code so it behaves like a match, but
the analysis uses each camera's raw per-camera estimates (logged before filtering), not the fused
pose.

| Run | Left camera | Right camera | Repeats | Status |
|---|---|---|---|---|
| A/A | A | A | 2 | to do |
| X1 | A | B | 3 | to do |
| X2 | B | A | 3 | to do |

Order the runs randomly. Write the PhotonVision settings of both cameras into this table before
each run; the Pi publisher also logs them, so verify from the log, not from the notes.

### Open

- **What is setting B?** 800x600 decimate 2 is decided as A. B was not chosen on 2026-11-14.
  Candidates: 1280x800 decimate 2, 4 threads (63 results/s on stock PhotonVision); or 800x600
  decimate 1 (68/s). Stock PhotonVision cannot do frames in flight, so B here tests resolution or
  detail **at a lower rate**; it is a pessimistic proxy for the frames-in-flight idea. If B at
  63/s already matches A at 101/s, B at full rate can only be better.
- **Calibration at B's resolution.** Intrinsics are per resolution. B needs its own.
- **Rate vs resolution.** The rate effect can be estimated afterwards by thinning A's estimates to
  B's rate in the log.

### Before the session

- [ ] Camera mounts known well enough. On 2026-11-14 the constants matched a tape measure, and the
      spin & drive tool did not; see [the calibration notes](../../../camera-mount-calibration-notes.md).
      The left/right swap cancels most mount error, so this does not block the experiment.
- [ ] Intrinsics calibrated at the resolution of every setting used.
- [ ] Settings for A and B written into the run table; exposure and gain identical.
- [ ] Taped start and end marks.
- [ ] Logs from each run named here; trimmed with the WPILog Janitor.

## Results

Not run yet.

## Next experiment

If B wins: try the in-flight setup on the bench with 2 workers x 2 threads, then decide whether
to take it upstream. If it does not: stay on stock PhotonVision at 800x600 decimate 2.
