# 2026 Vision System — Code Analysis

> Reviewed against: [VisionTalk_Summary.md](../VisionTalk_Summary.md) (Team 6328 / Jonah talk)  
> Codebase: `C:\Users\importsjc\robotics\2026Robot`  
> Vision stack: PhotonVision + WPILib `SwerveDrivePoseEstimator`

---

## Architecture Overview

```
PhotonCamera (Left)     PhotonCamera (Right)
       │                       │
   Camera.java            Camera.java
  [PnP + filter]         [PnP + filter]
       │                       │
       └──────────┬────────────┘
              Vision.java
         [velocity weighting]
                  │
          RobotContainer
       [correctOdometry()]
                  │
   CommandSwerveDrivetrain
    [addVisionMeasurement()]
                  │
   SwerveDrivePoseEstimator
     (single unified estimator)
```

### Cameras

| Camera | Mount (robot-relative) | Calibration | FOV (from intrinsics) |
|--------|------------------------|-------------|----------------------|
| Left  | +2.19in X, +10.91in Y, 28.7in Z; Pitch -25°, Yaw -10° | 1280×800, fx≈910 | ~70° H |
| Right | +2.19in X, -10.91in Y, 28.7in Z; Pitch -25°, Yaw +10° | 1280×800, fx≈912 | ~70° H |

Both cameras are forward-facing, toed inward by ±10°. Both have full calibration matrices with 8-coefficient distortion.

### Pose Estimator Strategy

```java
PoseStrategy.MULTI_TAG_PNP_ON_COPROCESSOR
// fallback:
PoseStrategy.LOWEST_AMBIGUITY
```

Multi-tag PnP runs on the PhotonVision co-processor. Falls back to lowest-ambiguity single-tag when only one tag is visible. **No heading data is injected** (`addHeadingData()` is commented out).

---

## Filtering Pipeline — Detailed Breakdown

The pipeline has **two stages**: per-camera in `Camera.java` and per-sample in `Vision.java`.

### Stage 1: `Camera.java` — Per-Camera Filters

#### 1a. Tag Pruning (`pruneTags`)

```java
if (AprilTags.observableTag(target.fiducialId)) { keep; }
```

`observableTag()` currently returns `true` for **all tags**. The commented-out logic would restrict to the alliance's half of the field. **This is intentional for Reefscape-style games where both alliances' tags are relevant.**

#### 1b. Velocity Jump Rejection

```java
double distanceFromLastUpdate = pose.getTranslation().getDistance(previousUpdate.pose().getTranslation());
if (distanceFromLastUpdate > timeSinceLastUpdate * 5.0) {
    return Optional.empty();  // reject
}
```

Rejects any pose estimate that implies the robot moved >5 m/s between consecutive frames. **This is a solid sanity-check filter** — effectively catches tag glitches and large outliers.

#### 1c. Area-Based Trust (`AREA_WEIGHT_COEFFICIENT`)

```
Area (% of frame) → Trust multiplier
0.0%  → 0.0 (fully rejected)
0.2%  → 0.35
1.0%  → 0.45
4.0%  → 0.70
7.5%  → 1.0
```

Area is a proxy for distance — larger tags = closer = more trustworthy. However, area is **nonlinear with distance** (falls off with distance²), and the curve is somewhat arbitrary. This is functional but not principled.

#### 1d. Pixel Offset Trust (`PIXEL_OFFSET_WEIGHT_COEFFICIENT`)

```
Distance from frame center (normalized 0–1) → Trust multiplier
0.0–0.2 → 1.0   (near center, full trust)
0.65    → 0.75
1.0     → 0.35  (near corner, reduced trust)
```

Tags at the edges of the frame suffer more lens distortion. **This is a smart filter** — reduces trust for edge detections where calibration accuracy degrades.

#### 1e. Aspect Ratio Trust (`HEIGHT_WIDTH_PROPORTION_WEIGHT_COEFFICIENT`)

```
min(h,w)/max(h,w) → Trust multiplier
0.25 → 0.0   (very skewed = likely motion blur or extreme angle)
0.70 → 0.9
1.0  → 1.0   (square = ideal)
```

Tags that are very elongated (extreme viewing angle or rolling shutter distortion) are distrusted. **Good filter.**

#### 1f. TAG_RANKINGS (Commented Out)

```java
// for (int tagId : seenTags) {
//     trust *= Filtering.TAG_RANKINGS.getOrDefault(tagId, 0.0);
// }
```

The rankings map was defined to give weight 1.0 to reef tags (6–11, 17–22) and **0.0 to all others** (coral stations, barge, processor). If uncommented, this would **zero out any non-reef estimate**, effectively creating a reef-only local estimator. It was clearly intentional — it was just disabled, likely because the team wanted global positioning too.

---

### Stage 2: `Vision.java` — Velocity-Based Weight Scaling

Applied on top of the per-camera weight:

#### 2a. Linear Velocity

```
Speed (m/s) → Weight multiplier
0.0 → 1.0
2.5 → 0.8
5.0 → 0.1
```

Reduces vision trust significantly at high linear speeds. At max robot speed (~5 m/s) the weight drops to 10% of its baseline. **Rolling shutter concern is real** — this is appropriate, though a global shutter camera would make this unnecessary.

#### 2b. Angular Velocity

```
ω (rad/s) → Weight multiplier
0.0  → 1.0
7.0  → 0.65
12.0 → 0.0
```

Reduces trust at high spin rates. 12 rad/s ≈ 687 deg/s which is near the CTRE swerve limit. At 7 rad/s (~400 deg/s) trust is at 65%.

---

### Stage 3: `RobotContainer.correctOdometry()` — StdDev Assignment

```java
double thetaStddev = sample.weight() > 0.9 ? 10.0 : 99999.0;  // binary!
drivetrain.addVisionMeasurement(
    sample.pose(), sample.timestamp(),
    VecBuilder.fill(0.1 / sample.weight(), 0.1 / sample.weight(), thetaStddev));
```

**XY standard deviation:** `0.1 / weight` — inversely proportional. At weight=1.0 → stddev=0.1m. At weight=0.5 → stddev=0.2m. Reasonable, but 0.1m base might be tight.

**Theta standard deviation:** Hard binary at 0.9 threshold. Either full rotation trust (10.0 rad = essentially ignored) or minimal trust (99999 = completely ignored). **This is very abrupt** — there's no smooth transition. Everything below 0.9 gets its rotation completely ignored, which may cause the orbiting behavior described in the VisionTalk.

---

## NT Logging Gaps

Currently published to NetworkTables / SmartDashboard:

| Key | Type | Notes |
|-----|------|-------|
| `Camera1_EstimatedPose` | Pose2d | Raw estimate from camera 1 (only first 2 samples) |
| `Camera2_EstimatedPose` | Pose2d | Raw estimate from camera 2 |
| `VisionWeight` | double | Last weight computed — overwrites each camera |
| `/Vision/{name}/isConnected` | boolean | Per-camera connection status |
| `SeenTags` | Pose2d[] | Field poses of observed tags |
| `DriveState/Pose` | Pose2d | Fused odometry pose |

**Missing NT topics that would help debugging:**

- Per-camera raw stddevs (x, y, theta) being fed to the estimator
- Number of tags used per estimate
- Which specific tags were used
- Rejected estimate count per reason (jump rejection, zero trust)
- Distance to nearest tag
- Per-filter weight contributions (area, pixel offset, aspect ratio)
- Delta between raw vision pose and final odometry pose (the correction magnitude)

---

## Gap Analysis vs. VisionTalk Recommendations

| Recommendation | Status | Notes |
|----------------|--------|-------|
| Design top-down with clear goals | ⚠️ Partial | Two cameras tuned for forward coverage; no documented goals for global vs. local |
| Precise local positioning | ⚠️ Partial | `PidToPoseCommand` exists, but uses single global estimator — no dedicated local pipeline |
| Imprecise global positioning | ✅ Done | Single estimator serves both; global coverage is limited to 2 forward cameras |
| Reject poses outside field bounds | ❌ Missing | No boundary check; out-of-bounds estimates corrupt the estimator |
| Reject by reprojection error / ambiguity score | ⚠️ Partial | `LOWEST_AMBIGUITY` fallback helps, but no score threshold |
| Distance-based trust metric | ⚠️ Partial | Area is a proxy; `distanceSquared` would be more principled |
| Smooth theta trust scaling | ❌ Missing | Binary 0.9 threshold — should be a continuous function of weight |
| Multi-tag support | ✅ Done | `MULTI_TAG_PNP_ON_COPROCESSOR` |
| Latency compensation | ✅ Done | `Utils.fpgaToCurrentTime()` applied |
| Separate local and global pipelines | ❌ Missing | TAG_RANKINGS defined but commented out; single estimator used |
| Per-tag local pose estimates | ❌ Missing | Not implemented |
| Camera calibration | ✅ Done | Full 8-coefficient matrices per camera |
| Motion-based weight reduction | ✅ Done | Both linear and angular velocity |
| Field calibration procedure | ❓ Unknown | No documented procedure found |
| Onboard video recording | ❌ Missing | Not implemented |
| Global shutter cameras | ❓ Unknown | Camera models not specified in code |

---

## Summary: Strengths

1. **Full camera calibration** with 8-coefficient distortion models — this is better than many teams
2. **Multi-tag PnP** on coprocessor with ambiguity fallback
3. **Velocity jump rejection** catches wild outliers cleanly
4. **Multi-axis weighting** (area + pixel position + aspect ratio) is thoughtful
5. **Motion-based trust reduction** handles rolling shutter blur gracefully
6. **Latency-compensated** `addVisionMeasurement` calls
7. **TAG_RANKINGS infrastructure** already designed and waiting to be activated

## Summary: Gaps

1. **No field boundary rejection** — single most impactful missing filter
2. **Binary theta stddev** — causes sharp discontinuities in orientation trust
3. **TAG_RANKINGS disabled** — local vs. global distinction is fully designed but dormant
4. **No separate local estimator** — alignment commands fight with global tag noise
5. **Thin NT logging** — insufficient data to scientifically tune or debug the pipeline
6. **Only forward cameras** — no rearward or wide-angle global coverage
