---
id: VIS-2026-11-03-pv-range
title: PhotonVision range — how far each camera setting sees tags, and how accurately
area: vision
date: 2026-11-03            # written; rename the folder to the day it runs
status: planned             # planned | running | analyzed | decided
decision: pending
robot_code: any build with VISION_EXTENDED_NT_LOGGING = true
logs: logs/offseason/<run date>/
analysis: analyze.py → results.json (to write: reuse cam_stats from ../2026-10-27-pv-throughput, one enabled span per setting)
raw_notes: notes/<run date>/notes.md
---

# PhotonVision range: how far each camera setting sees tags, and how accurately

## In short

The frame-pacing experiment showed that turning off Low Latency Mode lets finer camera settings
keep up with the camera: decimate 2 now runs at the full 100 results/s, where it ran at half rate
before. A finer image costs Pi CPU, though, and is only worth it if it **sees tags further away or
measures them more accurately**. This experiment parks the robot at fixed, tape-measured distances
from a tag and compares the settings side by side.

**Not run yet.** Run it after the frame-pacing runs R6 and R13, which decide which settings are
worth comparing.

## What we're testing

1. **How far away does each setting still see the tag reliably?** The fraction of camera frames
   that produce a result, at each distance. *(all runs)*
2. **How accurate is it at range?** The distance PhotonVision reports vs the tape measure, and
   how much the pose jumps around while the robot sits still. *(all runs)*
3. **Does viewing angle change the answer?** Tags seen at about 45° are harder than straight on.
   *(A-runs)*

A setting is **worth its CPU** at a distance if, compared with the baseline (S0) at that distance:

| Check | Better if |
|---|---|
| Detection rate (results ÷ camera frames) | at least 10 percentage points higher, or the baseline is under 80% and this one isn't |
| Distance error (median, vs tape) | smaller by at least 2 cm or 1% of the distance |
| Pose noise (standard deviation of x and y while still) | at least 25% lower |

The settings themselves must still pass the frame-pacing checks (≥ 90% of camera fps, ≤ 3%
dropped frames).

### Words used here

- **Setting (S0–S3)**: one PhotonVision camera configuration, saved as its own pipeline (see
  "Before the session").
- **Decimate**: how much PhotonVision shrinks the image before searching for tags. Lower = finer
  image = sees smaller (further) tags, costs more CPU.
- **Detection rate**: results/s ÷ camera fps. 100% means every frame found the tag.
- **Distance error**: PhotonVision's camera-to-tag distance (`Vision/<cam>/RawAvgDistancesMeters`)
  minus the tape-measured one.
- **Pose noise**: standard deviation of the estimated x, y and heading while the robot doesn't
  move. With the robot parked, it should be zero.

## The settings

All with **Low Latency Mode off**. Leave out any setting that failed in the frame-pacing
experiment, and note which.

| | Camera mode | Decimate | Why |
|---|---|---|---|
| S0 | 800x600 @100 | 3 | Baseline: the 10-27 recommendation |
| S1 | 800x600 @100 | 2 | Passed in frame-pacing R3 |
| S2 | 800x600 @100 | 1 | If frame-pacing R6 passes |
| S3 | 1280x800 @100 | 2 | If frame-pacing R13 passes |

## The runs

One log per robot position. At each position, enable for about 10 s **once per setting** (four
enabled spans), switching the pipeline between spans. Always use the same order (S0, S1, S2, S3)
and write it in the notes.

| Run | Robot position (camera to tag, along the floor) | What it checks | Status |
|---|---|---|---|
| D2 | 2 m, straight on | Close range; every setting should be ~100% | to do |
| D4 | 4 m, straight on | | to do |
| D6 | 6 m, straight on | Where we expect the settings to separate | to do |
| D8 | 8 m, straight on (or as far as the space allows) | Edge of range | to do |
| A4 | 4 m, about 45° to the tag | Viewing angle | to do |
| A6 | 6 m, about 45° | Viewing angle at range | to do |

Measure from the **camera lens** to the **tag centre**, for both cameras if both see the tag.
Write the measured distances in the notes. Height doesn't matter if it's the same every run.

### Before the session

- [ ] Frame-pacing R6 and R13 done, so we know which of S2/S3 to include.
- [ ] **On each Pi, make one PhotonVision pipeline per setting** (S0 = index 0, S1 = 1, …). A
  camera mode is per pipeline, so each one holds its own resolution and decimate. Then switch
  settings from Elastic or AdvantageScope by writing
  `/photonvision/<camera>/pipelineIndexRequest`, with no PhotonVision browser tab open. Check
  `/photonvision/<camera>/pipelineIndex` before each span.
- [ ] Copy each pipeline's settings into the notes (resolution, decimate, Low Latency Mode,
  threads).
- [ ] Mark the floor positions with tape before the session, so the robot goes back to the same
  spot.
- [ ] Enable in teleop with the sticks untouched, so the robot holds still. Check that the
  odometry pose doesn't drift during a span; if it does, note it.

## Results

Not run yet. `analyze.py` should, for each run and each enabled span (= setting): detection rate,
median distance and its error vs the tape, pose noise (x, y, heading), ambiguity, and how many
results the robot's vision filters accepted. The 10-27 `cam_stats` already computes all of these
for one window; call it once per span.

## Next experiment

If a finer setting wins only beyond some distance, the next question is whether to switch
settings by distance (two pipelines and a robot-side switch), or to just accept the CPU cost.

## Reproduce

```bash
python docs/experiments/vision/2026-11-03-pv-range/analyze.py
```

---

## Background

<details>
<summary><b>Why stationary, and why one log per position</b></summary>

When the robot is moving, the pose changes, so any variation in the estimate mixes the robot's
motion with the measurement's noise. Parked, any variation in the estimate *is* the noise, and the
true distance is a tape measure away. Running every setting at the same position, a few seconds
apart, means the lighting, the robot's placement and the Pi's temperature are the same for all of
them. Only the setting changes.

The 10-27 open question 2 asked for this test: "Higher resolution only earns its cost at range."

</details>
