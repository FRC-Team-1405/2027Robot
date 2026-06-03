# 2027 Vision System — Improvement Plan

> Based on: [2026 code analysis](./vision-analysis-2026.md) + [VisionTalk Summary](../VisionTalk_Summary.md)  
> Stack: PhotonVision + WPILib `SwerveDrivePoseEstimator`

---

## Priority Tier Summary

| Priority | Change | Effort | Impact |
|----------|--------|--------|--------|
| 🔴 P1 | Add field boundary rejection | Low | High |
| 🔴 P1 | Fix binary theta stddev → smooth curve | Low | High |
| 🟠 P2 | Expand NT logging for filter visibility | Low | High (for tuning) |
| 🟠 P2 | Activate TAG_RANKINGS with a dedicated local estimator | Medium | Medium-High |
| 🟠 P2 | Replace area-weight with distance-based stddev | Medium | Medium |
| 🟡 P3 | Add ambiguity score threshold | Low | Medium |
| 🟡 P3 | Add back camera for global FOV coverage | High | Medium |
| 🟡 P3 | Onboard video recording | Low | Medium (debugging) |

---

## P1 — Field Boundary Rejection

### Problem
The current pipeline has no check for whether an estimated pose is physically plausible. A single bad detection (damaged tag, shadow, another robot occluding) can produce a pose wildly outside the field, which then corrupts the Kalman filter state.

### Fix
In `Camera.java`, inside `update()`, after computing `pose`:

```java
// Reject estimates outside field boundaries (with small margin)
double fieldLength = AprilTags.getAprilTagFieldLayout().getFieldLength();
double fieldWidth  = AprilTags.getAprilTagFieldLayout().getFieldWidth();
double margin = 0.5; // meters of buffer
if (pose.getX() < -margin || pose.getX() > fieldLength + margin ||
    pose.getY() < -margin || pose.getY() > fieldWidth  + margin) {
    return Optional.empty(); // out of bounds — reject
}
```

Also consider a Z-height check on the 3D estimate before projecting to 2D:
```java
double estimatedZ = estRoboPose.estimatedPose.getZ();
if (Math.abs(estimatedZ) > 0.75) { // robot center shouldn't be >0.75m off the floor
    return Optional.empty();
}
```

**Log the rejection:**
```java
SmartDashboard.putNumber("/Vision/" + getName() + "/RejectedBoundary", ++boundaryRejectCount);
```

---

## P1 — Smooth Theta StdDev Curve

### Problem
The current rotation trust is binary:

```java
double thetaStddev = sample.weight() > 0.9 ? 10.0 : 99999.0;
```

This causes a sharp discontinuity at weight=0.9. Estimates just below 0.9 get *no* rotation correction at all, even if they are nearly perfect. This can cause the "orbiting" artifact described in the VisionTalk.

### Fix
Replace with a continuous mapping via `LerpTable` (already in the codebase):

```java
// In VisionConstants.java
public static final LerpTable THETA_STDDEV_WEIGHT_COEFFICIENT = new LerpTable(
    new LerpTable.LerpTableEntry(0.0,  99999.0),  // full reject
    new LerpTable.LerpTableEntry(0.4,  100.0),    // very low trust
    new LerpTable.LerpTableEntry(0.7,  20.0),     // partial trust
    new LerpTable.LerpTableEntry(0.85, 10.0),     // moderate trust
    new LerpTable.LerpTableEntry(1.0,  2.0));     // near-full trust
```

```java
// In RobotContainer.correctOdometry()
double thetaStddev = Filtering.THETA_STDDEV_WEIGHT_COEFFICIENT.lerp(sample.weight());
drivetrain.addVisionMeasurement(
    sample.pose(), sample.timestamp(),
    VecBuilder.fill(0.1 / sample.weight(), 0.1 / sample.weight(), thetaStddev));
```

**Tune the curve using log replay** — see the [testing protocol](./vision-testing-protocol.md).

---

## P2 — NT Logging Expansion

### Problem
The current pipeline publishes only coarse per-camera poses and a single `VisionWeight` scalar. There's no visibility into which filters fired, how much each contributed, or how far vision is correcting odometry. This makes scientific tuning nearly impossible.

### Recommended Additions

Add to `Camera.java` (per camera, keyed by `getName()`):

```java
// Per-frame, per-camera
SmartDashboard.putNumber("/Vision/" + getName() + "/TagCount",      estRoboPose.targetsUsed.size());
SmartDashboard.putNumber("/Vision/" + getName() + "/TagArea",       sumArea);
SmartDashboard.putNumber("/Vision/" + getName() + "/PixelOffset",   avgNormalizedPixelsFromCenter);
SmartDashboard.putNumber("/Vision/" + getName() + "/AspectRatio",   avgDimensionProportion);
SmartDashboard.putNumber("/Vision/" + getName() + "/TrustPre",      trustScalar);   // before lerp multipliers
SmartDashboard.putNumber("/Vision/" + getName() + "/TrustPost",     trust);          // after all multipliers
SmartDashboard.putNumber("/Vision/" + getName() + "/RejectJump",    jumpRejectCount);
SmartDashboard.putNumber("/Vision/" + getName() + "/RejectBounds",  boundaryRejectCount);
```

Add to `Vision.java`:
```java
SmartDashboard.putNumber("/Vision/LinearVelocityWeight", Filtering.LINEAR_VELOCITY_WEIGHT_COEFFICIENT.lerp(linearSpeed));
SmartDashboard.putNumber("/Vision/AngularVelocityWeight", Filtering.ANGULAR_VELOCITY_WEIGHT_COEFFICIENT.lerp(Math.abs(omega)));
```

Add to `RobotContainer.correctOdometry()`:
```java
// Per sample: log the pose delta between vision and current odometry
Pose2d current = drivetrain.getState().Pose;
double correctionMagnitude = sample.pose().getTranslation().getDistance(current.getTranslation());
SmartDashboard.putNumber("/Vision/CorrectionMagnitudeMeter", correctionMagnitude);
SmartDashboard.putNumber("/Vision/ThetaStddev", thetaStddev);
SmartDashboard.putNumber("/Vision/XYStddev", 0.1 / sample.weight());
```

These topics are all directly viewable in AdvantageScope as time-series graphs and can be correlated with robot behavior.

---

## P2 — Local/Global Estimator Separation

### Context and Importance

**Short answer: medium-high impact for alignment commands, low impact for general odometry.**

The current setup uses one `SwerveDrivePoseEstimator` for everything. Because area-based weighting already implicitly trusts nearby tags more, the estimator *naturally* shifts toward local positioning when close to a scoring target. This is the "implicit shapeshifting" described in the VisionTalk — and it does work.

However, there are two failure modes:
1. When a distant tag (coral station, barge) is simultaneously large in frame from a weird angle, it can pollute the estimate during alignment
2. The theta stddev issue above is worse for the global case — you don't want orientation drift from a distant tag to affect the alignment

**The TAG_RANKINGS map is already fully coded** and just needs to be split into two modes:

### Option A — Minimal (Uncomment + Separate Path)

Add a flag in `VisionConstants`:

```java
public enum EstimatorMode { GLOBAL, LOCAL_REEF }
```

When `PidToPoseCommand` starts, switch to `LOCAL_REEF` mode. The `correctOdometry()` loop uses different TAG_RANKINGS and tighter stddevs. When alignment ends, return to `GLOBAL`.

Estimated implementation time: ~2–3 hours.

### Option B — Full Per-Tag Local Estimator (Team 6328 Approach)

Maintain a separate `SwerveDrivePoseEstimator` per AprilTag or per scoring zone. Alignment commands query the estimator for the specific tag adjacent to their target. This eliminates all cross-tag interference.

Estimated implementation time: ~2–3 days. High value for games requiring precision placement (e.g., 2025 Reefscape).

**Recommendation:** Start with Option A. If the game requires sub-inch placement, upgrade to Option B.

### Why NOT to fully separate without a specific game need

If the 2027 game uses a shooting mechanic with ~6" tolerance (like 2024), the implicit approach already works well. The implicit approach + the P1 fixes above may be sufficient. Explicit separation adds code complexity — only justified if alignment accuracy issues are observed during testing.

---

## P2 — Distance-Based StdDev

### Problem
Area is a reasonable proxy for distance but is nonlinear and affected by tag orientation. A tag viewed at an angle has smaller apparent area despite the same distance. Distance in meters is a more principled and game-agnostic metric.

### Fix

In `Camera.java`, compute the average distance to tags used:

```java
double avgDistanceMeters = estRoboPose.targetsUsed.stream()
    .map(t -> t.getBestCameraToTarget().getTranslation().getNorm())
    .mapToDouble(Double::doubleValue)
    .average()
    .orElse(5.0);
```

Then use `distanceSquared` for stddev (matches 6328's approach):

```java
// In VisionConstants
public static final LerpTable DISTANCE_XY_STDDEV = new LerpTable(
    new LerpTable.LerpTableEntry(0.5,  0.05),   // very close: tight
    new LerpTable.LerpTableEntry(2.0,  0.15),
    new LerpTable.LerpTableEntry(4.0,  0.5),
    new LerpTable.LerpTableEntry(6.0,  1.5),    // far: loose
    new LerpTable.LerpTableEntry(8.0,  9999.0));// beyond range: reject
```

This cleanly replaces the `0.1 / sample.weight()` formula with something physically motivated. Both can coexist temporarily during A/B testing.

---

## P3 — Ambiguity Score Threshold

PhotonVision exposes a `getPoseAmbiguity()` score (0.0 = unambiguous, 1.0 = completely ambiguous) on single-tag estimates. The current code uses `LOWEST_AMBIGUITY` fallback but doesn't threshold the score.

### Fix

In `Camera.java`, before calling `update()`:

```java
// Only use single-tag estimates below an ambiguity threshold
if (estRoboPose.targetsUsed.size() == 1) {
    double ambiguity = estRoboPose.targetsUsed.get(0).getPoseAmbiguity();
    if (ambiguity > 0.2) {  // tune this threshold
        return; // skip this estimate
    }
}
```

This is especially important for games where tags are at robot height (Reefscape), where ambiguity is higher.

---

## P3 — Back Camera for Global Coverage

### Problem
Both cameras face forward. When the robot faces away from the reef, vision goes dark and odometry drifts. For games that require field-wide awareness (picking the correct scoring zone, passing, etc.), a rear camera significantly increases global uptime.

### Considerations
- A wide-angle (90°) USB3 rear camera (avoid MJPEG compression for accuracy) covers the posterior hemisphere
- Calibrate independently — don't share calibration files
- Use TPU mount to survive collisions
- Point it toward where your alliance's secondary scoring elements are

### Impact
Depends entirely on the 2027 game. If the game has targets on multiple sides of the field or requires field-wide positioning, this is **high priority**. If the game concentrates scoring near one end (like the reef), lower priority.

---

## P3 — Onboard Video Recording

### Problem
When a tag detection fails at a competition, there's no way to know why without video. Was it a shadow? Damaged tag? Exposure issue? Camera disconnect?

### Options

1. **PhotonVision snapshots** — enable in PhotonVision UI settings; triggers during match events
2. **Dashboard screen recording** — Operator station captures PhotonVision stream
3. **On-robot recording** — Pipe camera stream to file via CameraServer or PhotonVision recording mode (more complex, requires sufficient co-processor storage)

**Start with option 1 or 2** — they require zero code changes. Option 3 is ideal but more involved.

---

## Full Change Checklist (for 2027)

```
Phase 1 — Quick Wins (pre-season or early build):
[ ] Add field boundary + Z-height rejection in Camera.java
[ ] Add smooth theta stddev curve via LerpTable
[ ] Expand NT logging (per-filter weights, rejection counts, correction magnitude)
[ ] Add ambiguity score threshold for single-tag estimates
[ ] Enable PhotonVision snapshots for post-match review

Phase 2 — Pipeline Improvements (mid build):
[ ] Switch trust metric from area to distance-based stddev
[ ] Decide Option A or B for local/global separation based on 2027 game
[ ] Implement chosen separation strategy with game-appropriate tag sets

Phase 3 — Hardware (if needed):
[ ] Evaluate if 2027 game warrants rear camera for global coverage
[ ] Confirm cameras are global shutter (check model specs)
[ ] Confirm cameras use USB3 or MIPI (not USB2 MJPEG)
```
