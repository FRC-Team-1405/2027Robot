# Console load and 20 ms loop diagnostics

## What the October 20 notes establish

The warning lists are WPILib watchdog timing reports, not evidence that every named function
is printing or failing. `disabledPeriodic()` is empty in this project; the reported calls took
about 0.1–0.24 ms. `SmartDashboard.updateValues()` took about 0.46–1.08 ms. Neither explains the
whole overrun. Individual samples show Vision at 14.25 ms, Shooter at 13.99 ms, and button polling
at 10.30 ms. Reports can come from different loops/threads; do not sum unrelated snippets.
Elapsed time includes scheduling/GC pauses and is not a measurement of active CPU time.

Console formatting, Driver Station warning delivery and console capture can amplify a slow loop.
The repeated missing-POV warning is actionable: port 1 may be absent, incorrectly mapped in the
Driver Station, or reporting a controller layout without a POV. It does not imply SmartDashboard
or disabledPeriodic is broken. Reducing this traffic may help CPU and latency; it will not directly
reduce CAN frame utilization. No percentage improvement has been measured on the robot yet.

## Changes and switches

All switches are in `src/main/java/frc/robot/constants/FeatureSwitches.java` and are included in
`Metadata/FeatureSwitches` in each new AKit log. Existing performance experiment settings remain.

| Switch | Default | Effect |
| --- | --- | --- |
| `QUIET_JOYSTICK_WARNINGS` | `true` | Uses WPILib's supported missing-controller warning suppression on the bench. FMS overrides suppression automatically. |
| `QUIET_SCHEDULER_OVERRUN_WARNINGS` | `true` | Raises the **diagnostic scheduler watchdog only** from 20 ms to 1 second, avoiding repeated verbose scheduler epoch dumps for ordinary overruns. It still reports extreme stalls. |
| `ENABLE_SHOOTER_TEST_CONTROLLER` | `true` | Preserves existing port-2 controls. Set false if unused to avoid installing/polling those bindings. |
| `ENABLE_SUBSYSTEM_DEBUG_PRINTS` | existing `false` | Now also gates PointAtTarget's per-execute printf and RumbleJoystick's informational print. Formatting is skipped when off. |

The robot scheduling period remains 20 ms. The outer WPILib robot watchdog remains at 20 ms and
still prints its warnings and epochs. This pinned WPILib version has no public API to change its
private watchdog reporting policy independently of the robot period. We do not replace WPILib,
filter global stdout/stderr, suppress all warnings, or change motor safety to silence it.
Set `QUIET_SCHEDULER_OVERRUN_WARNINGS=false` to restore stock scheduler timing dumps.
This is a threshold change for verbose reporting, not a rate limiter and not a fix for slow work.

Driver/operator controller capability alerts update at 1 Hz while DS is attached, including an
alert for a connected controller with fewer than 6 axes, 10 buttons or 1 POV. These are the Xbox
controls this project expects. Port 2 is checked only when its test controls are enabled.
Alerts clear after reconnecting; there are no repeating custom console messages. Actual counts
are logged at `RealOutputs/Diagnostics/Controllers/Port{0,1,2}/{Axes,Buttons,POVs}`.

## Measure the effect

Record otherwise identical runs after warmup, with the same enabled state, controller mapping,
vision activity and dashboard clients. Change one switch at a time; deploy/restart between runs.
Use at least 60 seconds per run, and include both disabled and representative enabled operation.
Start with both quiet switches true. Then restore each to false separately for comparison.
If port 2 is unused, test its binding switch separately. Fix the DS port-1 mapping as well.

Compare CPU average/p95 and the rate of actual deadline misses, not warning counts:

- `RealOutputs/Diagnostics/LoopMs`, `LoopMaxMs`, `LoopOverrunCount`: measures the WPILib loop body,
  including dashboard updates and any outer epoch output outside robotPeriodic. Max/count are
  cumulative since robot-code start; compare count differences within equal post-warmup windows.
- `RealOutputs/Diagnostics/SchedulerMs`, `SchedulerMaxMs`, `SchedulerOverrunCount`: elapsed scheduler
  duration, with misses counted against **20 ms regardless of the verbose watchdog switch**.
- These diagnostics remain active with `LOG_SUBSYSTEM_TIMINGS=false`. A dashboard warning remains
  active for 5 seconds after a loop-body deadline miss, independently of verbose scheduler output.
- With `LOG_SUBSYSTEM_TIMINGS=true`, inspect `Timing/Shooter/RefreshSignalsMs`,
  `Timing/Shooter/ReadInputsMs`, `Timing/Shooter/ProcessInputsMs`, and
  `Timing/Vision/<camera name>/ReadInputsMs` / `ProcessInputsMs` under `RealOutputs`.
  Shooter ReadInputs includes RefreshSignals; do not add them together.
- Also compare AdvantageKit's built-in loop/logging/GC timing and CPU statistics: the loop-body
  diagnostic excludes AKit's before/after-user logging work. A quieter console is not proof that
  CPU load or the complete iteration improved.

If quiet output barely helps, the next useful evidence is which of the new IO-read versus
process-input timers spikes, whether GC coincides, and whether AKit logging work lies outside
robotPeriodic. That narrows down CAN accessor/refresh cost, vision processing/allocation, or
logging overhead before changing additional functionality. Keep the raw AKit logs for comparison.

Implementation references, pinned to the project's WPILib version:

- [DriverStation warning policy](https://github.com/wpilibsuite/allwpilib/blob/v2026.2.1/wpilibj/src/main/java/edu/wpi/first/wpilibj/DriverStation.java)
- [CommandScheduler diagnostic watchdog](https://github.com/wpilibsuite/allwpilib/blob/v2026.2.1/wpilibNewCommands/src/main/java/edu/wpi/first/wpilibj2/command/CommandScheduler.java)
- [Outer robot watchdog](https://github.com/wpilibsuite/allwpilib/blob/v2026.2.1/wpilibj/src/main/java/edu/wpi/first/wpilibj/IterativeRobotBase.java)
