# CAN bus load and loop time: A/B switches

At Ruckus 2026 the roboRIO's CAN bus idled at about **65 %** with the robot *disabled and still* (about 77 %
enabled, 100 % at peaks), and the robot loop took a median of **38 ms against a 20 ms period** (about 90 % of
that is our code, not WPILib or logging). Everything is on the roboRIO's classic 1 Mbit/s bus: all motors are
`rio-N`, there is no CANivore.

This page is the protocol for finding out which of the suspects costs what. Every switch lives in
[`FeatureSwitches.java`](../src/main/java/frc/robot/constants/FeatureSwitches.java) and **defaults to the
behavior the robot had at Ruckus**, so nothing changes until you flip one.

## The suspects and their switches

| Suspect | Switch | Default | What flipping it does |
|---|---|---|---|
| `PowerTelemetry` subscribes 14 status signals on all ~16 devices (≈100 Hz each) and logs ~45 fields per device every loop | `POWER_TELEMETRY_SIGNALS` | `true` | `false`: devices stay declared and their config is read once, but no status signals are subscribed or refreshed. **Motor current/temperature/fault data disappears from logs**, so this is a test, not a match setting. |
| The simple mechanism motors report at 100 Hz | `MECHANISM_STATUS_SIGNAL_HZ` | `0` (Phoenix default) | `> 0` (try `20`): Hopper, Indexer, Pickup and Intake-pickup status signals are set to that rate. Swerve modules and the shooter are never touched. |
| Phoenix sends signals nobody reads | `OPTIMIZE_BUS_UTILIZATION` | `false` | `true`: on those same four motors, every signal the code reads gets an explicit rate first (the configured one, else 50 Hz), then `optimizeBusUtilization()` silences the rest. |
| Dead or unplugged motors are read every loop | `SKIP_ABSENT_DEVICES` | `false` | `true`: a motor whose status has been bad for 5 s is only re-checked every 5 s; its rows read `SkippedAbsent`. |
| Vision logs a lot every loop (39 `recordOutput`s, per-camera traces) | `VISION_EXTENDED_NT_LOGGING` (existing) | `true` | `false` drops the extended vision logging. |
| Where the 38 ms goes | `LOG_SUBSYSTEM_TIMINGS` | `false` | `true`: logs `RealOutputs/Timing/<Section>Ms` for each part of `robotPeriodic` and each subsystem's `periodic()`, and mirrors the `Tracer` table (Vision) to `RealOutputs/Timing/Tracer/...`. |

Why only four motors for the rate switches: a Phoenix status signal's rate belongs to the *device*, not to
whoever asked for it. Lowering a swerve module's or the shooter's signals would slow odometry and shooter
lock. The four mechanism motors are only read for their own inputs and logging.

## The protocol (pit test, one change at a time)

1. Baseline: deploy as-is. Power up, leave the robot **disabled** for about a minute, enable for a
   minute or two in teleop (drive, intake, shoot if you can), disable.
2. Open **Health Check** on the log (or live) and note two numbers:
   - *roboRIO / CAN bus / CAN utilization while disabled (idle baseline)*: this is the number the signal
     switches move.
   - *roboRIO / Controller / Robot loop time (mean while enabled)*: this is the number the code-time
     switches move.
3. Flip **one** switch, redeploy, repeat the same routine, compare. Keep what helped.
4. To see *where* loop time goes, set `LOG_SUBSYSTEM_TIMINGS = true` for one run: Health Check gets a
   **Loop time breakdown** group (one row per section, mean while enabled). `RobotPeriodic` is the whole
   loop body; `CommandScheduler` contains each subsystem's `Timing/<Subsystem>` plus commands, so
   `CommandScheduler − Σ subsystems` is the commands themselves.

Expected shape if the theory holds: `POWER_TELEMETRY_SIGNALS = false` drops the idle baseline sharply (the
extra signals are most of the idle traffic); `MECHANISM_STATUS_SIGNAL_HZ = 20` takes a smaller bite. Loop
time moves with `POWER_TELEMETRY_SIGNALS` (no refresh/log of ~45 fields × 16 devices) and with
`VISION_EXTENDED_NT_LOGGING`.

## One finding to act on

`IntakeIOTalonFX.setupDeployMotor()` calls `deployMotor.optimizeBusUtilization()` after setting only the
position signal to 10 Hz. That disables the velocity/current signals, so in Ruckus logs the **Intake Deploy**
motor was `Valid` 0.2 % of the time with about 49 velocity/current samples against about 4,500 for the other
motors. `PowerTelemetry` subscribing afterwards does not re-enable them. The deploy current and velocity in
the logs are therefore effectively missing. It has not been changed (it is a behavior change on a
mechanism that works); if you want that data, give the deploy signals explicit rates before the optimize
call.

## Developer notes

- `power/BusLoad.java`: rate selection and the order of operations (IO constructors list what they read via
  `tuneMechanismMotor`; `PowerTelemetry.initialize()` then finishes and optimizes).
- `power/AbsenceTracker.java`: time-based skip logic, no hardware.
- `util/LoopTimings.java`: no-op (a constant-folded branch) while `LOG_SUBSYSTEM_TIMINGS` is false.
- Tests: `CanLoadSwitchesTest.java`, `tools/logbench/tests/test_health_loadswitches.py`.
