# Beyond the Co-Processor: Lessons in FRC Vision and Localization

> **Speaker:** Jonah — Lead Software Mentor, FRC Team 6328 (Mechanical Advantage), CS/Math student at WPI  
> **Context:** Talk given at a robotics conference (likely WPI Symposium). Slides linked in the talk.  
> **Audience:** Teams with basic FRC vision experience looking to level up.

---

## Table of Contents

1. [Core Philosophy](#1-core-philosophy)
2. [Vision Goal Framework](#2-vision-goal-framework)
3. [Why NOT Precise Global Positioning](#3-why-not-precise-global-positioning)
4. [Camera Selection & Placement](#4-camera-selection--placement)
5. [Solver Algorithms](#5-solver-algorithms)
6. [Global Positioning Strategies](#6-global-positioning-strategies)
7. [Filtering & Pose Estimation](#7-filtering--pose-estimation)
8. [Fusing Local and Global Estimates](#8-fusing-local-and-global-estimates)
9. [Quick Tips](#9-quick-tips)
10. [Key Technologies & Resources](#10-key-technologies--resources)
11. [Season-by-Season Summary](#11-season-by-season-summary)

---

## 1. Core Philosophy

The most fundamental lesson from 6328's experience: **design vision systems top-down, not bottom-up.**

Most teams start by picking hardware, cameras, and filtering algorithms — then try to figure out what the system can do. The best vision systems start by asking:

> *"What is the purpose of vision on this robot? What are we trying to achieve?"*

Without clear goals, teams fall into two common traps:
- **Blackbox localization solutions** — using a vision pipeline without understanding what it's actually doing or what accuracy it delivers.
- **Chasing FPS** — optimizing frame rate or some other raw metric without knowing whether it meaningfully helps game performance.

---

## 2. Vision Goal Framework

After surveying years of competitive FRC, 6328 categorizes vision tasks into three buckets:

### 🎯 Precise Local Positioning *(Highest Priority)*

> Determining the **relative position** between the robot and a **specific field element**.

- Used for: auto-alignment to scoring targets (pick-and-place, shooting, placing)
- Required precision varies by game — could be sub-inch (coral reef 2025) or six inches (speaker 2024)
- Only two transforms are needed: **robot → vision target** and **vision target → scoring location**
- Both transforms are well-constrained and physically tied to a single object
- **This is the most impactful and universally applicable use of vision**

### 🗺️ Imprecise Global Positioning *(Secondary Priority)*

> Determining the robot's **position relative to multiple field objects** — doesn't require high accuracy.

- Used for: selecting the closest branch/target, zone-based behavior changes, long-range passing to partners
- Accuracy of a **few feet** is often sufficient
- More niche — many highly competitive teams skip this entirely
- Niche but powerful when implemented correctly

### 🎮 Game Piece Localization *(Tertiary / Situational)*

> Detecting and tracking **game pieces** on the field (notes, coral, etc.)

- Most different in requirements; often uses object detection (ML-based) rather than AprilTags
- Not always needed even when you'd expect it (2024: dynamic note selection in auto used odometry, not vision)
- Not covered in depth in this talk

---

## 3. Why NOT Precise Global Positioning

A natural question: if imprecise global positioning is good, wouldn't *precise* global positioning be even better?

**Two fundamental problems:**

#### Problem 1 — Limited Utility
- Almost all critical game objectives only need to know position *relative to a nearby field element*, not precise absolute field position
- Global positioning is most useful in the middle of the field, where there are rarely scoring objectives

#### Problem 2 — The Coordinate System is a Lie

For **local positioning**, only two transforms exist:

```
Robot → Vision Target → Scoring Location
```

Both are well-defined and physically constrained to a single object.

For **global positioning**, every pose is represented in a shared field coordinate system:

```
Origin → AprilTag A → Origin → Branch → Origin → Robot
```

This only works if **every field element is in perfect alignment** with every other — which is never true. Fields deviate from drawings during fabrication. Robots running into elements shift them further. Even with sub-quarter-inch manufacturing tolerances claimed in the manual, the real-world compound errors make a precise shared coordinate system fundamentally unreliable.

> **Key insight:** This isn't a technology limitation — no fancy calibration or VR tracking system solves it. The FRC field just can't be precisely modeled by a fixed coordinate system.

**Imprecise global positioning is still absolutely worth doing** — you don't need a precise field model to pick the closest target or change robot behavior by field zone.

---

## 4. Camera Selection & Placement

Camera placement is one of the most game-dependent decisions in vision system design. Think from the top down: *"What do I need to see, and from where?"*

### ✅ Dos

| Guideline | Reasoning |
|-----------|-----------|
| Point cameras toward **relevant vision targets** | Don't optimize for maximum FOV — optimize for visibility of specific elements from your robot's typical positions |
| Choose a **well-defined, rigid mounting location** | Lower on the robot → better matches CAD model → better pose accuracy |
| Use **multiple cameras** for different scenarios | Combining functionality often requires compromise; extra cameras are usually easier |
| Use a **variety of camera types** | Mix FOV, monochrome vs. color, based on task requirements |
| Print mounts from **TPU (flexible filament)** | Rigid mounts crack on impact; flexible mounts absorb hits — 6328 switched to TPU and virtually eliminated cracked mounts |
| **Design for maintenance access** | You'll need to remove, calibrate, and debug cameras after initial install |

### ❌ Don'ts

| Anti-Pattern | Problem |
|---|---|
| Maximizing field of view on individual cameras | Wide cameras have poor pose accuracy (>100°); use multiple narrower cameras instead |
| Mounting on **moving parts** | Compensating for kinematic transforms is very difficult and error-prone |
| Over-rigid mounts | Will crack on collision; TPU is preferred |
| Treating maintenance as an afterthought | Post-installation calibration, debugging, and adjustments are inevitable |

### 2025 Example — "Manta" (Team 6328)

- **Front:** Two cameras angled *inward* for overlapping near-field FOV when aligning to the reef. Spread wide enough to also cover distant tags.
- **Back (hopper config):** Angled up, aimed at human player station tag.
- **Back (ground intake config):** Angled down, switched to **color camera** for game piece localization.

> Use robot CAD to virtually place the robot at key field positions and verify all camera FOVs before fabrication.

---

## 5. Solver Algorithms

Four classes of algorithms are used in FRC to determine robot position from vision data. All four remain valid; choosing depends on the use case.

### 1. Servoing *(Simplest)*

> Rotate the robot until the target is centered in the camera frame.

- **Pros:** Few points of failure, easy to implement, sufficient for many use cases
- **Cons:**
  - Requires high frame rate or additional motion compensation logic
  - Camera must be aligned with the scoring mechanism
  - **Cannot operate in multiple axes** — can't control translation or approach angle

---

### 2. Trig-Based Solvers

> Calculate the **distance to the target** using the vertical angle of the target in frame, then compute a full 2D pose using gyro heading.

- **Pros:** Full pose calculation (X, Y, θ), more control than servoing
- **Cons:**
  - Requires a **height difference** between camera and target
  - Depends on an **accurate gyro** — susceptible to drift, especially after hard impacts
  - Cannot be used for 2023/2025-style games where AprilTags are near robot height

---

### 3. 3D Solvers (solvePnP) *(Most Common for AprilTags)*

> Compute the **3D transform** from the camera to the target directly from image geometry, with no gyro dependency.

- **Algorithm:** `solvePnP` from [OpenCV](https://docs.opencv.org/4.x/d5/d1f/calib3d_solvePnP.html) — solves the [Perspective-n-Point](https://en.wikipedia.org/wiki/Perspective-n-Point) problem
- **Pros:**
  - No gyro required — rotation solved directly from the image
  - No height difference required — works with tags at robot level
  - Multi-tag support dramatically reduces error
- **Cons:**
  - Noisier than trig solvers (higher variance, lower bias)
  - **Single-tag ambiguity** — two valid pose solutions exist when only one tag is visible

> **Tag Ambiguity:** When only one AprilTag is visible, `solvePnP` may produce two geometrically valid solutions. This can be resolved by comparing reprojection errors or validating against gyro estimate. Note: Limelight does not provide enough raw data to resolve this properly.

---

### 4. Combined Gyro + 3D Solver *(Increasingly Popular)*

> Use the **stable gyro signal** to stabilize and correct the noisier 3D solver output.

- Reduces jitter significantly vs. pure 3D solver
- **Still requires accurate gyro** — errors compound if gyro drifts
- **Sensitive to mounting accuracy** — especially when tracking distant tags
- **Latency-sensitive** — compensating for the delay between image capture and result delivery on the RIO is critical; even 20ms offset causes significant error at speed

---

### Solver Comparison

| Solver | Gyro Required | Height Diff Required | Noise | Bias | Multi-Axis | Best For |
|--------|:---:|:---:|:---:|:---:|:---:|---|
| Servoing | ❌ | ❌ | Low | Low | ❌ | Simple 1-axis alignment |
| Trig-Based | ✅ | ✅ | Low | Higher at range | ✅ | Mid-height targets, stable gyro |
| 3D (solvePnP) | ❌ | ❌ | Higher | Low | ✅ | AprilTag local + global |
| Gyro + 3D | ✅ | ❌ | Low | Medium | ✅ | Smooth local positioning |

> **6328 uses:** Combined Gyro + 3D for **local positioning** and pure 3D for **global positioning** (to avoid relying on gyro accuracy over the full match).

---

## 6. Global Positioning Strategies

### Maximizing Field of View (Across All Cameras)

For global positioning, you want to see *some* AprilTag in every robot orientation. 6328 built a **custom visibility analysis tool** that:

1. Plots a representative auto/teleop robot path on the field
2. Analyzes tag visibility from all robot-relative angles throughout that path
3. Produces a **heat map** showing which directions have the highest tag visibility

Key finding: for most FRC games, tags are **fairly evenly distributed** around the robot across a typical match. This supports a strategy of maximizing **total omnidirectional field of view** rather than biasing cameras toward one direction.

### Camera FOV Limit (~100°)

> **Do not use cameras wider than ~100° per camera.**

The standard "fisheye" camera model breaks down above 100°. Pose accuracy degrades significantly. Use **multiple cameras** at 90–100° each instead of one ultra-wide camera.

### Solver Choices for Global

| Solver | Suitable for Global? | Notes |
|--------|:---:|---|
| Servoing | ❌ | No full pose |
| Trig-Based | ⚠️ | Requires height diff; increasingly uncommon |
| 3D (solvePnP) | ✅ | Preferred — doesn't depend on gyro accuracy over full match |
| Gyro + 3D | ✅ | Great option if gyro can be trusted |

---

## 7. Filtering & Pose Estimation

> "You should be suspicious of anyone saying that filtering is unnecessary or an afterthought."

All pose solvers have noise. Global positioning involves multiple cameras, tags at varying distances, and multiple error types. Filtering is **mandatory** — not optional.

### Filtering Pipeline (6328 Approach)

#### Step 1 — Resolve Tag Ambiguity
- Compare reprojection errors for the two candidate poses
- Validate against current gyro estimate
- Only update rotation estimate from vision if it was based on **unambiguous** detections

#### Step 2 — Reject Invalid Estimates
- Check that Z-coordinate (height) is physically plausible
- Confirm estimated pose is within field boundaries
- Reject estimates from tags that are too far or too small

#### Step 3 — Assign a Trust Metric (Standard Deviation)
Calculate a per-estimate confidence score. Inputs include:
- **Distance to tags** (squared distance in 6328's implementation)
- **Number of tags** in the frame (more = more trustworthy)
- **Camera type** (zoomed cameras → larger tags in frame → lower noise)

> Think of this as a "generic tuning metric" — exact units don't matter as much as relative tuning via trial and error.

#### Step 4 — Fuse All Estimates
- Feed all per-camera estimates with their trust metrics into [WPILib's Pose Estimator](https://docs.wpilib.org/en/stable/docs/software/advanced-controls/state-space/state-space-pose-estimators.html)
- The estimator (based on a Kalman filter) fuses vision poses with odometry/gyro data
- Output: a single clean, latency-compensated pose for use in auto-alignment or control logic

#### ⚠️ Orbiting Artifact
When gyro offsets conflict with vision measurements, WPILib's estimator can produce an "orbiting" robot visualization. This is a known quirk — workarounds exist if needed.

---

## 8. Fusing Local and Global Estimates

### Implicit Separation (2023–2024)
For most of these years, 6328 used **one pose estimator** that implicitly prioritized the right tags. When aligned to the speaker, nearby speaker tags were **large and numerous in frame** → the trust metric naturally up-weighted them without any special logic. The estimator "shapeshifted" between global and local positioning on its own.

### Explicit Separation (2025)
For Reefscape's precise coral placement, 6328 moved to **separate pipelines** for local and global:

- Different solver settings, tuned independently
- Different latency/smoothness tradeoffs
- **A separate local pose estimate for every individual AprilTag**
  - Auto-align picked not just the *closest* tag but the tag *correct for the specific branch* to score on
  - Zero interference from unrelated tags — they were never incorporated into that estimate

---

## 9. Quick Tips

### 📷 Camera Parameters

| Parameter | Effect | Recommendation |
|---|---|---|
| Resolution | Higher → better pose accuracy, lower FPS | Bias toward more resolution over more FPS |
| Downscaling | Improves FPS, hurts accuracy & range | Avoid unless on very low-power hardware |
| Exposure / Gain (Brightness) | Higher → more brightness but more motion blur | Keep as low as possible while still seeing needed tags |
| Frame Rate | Higher → more stable servo-based alignment | Balance with resolution |

---

### 🔭 Global Shutter vs. Rolling Shutter

| | Rolling Shutter | Global Shutter |
|---|---|---|
| How it works | Scans top-to-bottom | Entire sensor exposed simultaneously |
| Motion artifact | Blur and distortion at speed | Clean image even while spinning |
| Cost | Cheaper | More expensive |
| FRC use | Adequate for slow robots | **Strongly preferred** for fast robots |

> A global shutter camera can produce clean, trackable AprilTag images from a robot spinning at full speed. A rolling shutter cannot.

---

### 📡 MJPEG Compression (USB 2 Cameras)

USB 2 cameras must compress images (MJPEG) to fit within bandwidth limits. Compression artifacts around AprilTag edges introduce noise in pose estimates.

> **Observed impact:** MJPEG compression can increase pose estimate noise by **40% or more.**

**Solutions:**
- Use a **MIPI-connected camera** on a Raspberry Pi (e.g., Limelight uses this internally)
- Use a **USB 3 camera** — much higher bandwidth, no forced compression

---

### 📐 Camera Calibration

Always calibrate every camera individually, even if they are identical models. Consumer cameras are built to loose tolerances and will have measurably different intrinsic parameters.

**Calibration target:** [ChArUco board](https://docs.opencv.org/4.x/df/d4a/tutorial_charuco_detection.html) (or similar), supported by all major FRC vision platforms.

> 6328 once mixed up calibration files between four identical cameras and could tell which was which purely by the quality of pose estimates.

---

### 🔎 Focus

Focus cameras at an appropriate distance and **lock the lens** per manufacturer guidance. Consider biasing focus slightly farther than your minimum detection distance — closer tags are large enough to detect even slightly blurred, but distant tags are more sensitive to focus.

---

### ⏱️ Latency Compensation

Between image capture and pose arriving at the RoboRIO, latency can exceed **200 ms** at low frame rates. Naively integrating delayed poses while the robot is moving will drag the estimate significantly away from truth.

- WPILib's pose estimator supports **timestamped vision measurements** — use this
- Even a **single-frame error (20 ms)** caused significant auto accuracy problems for 6328 at their first 2024 event

---

### 🏟️ Field Calibration Time

A robust vision system is designed to tolerate normal field variation. Field calibration should be quick:

1. **Check for major field errors** — swapped or misplaced AprilTags (6328 has caught this at events)
2. **Adjust camera brightness** — competition venue lighting may differ from your shop; verify you can see needed tags from common positions

> Don't waste field cal trying to measure every element location. That's a sign of a system that isn't properly tolerant of field variation.

---

### 🎥 Onboard Video Recording

Recording camera feeds during matches allows rapid post-match debugging:

- Was a missed detection caused by a shadow? Bad exposure? A physically damaged tag?
- 6328 found a gashed AprilTag at CHAMPS by reviewing footage — fixed within 5 minutes
- Tools: dashboard screen recording, PhotonVision snapshot mode, or custom on-robot recording
- Compared to the value it provides, this is dramatically underused in FRC

---

## 10. Key Technologies & Resources

### AprilTags

**What they are:** Square fiducial markers with a unique binary pattern, designed for robust detection and 6DOF pose estimation from a single camera.

- Introduced to FRC in **2023**
- Enable full 3D pose calculation without other sensors
- Field AprilTag positions are known and published in the game manual
- Multi-tag detection greatly reduces pose noise and eliminates ambiguity

📎 [WPILib AprilTag Docs](https://docs.wpilib.org/en/stable/docs/software/vision-processing/apriltag/apriltag-intro.html)

---

### OpenCV `solvePnP`

**What it is:** A function in the OpenCV computer vision library that solves the **Perspective-n-Point (PnP)** problem — computing the 3D rotation and translation of a camera relative to known world points given their 2D image projections.

- Takes 3D object points + 2D image points + camera intrinsic matrix → outputs rotation vector + translation vector
- Multiple algorithm variants (P3P, EPnP, SQPNP, etc.)
- **Used by PhotonVision, Limelight, and custom pipelines** under the hood

📎 [OpenCV solvePnP Docs](https://docs.opencv.org/4.x/d5/d1f/calib3d_solvePnP.html)

---

### WPILib Pose Estimators

**What they are:** Built-in FRC classes (`SwerveDrivePoseEstimator`, `DifferentialDrivePoseEstimator`, `MecanumDrivePoseEstimator`) that fuse odometry (encoder + gyro) with vision measurements using a Kalman-filter-based approach.

- Accept **timestamped vision measurements** for proper latency compensation
- Tunable via standard deviations for model trust vs. vision trust
- Output a single best-estimate field pose used by the rest of the robot code

📎 [WPILib Pose Estimator Docs](https://docs.wpilib.org/en/stable/docs/software/advanced-controls/state-space/state-space-pose-estimators.html)

---

### AdvantageKit

**What it is:** An open-source **logging, telemetry, and replay framework** developed by Team 6328. Allows the complete state of robot code to be replayed in simulation from a real log file.

- Enables development and tuning of filtering pipelines using **real field data** without needing a robot
- Companion tool **AdvantageScope** provides 2D/3D field visualizations, graph views, swerve module displays, and synchronized video
- Described in the talk as transformative: *"We were left asking ourselves how we ever got by without this tool."*

📎 [AdvantageKit Docs](https://docs.advantagekit.org/)  
📎 [AdvantageKit GitHub](https://github.com/Mechanical-Advantage/AdvantageKit)

---

### PhotonVision

**What it is:** Open-source FRC vision software that runs on a co-processor (Raspberry Pi, Orange Pi, or Limelight hardware). Handles AprilTag detection, camera calibration, pose estimation, and object detection.

- Free, community-supported
- Provides snapshot capture for match review
- Integrates with WPILib's pose estimator via a Java/C++ client library
- Can run on custom hardware (any Pi-class SBC) or Limelight hardware with PhotonVision firmware

📎 [PhotonVision Docs](https://docs.photonvision.org)

---

### Limelight

**What it is:** A commercial all-in-one FRC vision co-processor (camera + compute + software) from Limelight Robotics.

- Proprietary software with a web dashboard UI; plug-and-play for teams
- Hardware uses MIPI camera (no USB compression)
- **Known limitation noted in talk:** Does not expose enough raw data to resolve single-tag pose ambiguity properly
- **Latency challenge:** The Gyro+3D solver runs on the co-processor rather than the RIO, adding pipeline latency that must be carefully compensated

📎 [Limelight Docs](https://docs.limelightvision.io)

---

### Odometry

**What it is:** Estimating robot position using wheel encoder readings + gyroscope heading, without any external sensing.

- Accumulates error over time (especially during impacts that disturb the gyro)
- Vision measurements are used to **correct** odometry drift
- The talk's gyro+3D solver actually uses global 3D vision estimates to **recalibrate the gyro estimate** over the match, improving local estimate quality

---

### Coordinate Frames & Transforms

**What they are:** Mathematical representations of positions and orientations in space. A **transform** describes how to go from one coordinate frame to another.

- **Local positioning** uses: `Robot → Tag` and `Tag → Target` (both physically constrained)
- **Global positioning** uses: `Origin → Tag` and `Origin → Robot` (assumes a perfect shared field coordinate system)
- The **field coordinate system** (origin at field corner, X/Y/angle) is the standard in FRC — but is only as accurate as the physical field matches the drawings

---

### Camera Calibration (Intrinsics)

**What it is:** The process of measuring a camera's intrinsic parameters — focal length, principal point, and lens distortion coefficients. Required for accurate pose estimation.

- Performed by waving a known pattern (ChArUco or checkerboard) in front of the camera
- Each physical camera must be calibrated individually, even if nominally identical
- Supported by all major FRC vision platforms

---

## 11. Season-by-Season Summary

| Year | Game | Key Vision Uses |
|------|------|-----------------|
| 2023 | Charged Up | Auto-align to nodes & substations; odometry reset over cable bump at speed |
| 2024 | Crescendo | Accurate speaker scoring; field-position-relative passing; dynamic note selection in auto (odometry only, no vision) |
| 2025 | Reefscape | Precise coral branch alignment; automated branch selection; dynamic coral ground pickup; explicit local/global pose separation |

---

## Summary

The two universal goals that define elite FRC vision systems:

> 1. ✅ **Precise Local Positioning** — Reliable relative pose to the nearest scoring target  
> 2. ✅ **Imprecise Global Positioning** — Approximate field-wide awareness for dynamic decision-making

All other complexity — solvers, filtering, camera placement, calibration — exists in service of these two goals. The teams that achieve them most consistently are those who define these goals *first*, then design their hardware and software to serve them.
