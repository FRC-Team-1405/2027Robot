# Vision Testing & Validation Protocol

> How to scientifically measure the impact of each proposed vision improvement.  
> Stack: PhotonVision → NT → AdvantageScope

---

## Core Principle

Every proposed change should be testable with a **before/after measurable metric**. The existing NT logging infrastructure (plus the additions proposed in [vision-improvements-2027.md](./vision-improvements-2027.md)) provides the data foundation. 

**The key insight:** You already have the infrastructure to do A/B testing — the `FeatureSwitches` constant class lets you hot-swap behaviors. The goal is to define what "better" actually means numerically.

---

## Metrics to Capture

Before designing experiments, establish what you're measuring:

| Metric | What It Represents | How to Measure |
|--------|--------------------|---------------|
| **Correction magnitude** | How far vision pulls the odometry pose | `sample.pose().getDistance(drivetrain.getPose())` — log per sample |
| **Alignment error** | Final pose error when `PidToPoseCommand` finishes | Already loggable from PID controller error at `isFinished()` |
| **Pose noise** | Variance of consecutive vision poses in steady state | Standard deviation of `Camera1_EstimatedPose` while stationary |
| **Tag detection uptime** | % of time a tag is detected during a match | Frames with estimate / total frames |
| **Rejection rate per filter** | How often each filter fires | Log counters per filter reason |
| **Fused pose drift** | How much odometry drifts between vision corrections | Sample pose at T=0 and T+Δt while stationary |

---

## Experiment 1 — Baseline Noise Characterization

**Goal:** Establish a baseline for how noisy the current system is.

**Setup:**
1. Place the robot at a **known, measured field position** (tape the exact spot on the floor, measure to sub-centimeter)
2. Robot is stationary, disabled
3. Run for 60 seconds, log all `Camera1_EstimatedPose` and `Camera2_EstimatedPose`

**Analysis in AdvantageScope:**
- Export pose data to CSV
- Compute X standard deviation, Y standard deviation, θ standard deviation over the 60-second window
- This is your baseline noise floor

**Record:**
```
Stationary Noise Baseline (date, field, camera config)
  Camera Left:  σX = ?, σY = ?, σθ = ?
  Camera Right: σX = ?, σY = ?, σθ = ?
  Distance to nearest tag: ?m
```

Run this with tags at **multiple distances**: 0.5m, 1m, 2m, 3m, 5m. You'll see noise scale with distance — this informs how you tune stddev LerpTables.

---

## Experiment 2 — Filter Impact Isolation

**Goal:** Measure the contribution of each individual filter to overall noise.

**Method:** Add a `FeatureSwitch` boolean per filter:

```java
// FeatureSwitches.java
public static final boolean VISION_FILTER_BOUNDARY_CHECK     = true;
public static final boolean VISION_FILTER_VELOCITY_JUMP      = true;
public static final boolean VISION_FILTER_AREA_WEIGHT        = true;
public static final boolean VISION_FILTER_PIXEL_OFFSET       = true;
public static final boolean VISION_FILTER_ASPECT_RATIO       = true;
public static final boolean VISION_FILTER_VELOCITY_SCALING   = true;
public static final boolean VISION_FILTER_SMOOTH_THETA       = true;
```

Run the Experiment 1 stationary test with each filter **disabled one at a time**. Compare noise metrics.

**Expected findings:**
- Velocity jump rejection: reduces outlier spikes (look at max error, not stddev)
- Area weight: reduces noise at distance (larger stddev improvement at >3m)
- Smooth theta: reduces θ stddev, especially for lower-quality estimates

**Document as a table:**

| Filter Disabled | σX change | σY change | σθ change | Outliers/min |
|-----------------|-----------|-----------|-----------|--------------|
| Boundary check  | -         | -         | -         | -            |
| Velocity jump   | -         | -         | -         | -            |
| ... etc.        |           |           |           |              |

---

## Experiment 3 — Alignment Accuracy Test

**Goal:** Measure how accurately `PidToPoseCommand` places the robot at a target pose.

**Setup:**
1. Choose a specific target pose adjacent to a known April tag (e.g., reef branch approach)
2. Run `PidToPoseCommand` from the same starting pose 10 times
3. Physically measure the robot's final position with a tape measure or field measurement jig

**Metrics:**
- Mean error in X (meters)
- Mean error in Y (meters)
- Mean error in θ (degrees)
- Standard deviation of all three (repeatability)
- 90th percentile error (worst-case robustness)

**Log the PID errors:** Add to `PidToPoseCommand.java`:
```java
// At end of execute():
SmartDashboard.putNumber("/PidToPose/XError", xController.getPositionError());
SmartDashboard.putNumber("/PidToPose/YError", yController.getPositionError());
SmartDashboard.putNumber("/PidToPose/ThetaError", thetaController.getPositionError());
```

**Compare before/after each P1 fix.**  
Expected improvement from smooth theta stddev: reduced final heading error.  
Expected improvement from boundary rejection: fewer alignment failures from glitch estimates.

---

## Experiment 4 — Local vs. Global Estimator Comparison

**Goal:** Determine if TAG_RANKINGS or explicit local/global separation improves alignment.

**Setup:**
1. Robot approaches reef scoring position from 3m away
2. Run `PidToPoseCommand` 10 times with TAG_RANKINGS **off** (current state)
3. Run 10 times with TAG_RANKINGS **on** (reef tags only)
4. Compare alignment accuracy metrics from Experiment 3

**Add a toggle:**
```java
// FeatureSwitches.java
public static final boolean VISION_USE_TAG_RANKINGS = false;  // toggle for testing
```

```java
// Camera.java — activate based on switch
if (FeatureSwitches.VISION_USE_TAG_RANKINGS) {
    for (int tagId : seenTags) {
        trust *= Filtering.TAG_RANKINGS.getOrDefault(tagId, 0.0);
    }
}
```

**What to look for:**
- If alignment accuracy improves significantly (>30% error reduction): full local/global separation is worth building
- If improvement is marginal (<10%): the implicit area-based approach is already doing the job; save the complexity

This experiment directly answers the "how important is separation?" question with real data from your robot and your cameras.

---

## Experiment 5 — Distance-Based StdDev vs. Area-Based

**Goal:** Compare the two trust metric approaches.

**Add to FeatureSwitches:**
```java
public static final boolean VISION_USE_DISTANCE_STDDEV = false;  // true = new, false = old
```

In `RobotContainer.correctOdometry()`:
```java
double xyStddev;
if (FeatureSwitches.VISION_USE_DISTANCE_STDDEV) {
    xyStddev = Filtering.DISTANCE_XY_STDDEV.lerp(sample.avgDistanceMeters()); // add this field
} else {
    xyStddev = 0.1 / sample.weight();
}
```

Run the stationary noise baseline (Experiment 1) at multiple distances with both modes.  
**Expected:** Distance-based stddev produces tighter noise at close range and more appropriate rejection at long range.

---

## Experiment 6 — In-Motion Accuracy (Latency Sensitivity)

**Goal:** Verify latency compensation is working correctly.

**Setup:**
1. Robot drives a known straight path at 3 m/s (e.g., along a field wall)
2. Place tags at known positions along the path
3. Compare `Camera1_EstimatedPose` against `DriveState/Pose` during motion

**What to look for:**
- If vision estimates consistently lag *behind* the odometry pose: latency compensation is working (estimates should match odometry when applied to the past timestamp, not the present)
- If vision estimates are *ahead* of odometry: there is a timestamp inversion bug
- If vision estimates are consistently offset while stationary but drift during motion: gyro integration error is compounding; check `addHeadingData()`

**Log:** `CorrectionMagnitudeMeter` vs. robot speed. You expect a U-shape: low correction at rest (good accuracy), rising at speed (motion blur), falling very high speed (trust weights near zero → less correction).

---

## Experiment 7 — Competition Environment Simulation

**Goal:** Validate the system under match-representative conditions.

**Simulate:**
1. Robot runs a full auto routine against the tape-marked positions
2. Teleop: driver performs 5 alignment actions to the same target
3. Simulate a "bad tag" by covering one tag with a piece of cardboard mid-match

**Metrics:**
- How many alignment attempts succeed within tolerance (e.g., ±1 inch)
- How quickly the estimator recovers from the covered tag
- Whether any boundary-violating estimates make it through to `addVisionMeasurement`

---

## Logging Template

For each experiment, record:

```
Date: 
Robot config: 
Camera firmware: PhotonVision vX.X.X
FeatureSwitches state: (list active flags)
Tag layout: 
Conditions: (lighting, field, distance)

Results:
  σX:     
  σY:     
  σθ:     
  Max single-frame error: 
  Rejection rate:         
  Notes:
```

Store logs in: `TestingLogs/` (already exists in the 2026 repo, carry forward to 2027).

---

## Recommended Test Order

```
Week 1:
  1. Add NT logging (pre-requisite for all other experiments)
  2. Run Experiment 1 (stationary baseline) — establishes your current floor

Week 2:
  3. Apply P1 fixes (boundary check + smooth theta)
  4. Re-run Experiment 1 — compare noise; expect θ improvement
  5. Run Experiment 3 (alignment accuracy) before and after P1

Week 3:
  6. Run Experiment 4 (TAG_RANKINGS on/off) — make the local/global decision
  7. Run Experiment 5 (distance vs. area stddev) if time permits

Pre-competition:
  8. Run Experiment 7 (full simulation)
  9. Document final FeatureSwitches state and filter table values
```
