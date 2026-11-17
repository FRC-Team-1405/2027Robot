# Vision Subsystem Log Analysis — Theory & Metrics

This document describes how to analyze the `.wpilog` files produced by the vision
subsystem to answer the questions that matter most after a match:

- Is this camera performing well on its own?
- Is one camera better or worse than the other?
- Are there signs of a calibration problem?
- Is the coprocessor keeping up?
- How much did vision actually contribute to odometry — and when did it fail to?
- When should we have seen a tag and didn't?

No specific tooling is assumed. The framework here can be applied in AdvantageScope,
a Python notebook, a custom log parser, or any environment that can read `.wpilog` files.

---

## 1. Available Data

### 1.1 Per-Camera Raw Inputs

Logged under `Vision/<CameraName>/` via `Logger.processInputs()` every robot loop (50 Hz).
One entry per pipeline result delivered by the coprocessor in that loop — may be 0, 1,
or several results per loop depending on coprocessor frame rate.

| Signal | Type | Meaning |
|--------|------|---------|
| `connected` | `boolean` | Camera connection state from PhotonVision |
| `currentFps` | `double` | Rolling ~1 s average of pipeline frame rate |
| `latestResultTimestampSec` | `double` | Timestamp of the most recent result processed |
| `visibleTagIds` | `int[]` | All AprilTag IDs detected this loop (across all results) |
| `rawEstimatedPoses` | `Pose3d[]` | 3D pose estimates from PnP, **before any rejection filter** |
| `rawTimestampsSec` | `double[]` | Coprocessor-side timestamp of each pose estimate |
| `rawAmbiguities` | `double[]` | PnP ambiguity per result (−1 for multi-tag; 0–1 for single-tag) |
| `rawAvgDistancesMeters` | `double[]` | Average camera-to-tag distance per result |
| `rawSumTagAreas` | `double[]` | Sum of tag pixel areas (0–100 scale) per result |
| `rawAvgNormalizedPixelOffsets` | `double[]` | Average normalized pixel distance from image center (0 = center, 1 = corner) |
| `rawAvgAspectRatioDevs` | `double[]` | Average tag aspect ratio deviation per result (1.0 = perfect square) |
| `rawTagCountsPerResult` | `int[]` | Number of tags used in each pose estimate |
| `rawTagIdsFlat` | `int[]` | All tag IDs, concatenated in result order (use counts to split) |

**Key architectural note:** These are pre-filter. Every pipeline result that PhotonVision
produced — including those that would later be rejected by the ambiguity threshold,
boundary check, or velocity check — appears here. This is intentional: you can replay
a log with different filter parameters and see how the rejection decisions change.

### 1.2 Computed Filter Outputs

Logged under `Vision/<CameraName>/` via `Logger.recordOutput()` **after** `processInputs()`.
These are recomputed on every replay, so they reflect the current filter code.

| Signal | Type | Meaning |
|--------|------|---------|
| `AcceptedPoses` | `Pose2d[]` | Estimates that passed all three rejection filters |
| `RejectedBoundary` | `int` | Count rejected this loop by field boundary check |
| `RejectedVelocity` | `int` | Count rejected this loop by velocity (>5 m/s jump) |
| `RejectedAmbiguity` | `int` | Count rejected this loop by ambiguity threshold (≥0.2) |

### 1.3 Drivetrain Signals (Correlatable)

The drivetrain logs its own chassis speeds and odometry pose. These can be joined to vision
signals by timestamp to understand the relationship between robot motion and vision quality.

| Signal | Source | Use in vision analysis |
|--------|--------|----------------------|
| Chassis speeds (vx, vy, ω) | Swerve `@AutoLogOutput` | Velocity bucketing, weight reconstruction |
| Robot odometry pose | `CommandSwerveDrivetrain` | Expected-vs-actual coverage computation |

### 1.4 What is NOT Logged (Data Gaps)

Understanding the gaps helps avoid false conclusions:

- **Per-tag individual areas** — only the sum across all tags in a result is logged. You
  cannot distinguish "one 4-unit-area tag" from "four 1-unit-area tags" from the log alone.

- **Coprocessor pipeline latency** — `rawTimestampsSec` is the coprocessor-reported capture
  time. The skew between the coprocessor clock and the roboRIO clock is not captured, so
  latency estimates from `(robot_loop_time − rawTimestampsSec)` may carry a systematic bias
  of 20–80 ms. This affects result-latency metrics but not relative comparisons.

- **Image quality metrics** — blur, brightness, and exposure are not available in the
  `.wpilog`. These would require coprocessor-side logging via PhotonVision's dashboard
  or a custom NT publisher.

- **Ground truth robot pose** — there is no external reference to measure absolute
  odometry accuracy from. Multi-camera agreement (when both cameras accept estimates in
  the same loop) is the best available proxy.

- **Tag pixel corner positions** — the individual corner locations that PhotonVision used
  to solve PnP are not logged. These would enable independent verification of the PnP
  result and a more direct calibration diagnostic.

---

## 2. Derived Metrics

### 2.1 Pipeline Health Metrics

These describe whether the camera and coprocessor are functioning at a basic level.

**FPS statistics**
Compute from the `currentFps` signal over enabled time:
- Mean FPS — should match the configured pipeline rate (typically 15–30 Hz for 1280×800)
- Minimum FPS — any sustained dip below configured rate indicates CPU saturation or a USB problem
- Std dev of FPS — high variance suggests intermittent dropouts rather than steady degradation

**Connection uptime**
```
uptime % = (loops where connected == true) / (total enabled loops) × 100
```
Even brief disconnections (a few loops) are worth flagging; a `connected = false` event
always precedes missed frames.

**Results-per-loop rate**
```
mean results/loop = sum(rawEstimatedPoses.length across loops) / total enabled loops
```
Compare against expected: a 30 Hz camera on a 50 Hz robot loop should average ~0.6 results/loop.
Consistently below expected → some frames are being dropped before the robot sees them.

**Result latency**
```
latency[j] = robot_loop_timestamp − rawTimestampsSec[j]
```
This is how stale each result is when the robot processes it. Healthy range: <100 ms.
Latency >150 ms suggests NT bandwidth saturation or a USB stall. Note the clock-skew caveat
above — treat absolute latency with caution and focus on relative trends.

---

### 2.2 Pose Acceptance Quality Metrics

These describe how many of the raw results survive the filter pipeline and in what condition.

**Acceptance rate**
```
acceptance rate = sum(AcceptedPoses.length) / sum(rawEstimatedPoses.length)
```
The denominator excludes loops with zero raw results (coprocessor saw nothing). A healthy
acceptance rate above 60% is expected; below 40% suggests the filter is too aggressive,
the camera is looking at tags it can't resolve well, or there is a calibration problem.

**Rejection breakdown**
Across all loops, sum each rejection counter and compute fractions:
```
ambiguity rejection % = sum(RejectedAmbiguity) / total_rejected × 100
boundary rejection %  = sum(RejectedBoundary)  / total_rejected × 100
velocity rejection %  = sum(RejectedVelocity)  / total_rejected × 100
```
The mix tells you where to look:
- Dominated by ambiguity → mostly single-tag observations at difficult angles or distances
- Dominated by boundary → Z-height calibration error or tags detected outside field (noise)
- Dominated by velocity → large pose jumps between consecutive estimates — calibration or
  outlier poses getting through ambiguity check

**Multi-tag rate**
```
multi_tag_rate = (results where rawTagCountsPerResult[j] > 1) / total results
```
Multi-tag PnP is dramatically more reliable than single-tag. A low multi-tag rate means
the camera is rarely seeing two or more reef tags simultaneously — either a coverage issue,
a distance issue (tags subtend too small an angle to appear together), or a calibration
issue reducing detection range.

**Ambiguity distribution**
For single-tag results only (rawTagCountsPerResult[j] == 1, rawAmbiguities[j] ≥ 0):
Plot a histogram of `rawAmbiguities[j]` from 0 to 1 in 0.05 bins. Healthy distribution
peaks at < 0.1 and drops sharply before the 0.2 rejection threshold. A wide distribution
or a significant mass at 0.15–0.19 (just below rejection) indicates the camera is often
operating near its reliable single-tag limit.

**Distance distribution**
Histogram of `rawAvgDistancesMeters` for accepted estimates only:
- Peak < 2 m → camera is mostly contributing at close range; low-distance stddev is small,
  so these contributions are high-quality
- Peak > 4 m → camera is contributing mostly from far away; stddev climbs sharply with
  distance (see `DISTANCE_XY_STDDEV` LerpTable), so these contributions are low-weight

---

### 2.3 Calibration Health Indicators

Calibration errors leave systematic signatures in the raw data. These are most visible when
other confounders (motion, distance) are controlled for.

**Z-height distribution**
The Z component of `rawEstimatedPoses[j]` should cluster tightly around zero — the robot
drives on the floor. A systematic non-zero mean is a direct indicator of calibration error:

| Z-height mean | Likely cause |
|---------------|--------------|
| Consistently +0.10 m | Camera mounted higher than constants say, or pitch angle wrong (camera looking down too steeply) |
| Consistently −0.05 m | Camera looking up too much, or height underspecified |
| Large variance (±0.2 m) | Wrong focal length; PnP solution unstable at this distance |

Compute Z-height distribution separately for single-tag and multi-tag results — multi-tag
is more stable and gives a cleaner calibration signal.

**Aspect ratio deviation distribution**
`rawAvgAspectRatioDevs[j]` measures how square the detected tags look. A perfectly calibrated
camera looking at a square tag head-on should return 1.0. Systematic deviation from 1.0:

| Avg aspect ratio | Likely cause |
|-----------------|--------------|
| < 0.6 consistently | Large perspective distortion — tag very far off-axis, or wrong focal length ratio fx/fy |
| 0.7–0.85, distance-correlated | Normal: tags seen at oblique angles at range appear squashed |
| 0.7–0.85, angle-independent | Lens distortion not fully calibrated; distortion coefficients wrong |
| Bimodal distribution | Two populations of tag orientations (expected for reef layout) |

**Pixel offset distribution**
`rawAvgNormalizedPixelOffsets[j]` is 0 when tags are in the center of the frame and 1 when
they are at the corners. The distribution depends on camera placement and what tags are visible:

- A roughly uniform distribution from 0 to 0.7 is expected for a well-positioned camera
- A systematic bias toward 1.0 (corner) means the camera is consistently looking past the tags —
  yaw or pitch of the camera mount may be off in the constants
- A consistent bias toward 0 (center) means the camera is always pointed directly at a tag,
  which is fine but suggests limited field-of-view utilization

Pixel offset also strongly affects trust weight (via `PIXEL_OFFSET_WEIGHT_COEFFICIENT`), so
high offset produces low-weight contributions even when the pose estimate is valid.

**Boundary rejection Z-vs-XY decomposition**
When `RejectedBoundary > 0`, inspect which coordinate triggered the rejection:
- Rejections where only |Z| > 0.75 m → pure height calibration error; X/Y plausible
- Rejections where X or Y is outside field + margin → tag misidentification, extreme range, or
  camera transform wrong in the lateral direction
- Both coordinates out of range → severe calibration error or a phantom detection

This decomposition requires replaying the log with extra `Logger.recordOutput()` calls inside
the boundary check block, since the current log only captures the count, not which axis failed.

**Multi-camera pose agreement**
On loops where both cameras produce accepted estimates, compare their accepted `Pose2d`:
```
agreement_error = distance(Left.AcceptedPoses[j], Right.AcceptedPoses[k])
```
where j and k are from the same robot loop. If both cameras are well-calibrated and observing
the same field, their estimates should agree within 0.10–0.20 m. Systematic disagreement
between cameras > 0.30 m indicates one or both have a calibration error.

---

### 2.4 Velocity-Correlated Quality Analysis

Robot velocity is the primary external confounder for vision quality. Fast rotation causes
motion blur and makes the velocity rejection filter more aggressive. Fast translation moves
the robot between the coprocessor capturing a frame and the robot processing it.

**Motion state bucketing**
Assign each robot loop to one of four motion states using chassis speeds:

| Bucket | Condition |
|--------|-----------|
| Stationary | \|v_linear\| < 0.2 m/s AND \|ω\| < 0.3 rad/s |
| Slow translate | v_linear 0.2–1.5 m/s AND \|ω\| < 0.8 rad/s |
| Rotating | \|ω\| ≥ 1.5 rad/s (any linear speed) |
| Full speed | v_linear > 2.0 m/s OR \|ω\| > 4.0 rad/s |

For each bucket, compute: acceptance rate, multi-tag rate, mean ambiguity (single-tag only),
mean distance of accepted estimates.

The expected pattern is:
- Stationary → highest acceptance rate, best ambiguity, longest distances
- Slow translate → slightly lower acceptance (velocity check fires more)
- Rotating → substantially lower acceptance; motion blur, velocity rejection spikes
- Full speed → lowest acceptance; weight multipliers near 0 even for accepted estimates

**The "stationary quality score" — the headline metric**

```
stationary_quality_score = (accepted estimates in stationary loops) /
                           (raw estimates in stationary loops)
```

This is the single most diagnostic number for camera health. When the robot is stationary:
- Motion blur cannot cause ambiguity failures
- The velocity rejection filter cannot fire (no previous jump)
- The angular-velocity weight multiplier is 1.0
- All remaining failures are intrinsic to the camera or calibration

A healthy camera should score > 80% in stationary loops. Below 60% in stationary is a red
flag independent of anything else.

**The "stationary and bad" event list**

Enumerate individual robot loops where:
1. Motion state = Stationary
2. `rawEstimatedPoses.length > 0` (coprocessor sent results)
3. `AcceptedPoses.length == 0` (all rejected)

For each such loop, record the rejection reason, distance, ambiguity, and Z-height. This
is the most actionable list that log analysis can produce — every event is one that the
robot had no motion-based excuse for missing.

**Acceptance rate vs. velocity scatter plots**

Plot two scatter plots:
1. `acceptance_rate` (per loop) vs. `|v_linear|` — expect negative correlation
2. `acceptance_rate` (per loop) vs. `|ω|` — expect strong negative correlation

Outliers above the trend line (high velocity but high acceptance) can indicate a camera
that is unusually robust. Outliers below the trend line (low velocity but low acceptance)
are the diagnostic target — they suggest camera-intrinsic problems masked by the general
velocity correlation.

---

### 2.5 Expected-vs-Actual Coverage Analysis

This is the most powerful diagnostic available. Given the robot's known position, the camera's
known transform, and the AprilTag field layout, we can compute which tags *should* have been
visible to each camera at each moment — and compare that expectation to what was actually seen.

**Geometric observability algorithm**

For each camera, for each robot loop:
1. Look up the robot's odometry pose at that timestamp
2. Apply the camera transform from `VisionConstants.CONFIGS` to get the camera's pose in
   field coordinates
3. For each AprilTag in the field layout:
   a. Compute the tag's position in the camera's coordinate frame
   b. Check the tag is in front of the camera (positive Z in camera frame)
   c. Project the tag center to pixel coordinates using the camera intrinsics
   d. Check the projected point is within the image bounds (0 ≤ px ≤ width, 0 ≤ py ≤ height)
   e. Check the camera-to-tag distance is within the maximum reliable range (~7 m from
      the `DISTANCE_XY_STDDEV` table where stddev reaches 9999)
   f. Check the tag is facing the camera (dot product of tag surface normal and
      camera-to-tag vector is negative — tag faces away from wall)
4. If all checks pass: this tag is **geometrically observable** this loop

**Metrics enabled by this analysis**

*Detection gap rate (per camera)*
```
detection_gap_rate = loops where (≥1 tag observable AND visibleTagIds is empty) /
                     loops where ≥1 tag observable
```
This measures how often the camera simply failed to report any detection despite being in
a position where it should have seen something. High values suggest coprocessor-side failures
(pipeline crash, USB dropout) rather than an algorithm problem.

*Per-tag detection rate*
```
tag_N_detection_rate = loops where tag N is in visibleTagIds /
                       loops where tag N is geometrically observable
```
Compute this for every tag ID. Tags with low detection rates when they should be visible
reveal specific field zones where the camera underperforms. Group by reef side to compare
robot behavior on each alliance's side.

*Quality vs. expectation delta*
For loops where a tag is geometrically observable AND the camera reports a result:
1. Compute expected tag area given the geometric distance (using tag physical size and
   camera focal length: `area ≈ (tag_side_meters × fx / distance)²`)
2. Compare to `rawSumTagAreas[j]`
3. A large negative delta (actual area << expected) suggests partial occlusion, wrong
   focal length in constants, or the coprocessor running a reduced-resolution pipeline
4. A large positive delta suggests the camera transform is wrong — the robot thinks the
   tag is farther than it is

*"Should have seen it well" failure events*
The most actionable event type. Criteria:
- Tag is geometrically observable
- Projected pixel position is within the inner 60% of the image (not an edge case)
- Camera-to-tag distance is < 3 m
- Robot is in the Stationary or Slow translate motion bucket
- Camera did NOT accept any estimate that loop

These events combine all favorable conditions: close, centered, not moving. Failure here
cannot be explained by distance, angle, or motion. It points directly to a calibration
error, coprocessor problem, or physical obstruction.

**Why this matters more than raw acceptance rate**

Raw acceptance rate conflates two very different failure modes: "the camera couldn't possibly
see that tag from here" and "the camera should have seen that tag perfectly and didn't."
The expected-vs-actual framework separates them. A camera with 40% acceptance rate but near-zero
"should have seen it well" failures is performing correctly — it's rejecting physically
marginal observations. A camera with 70% acceptance rate but many "should have seen it well"
failures has a real problem hidden by favorable conditions.

---

### 2.6 Odometry Contribution Metrics

Vision is most valuable when it corrects drift in wheel odometry. These metrics describe
how often and how strongly vision actually fed estimates to the pose estimator.

**Sample rate**
```
sample_rate = sum(AcceptedPoses.length) / enabled_time_seconds
```
Target: matches or slightly exceeds camera frame rate (filtered to accepted estimates).
A sample rate far below camera FPS means most frames are rejected; a zero-sample gap
lasting > 2 seconds means the robot was navigating entirely on wheel odometry.

**Contribution gap analysis**
Find all time intervals where `AcceptedPoses.length == 0` for consecutive loops. Report:
- Longest single gap (worst-case dead reckoning period)
- Total gap time as a fraction of enabled time
- Gap distribution (are there many short gaps or a few long ones?)

Correlate gaps with robot motion state. Gaps during full-speed rotation are expected and
harmless (the weight multiplier would be near 0 anyway). Gaps during stationary or slow
periods are the red flags.

**Effective trust weight reconstruction**
The final weight applied to each accepted estimate is:
```
effective_weight ≈ getTrustScalar()
                 × AREA_WEIGHT_COEFFICIENT.lerp(rawSumTagAreas[j])
                 × PIXEL_OFFSET_WEIGHT_COEFFICIENT.lerp(rawAvgNormalizedPixelOffsets[j])
                 × HEIGHT_WIDTH_PROPORTION_WEIGHT_COEFFICIENT.lerp(rawAvgAspectRatioDevs[j])
                 × LINEAR_VELOCITY_WEIGHT_COEFFICIENT.lerp(|v_linear|)
                 × ANGULAR_VELOCITY_WEIGHT_COEFFICIENT.lerp(|ω|)
```
All inputs to this product are logged (the LerpTable constants are fixed per build, so they
can be applied in analysis). Compute the effective weight for each accepted estimate and
plot its distribution:
- Weight consistently < 0.2 → vision is being heavily discounted; wheel odometry dominates
  even when vision accepts a result
- Weight > 0.8 only during stationary periods → weight function is working as designed
- Weight < 0.3 during stationary periods → the area or pixel-offset LerpTables may be
  too aggressive; consider retuning

---

## 3. Analysis Profiles

Each profile groups the metrics above to answer a specific question.

---

### Profile 1: Camera Health Snapshot

**Question: Is this camera working at a basic level?**

Key numbers (compute over the entire enabled period):
1. **Stationary quality score** — the headline; > 80% is healthy
2. Connection uptime %
3. Mean FPS ± std dev
4. Mean result latency
5. Acceptance rate (all conditions combined)
6. Rejection breakdown (ambiguity / boundary / velocity %)

Plot: FPS and `connected` vs. time to identify any transient failures.

**Interpretation:**
- Stationary quality score < 60% → camera or calibration problem; investigate profiles 3 and 6
- Connection uptime < 99% → USB or power issue; physical inspection
- Mean FPS < 80% of configured rate → coprocessor CPU overload; see profile 4
- Acceptance rate < 40% → filter may be misconfigured, or calibration is producing bad poses

---

### Profile 2: Camera A vs. Camera B Comparison

**Question: Is one camera outperforming the other?**

Side-by-side for Left and Right cameras:

| Metric | Left | Right |
|--------|------|-------|
| Stationary quality score | | |
| Acceptance rate | | |
| Multi-tag rate | | |
| Mean distance of accepted estimates | | |
| Dominant rejection type | | |
| Mean FPS | | |
| Per-tag detection rates (by tag zone) | | |

Also compare: distance distributions (histogram overlay), ambiguity distributions (single-tag
only), Z-height distributions.

**Interpretation:**
- Large gap in stationary quality score → camera with lower score has a hardware or
  calibration problem independent of the robot's behavior
- One camera dominates multi-tag rate → field layout favors that camera's field of view;
  consider whether camera placement could be optimized
- Systematic Z-height difference between cameras → the camera with the offset has a
  height or pitch calibration error; the one closer to 0 is better calibrated

---

### Profile 3: Calibration Red Flags

**Question: Does this camera have calibration or mounting errors?**

Compute for each camera:
1. Z-height mean and std dev (from `rawEstimatedPoses[j].getZ()`)
2. Z-height distribution histogram (should peak sharply at 0)
3. Aspect ratio deviation distribution (should peak near 1.0)
4. Pixel offset distribution (should be centered, not edge-biased)
5. Boundary rejection Z-vs-XY decomposition
6. Multi-camera pose agreement error distribution (when both cameras have simultaneous accepts)

**Red flags and their implications:**

| Observation | Likely calibration issue | Fix |
|-------------|------------------------|-----|
| Z-height mean ≠ 0 by > 0.05 m | Height or pitch angle wrong in constants | Measure camera height more carefully; re-run photon calibration |
| Aspect ratio deviation mean < 0.7 | Focal length ratio fx/fy wrong, or high barrel distortion | Recalibrate; use more calibration frames at different distances |
| Pixel offset biased high (> 0.5 mean) | Camera yaw off in robot constants | Measure camera yaw angle; update `VisionConstants.CameraConfig` transform |
| Boundary rejections with Z as trigger | Camera height overestimated in constants | |
| Multi-camera agreement error > 0.3 m | One camera has lateral translation error | Check camera X/Y position in robot frame |

---

### Profile 4: Coprocessor Performance

**Question: Is the coprocessor processing frames fast enough and getting results to the robot in time?**

Key plots:
1. FPS vs. time (should be flat; dips indicate CPU saturation or frame drops)
2. Result latency vs. time (should be flat; spikes indicate NT bandwidth or USB stalls)
3. Results-per-loop vs. time (expect ~0.6 for a 30 Hz camera on 50 Hz robot)
4. Connection status timeline (any `connected = false` events)

**Interpretation:**
- FPS drops consistently when robot is moving fast → coprocessor image pipeline is
  not the issue (coprocessor doesn't know the robot is moving); more likely USB cable
  vibration causing reconnect events, or the camera exposure is increasing in motion
- FPS drops with no motion correlation → coprocessor CPU, thermal throttling, or the
  pipeline doing heavy computation (e.g., 3D pose solve with many tags)
- Result latency spikes isolated to specific moments → NT bandwidth saturation; consider
  reducing the number of NT signals being published
- Results-per-loop consistently below 0.4 on a 30 Hz camera → frames being dropped
  between the coprocessor and the robot; USB or NT issue

---

### Profile 5: Odometry Contribution

**Question: How much did vision actually help, and when did it fail to contribute?**

1. Plot sample rate (accepted estimates per second) vs. time
2. Scatter plot: sample rate vs. |v_linear| and vs. |ω|
3. Scatter plot: effective_weight vs. |v_linear| — should be strongly negatively correlated
4. Contribution gap timeline: mark all intervals > 0.5 s with zero accepted estimates
5. Correlate gaps with motion state bucket

**Most important output:** the "stationary and bad" event list — see section 2.4.

**Interpretation:**
- Long gaps during slow/stationary motion → camera coverage hole or filter too aggressive;
  cross-reference with profile 6 to see if a tag should have been in view
- Effective weight near 0 during stationary → LerpTables are discounting estimates even
  at close range; consider retuning AREA_WEIGHT_COEFFICIENT
- Sample rate matches camera FPS during stationary periods → filter is not over-rejecting;
  check that pose estimator is actually consuming these estimates

---

### Profile 6: Field Coverage Map

**Question: Are there parts of the field where camera coverage fails, or tags that are consistently missed when they should be visible?**

**Visualization elements:**

1. **Robot path** — the odometry pose trace overlaid on a 2D field diagram, one color per
   camera's accepted estimates

2. **Tag detection rate heatmap** — for each AprilTag ID, compute the per-tag detection rate
   (section 2.5). Color each tag on the field:
   - Green (> 85%) — consistently detected when geometrically observable
   - Yellow (50–85%) — mixed; investigate why
   - Red (< 50%) — frequently missed despite being in FOV

3. **Camera FOV cones** — at a few representative robot poses (e.g., scoring approach angles),
   draw the camera FOV projections onto the field to visualize coverage at those moments

4. **"Should have seen it well" events** — plot each event (section 2.5) as a red dot at
   the robot's position when it occurred; cluster of dots reveals spatial patterns

5. **Detection gap events** — mark the robot path with orange segments where neither camera
   produced any accepted estimate while a tag was geometrically observable

**Interpretation:**

- Cluster of "should have seen it well" failures at one side of the field → camera aimed
  wrong (yaw error), or systematic blind spot in that direction
- Tags consistently red despite the robot approaching them → tag may be partially
  blocked by a robot mechanism in that position, or the camera's mounting position doesn't
  give coverage in that zone
- Detection gap events correlate with specific approach angles → FOV is not aligned with
  the relevant tags at that approach; a camera mount angle adjustment would help
- One camera's red tags are all on the opposite side of the field → expected; the other
  camera should have complementary coverage; verify the overlap zone is adequate

---

## 4. Interpretation Reference

### What each metric tells you

| Metric | Healthy range | Out-of-range cause |
|--------|---------------|--------------------|
| **Stationary quality score** | > 80% | Calibration error, coprocessor issue, lighting |
| **Z-height mean** | ±0.05 m | Height or pitch angle wrong in constants |
| **Z-height std dev** | < 0.08 m | Wrong focal length; PnP unstable at this range |
| **Aspect ratio dev mean** | > 0.85 | Lens distortion, wrong fx/fy, oblique angle |
| **Pixel offset mean** | < 0.40 | Camera yaw/pitch mount error |
| **Ambiguity median (single-tag)** | < 0.12 | Tag small, far, bad lighting, motion blur |
| **Multi-tag rate** | > 30% | Limited tag co-visibility; distance or coverage issue |
| **Acceptance rate** | > 60% | Filter too aggressive, or calibration producing bad poses |
| **Velocity rejection fraction** | < 15% | Large pose jumps; calibration or outlier single-tag poses |
| **Boundary rejection fraction** | < 10% | Z calibration error, or phantom long-range detections |
| **FPS mean** | ≥ configured rate | Coprocessor CPU, thermal throttle, USB connection |
| **Result latency** | < 100 ms | NT bandwidth, USB stall; clock skew may bias this |
| **Results-per-loop** | ≈ camera_fps / 50 | Frames dropped between coprocessor and robot |
| **Detection gap rate** | < 5% | Coprocessor failure, USB dropout, severe occlusion |
| **Per-tag detection rate** | > 75% for priority tags | FOV coverage, occlusion, coprocessor issue |
| **Multi-camera agreement error** | < 0.20 m | One camera has systematic calibration offset |
| **"Should have seen it well" count** | 0 ideally | Worst-case diagnostic; any count demands root cause |

### Common failure signatures

**"Camera just doesn't work"**
Stationary quality score < 40%, Z-heights scattered ±0.3 m, high boundary rejections.
Usually: wrong camera transform in constants (swapped X/Y, or sign flip on a rotation).

**"Camera works but misses far tags"**
Stationary quality score good at close range, poor at > 4 m. Ambiguity distribution
has a long tail near 0.2. Usually: accurate calibration but insufficient detection range
for the camera's focal length and tag size.

**"Camera has a blind spot"**
Detection gap events clustered at specific robot headings. Per-tag detection rate low
for specific tags while nearby tags are fine. Usually: camera yaw misconfigured — the
camera is rotated a few degrees off in constants, shifting the FOV away from those tags.

**"Camera jitters during rotation"**
High velocity rejection fraction. Velocity rejection events mostly at high ω. Z-heights
during rotation show high variance even at close range. Usually: motion blur affecting
the PnP solve; consider lowering coprocessor exposure time, or tightening the ambiguity
threshold to avoid accepting blurred single-tag results.

**"Both cameras systematically disagree"**
Multi-camera agreement error > 0.25 m consistently. One camera's accepted poses form a
coherent path; the other's are offset. Usually: one camera's physical position on the robot
is not what the constants say — measure from a common reference point and update the
transform.

---

## 5. Data to Consider Adding

Adding these fields to `VisionIOInputs` would enable richer analysis without requiring
coprocessor changes:

| Addition | Signal(s) to add | Analysis unlocked |
|----------|-----------------|-------------------|
| Per-tag areas | `double[] rawIndividualTagAreas` | Pinpoint which specific tag is small/far in multi-tag results |
| Per-result tag IDs already available via `rawTagIdsFlat` | — | Per-tag detection rate already computable |
| Coprocessor-reported pipeline latency | `double[] rawPipelineLatencySec` | Separate coprocessor latency from NT latency |
| Tag corner pixel positions | `double[][] rawTagCornerPixels` | Compute expected vs. actual area from geometry; strongest calibration check |
| Coprocessor-reported result confidence | If PhotonVision exposes it | Weight estimates by coprocessor confidence rather than proxy metrics |

None of these require changes to the filter logic or replay architecture. They would be
added to `VisionIOPhotonVision.updateInputs()` and logged transparently.
