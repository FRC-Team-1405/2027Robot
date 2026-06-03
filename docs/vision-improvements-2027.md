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
[ ] Purchase and configure new coprocessor/cameras per buying guide below
```

---

## Hardware Buying Guide

> **Current baseline:** Orange Pi 5 (RK3588S, 4 GB, 2× USB3, 1× GbE, no NVMe, no built-in WiFi)  
> See [`docs/robot_details/vision_specs.md`](./robot_details/vision_specs.md) for full current spec.

This guide covers recommended upgrades to the coprocessor and cameras based on the requirements
described in this document: running 2-3 simultaneous PhotonVision streams, USB3 cameras (no MJPEG),
global shutter, and sufficient USB bandwidth if a rear camera is added.

---

### The USB3 Port Problem

**No single Orange Pi with an official PhotonVision image has more than 2 USB3 ports.**
This is the central hardware constraint for any team wanting 3 cameras all on USB3.

Verified USB3 port counts (from official orangepi.org hardware pages):

| Board | USB3 ports | USB2 ports | PV Official Image |
|---|---|---|---|
| **OPi5** (current) | **2** | 1 | ✅ Yes |
| OPi5 Pro | **1** | 1 + 4 via hub chip | ✅ Yes |
| OPi5 Ultra | **2** | 2 | ⚠️ Not yet listed |
| OPi5 Plus | **2** | 2 | ⚠️ Not yet listed |
| Raspberry Pi 5 | **2** | 2 | ✅ Yes (no object detection) |

> **Correction from earlier version of this doc:** The OPi5 Pro has only **1× USB3**, not 4.
> It exposes additional USB2 ports via a hub chip on the PCB. Do not use the Pro if you need
> 2 USB3 cameras on one board.

**The current OPi5 (2× USB3) is already sufficient for a 2-camera forward setup.**
There is no single supported board that adds more USB3 ports over what you already have.

---

### Coprocessor Upgrade

All Orange Pi 5-series boards share the **same RK3588(S) CPU and 6 TOPS NPU** — AprilTag
detection performance is identical across all variants. PhotonVision pins its service to the
four big Cortex-A76 cores equally on every model. The meaningful upgrade differences are
NVMe boot support, ethernet speed, and built-in WiFi.

#### Orange Pi 5-Series Comparison

| Feature | **OPi5** (current) | OPi5 Pro | **OPi5 Ultra** ⭐ | OPi5 Plus |
|---|---|---|---|---|
| Chip | RK3588S | RK3588S2 | RK3588 (full) | RK3588 (full) |
| NPU | 6 TOPS | 6 TOPS | 6 TOPS | 6 TOPS |
| RAM | 4/8/16 GB | 4/8/16 GB | 4/8/16 GB | 4/8/16 GB |
| **USB3 ports** | **2** | **1** | **2** | **2** |
| USB2 ports | 1 | 1 + 4 hub | 2 | 2 |
| Ethernet | 1× 1 GbE | 1× 1 GbE | 1× **2.5 GbE** | 2× **2.5 GbE** |
| M.2 NVMe | ❌ | ✅ 2280 PCIe 3.0 | ✅ 2280 PCIe 3.0 | ✅ 2280 PCIe 3.0 |
| Built-in WiFi | ❌ | WiFi 5 + BT 5.0 | **WiFi 6E + BT 5.3** | ❌ (M.2 module) |
| eMMC socket | ❌ | ✅ | ✅ | ✅ |
| PV official image | ✅ | ✅ | ⚠️ Not in stable docs | ⚠️ Not in stable docs |
| Est. price (8 GB) | ~$55 | ~$65 | ~$80-95 | ~$85-110 |

> OPi5 Ultra and OPi5 Plus specs sourced directly from
> [orangepi.org hardware pages](http://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/).
> PhotonVision image support status as of June 2026 - verify at
> [docs.photonvision.org](https://docs.photonvision.org) before purchasing.

#### Recommendation: Orange Pi 5 Ultra (8 GB) — if upgrading

For a **single-board 2-camera setup**, the **Orange Pi 5 Ultra** is the best upgrade:

- **2× USB3** — same count as current OPi5, no regression
- **2.5 GbE** — faster network link to the robot switch; eliminates coprocessor as a bottleneck
  during tuning when streaming debug video
- **M.2 NVMe** — boot from SSD instead of SD card. SD cards are the most common cause of
  filesystem corruption after robot collisions. A 64 GB M.2 NVMe (~$15) dramatically
  improves boot time and reliability
- **WiFi 6E + BT 5.3 built-in** — no M.2 WiFi module needed, frees slot for NVMe

**Avoid the OPi5 Pro for a camera setup** — it has only 1× USB3, which is fewer than the
board you already own.

**What does NOT improve with any upgrade:**
- AprilTag detection latency (identical big-core CPU and NPU performance across all models)
- Pose estimation accuracy (software, not hardware)

#### If You Want a Third Camera (Rear Coverage)

There is no single Orange Pi with 3 USB3 ports and an official PhotonVision image.
The options are:

**Option 1 - Two coprocessors (recommended):**
Run one OPi5 (or OPi5 Ultra) per 1-2 cameras. Each board gets its own IP address on
the robot network and publishes to NetworkTables independently. The roboRIO subscribes
to both. This is the approach used by top teams (e.g., 6328 Mechanical Advantage runs
a separate process instance per camera). Advantages: full USB3 bandwidth per camera,
no single point of failure, independent reboots.

> **Wiring note:** Assign static IPs (e.g., `10.14.5.11` and `10.14.5.12`). Configure
> each PV instance with a unique hostname. The robot code subscribes to both via their
> respective NetworkTables server addresses.

**Option 2 - OPi5 Plus or OPi5 Ultra + one USB2 camera for rear:**
If the rear camera is purely for global coverage (not precision alignment), USB2 is
acceptable — global-coverage tags are typically larger and closer to the field boundary,
where USB2 bandwidth (~60 MB/s) is not the bottleneck. Use one OV9281 on USB3 per
forward camera and a second OV9281 on USB2 for the rear. Single-board, simpler wiring.

**Option 3 - USB3 hub (not recommended):**
A USB3 hub still shares the same root-complex bus bandwidth on RK3588 platforms. Under
heavy camera load this causes frame drops and variable latency. The PhotonVision
documentation does not recommend USB hubs for multi-camera setups. Avoid this.

**Where to buy:**
- [AliExpress (official Orange Pi store)](https://www.aliexpress.com/store/1101239862) —
  cheapest; allow 3-4 weeks shipping
- [Amazon](https://www.amazon.com/s?k=orange+pi+5+ultra) — faster; typically $10-20 more

**Accessories to order with the coprocessor:**
- M.2 2280 NVMe SSD (any brand, 64-128 GB; e.g., Kingston NV3 ~$15)
- SanDisk Industrial SD card (SDSDQAF3-016G-I, ~$12) — fallback boot device
- USB-C 5V/5A power supply (Ultra requires 5A; verify bundle contents before ordering)
- Short right-angle USB-A cables for cameras (reduce connector stress)

---

### Camera Upgrade

The current cameras' shutter type should be confirmed before ordering replacements — see the
checklist item above. Global shutter is **required** to eliminate rolling-shutter skew while
the robot is moving; a rolling-shutter camera at 60 fps moving at 4 m/s produces ~1.5 cm of
horizontal smear per tag corner, which degrades PnP accuracy measurably.

PhotonVision recommends cameras in **UVC mode** (plug-and-play, no driver needed). Avoid
Arducam Pivariety cameras — they require a proprietary library and are incompatible with
PhotonVision.

#### Camera Comparison

| Camera | Sensor | Shutter | Interface | Resolution | FPS | Color | Price |
|---|---|---|---|---|---|---|---|
| **Arducam OV9281** ⭐ | OmniVision OV9281 | **Global** | USB2 UVC | 1280×800 (1 MP) | 60+ fps | Mono | **~$32** |
| Arducam OV9782 | OmniVision OV9782 | **Global** | USB2 UVC | 1280×800 (1 MP) | 60 fps | Color | ~$40 |
| Arducam AR0234 | onsemi AR0234CS | **Global** | **USB3 UVC** | 1920×1200 (2.3 MP) | 60 fps | Color/Mono | ~$65 |

#### Primary Recommendation: Arducam OV9281 (~$32 each)

The **Arducam OV9281** is PhotonVision's #1 recommended camera for AprilTag detection and is
the most battle-tested camera in FRC:

- **Global shutter** — no smear artifact during robot motion
- **Monochrome sensor** — AprilTag detection does not use color; mono has higher sensitivity
  and better signal-to-noise ratio in low-light conditions (common in competition venues)
- **UVC plug-and-play** — detected automatically by PhotonVision, no configuration needed
- **60+ fps** — important for high-update-rate pose estimation; use PhotonVision's camera
  settings to set resolution and exposure rather than relying on defaults
- **~$32 on Amazon** (ASIN: B0972KK7BC) — cost-effective for a 2- or 3-camera setup

**Important:** When running two identical OV9281s, use the
[Arducam Serial Number Tool](https://docs.arducam.com/UVC-Camera/Serial-Number-Tool-Guide/)
to assign unique device names. Without this, PhotonVision may swap camera identities between
reboots when USB enumeration order changes, silently flipping left/right camera transforms.

**Lens selection:**  
The standard M12 lens shipped with the OV9281 gives ~65° diagonal FOV. For AprilTag detection,
PhotonVision recommends **~100° diagonal FOV** to maximize the field of view for detecting tags
at angles and during rotation. Order the Arducam wide-angle lens kit separately, or search for
"M12 100 degree lens" — most M12 lenses are interchangeable.

#### When to Consider AR0234 Instead

The **Arducam AR0234** (2.3 MP, USB3) offers nearly 3× the pixel count of the OV9281. More
pixels means:
- Tags detected reliably at greater distance (more pixels subtend the tag at range)
- Better multi-tag PnP accuracy (more corner resolution)
- Higher data throughput — requires USB3; the OPi5 Ultra's 2× USB3 handles this well

Trade-offs:
- ~2× the price (~$65)
- Color sensor (slightly lower sensitivity than mono in low light)
- USB3 required — verify your coprocessor's USB3 port count

**Verdict:** Start with OV9281 unless you identify detection range as a specific weakness after
testing with the [testing protocol](./vision-testing-protocol.md). The OV9281 is adequate for
most FRC scoring distances (1–6 m).

---

### Sample Configuration Costs

| Configuration | Coprocessor | Cameras | Est. Total |
|---|---|---|---|
| Keep current board, add wide-angle lenses | OPi5 (existing) | 2× OV9281 | ~$65 |
| **Recommended 2027 upgrade (2 cameras)** | OPi5 Ultra 8 GB + NVMe | 2× OV9281 | ~$185 |
| 3-camera (two boards, each runs 1-2 cameras) | 2× OPi5 Ultra 8 GB + 2× NVMe | 3× OV9281 | ~$400 |
| High-res (2 cameras, same board) | OPi5 Ultra 8 GB + NVMe | 2× AR0234 | ~$240 |

> Prices are estimates as of mid-2026. Check current listings before ordering.
> Budget an additional ~$30 for cables, mounts, and a lens kit.
