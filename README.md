# 2027 Robot — FRC Team 1405

FRC robot code for the 2027 season. Built on WPILib 2026.2.1 with CTRE Phoenix6, PathPlanner, and PhotonVision.

## Project Structure

```
src/main/java/frc/robot/
├── Robot.java               # Main robot class (extends LoggedRobot)
├── RobotContainer.java      # Subsystem instantiation and button bindings
├── Constants.java           # Tuning constants (PID gains, CAN IDs, etc.)
├── Telemetry.java           # Swerve drivetrain telemetry
├── commands/                # WPILib commands
├── subsystems/              # Robot subsystems (Shooter, Intake, Indexer, …)
│   └── vision/              # PhotonVision integration
├── constants/               # Feature switches, field layout, robot constants
├── generated/               # CTRE Tuner X generated swerve constants
├── lib/                     # Shared utilities (logging, simulation helpers, …)
└── sim/                     # Physics simulation profiles
```

## Building & Deploying

```bash
# Build
./gradlew build

# Deploy to roboRIO
./gradlew deploy

# Simulate (desktop)
./gradlew simulateJava
```

## Feature Switches

`constants/FeatureSwitches.java` contains boolean flags to enable or disable
features at compile time (e.g. vision filters, debug logging, mechanical
protections). All flags default to the safe/2026-baseline state.

---

## AdvantageKit

[AdvantageKit](https://docs.advantagekit.org) (v26.0.2) is integrated for
structured telemetry logging and deterministic log replay.

### What it does

- **Logs all `@AutoLogOutput` fields** from every subsystem automatically each
  robot cycle, publishing them to NetworkTables and writing them to a `.wpilog`
  file on the roboRIO.
- **Enables log replay** — you can re-run robot code in simulation against a
  real match log, deterministically reproducing every sensor input and state
  change.

### Viewing logs

Open the `.wpilog` file created in `/home/lvuser/logs/` on the roboRIO with
[AdvantageScope](https://github.com/Mechanical-Advantage/AdvantageScope).
During a match or simulation you can also connect AdvantageScope to the robot's
live NetworkTables stream.

### Logging a new field

Add `@AutoLogOutput` to any `public` or package-private **instance field** in a
`SubsystemBase` subclass. Supported types include `boolean`, `int`, `double`,
`String`, `double[]`, `Pose2d`, `SwerveModuleState[]`, and other WPILib structs.

```java
import org.littletonrobotics.junction.AutoLogOutput;

public class MySubsystem extends SubsystemBase {

    @AutoLogOutput(key = "MySubsystem/IsActive")
    private boolean isActive = false;

    @AutoLogOutput(key = "MySubsystem/TargetRPS")
    private double targetRPS = 0.0;
}
```

The `key` is the path shown in AdvantageScope/NetworkTables under the
`AdvantageKit` root table.

You can also log one-off values anywhere in code with:

```java
Logger.recordOutput("MySubsystem/SomeValue", myValue);
```

### Current annotated fields

| Class      | Key                    | Type    |
|------------|------------------------|---------|
| `Shooter`  | `Shooter/TargetRPS`    | double  |
| `Shooter`  | `Shooter/Locked`       | boolean |
| `Shooter`  | `Shooter/WasLocked`    | boolean |
| `Shooter`  | `Shooter/ShotCount`    | int     |
| `Indexer`  | `Indexer/Active`       | boolean |

### Replaying a log (advanced)

> **Note:** Log replay is not wired up by default — simulation currently runs
> the physics sim with live NT telemetry only. To enable replay:

1. Transfer a `.wpilog` file from the roboRIO to your PC.
2. Open the log in AdvantageScope and use **File → Export replay log** to set it
   as the replay source, or edit `Robot.java`'s simulation block:

```java
} else {
    setUseTiming(false); // run as fast as possible during replay
    String logPath = LogFileUtil.findReplayLog();
    Logger.setReplaySource(new WPILOGReader(logPath));
    Logger.addDataReceiver(
        new WPILOGWriter(LogFileUtil.addPathSuffix(logPath, "_sim")));
}
```

3. Run `./gradlew simulateJava` — the robot code will re-execute against the
   recorded inputs and write a new `_sim` log with all outputs.

You can also watch for log file changes with the Gradle task:

```bash
./gradlew replayWatch
```

### Notes on logging configuration

On the real robot, AdvantageKit writes to `/home/lvuser/logs/` (same directory
as WPILib's `DataLogManager`). Both systems run in parallel — AKit writes its
own `.wpilog` file while DataLogManager writes a separate one for CTRE Hoot
compatibility. This is intentional; you can remove the `DataLogManager` calls
in `Robot.java` once you no longer need CTRE Hoot replay.

---

## Vision

The robot uses PhotonVision cameras for AprilTag-based pose estimation.
Vision filtering parameters (boundary rejection, stddev tuning, tag rankings)
are controlled via feature switches in `FeatureSwitches.java`. See
`docs/vision-testing-protocol.md` for the A/B testing methodology.
