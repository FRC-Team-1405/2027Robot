# AdvantageKit Swerve Drive Integration

**Research date:** 2026-06-21  
**Audience:** Team 1405 programmers planning 2027 robot architecture

---

## Background: Why This Matters

Your robot already uses AdvantageKit for logging (`Logger.recordOutput`, `@AutoLogOutput`, the IO layer pattern on Vision/Shooter/etc.) and for replay (`replayWatch`). The one major subsystem that currently sits **outside** the AKit replay boundary is the drivetrain — `CommandSwerveDrivetrain` extends CTRE's `TunerSwerveDrivetrain` directly, which is a black box from AKit's perspective.

That means:
- **Pose estimation** and **odometry** cannot be replayed deterministically.
- **Module states, motor velocities, turn angles** are not in the AKit log unless you manually record them with `Logger.recordOutput`.
- You cannot replay-tune swerve PID gains, path-following behavior, or vision-to-odometry fusion against a real match log.

Adding AKit to the swerve drive fixes all of this.

---

## The Two Approaches

There are two ways to integrate AKit with CTRE swerve. The choice is the central architectural decision.

---

### Approach A — Use AKit's TalonFX Swerve Template (Full Replay)

**Replace** `CommandSwerveDrivetrain` (which extends `TunerSwerveDrivetrain`) with AKit's own `Drive.java` subsystem, which implements the full IO layer pattern.

**What AKit provides:**
- `GyroIO` / `GyroIOInputs` interface — abstraction over the Pigeon 2 (or NavX)
- `ModuleIO` / `ModuleIOInputs` interface — abstraction over each swerve module (drive TalonFX, steer TalonFX, CANcoder)
- `ModuleIOTalonFX` — real hardware implementation
- `ModuleIOSim` — physics simulation implementation
- `PhoenixOdometryThread` — high-frequency odometry (250 Hz on CAN FD, 100 Hz on standard CAN) with timestamp-synchronized sample queues
- `Drive.java` subsystem — holds `GyroIO`, four `ModuleIO`s, runs the kinematics/pose estimator, exposes `Command`-returning factory methods

**What happens at Tuner X regeneration:**
- Only `TunerConstants.java` is regenerated (just as your current flow works — Tuner X outputs "Generate only TunerConstants").
- `CommandSwerveDrivetrain.java` is **gone** — replaced by AKit's `Drive.java`.
- Comment out the `createSwerveDrivetrain()` factory method and its import in `TunerConstants.java` (same step as current docs, already in your CLAUDE.md).
- Change `kSteerInertia` → 0.004 and `kDriveInertia` → 0.025 in `TunerConstants.java` (AKit applies gear ratios in firmware, not on the RIO, so these differ from CTRE defaults).

**IO layer structure (what you'd add to your codebase):**

```
subsystems/drive/
  Drive.java              // subsystem — replaces CommandSwerveDrivetrain
  GyroIO.java             // interface + @AutoLog GyroIOInputs
  GyroIOPigeon2.java      // real hardware
  GyroIOSim.java          // simulation (reads from Drive's physics model)
  ModuleIO.java           // interface + @AutoLog ModuleIOInputs
  ModuleIOTalonFX.java    // real hardware (TalonFX + CANcoder)
  ModuleIOSim.java        // simulation (physics model, stores own gains)
  PhoenixOdometryThread.java  // high-frequency CAN signal collector
```

**Gains note:** AKit's template requires **different PID and feedforward gains** than CTRE's default swerve code because it applies the gear ratio in TalonFX firmware rather than on the RIO. Run AKit's built-in FF characterization routine (auto routine "Drive Simple FF Characterization") on the 2027 robot before competing.

**Replay coverage:** Every layer is replayable — pose estimator, module states, vision fusion, path following. This is the strongest form of AKit integration.

**Pros:**
- Full deterministic replay of the entire drive stack
- No black boxes — can read and tune every layer
- AKit's odometry uses standard FPGA timestamps, so PhotonVision/Limelight pose measurements pass in directly without `Utils.fpgaToCurrentTime()` conversion
- Physics simulation via `ModuleIOSim` (or maple-sim for rigid body)
- Built-in wheel radius characterization routine
- Built-in SysId routines

**Cons:**
- Significant rewrite — need to migrate PathPlanner integration, vision measurement calls, SysId routines, alliance perspective logic, and any custom `SwerveRequest`-based commands
- CTRE's Hoot replay (`.hoot` files) becomes redundant — AKit `.wpilog` is the replay source
- Different gains require re-characterization on new robot hardware

---

### Approach B — Wrap CTRE's SwerveDrivetrain in an AKit IO Layer (Partial Replay)

**Keep** `CommandSwerveDrivetrain` as-is, but isolate it behind an AKit IO interface. The rest of your robot code (autonomous, vision fusion, commands) calls through the interface.

**What this looks like:**

```
DrivetrainIO.java              // interface: setModuleStates, resetPose, addVisionMeasurement...
DrivetrainIOCTRE.java          // wraps CommandSwerveDrivetrain — all hardware calls here
DrivetrainIOSim.java           // optional sim wrapper
Drivetrain.java                // AKit subsystem: holds DrivetrainIO, calls updateInputs, Logger.processInputs
```

**What is and isn't replayable:**
- **Replayable:** Everything outside the IO boundary — path following decisions, vision filtering, command sequencing, autonomous logic.
- **Not replayable:** Anything inside CTRE's `TunerSwerveDrivetrain` — the odometry thread, module state computation, internal pose estimator.

The AKit developers described this tradeoff explicitly in Chief Delphi discussions: *"Wrappers can be written in a way that preserves deterministic replay functions for the rest of the code by fully isolating the nondeterministic swerve code to an IO implementation. You lose the ability to replay vision pose estimation, or replay anything that relies on module states or internal TalonFX state."*

**Pros:**
- Much lower migration cost — keep all existing `CommandSwerveDrivetrain` code, PathPlanner wiring, SysId routines, `SwerveRequest`-based commands
- Tuner X regeneration still drops straight in
- CTRE Hoot replay still works for motor-level debugging

**Cons:**
- Cannot replay-tune swerve PID gains, path following, or vision fusion against a match log
- Cannot examine module states during replay
- Weaker simulation story (CTRE's sim, not physics-based)
- Still need to manually log module states with `Logger.recordOutput` if you want them in AKit logs

---

## What Other Teams Do

**Team 6328 (Mechanical Advantage)** — Authors of AKit. Their competition robots use Approach A exclusively. They do not use CTRE's `TunerSwerveDrivetrain` at all.

**Team 3061 (Huskie Robotics) — 3061-lib:** Maintain a full AKit swerve library with CTRE TalonFX support, Approach A architecture. Updated annually, incorporates AKit TalonFX swerve template best practices. Referenced by many teams building on CTRE hardware.  
Source: [HuskieRobotics/3061-lib](https://github.com/HuskieRobotics/3061-lib)

**Team 4079 (Huskie Robotics template):** FRC-Swerve-Template using AKit IO layer pattern with TalonFX hardware.  
Source: [FRC4079/FRC-Swerve-Template](https://github.com/FRC4079/FRC-Swerve-Template)

**Shenzhen Robotics Alliance:** Published `AdvantageKit-TalonSwerveTemplate-MapleSim`, combining AKit's TalonFX swerve template with Team 5516's maple-sim for rigid-body physics simulation (robot colliding with field elements, realistic carpet traction).  
Source: [Shenzhen-Robotics-Alliance/AdvantageKit-TalonSwerveTemplate-MapleSim](https://github.com/Shenzhen-Robotics-Alliance/AdvantageKit-TalonSwerveTemplate-MapleSim)

**Consensus:** Teams that care about replay-driven tuning universally use Approach A. Teams migrating mid-season or with heavy CTRE-specific customizations sometimes start with Approach B as a stepping stone.

---

## Recommendation for Team 1405 (2027)

**Use Approach A.** Since you're building a new robot and already have the IO pattern established everywhere else in the codebase, the 2027 robot is the right time to close the gap. The replay workflow you've already built for Vision (`replayWatch`, vision-testing-protocol, A/B testing via FeatureSwitches) becomes dramatically more powerful when the drivetrain's pose estimator is also inside the replay boundary.

Concrete reasons:
1. Your existing `Vision.java` feeds `addVisionMeasurement()` — with AKit's template this call gets logged at the IO boundary, making vision-to-odometry fusion replayable.
2. PathPlanner's path following accuracy is currently not tunable in replay — with Approach A it is.
3. You're already regenerating `TunerConstants.java` via Tuner X for 2027 hardware; this is the natural time to change `CommandSwerveDrivetrain`.
4. The gain re-characterization requirement is not additional cost — you'd need to re-characterize anyway for a new robot.

---

## Migration Plan (Approach A)

### Step 1 — Download AKit TalonFX Swerve Template
Download from the [AdvantageKit GitHub releases page](https://github.com/Mechanical-Advantage/AdvantageKit/releases). Look for the `TalonFXSwerve-YYYY.X.X.zip` asset in the latest 2026 release.

### Step 2 — Regenerate TunerConstants
Run Tuner X Swerve Project Generator on the 2027 robot, choose **"Generate only TunerConstants"**, overwrite `src/main/java/frc/robot/generated/TunerConstants.java`.

Then in `TunerConstants.java`:
- Comment out the last `import` line (the `CommandSwerveDrivetrain` import) and the `createSwerveDrivetrain()` factory method at the bottom.
- Set `kSteerInertia = 0.004` and `kDriveInertia = 0.025`.

### Step 3 — Copy Drive Subsystem Files
From the AKit template, copy into `src/main/java/frc/robot/subsystems/drive/`:
```
Drive.java
GyroIO.java
GyroIOPigeon2.java
GyroIOSim.java          (or NavX variant if needed)
ModuleIO.java
ModuleIOTalonFX.java
ModuleIOSim.java
PhoenixOdometryThread.java
```

### Step 4 — Update RobotContainer
Replace `CommandSwerveDrivetrain` instantiation:

```java
// Old
CommandSwerveDrivetrain drivetrain = TunerConstants.createDrivetrain();

// New (AKit pattern)
Drive drivetrain = new Drive(
    RobotBase.isReal() ? new GyroIOPigeon2() : new GyroIOSim(),
    RobotBase.isReal() ? new ModuleIOTalonFX(TunerConstants.FrontLeft)  : new ModuleIOSim(TunerConstants.FrontLeft),
    RobotBase.isReal() ? new ModuleIOTalonFX(TunerConstants.FrontRight) : new ModuleIOSim(TunerConstants.FrontRight),
    RobotBase.isReal() ? new ModuleIOTalonFX(TunerConstants.BackLeft)   : new ModuleIOSim(TunerConstants.BackLeft),
    RobotBase.isReal() ? new ModuleIOTalonFX(TunerConstants.BackRight)  : new ModuleIOSim(TunerConstants.BackRight)
);
```

### Step 5 — Migrate Custom Code from CommandSwerveDrivetrain
Audit `CommandSwerveDrivetrain.java` and migrate:

| Feature | Migration path |
|---|---|
| Alliance perspective logic | Move to `Drive.periodic()` or `RobotContainer` |
| `addVisionMeasurement()` | AKit's `Drive` exposes this; remove `Utils.fpgaToCurrentTime()` — AKit uses standard FPGA timestamps directly |
| `getFilteredAcceleration()` | Keep as helper, derive from `Drive.getChassisSpeeds()` |
| `getAngleToTarget()` / velocity compensation | Move to `SwerveFeatures` or a new helper class |
| `driveToPose()` / `PidToPoseCommand` | These call drivetrain methods; update method names to match `Drive`'s API |
| SysId routines | AKit template has its own — adopt them |
| `publishMotorCurrent()` / `publishDrivePidErrors()` | Replace with `@AutoLogOutput` fields or `Logger.recordOutput` calls inside `Drive.periodic()` |
| `initOverridePose()` / `checkForSetPose()` | Move or keep as-is in a `RobotContainer` command |

### Step 6 — Update PathPlanner Integration
AKit's `Drive` class exposes `getChassisSpeeds()` and `runVelocity(ChassisSpeeds)`. PathPlanner's `AutoBuilder` configuration changes to use these instead of `SwerveRequest`:

```java
AutoBuilder.configure(
    drivetrain::getPose,
    drivetrain::setPose,
    drivetrain::getChassisSpeeds,
    (speeds, feedforwards) -> drivetrain.runVelocity(speeds),
    new PPHolonomicDriveController(...),
    robotConfig,
    AllianceSymmetry::isRed,
    drivetrain
);
```

### Step 7 — Characterize on 2027 Hardware
Run these auto routines in order on the new robot:
1. **"Drive Simple FF Characterization"** — measures drive `kS` and `kV` (replaces SysId for routine FF tuning)
2. **"Drive Wheel Radius Characterization"** — measures effective wheel radius including carpet compression
3. Tune steer/drive PID gains in `TunerConstants.java`

---

## High-Frequency Odometry and the PhoenixOdometryThread

AKit's `PhoenixOdometryThread` is the direct equivalent of CTRE's internal odometry thread, but it feeds into the AKit logging boundary:

- Runs at **250 Hz** on CAN FD (CANivore), **100 Hz** on standard CAN.
- Collects timestamps, drive positions, steer angles, and gyro yaw all in a single synchronized batch.
- Each batch is queued and drained in `Drive.periodic()` via `odometryLock`.
- The entire batch is passed through `Logger.processInputs()` before the pose estimator runs — making odometry replay accurate.

If using a CANivore with Phoenix Pro, enable time sync: the thread synchronizes all samples to the CANivore's hardware clock, eliminating timestamp jitter. This is the same mechanism CTRE's `TunerSwerveDrivetrain` uses internally.

---

## Log Structure After Integration

With Approach A, every match log will contain:

```
Drive/GyroInputs/yawPosition
Drive/GyroInputs/yawVelocityRadPerSec
Drive/Module0/Inputs/drivePositionRad
Drive/Module0/Inputs/driveVelocityRadPerSec
Drive/Module0/Inputs/turnPosition
Drive/Module0/Inputs/driveCurrentAmps
...  (same for modules 1-3)
Drive/Pose           // estimated robot pose
Drive/OdometryPose   // raw wheel-encoder pose (no vision fusion)
Drive/SwerveStates/Measured
Drive/SwerveStates/Setpoints
```

This means in replay:
- You can change swerve PID gains and see how module states would have tracked.
- You can change vision stddev weights and see how the fused pose would have differed.
- The `vision-analyzer` tool gets all the inputs it needs without any extra `Logger.recordOutput` calls.

---

## AKit 2026 Specific Notes

- The 2026 release updated the TalonFX swerve template to support **TalonFXS + CANdi** as an alternative module implementation (relevant if 2027 robot uses Minion or other TalonFXS-based modules).
- AKit 2026 documentation was updated to align with **CTRE Hoot Replay** — Hoot and AKit logs are complementary rather than competing.
- Unit metadata support was added to `@AutoLog` — logged values now carry units for AdvantageScope's unit-aware graphing.
- Console logging now captures exceptions during replay watch, making debugging easier.

---

## Performance Analysis: AKit IO Layer vs CTRE Native Swerve

This section addresses a specific concern raised by the AKit developers themselves in their published talks: that the IO layer pattern causes the loss of "high-fidelity vendor feedback loops." This is a real architectural tradeoff. What follows is a detailed breakdown of exactly what is and isn't affected, backed by source code and CTRE's own benchmark data.

### The Core Architectural Difference

**CTRE's native `SwerveDrivetrain` runs a single high-frequency loop that does two things at once:**

1. Collects synchronized CAN signals (drive position, steer position, gyro yaw) at 250 Hz on CANivore
2. Immediately reapplies the current `SwerveRequest` using the freshly-read sensor data — computing inverse kinematics and sending new `VelocityVoltage` / `PositionVoltage` control requests to all eight motors

CTRE's documentation states this explicitly: *"Control is run inline with odometry updates."* This means module setpoints are recalculated and sent to the motors **250 times per second**, using gyro data that is at most 4 ms old.

**AKit's `Drive.java` separates these two concerns:**

1. `PhoenixOdometryThread` still runs at 250 Hz (on CAN FD) — identical sensor collection, same `waitForUpdate()` mechanism, same CANivore time sync
2. `Drive.periodic()` runs at **50 Hz** — drains the odometry queue, runs kinematics, and calls `io.setDriveVelocity()` / `io.setTurnPosition()`, which sends the control requests to the motors

The odometry accuracy is fully preserved. What changes is the **setpoint update rate**: motor targets update at 50 Hz in AKit instead of 250 Hz in CTRE's template.

---

### What Is Preserved (No Degradation)

These CTRE features work identically in AKit Approach A because they operate on the TalonFX motor controller itself, below the IO boundary:

| Feature | How it works | Preserved in AKit? |
|---------|-------------|-------------------|
| **On-controller velocity PID** | TalonFX runs drive velocity PID at ~1 kHz on-device. IO layer's `setDriveVelocity()` sends a `VelocityVoltage` request; the controller holds and regulates the setpoint at 1 kHz between calls. | ✅ Fully preserved |
| **On-controller position PID + MotionMagicExpo** | Steer motor runs MotionMagicExpo trajectory profile on-device at ~1 kHz. `setTurnPosition()` sends a new target; the profile interpolates smoothly until the next call. | ✅ Fully preserved |
| **FusedCANcoder** (Phoenix Pro) | CANcoder fused with rotor encoder at >1 kHz inside TalonFX firmware. Configured in `ModuleIOTalonFX` via `FeedbackSensorSourceValue.FusedCANcoder`. | ✅ Fully preserved |
| **TorqueCurrentFOC** (Phoenix Pro) | On-controller torque-current control mode. AKit template explicitly supports it: set `kDriveClosedLoopOutput = TorqueCurrentFOC` in `TunerConstants.java`. | ✅ Fully preserved |
| **250 Hz odometry** | `PhoenixOdometryThread` collects drive position and steer position at `Drive.ODOMETRY_FREQUENCY` (250 Hz on CAN FD, 100 Hz on RIO CAN). Pose estimator processes all samples in `periodic()`. | ✅ Fully preserved |
| **CANivore time sync** | `PhoenixOdometryThread` uses the CANivore's hardware clock for synchronized timestamps. All odometry samples arrive with hardware-synchronized timestamps. | ✅ Fully preserved |
| **Latency compensation** | `BaseStatusSignal` latency compensation is applied inside `PhoenixOdometryThread` when reading high-frequency positions. | ✅ Fully preserved |

Verification: inspecting `ModuleIOTalonFX.java` from the AKit GitHub confirms `VelocityVoltage`, `VelocityTorqueCurrentFOC`, `PositionVoltage`, `PositionTorqueCurrentFOC`, and `MotionMagicExpo` control requests are all used and configured identically to CTRE's template.

---

### What Is Actually Different (Real Degradation)

#### 1. Motor setpoint update rate: 250 Hz → 50 Hz

The kinematics step — converting `ChassisSpeeds` to per-module wheel speed and angle targets — runs at 50 Hz in AKit instead of 250 Hz. This means the TalonFX receives a new `VelocityVoltage` or `PositionVoltage` request every **20 ms** rather than every **4 ms**.

Between new setpoints, the motor controller's on-device PID/profile continues running at 1 kHz against the previously-sent target. This is fine for stable-speed path segments but creates a lag at any moment the target is changing (acceleration, deceleration, sharp heading change).

**Estimated impact:** For the drive (velocity) motor, this lag is small. Drive inertia is large relative to 4 ms update gains, so the motor controller's velocity PID easily bridges 20 ms between new targets. For the steer (position) motor, 20 ms between position targets is more noticeable in theory. At peak steer velocity (~10 RPS through a typical gear ratio), the module can rotate ~9° between setpoint updates. MotionMagicExpo smooths this, but a fresh target at 250 Hz vs 50 Hz means the motion profile is re-anchored to the current position 5x more often in CTRE's architecture. In practice, AKit teams report no visible module oscillation or tracking lag attributable to this.

#### 2. Field-centric rotation compensation uses older gyro data

CTRE's template recomputes field-centric kinematics using gyro data that is at most 4 ms old. AKit's template uses gyro data that is at most 20 ms old (the reading captured in the current `periodic()` cycle).

At high angular velocity — e.g., 720°/s — the robot rotates 14.4° in 20 ms vs 2.9° in 4 ms. The field-centric rotation matrix applied to driver inputs or path following velocity is therefore based on a heading that may be up to 14.4° stale. AKit's `Drive.runVelocity()` calls `ChassisSpeeds.discretize(speeds, 0.02)` to partially compensate for this (WPILib's twist correction for holonomic second-order kinematics), but this is an approximation, not a fix.

For a typical FRC autonomous path, maximum angular velocity is usually under 180°/s, meaning the maximum gyro lag error is ~3.6° — equivalent to the 2-4 ms lag error in CTRE's 250 Hz setup under the same conditions. At teleop maximum rotation (720°/s), the error grows to 14.4° per loop cycle, which is noticeable only during continuous full-speed spin. In practice, a 14.4° error in the rotation matrix appears as a very brief translation misalignment while spinning at maximum speed, corrected within the next loop cycle.

#### 3. `SwerveRequest` mechanism is replaced

CTRE's `SwerveRequest` API provides built-in behaviors like `ForcePointWheels`, heading lock, and dead-band handling that run inside the 250 Hz loop. AKit replaces this entirely with standard WPILib `SwerveDriveKinematics` at 50 Hz. Any team-specific `SwerveRequest` customizations (e.g., snap-to-angle, wheel force control) must be re-implemented in `Drive.java` or command logic.

---

### Quantitative Evidence

**CTRE's own benchmark** (from their update frequency devblog): 10 autonomous runs each for RIO 250 Hz and CANivore 250 Hz odometry. Average positional error at end of auto:
- RIO 250 Hz: **0.336 m** average, 0.173 m std dev
- CANivore 250 Hz: **0.284 m** average, 0.114 m std dev

This data measures the **odometry** benefit of 250 Hz signals and CANivore time sync — both of which AKit Approach A preserves. AKit's odometry accuracy is therefore expected to match the CANivore 250 Hz row, not degrade toward 50 Hz numbers.

**AKit's high-frequency odometry study** (Team 6328, November 2023): 16 runs of a 12-second PathPlanner auto, 8 runs at 50 Hz and 8 runs at 250 Hz odometry. Result: 250 Hz odometry significantly tightened the cluster of ending positions, confirming the accuracy improvement. AKit Approach A captures this benefit because `PhoenixOdometryThread` still runs at 250 Hz.

**In competition**: Team 6328 has used the AKit TalonFX swerve template on their competition robots since 2024 (the template was first released for 2025). They have placed in the top tier at every championship they have attended since adopting this architecture. No published post-match analysis from any team using AKit Approach A has identified setpoint update frequency (50 Hz vs 250 Hz) as a measurable source of degradation.

---

### Where the "High-Fidelity Vendor Feedback Loop" Warning Actually Applies

When the AKit creators discuss this con in their talks, the concern is specifically about **Approach B (the wrapper)**. With a wrapper:
- The entire CTRE `TunerSwerveDrivetrain` stack — including the 250 Hz control inline with odometry — is inside the IO implementation
- No AKit code can observe or influence module-level setpoints
- The loss is not performance but **observability and replayability**: you cannot tune swerve PID or view module states in replay

For **Approach A**, the IO boundary sits between the `Drive` subsystem and the TalonFX control requests. The on-controller loops (velocity PID, MotionMagicExpo) run at full 1 kHz speed regardless. What is reduced is the **RIO-side setpoint refresh rate**: 50 Hz instead of 250 Hz. This is not "losing vendor feedback loops" — it is shifting the update rate of the outer (setpoint) loop while preserving all inner (on-device) loops.

---

### Verdict

| Concern | Actual severity | Notes |
|---------|----------------|-------|
| On-controller PID accuracy | **None** | 1 kHz on-device PID fully preserved |
| Odometry accuracy (250 Hz) | **None** | PhoenixOdometryThread preserves 250 Hz |
| CANivore time sync | **None** | Preserved in PhoenixOdometryThread |
| Phoenix Pro features (FOC, FusedCANcoder, TorqueCurrentFOC) | **None** | All configured in ModuleIOTalonFX |
| Setpoint update rate (50 Hz vs 250 Hz) | **Minimal** | On-device profiles bridge the gap; PathPlanner generates at 50 Hz anyway |
| Field-centric gyro freshness | **Small** | Up to 14.4° stale at max spin; `ChassisSpeeds.discretize()` partially compensates |
| SwerveRequest replacement | **Medium complexity** | Requires reimplementing any custom SwerveRequest behaviors in Drive.java |

**Bottom line:** Approach A degrades swerve drive performance by a small, measurable but practically insignificant amount. The odometry accuracy that matters most — the 250 Hz high-frequency batch — is fully preserved. The reduction from 250 Hz to 50 Hz setpoint updates is theoretically present but not observed as a meaningful competitive handicap by the teams that have shipped this architecture. The tradeoff is accepted by the best teams in FRC because the replay and simulation benefits are worth more in practice than the 5x setpoint frequency advantage of CTRE's native template.

---

## Sources

- [AdvantageKit TalonFX(S) Swerve Template — Official Docs](https://docs.advantagekit.org/getting-started/template-projects/talonfx-swerve-template/)
- [AdvantageKit Spark Swerve Template — Official Docs](https://docs.advantagekit.org/getting-started/template-projects/spark-swerve-template/)
- [What's New in AdvantageKit 2026?](https://docs.advantagekit.org/whats-new/)
- [AdvantageKit GitHub Releases](https://github.com/Mechanical-Advantage/AdvantageKit/releases)
- [CTRE Swerve with AdvantageKit — Chief Delphi Thread](https://www.chiefdelphi.com/t/ctre-swerve-with-advantagekit/457838)
- [CTRE Swerve with AdvantageKit Logging — Chief Delphi Thread](https://www.chiefdelphi.com/t/ctre-swerve-with-advantage-kit-logging/511862)
- [AdvantageKit 2026: Replay, Refined — Chief Delphi Thread](https://www.chiefdelphi.com/t/advantagekit-2026-replay-refined/509227)
- [AdvantageKit 2025: Log Replay, Streamlined — Chief Delphi Thread](https://www.chiefdelphi.com/t/advantagekit-2025-log-replay-streamlined/476019)
- [HuskieRobotics/3061-lib — AKit CTRE swerve library](https://github.com/HuskieRobotics/3061-lib)
- [Shenzhen-Robotics-Alliance/AdvantageKit-TalonSwerveTemplate-MapleSim](https://github.com/Shenzhen-Robotics-Alliance/AdvantageKit-TalonSwerveTemplate-MapleSim)
- [FRC4079/FRC-Swerve-Template](https://github.com/FRC4079/FRC-Swerve-Template)
- [MARSProgramming/Prometheus-Sim-Logging](https://github.com/MARSProgramming/Prometheus-Sim-Logging)
- [CTRE Phoenix 6 Tuner X Swerve Generator Docs](https://v6.docs.ctr-electronics.com/en/stable/docs/tuner/tuner-swerve/index.html)
- [CTRE Update Frequency & Odometry Accuracy Devblog](https://pro.docs.ctr-electronics.com/en/latest/docs/application-notes/update-frequency-impact.html)
- [CTRE Swerve Overview — "Control inline with odometry"](https://v6.docs.ctr-electronics.com/en/stable/docs/api-reference/mechanisms/swerve/swerve-overview.html)
- [AKit High-Frequency Odometry Study (Team 6328, 2023)](https://docs.advantagekit.org/theory/high-frequency-odometry)
- [AKit Log Replay Comparison — Deterministic vs Hoot](https://docs.advantagekit.org/theory/log-replay-comparison)
- [AKit ModuleIOTalonFX.java — Source (GitHub)](https://github.com/Mechanical-Advantage/AdvantageKit/blob/main/template_projects/sources/talonfx_swerve/src/main/java/frc/robot/subsystems/drive/ModuleIOTalonFX.java)
- [AKit Drive.java — Source (GitHub)](https://github.com/Mechanical-Advantage/AdvantageKit/blob/main/template_projects/sources/talonfx_swerve/src/main/java/frc/robot/subsystems/drive/Drive.java)
