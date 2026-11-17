# AdvantageKit Swerve Drive Integration

**Research date:** 2026-10-21  
**Audience:** Team 1405 programmers planning 2027 robot architecture

**Summary:**
- Replay cannot tune swerve PID gains under any approach, because those gains run on the TalonFX. The drive-side capability worth having is a replayable **pose estimator**. Approach C gets that while keeping CTRE's swerve library.
- The AKit template drops three CTRE features we use: MotionMagicExpo steering, PathPlanner wheel-force feedforwards, and coupling-ratio compensation.
- CTRE's swerve is a vendordep library that gets updates. The AKit template is copied once, and after that we maintain it.
- PR #7 (`akit-swerve-approach-b-partial-replay`) implements a narrow form of Approach B.

---

## Background: Why This Matters

Your robot already uses AdvantageKit for logging (`Logger.recordOutput`, `@AutoLogOutput`, the IO layer pattern on Vision/Shooter/etc.) and for replay (`replayWatch`). The one major subsystem that currently sits **outside** the AKit replay boundary is the drivetrain — `CommandSwerveDrivetrain` extends CTRE's `TunerSwerveDrivetrain` directly, which is a black box from AKit's perspective.

That means:
- **Pose estimation** and **odometry** cannot be replayed deterministically.
- **Module states, motor velocities, turn angles** are not in the AKit log unless you manually record them with `Logger.recordOutput`.
- You cannot replay-tune path-following logic or vision-to-odometry fusion against a real match log.

Adding AKit to the swerve drive addresses these. Some limits apply under every approach:
- **Swerve PID/FF gains cannot be replay-tuned.** They run on the TalonFX, and replay re-runs RIO code against the *logged* sensor readings. If you change a gain in replay, the logged wheel motion stays the same. Tune gains on the robot, or in physics sim such as maple-sim.
- **Closed-loop behavior diverges in replay.** If a replayed command decides differently than it did on the robot (different path-following output, different heading command), the logged sensor data still reflects what the robot *actually* did. Replay is trustworthy for estimation and decision logic, and only up to the first point where the replayed output differs from the logged one.

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
- Change `kSteerInertia` → 0.004 and `kDriveInertia` → 0.025 in `TunerConstants.java`. These values are only used by the template's `ModuleIOSim`; they don't affect the real robot. (The AKit docs give the values without saying why.)

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

**Replay coverage:** Every RIO-side layer is replayable: the pose estimator, kinematics, vision fusion, and path-following decisions. This is the strongest form of AKit integration. The on-TalonFX loops are not replayable, as explained in Background.

**Pros:**
- Deterministic replay of the RIO-side drive stack, including odometry + vision fusion
- No black boxes: every RIO-side layer is our source code
- AKit's odometry uses standard FPGA timestamps, so PhotonVision/Limelight pose measurements pass in directly without `Utils.fpgaToCurrentTime()` conversion
- Physics simulation via `ModuleIOSim` (or maple-sim for rigid body)
- Built-in wheel radius characterization routine
- Built-in SysId routines

**Cons:**
- Significant rewrite. We would have to migrate PathPlanner integration, vision measurement calls, SysId routines, alliance perspective logic, and every `SwerveRequest`-based command. Today those live in `AutoPilotCommand`, `AutoPilotV2Command`, `ChainedAutoPilotCommand`, `PidToPoseCommand`, `CircleFacingTagCommand`, `CommandsForAutos`, `FieldCentricAutoPoint`, `SwerveFeatures` and `RobotContainer`.
- The template drops CTRE features we use today:
  - **PathPlanner wheel-force feedforwards.** `CommandSwerveDrivetrain` passes them to `ApplyRobotSpeeds`. The template's `AutoBuilder` consumer is `this::runVelocity` and ignores them.
  - **Heading control at the odometry rate.** `FieldCentricFacingAngle` runs its heading PID inside CTRE's odometry loop. Under A, every heading PID would run in our commands at 50 Hz and need re-tuning.
  - **Coupling-ratio compensation.** We set `kCoupleRatio = 3.71`. `ModuleIOTalonFX` never reads `CouplingGearRatio`, so steering while driving adds small drive-velocity and odometry errors.
  - **MotionMagicExpo steering.** CTRE's default steer request is MotionMagicExpo. The template sets the Motion Magic configs but sends plain `PositionVoltage`/`PositionTorqueCurrentFOC`.
- **Maintenance moves to us.** CTRE's swerve is a vendordep maintained by the hardware vendor, so fixes and new requests arrive when we update it. The AKit template is copied into our repo once. 6328 updates it yearly, but each update would be a manual diff/merge by students.
- Different gains require re-characterization on new robot hardware
- CTRE's Hoot replay (`.hoot` files) becomes redundant, since AKit `.wpilog` is the replay source

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
- Vision fusion (CTRE's pose estimator) can't be replayed. Approach C fixes this.
- Weaker simulation story (CTRE's sim, not physics-based)

### What PR #7 implements

PR #7 (`akit-swerve-approach-b-partial-replay`) is a narrow form of B. `DriveIO` takes one snapshot of CTRE's **outputs** per loop: fused pose, speeds, module states/targets/positions, raw heading, odometry timestamp and DAQ counts. It records them as AKit inputs. Code reads them through `getLoggedState()` instead of `getState()`.

- **Gains:** everything downstream (AutoPilot, PidToPose, PathPlanner, aiming, vision bookkeeping) reads one consistent snapshot per loop, and that snapshot replays exactly. Module states are in the AKit log.
- **Limit:** the replayed pose is the **recorded** pose. Changing vision filters or stddevs in replay changes which samples get accepted, but the pose doesn't move, and neither does anything that consumes the pose.
- **Performance:** no change to how the robot drives. The added cost is one `getStateCopy()` per loop.

---

### Approach C — B plus a Replayable Shadow Pose Estimator

**Keep CTRE's swerve library driving the robot** (as in B), but build a second pose estimator inside the replay boundary from the same raw data.

**How it works:**
1. CTRE's `registerTelemetry` callback runs inside the odometry loop, every sample (100 Hz on the RIO bus, 250 Hz on CAN FD). Use it to queue each sample's module positions, raw gyro heading, and timestamp (converted to FPGA time). Note that `RobotContainer` already registers `logger::telemeterize` here; registering again replaces the callback, so the two must be chained.
2. Each loop, `DriveIO.updateInputs()` drains the queue into array inputs. This is the same shape as AKit's `PhoenixOdometryThread` queues.
3. A WPILib `SwerveDrivePoseEstimator` on the RIO consumes those samples plus the same vision measurements we send to CTRE. This "shadow" estimator is fully replayable.
4. Log both poses (`Drivetrain/Pose` from CTRE, `Drivetrain/ShadowPose` from ours) and compare them in logbench.

**What this buys:**
- Replayable vision-fusion tuning: change stddevs or filters, run `replayWatch`, and see the shadow pose change. This is the drive-side capability Approach A was mainly wanted for.
- No change to robot control. CTRE's request loop, heading PIDs, wheel-force FF and coupling compensation all stay in place.
- A low-risk way to validate. The shadow estimator can be compared against CTRE's on every match log before anything relies on it. Later we could use it as the authoritative pose for aiming or auto, either by reading it directly or by `resetPose`-ing CTRE to it.

**Costs:**
- About 150–250 lines of new code (sample queue, inputs, estimator wiring) that we maintain.
- Two estimators can disagree. We have to decide which one commands use, and that choice should go behind a `FeatureSwitches` flag so it can be A/B tested.
- The 250 Hz samples add to log size, about the same as Approach A would.

---

## What Other Teams Do

**Team 6328 (Mechanical Advantage)**: authors of AKit. Their competition code uses their own IO-layer drive and does not use CTRE's `TunerSwerveDrivetrain`. Note that 6328 maintains both AKit and the template, so their adoption is not independent evidence.

**Team 3061 (Huskie Robotics) — 3061-lib:** Maintain a full AKit swerve library with CTRE TalonFX support, Approach A architecture. Updated annually, incorporates AKit TalonFX swerve template best practices. Referenced by many teams building on CTRE hardware.  
Source: [HuskieRobotics/3061-lib](https://github.com/HuskieRobotics/3061-lib)

**Team 4079:** FRC-Swerve-Template using AKit IO layer pattern with TalonFX hardware.  
Source: [FRC4079/FRC-Swerve-Template](https://github.com/FRC4079/FRC-Swerve-Template)

**Shenzhen Robotics Alliance:** Published `AdvantageKit-TalonSwerveTemplate-MapleSim`, combining AKit's TalonFX swerve template with Team 5516's maple-sim for rigid-body physics simulation (robot colliding with field elements, realistic carpet traction).  
Source: [Shenzhen-Robotics-Alliance/AdvantageKit-TalonSwerveTemplate-MapleSim](https://github.com/Shenzhen-Robotics-Alliance/AdvantageKit-TalonSwerveTemplate-MapleSim)

**What this does and doesn't show:** Approach A is common among teams that prioritize replay. Many teams also run CTRE's generated swerve with only logging layered on. We found **no independent head-to-head benchmark** of the two stacks for path-tracking or heading accuracy. The evidence that A causes no degradation comes from 6328's own work and from a lack of complaints, not from measurement.

---

## Recommendation for Team 1405 (2027)

**Merge B (PR #7), build C next, and treat A as an offseason experiment that has to win on data.**

1. **Merge PR #7** after normal review. It is low risk, doesn't change how the robot drives, and makes everything downstream of the drivetrain replay deterministically.
2. **Build Approach C** (shadow estimator). This is what the vision replay workflow (`replayWatch`, `docs/vision-testing-protocol.md`, FeatureSwitches A/B) actually needs. It keeps CTRE's control loop, which was built by the hardware vendor and is maintained through a vendordep.
3. **Only adopt A if a bake-off shows no regression.** If we want A, build it on a test chassis or the 2027 robot in the offseason. Run identical PathPlanner autos and heading-hold/aim tasks on both stacks, and compare in logbench:
   - end-of-auto pose error (mean and spread), checked against a tape-measured ground truth
   - heading-tracking error during `FieldCentricFacingAngle`-style aiming while translating
   - module tracking error (measured vs. target states)

   A should win, or at least tie, before we take on the rewrite and the maintenance.

Why not go straight to A:
- Its main drive-side benefit is replayable vision fusion, and C provides that.
- The "replay-tune PathPlanner/PID" benefit doesn't exist, as explained in Background.
- It gives up features we use: wheel-force FF, heading PID at the odometry rate, and coupling compensation. It also moves maintenance of a core subsystem from CTRE to our students.

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
- You can change vision stddev weights and see how the fused pose would have differed.
- You can view measured vs. target module states. You **cannot** change swerve PID gains and see how the modules would have tracked, because the logged measurements are what the TalonFX actually did with the old gains.
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

CTRE's documentation states this explicitly: *"Control is run inline with odometry updates."* This means module setpoints are recalculated and sent to the motors at the odometry rate. That is **250 times per second** on a CANivore (gyro data at most 4 ms old), or **100 times per second** on the RIO CAN bus. Our current `TunerConstants` uses the RIO bus (`kCANBus = ""`), so today we run at 100 Hz. The 2027 bus choice decides which number applies.

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
| **On-controller steer position PID** | Steer motor runs position PID on-device at ~1 kHz. `setTurnPosition()` sends a new target. | ✅ Preserved, but the template sends plain `PositionVoltage`/`PositionTorqueCurrentFOC`, **not** MotionMagicExpo (CTRE's default). Matching CTRE means changing `ModuleIOTalonFX` to send a Motion Magic request. |
| **FusedCANcoder** (Phoenix Pro) | CANcoder fused with rotor encoder at >1 kHz inside TalonFX firmware. Configured in `ModuleIOTalonFX` via `FeedbackSensorSourceValue.FusedCANcoder`. | ✅ Fully preserved |
| **TorqueCurrentFOC** (Phoenix Pro) | On-controller torque-current control mode. AKit template explicitly supports it: set `kDriveClosedLoopOutput = TorqueCurrentFOC` in `TunerConstants.java`. | ✅ Fully preserved |
| **250 Hz odometry** | `PhoenixOdometryThread` collects drive position and steer position at `Drive.ODOMETRY_FREQUENCY` (250 Hz on CAN FD, 100 Hz on RIO CAN). Pose estimator processes all samples in `periodic()`. | ✅ Fully preserved |
| **CANivore time sync** | `PhoenixOdometryThread` uses the CANivore's hardware clock for synchronized timestamps. All odometry samples arrive with hardware-synchronized timestamps. | ✅ Fully preserved |
| **Latency compensation** | `BaseStatusSignal` latency compensation is applied inside `PhoenixOdometryThread` when reading high-frequency positions. | ✅ Fully preserved |

Verification: `ModuleIOTalonFX.java` in the AKit GitHub uses `VelocityVoltage`/`VelocityTorqueCurrentFOC` for drive and `PositionVoltage`/`PositionTorqueCurrentFOC` for steer. It sets Motion Magic configs but never sends a Motion Magic request. It applies `SensorToMechanismRatio` (drive) and `RotorToSensorRatio` (steer) in firmware. It never reads `CouplingGearRatio`.

---

### What Is Actually Different (Real Degradation)

#### 1. Motor setpoint update rate: 250 Hz → 50 Hz

The kinematics step — converting `ChassisSpeeds` to per-module wheel speed and angle targets — runs at 50 Hz in AKit instead of 250 Hz. This means the TalonFX receives a new `VelocityVoltage` or `PositionVoltage` request every **20 ms** rather than every **4 ms**.

Between new setpoints, the motor controller's on-device PID/profile continues running at 1 kHz against the previously-sent target. This is fine for stable-speed path segments but creates a lag at any moment the target is changing (acceleration, deceleration, sharp heading change).

**Estimated impact:** For the drive (velocity) motor, this lag is small. Drive inertia is large relative to 4 ms update gains, so the motor controller's velocity PID easily bridges 20 ms between new targets. For the steer (position) motor, 20 ms between position targets is more noticeable in theory. At peak steer velocity (~10 RPS through a typical gear ratio), the module can rotate ~9° between setpoint updates. CTRE's default MotionMagicExpo profile smooths the motion toward each target. The AKit template's plain position PID does not. AKit teams report no visible module oscillation or tracking lag from this, but we found no measurement.

#### 2. Field-centric rotation compensation uses older gyro data

CTRE's template recomputes field-centric kinematics using gyro data that is at most 4 ms old. AKit's template uses gyro data that is at most 20 ms old (the reading captured in the current `periodic()` cycle).

At high angular velocity — e.g., 720°/s — the robot rotates 14.4° in 20 ms vs 2.9° in 4 ms. The field-centric rotation matrix applied to driver inputs or path following velocity is therefore based on a heading that may be up to 14.4° stale. AKit's `Drive.runVelocity()` calls `ChassisSpeeds.discretize(speeds, 0.02)` to partially compensate for this (WPILib's twist correction for holonomic second-order kinematics), but this is an approximation, not a fix.

For a typical FRC autonomous path, maximum angular velocity is usually under 180°/s, meaning the maximum gyro lag error is ~3.6° — equivalent to the 2-4 ms lag error in CTRE's 250 Hz setup under the same conditions. At teleop maximum rotation (720°/s), the error grows to 14.4° per loop cycle, which is noticeable only during continuous full-speed spin. In practice, a 14.4° error in the rotation matrix appears as a very brief translation misalignment while spinning at maximum speed, corrected within the next loop cycle.

#### 3. `SwerveRequest` mechanism is replaced

CTRE's `SwerveRequest` API provides built-in behaviors like `PointWheelsAt`, `SwerveDriveBrake`, `FieldCentricFacingAngle` heading lock, and deadband handling, all running inside the odometry-rate loop. AKit replaces this entirely with standard WPILib `SwerveDriveKinematics` at 50 Hz. Any team-specific `SwerveRequest` behavior (e.g., snap-to-angle, wheel force control) must be re-implemented in `Drive.java` or command logic. For us, the heading PIDs used throughout AutoPilot, `CircleFacingTagCommand` and `CommandsForAutos` would move to 50 Hz and need re-tuning.

#### 4. PathPlanner wheel-force feedforwards are dropped

`CommandSwerveDrivetrain` passes PathPlanner's `robotRelativeForcesX/YNewtons` into `ApplyRobotSpeeds`, and CTRE turns them into per-module current/voltage feedforward. The template's `AutoBuilder` uses `this::runVelocity`, which takes only `ChassisSpeeds`. Under acceleration, path tracking then depends entirely on feedback. We could add the feedforwards back, but we would have to write that code.

#### 5. No coupling-ratio compensation

On a swerve module, turning the azimuth also turns the drive motor (our `kCoupleRatio = 3.71`). CTRE subtracts this from both the drive velocity command and odometry. The AKit template does neither, so modules that steer while driving introduce small speed and odometry errors.

#### 6. Maintenance model

CTRE's swerve library ships in the Phoenix 6 vendordep, so updating the vendordep brings bug fixes and new features. The AKit template is copied into our repository; it is not a dependency. 6328 publishes a new version yearly, but bringing any of it into our code is a manual merge.

---

### Quantitative Evidence

**CTRE's own benchmark** (from their update frequency devblog): 10 autonomous runs each for RIO 250 Hz and CANivore 250 Hz odometry. Average positional error at end of auto:
- RIO 250 Hz: **0.336 m** average, 0.173 m std dev
- CANivore 250 Hz: **0.284 m** average, 0.114 m std dev

This data measures the **odometry** benefit of 250 Hz signals and CANivore time sync — both of which AKit Approach A preserves. AKit's odometry accuracy is therefore expected to match the CANivore 250 Hz row, not degrade toward 50 Hz numbers.

**AKit's high-frequency odometry study** (Team 6328, November 2023): 16 runs of a 12-second PathPlanner auto, 8 at 50 Hz and 8 at 250 Hz odometry, without vision. Mean ending error went from 0.388 m to 0.297 m, and the standard deviation from 0.180 m to 0.028 m. In other words, the autos became far more *consistent*, though only modestly more *accurate*. AKit Approach A keeps this benefit because `PhoenixOdometryThread` still runs at 250 Hz.

**What hasn't been measured:** Neither study compares *control* at 50 Hz against the odometry rate. We found no published analysis that identifies setpoint update rate as a source of degradation. We also found no independent measurement showing that it isn't one. Our planned bake-off (see Recommendation) would answer this for our robot.

---

### Where the "High-Fidelity Vendor Feedback Loop" Warning Actually Applies

When the AKit creators discuss this con in their talks, the concern is specifically about **Approach B (the wrapper)**. With a wrapper:
- The entire CTRE `TunerSwerveDrivetrain` stack — including the 250 Hz control inline with odometry — is inside the IO implementation
- No AKit code can observe or influence module-level setpoints
- The loss is not performance but **observability and replayability**: you cannot tune swerve PID or view module states in replay

For **Approach A**, the IO boundary sits between the `Drive` subsystem and the TalonFX control requests. The on-controller loops (velocity PID, steer position PID) run at full 1 kHz speed regardless. What is reduced is the **RIO-side setpoint refresh rate**: 50 Hz instead of 250 Hz. This is not "losing vendor feedback loops" — it is shifting the update rate of the outer (setpoint) loop while preserving all inner (on-device) loops.

---

### Verdict

| Concern | Actual severity | Notes |
|---------|----------------|-------|
| On-controller PID accuracy | **None** | 1 kHz on-device PID fully preserved |
| Odometry accuracy (250 Hz) | **None** | PhoenixOdometryThread preserves 250 Hz |
| CANivore time sync | **None** | Preserved in PhoenixOdometryThread |
| Phoenix Pro features (FOC, FusedCANcoder, TorqueCurrentFOC) | **None** | All configured in ModuleIOTalonFX |
| Setpoint update rate (50 Hz vs 100/250 Hz) | **Likely small, unmeasured** | On-device loops bridge the gap; PathPlanner itself runs at 50 Hz |
| Field-centric gyro freshness | **Small** | Up to 14.4° stale at max spin; `ChassisSpeeds.discretize()` partially compensates |
| Heading PID moves to 50 Hz | **Small–medium, unmeasured** | Affects every `FieldCentricFacingAngle` use (aiming, AutoPilot); needs re-tuning |
| Steer profile (MotionMagicExpo → plain position PID) | **Small** | Can be restored by editing `ModuleIOTalonFX` |
| PathPlanner wheel-force FF dropped | **Small–medium** | Path tracking under acceleration relies on feedback alone unless we re-add FF |
| No coupling-ratio compensation | **Small** | Drive speed/odometry error while modules steer; we'd have to add it |
| SwerveRequest replacement | **Medium complexity** | Every request-based command must be rewritten |
| Maintenance | **Ongoing cost** | Template code becomes ours; CTRE's library updates via vendordep |

**Bottom line:** A keeps the things that most affect odometry accuracy: 250 Hz sampling, time sync, and on-controller loops. It also drops several CTRE control features we currently use, moves heading control to 50 Hz, and makes the drive code ours to maintain. Each of these is probably small. None has been measured head-to-head. Its one drive-side capability we can't otherwise get, replayable pose estimation, is also available from Approach C without these costs. So A should be adopted only if a bake-off shows it doesn't regress.

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
