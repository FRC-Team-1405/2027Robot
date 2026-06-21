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
