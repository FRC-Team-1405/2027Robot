# AdvantageKit: Logging and Replay Workflow

---

## On the Robot (Real Hardware)

### What gets logged

Every match automatically produces two log files in `/home/lvuser/logs/`:

| File | Written by | Contents |
|------|-----------|----------|
| `FRC_YYYYMMDD_HHMMSS.wpilog` | AdvantageKit `WPILOGWriter` | All AKit inputs + outputs (the primary replay log) |
| `FRC_YYYYMMDD_HHMMSS.wpilog` (second) | WPILib `DataLogManager` | CTRE Hoot joystick and timestamp data |

The AKit log captures:
- Every field in every `@AutoLog` Inputs struct (`Logger.processInputs`)
- Every `@AutoLogOutput` field and method across all subsystems
- Robot metadata (project name, git hash, match time, runtime type)
- Driver station data (enabled/disabled, alliance, match number)

### How to retrieve the log

Connect to the robot via the driver station laptop on the field network, or
SSH to the roboRIO after a match:

```bash
# Option 1: SCP from roboRIO
scp admin@10.14.05.2:/home/lvuser/logs/*.wpilog ./logs/

# Option 2: USB drive
# The roboRIO will write logs to a USB drive inserted into its port
# if the drive is formatted FAT32 and has a /logs/ directory.
```

Logs accumulate and are NOT auto-deleted. Clear old logs periodically:

```bash
ssh admin@10.14.05.2 "rm /home/lvuser/logs/*.wpilog"
```

---

## Viewing Logs in AdvantageScope

[AdvantageScope](https://github.com/Mechanical-Advantage/AdvantageScope) is
the official log viewer for AKit.

### Open a log

```
File → Open Log → select .wpilog
```

### Key views

| Tab | Use it to… |
|-----|-----------|
| **Line Graph** | Plot any numeric signal over time. Drag signals from the left panel. |
| **Odometry** | Visualize robot pose on the field. Drag a `Pose2d` or `Pose2d[]` signal. |
| **Mechanism** | View swerve module states, arm angles, etc. |
| **Table** | See all signal values at a specific timestamp. |
| **Statistics** | Distribution histograms, min/max/mean of a signal. |

### Useful signals to inspect after a match

```
/Shooter/motor1VelocityRPS        — actual flywheel speed
/Shooter/TargetRPS                — commanded speed
/Shooter/Locked                   — lock state (boolean)
/Shooter/TimeToLockSeconds        — how long to reach lock
/Shooter/ShotCount                — cumulative shots

/Intake/deployPositionRots        — arm position
/Intake/deployStatorCurrentAmps   — stall detection signal
/Intake/IsDeployed                — deploy state

/Vision/Camera1/estimatedPoses    — accepted pose estimates
/Vision/Camera1/connected         — camera connection drops
/Vision/Camera1/currentFps        — frame rate

/Indexer/velocityRPS              — indexer speed
/Indexer/Active                   — running flag

RealMetadata/ProjectName          — confirms which build ran
```

---

## Running a Replay

Replay lets you run the current code against a real match log without the
robot. The hardware inputs are fed from the log; all subsystem logic
re-executes on your machine.

### Prerequisites

- Gradle build environment (Windows/Mac dev laptop, not the Pi)
- The `.wpilog` file from the match you want to replay

### Setup

1. Place the `.wpilog` file somewhere accessible (project root, `logs/`, etc.)

2. Set the `AKIT_LOG_PATH` environment variable **or** let `LogFileUtil`
   find it automatically (it searches common locations):

   ```bash
   export AKIT_LOG_PATH=/path/to/FRC_20260315_123456.wpilog
   ```

   Alternatively, configure `LogFileUtil.findReplayLog()` in `Robot.java`
   with a hard-coded path for one-off replays.

3. Run the Gradle simulation target:

   ```bash
   ./gradlew simulateJava
   # or in VS Code: WPILib: Simulate Robot Code
   ```

   The robot will start, detect the replay source, and run through the
   entire match as fast as the CPU allows (`setUseTiming(false)` is already
   set in `Robot.java`).

4. A new `*_sim.wpilog` file is written alongside the original log.

### Comparing original vs. replay in AdvantageScope

Open both logs simultaneously:

```
File → Open Log → (select original .wpilog)
File → Open Log in New Window → (select _sim.wpilog)
```

Or drag both into a single AdvantageScope window and overlay signals using
the `+` button on a graph. The `_sim` log has the same signals but computed
by your new code — easy to diff.

---

## The Replay Guarantee

During replay, `Logger.processInputs("Foo", inputs)` **overwrites** what
`io.updateInputs(inputs)` wrote. The IOSim runs but its results are
discarded. The inputs that reach your subsystem logic are bit-for-bit
identical to what the real hardware reported during the original match.

```
Original match                     Replay
─────────────────────────────      ─────────────────────────────
TalonFX.getVelocity() → 42.3  →   inputs.velocityRPS = 42.3
           ↓                                  ↓
  Shooter.periodic()            Shooter.periodic()
  (old code: locked at ±2 RPS)  (new code: locked at ±1 RPS)
           ↓                                  ↓
  Locked = true @ t=1.23s       Locked = true @ t=1.18s  ← faster lock
```

**What changes between original and replay:**
- Any code change in a subsystem class
- New or modified `@AutoLogOutput` computations
- New commands or state machines

**What does NOT change:**
- All `inputs.*` values (they come from the log)
- Timing of hardware events (motor stalls, camera disconnects, etc.)
- Field positions, alliance color, driver inputs (replayed via Hoot)

---

## What Cannot Be Replayed

| Thing | Why |
|-------|-----|
| Swerve odometry (CTRE internal) | Runs inside `SwerveDrivetrain`, not through an IO interface. Replayed separately via `.hoot` files using `HootAutoReplay`. |
| `SmartDashboard.putX()` calls that bypass AKit | These go directly to NT and are not in the `.wpilog`. Convert to `@AutoLogOutput` or `Logger.recordOutput()` to fix. |
| Vision camera images | Raw frames are not logged — only the processed pose estimates are captured in `VisionIOInputs`. |

---

## Live Telemetry (No Log File)

When no replay log is found in simulation (or on the real robot), AKit
publishes all signals live via `NT4Publisher`. Connect AdvantageScope to the
robot (or the simulator's NT server) for live dashboarding:

```
AdvantageScope → File → Connect to Robot → 10.14.05.2
                                     or → localhost (simulator)
```

All signals under `/Shooter/`, `/Intake/`, `/Vision/`, etc. are visible
live, with the same structure as the log file.

---

## Logging from Command and Non-Subsystem Code

For signals that don't belong in an IO Inputs struct, use:

```java
// Log a single value (appears in AdvantageScope under the given key)
Logger.recordOutput("MyCommand/IsRunning", true);
Logger.recordOutput("AutoPilot/TargetPose", new Pose2d(...));

// Log an array of poses (renders on the Odometry tab)
Logger.recordOutput("AutoPath/Waypoints", new Pose2d[]{ p1, p2, p3 });
```

Call this anywhere — commands, RobotContainer, utility classes. The value
is timestamped to the current loop and written to the `.wpilog`.

---

## Troubleshooting

### "No replay log found" crash in simulation
`LogFileUtil.findReplayLog()` returns `null` when no log is present. `Robot.java`
handles this by falling back to `NT4Publisher` for live sim. If you want
replay, make sure `AKIT_LOG_PATH` is set or the log is in a location
`LogFileUtil` searches.

### Inputs are all zero during replay
The Logger key passed to `processInputs` must exactly match the key used
when the log was written. Check for typos or case differences (keys are
case-sensitive).

### @AutoLogOutput field not appearing in the log
- Make sure the subsystem is registered with the `CommandScheduler`
  (extends `SubsystemBase` and is instantiated in `RobotContainer`).
- The field must be non-static.
- Enums don't serialize automatically — log `.name()` via a method instead.

### Simulation runs but motors don't move
The `IOSim` receives commands but `updateInputs()` must be called by the
subsystem's `periodic()`. If a subsystem doesn't extend `SubsystemBase` or
isn't registered, its `periodic()` never runs.

### Log files growing too large
Default AKit logging rate is 50 Hz for all signals. Signals that change
rarely (temps, connection status) can be throttled:

```java
// In the IOTalonFX constructor — log temp at 4 Hz instead of 50 Hz
motor1.getDeviceTemp().setUpdateFrequency(4);
```
