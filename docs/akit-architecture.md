# AdvantageKit: Robot Architecture

This document describes how AdvantageKit integrates into the full robot
software stack — from the hardware signals up through the subsystem layer,
command layer, and into the log files.

---

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Robot.java                           │
│  extends LoggedRobot  ←─ AKit wraps every periodic() call  │
│                                                             │
│  robotPeriodic():                                           │
│    CommandScheduler.run()  ←─ runs all subsystem periodic() │
└─────────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────┐
│                    Subsystem.periodic()                     │
│                                                             │
│   io.updateInputs(inputs)                                   │
│       │                                                     │
│       ▼                                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              FooIO (interface)                       │   │
│  │                                                      │   │
│  │   Real robot:        Simulation:                     │   │
│  │   FooIOTalonFX       FooIOSim                        │   │
│  │   reads TalonFX  OR  steps DCMotorSim                │   │
│  │   signals            and returns results             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│   Logger.processInputs("Foo", inputs)                       │
│       │   ┌──────────────────────────────────────────┐     │
│       │   │ On real robot: writes inputs to .wpilog  │     │
│       │   │ On replay:     reads inputs from .wpilog  │     │
│       │   │ (so hardware is never touched in replay) │     │
│       └──►└──────────────────────────────────────────┘     │
│                                                             │
│   ... subsystem logic using inputs.field ...                │
│                                                             │
│   @AutoLogOutput fields/methods are sampled by AKit        │
│   and appended to the same log                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Startup Sequence (Robot.java constructor)

```
Robot()
  │
  ├─ Logger.recordMetadata(...)     // git hash, project name, runtime type
  │
  ├─ if isReal():
  │     Logger.addDataReceiver(new WPILOGWriter("/home/lvuser/logs"))
  │     Logger.addDataReceiver(new NT4Publisher())
  │
  └─ else (simulation):
        if replay log found:
          Logger.setReplaySource(new WPILOGReader(logPath))
          Logger.addDataReceiver(new WPILOGWriter(logPath + "_sim"))
          setUseTiming(false)          // run as fast as possible
        else:
          Logger.addDataReceiver(new NT4Publisher())   // live sim, no replay
  │
  └─ Logger.start()                  // lock in receivers — no changes after this
  │
  └─ HootAutoReplay(...)             // CTRE Hoot replay, after Logger.start()
  │
  └─ new RobotContainer()            // subsystems instantiated HERE
         │
         └─ Foo = new Foo(
                RobotBase.isReal()
                  ? new FooIOTalonFX()
                  : new FooIOSim())
```

**Critical:** `Logger.start()` must be called before any subsystem is
constructed. All hardware objects in the IO implementations are created
after this point.

---

## Data Flow Per Robot Loop (50 Hz)

```
Robot loop tick
│
├─ LoggedRobot (AKit) calls robotPeriodic()
│   │
│   └─ CommandScheduler.run()
│       │
│       └─ For each registered subsystem:
│           subsystem.periodic()
│           │
│           ├─ 1. io.updateInputs(inputs)
│           │       Fills inputs struct from hardware or sim.
│           │
│           ├─ 2. Logger.processInputs("Subsystem", inputs)
│           │       On real robot: serializes all inputs fields → .wpilog
│           │       On replay:     overwrites inputs fields from .wpilog
│           │                      (hardware is bypassed entirely)
│           │
│           └─ 3. Business logic (lock detection, state machines, etc.)
│                   Reads from inputs.field
│                   Writes to @AutoLogOutput fields
│
└─ LoggedRobot records all @AutoLogOutput values and any
   Logger.recordOutput() calls into the same .wpilog
```

---

## This Codebase's Subsystems

All eight hardware subsystems follow the IO pattern:

| Subsystem | IO Interface | Logger Key | What's in Inputs |
|-----------|-------------|-----------|-----------------|
| `Shooter` | `ShooterIO` | `"Shooter"` | 3-motor velocity, supply/stator/torque current, output voltage, temp, CL error/reference |
| `Indexer` | `IndexerIO` | `"Indexer"` | Velocity, stator/supply current, voltage, CL error, rotor position |
| `Hopper` | `HopperIO` | `"Hopper"` | Velocity, stator/supply current, voltage, CL error |
| `Pickup` | `PickupIO` | `"Pickup"` | Velocity, stator/supply current, voltage, CL error |
| `Intake` | `IntakeIO` | `"Intake"` | Deploy: position, velocity, currents, voltage, CL error/ref; Pickup roller: same |
| `Climber` | `ClimberIO` | `"Climber"` | Arm + grabber: position, velocity, currents, voltage, CL error/ref |
| `AdjustableHood` | `HoodIO` | `"Hood"` | Servo 1 position, servo 2 position, target, enabled |
| `Vision` (per camera) | `VisionIO` | `"Vision/<CameraName>"` | Connected, FPS, rejection counts, pose estimate arrays, visible tag IDs |

### Subsystem Computed Outputs (@AutoLogOutput)

These are calculated by the subsystem each loop from the inputs and are
logged separately. They are NOT replayable — they're recomputed during replay
from the replayed inputs, which is the whole point: you can change the
calculation and see different results without re-running the robot.

| Subsystem | @AutoLogOutput fields |
|-----------|-----------------------|
| `Shooter` | `Locked`, `WasLocked`, `ShotCount`, `TargetRPS`, `TimeToLockSeconds`, `SettleCount`, `AverageError`, `StdDev`, `ExitVelocityFPS`, `Motor2/3RPSDelta`, `RequestedSpeedRPS` |
| `Indexer` | `Active`, `VelocityRPS` |
| `Hopper` | `Active`, `VelocityRPS` |
| `Pickup` | `Active`, `VelocityRPS` |
| `Intake` | `IsDeployed`, `PositionTarget`, `AtTarget` |
| `Climber` | `ArmPositionTarget`, `GrabberPositionTarget`, `ArmAtTarget`, `GrabberAtTarget` |
| `Hood` | `Target`, `CurrentPosition` |

---

## CommandSwerveDrivetrain — Special Case

The swerve drivetrain is generated by CTRE's Tuner X and extends
`SwerveDrivetrain`, which manages its own high-frequency odometry thread,
CAN bus signal caching, and Phoenix 6 signal logging.

It does **not** use the IO interface pattern for two reasons:
1. CTRE's Phoenix 6 provides its own `.hoot` log format, captured by
   `DataLogManager` / `HootAutoReplay`.
2. Refactoring the Tuner X generated code to IO pattern requires rewriting
   the entire swerve stack (ModuleIO + DriveIO + OdometryThread), which is
   a significant undertaking best done from a fresh Tuner X template.

The `HootAutoReplay` initialized in `Robot()` replays the CTRE joystick and
timestamp data from the hoot log during simulation.

---

## Log File Layout in AdvantageScope

After a match the `.wpilog` file written to `/home/lvuser/logs/` contains:

```
/Shooter/
  ├── motor1VelocityRPS         ← from inputs (logged by processInputs)
  ├── motor2VelocityRPS
  ├── motor3VelocityRPS
  ├── motor1StatorCurrentAmps
  ├── ... (all 21 fields in ShooterIOInputs)
  ├── Locked                    ← @AutoLogOutput (computed)
  ├── TargetRPS                 ← @AutoLogOutput
  ├── ShotCount                 ← @AutoLogOutput
  └── ...

/Indexer/
  ├── velocityRPS               ← inputs
  ├── statorCurrentAmps         ← inputs
  ├── Active                    ← @AutoLogOutput
  └── ...

/Intake/
  ├── deployPositionRots        ← inputs
  ├── deployVelocityRPS         ← inputs
  ├── IsDeployed                ← @AutoLogOutput
  └── ...

/Vision/
  ├── Camera1/
  │   ├── connected             ← inputs
  │   ├── currentFps            ← inputs
  │   ├── estimatedPoses        ← inputs (Pose2d[])
  │   └── ...
  └── Camera2/
      └── ...

/RealMetadata/
  ├── ProjectName
  ├── RuntimeType
  └── ...
```

Every leaf signal is timestamped with microsecond precision and can be
graphed, compared, and filtered in AdvantageScope.

---

## Simulation Implementations

Each `*IOSim` class owns its own `DCMotorSim` instance. The sim is
stepped inside `updateInputs()`, called by `SubsystemBase.periodic()`,
which is called by `CommandScheduler.run()` every 20 ms.

There is no global physics sim singleton — `PhysicsSim` /
`PhysicsSim_SJC` are no longer called in `Robot.simulationPeriodic()`.

```
CommandScheduler.run()
  └─ Shooter.periodic()
      └─ io.updateInputs(inputs)
             ↓ (io is ShooterIOSim)
         DCMotorSim.setInputVoltage(...)
         DCMotorSim.update(0.020)
         inputs.motor1VelocityRPS = sim.getAngularVelocityRPM() / 60.0
         ...
      └─ Logger.processInputs("Shooter", inputs)
```

---

## What Happens During Replay

```
Replay run (simulation, log file present)
│
├─ Logger.setReplaySource(new WPILOGReader(logPath))
│
└─ Each loop:
    subsystem.periodic()
    │
    ├─ io.updateInputs(inputs)
    │       ↑ io is FooIOSim — it runs, but its results are DISCARDED
    │       AKit replaces inputs with logged values from the .wpilog
    │
    ├─ Logger.processInputs("Foo", inputs)
    │       Inputs are now the EXACT values from the original match.
    │       Any code changes in the subsystem now run against those values.
    │
    └─ Business logic re-executes with original hardware data
        @AutoLogOutput fields are written to a new _sim.wpilog
```

This is the replay guarantee: **hardware inputs are identical to the
original match; everything above `processInputs` is re-run from your
current code.**

Change the shooter lock detection threshold? Replay and see exactly how many
more/fewer locks would have occurred during that match. Change the vision
weighting algorithm? Replay and compare odometry error before and after.
