# CAN bus load, RIO CPU and loop time experiments

All switches are in `src/main/java/frc/robot/constants/FeatureSwitches.java`. New switches preserve
current beta behavior until changed; the existing CAN switches retain your committed settings.
Every run now records **Metadata/FeatureSwitches** with the actual compiled values. Check it before
comparing runs: at implementation time beta still had `MECHANISM_STATUS_SIGNAL_HZ = 0.0`, while the
bench report described a deployment at 20 Hz. Uncommitted/deployed settings can differ.
Mechanism rate/optimization results and applied IO signal frequencies are also recorded once at
startup under `RealOutputs/Performance/CAN/<bus-id>/`. Check for configuration failures and shared
frame rate floors instead of assuming a requested 20 Hz was applied.

## What the code explains

- `POWER_TELEMETRY_SIGNALS = false` only removes extra status reads/subscriptions. It still calls
  `Logger.processInputs` for roughly 45 fields per motor every loop, and motor control call sites
  still decode/format request maps. It does **not** switch PowerTelemetry off. This is a plausible
  remaining CPU cost even with the existing switch off.
- `CoprocessorHealthLogger` recursively enumerates/read/logs the whole OrangePi table in a burst
  every 0.5 s. `LoopTimings.mirrorTracer` does a similar recursive walk **every robot loop** when
  timings are on. Cache of entry handles does not eliminate those table enumerations.
- AKit `.wpilog`, DataLogManager's NT-mirrored `FRC_*.wpilog`, and Phoenix `.hoot` logging all run.
  The extra loggers are candidates for CPU, allocation and disk overhead, not proof of CAN load.
- `Telemetry.telemeterize` runs from the CTRE swerve callback, not just `robotPeriodic`. It publishes
  structs and updates four Mechanism2d widgets at that callback's rate.
- The earlier CAN switches cover simple mechanisms, not the eight swerve motors or three shooter
  motors. Phoenix 2026 also changed no-argument `optimizeBusUtilization()` to slow unspecified
  signals to **4 Hz**, not zero. Signals sharing a CAN frame use the fastest requested rate in that
  frame. Setting a few individual signals to 20 Hz need not reduce utilization much.

A 30 ms timing sample is elapsed time, including time spent paused by garbage collection or scheduling.
It does not prove 30 ms of active CPU work in that particular method. Use the removal experiments
below to establish causation. CPU, loop latency and CAN utilization are separate measurements.

## Highest benefit for least cost: test in this order

These are hypotheses ranked from the reported timings and code, not measured savings. Restore the
baseline between runs. Once individual benefits are known, combine the winners and verify again.

| Order | Change for one run | Primary target | Cost / interpretation |
|---|---|---|---|
| 1 | `ENABLE_POWER_TELEMETRY = false` | CPU + loop time | Bypasses registration/config readback, request decoding and all periodic PowerTelemetry work. Motor commands/IO and AKit built-in battery/PDH data continue. Per-motor Power diagnostics and state context are absent. With `POWER_TELEMETRY_SIGNALS` already false, expect mainly CPU savings, not additional CAN savings. |
| 2 | `COPROCESSOR_HEALTH_LOGGING = false` | Periodic spikes | Disables only Pi-to-AKit mirroring. Live NT health and Pi recorder services continue; finished-log Pi/recorder checks lose these fields. |
| 3 | `MIRROR_TRACER_TIMINGS = false`, keep `LOG_SUBSYSTEM_TIMINGS = true` | CPU + loop time | Removes recursive NT timing copies while retaining the direct subsystem measurements. Vision's original Tracer itself still runs. |
| 4 | `LOG_NETWORKTABLES_TO_WPILOG = false` | CPU + disk/NT duplication | Keeps the authoritative AKit `.wpilog` and DS logging. The separate FRC log no longer has all NT topics; select the **akit_** log for analysis/replay. |
| 5 | `SWERVE_TELEMETRY_10_HZ = true` | CPU + NT/visualization overhead | Only dashboard/custom-Hoot callback outputs become 10 Hz. Swerve odometry/control and automatic Phoenix capture keep their rates. |
| 6 | `ROBOT_DASHBOARD_10_HZ = true` | CPU + repeated diagnostic reads | Throttles diagnostic publishing, including drive diagnostic getter calls. IO, scheduler, commands, vision fusion and the RobotTime clock reference continue every loop. Widgets become slower. |
| 7 | `PHOENIX_SIGNAL_LOGGING = false` | CPU + disk | Stops automatic/manual `.hoot` logging and real-robot Hoot timestamp/joystick capture. AKit stays enabled. Loses CTRE high-rate forensic data and Hoot replay capture. |

If steps 1/2 help, try the less disruptive alternatives **with those features enabled again**:

| Switch | Behavior / limit |
|---|---|
| `POWER_TELEMETRY_10_HZ = true` | Refreshes/processes PowerTelemetry once per 0.1 s instead of every loop. Reduces average CPU but still does a full batch on sample loops, so a 15 ms burst might remain. Short current spikes can be missed. Does not change CAN frame rates. AKit replay still processes recorded inputs every loop. |
| `POWER_REQUEST_DETAILS = false` | Removes request map construction/string formatting/decoding from command call sites and telemetry fallback. The same request object still reaches `setControl`. Request provenance fields become unknown. Combine with 10 Hz sampling only after testing independently. |
| `BATCH_COPROCESSOR_HEALTH_LOGGING = true` | Flat topic discovery every 5 s; at most 8 entry reads per robot loop, only changed NT timestamps logged. Full sweep takes `ceil(topic count / 8)` loops (200 topics: about 0.5 s at 50 Hz). New topics can take up to 5 s plus a sweep to appear. Discovery still has a cost; this is bounded entry processing, not a hard wall-time guarantee. No background Logger calls. |

## CAN-specific experiments

Try these separately from the CPU experiments so their effect is attributable.

| Switch | Scope |
|---|---|
| `MECHANISM_STATUS_SIGNAL_HZ = 20.0` | Existing rate experiment: Hopper, Indexer, Pickup and Intake pickup roller. Intake and Pickup share a CAN ID in this robot, so these are not four independent physical motors. Does not change swerve/shooter or intake deploy rates. |
| `OPTIMIZE_BUS_UTILIZATION = true` + `ZERO_UNUSED_MECHANISM_STATUS_SIGNALS = true` | Explicitly sets unspecified status signals to 0 Hz on those already-tuned simple mechanisms after preserving IO/telemetry signals. No extra effect if optimization is off. Mechanism optimization remains active even when `ENABLE_POWER_TELEMETRY` is false. Disabled diagnostics are unavailable to Hoot. |
| `LOW_RATE_SHOOTER_DIAGNOSTICS = true` | Requests 20 Hz for shooter currents/diagnostic voltages, 4 Hz for temperature. All three motor velocities remain 100 Hz; leader closed-loop error/reference remain 100 Hz. Leader DutyCycle/MotorVoltage/TorqueCurrent stay 100 Hz for Phoenix followers. Shared-frame constraints may limit savings. Does not optimize/disable unspecified shooter signals. |
| `SKIP_ABSENT_DEVICES = true` | Existing PowerTelemetry-only skip/reprobe for devices with repeated bad status. Does not stop subsystem IO polling an absent device, and does not remove frames from healthy devices. |

No new switch lowers swerve odometry, CANcoder/gyro feedback, motor control request frequency, motor
current limits, or shooter follower-output rates. Those changes require a separate controls review.
If utilization stays high, check CAN TxFull/Rx/Tx errors and bus-off counts before treating all traffic
as useful load: wiring/termination problems cannot be fixed by logging switches. If there are no errors,
more savings likely require a complete frame-rate audit of the swerve/encoders/gyro or a CANivore,
rather than further slowing a few roller motors.

## Repeatable bench procedure

1. Use the same wiring, battery and robot state. Hold dashboards/Health Check clients constant;
   disconnect Phoenix Tuner plots during comparisons. Change one switch, redeploy/restart, and
   confirm **Metadata/FeatureSwitches** in the resulting AKit log.
2. Allow 20 s for startup, record 60 s disabled/still, then repeat a fixed enabled routine. Run each
   candidate more than once so a single garbage-collection pause or radio change does not win.
3. Compare CAN mean/p95/peak and error counters, RIO CPU mean/p95, loop mean/p95/p99/maximum and
   fraction exceeding 20 ms. Health Check's means are useful but insufficient for 30 ms spikes;
   graph `RealOutputs/Timing/*Ms` and built-in `LoggedRobot`/SystemStats CPU/GC fields too.
4. `Timing/RobotPeriodicMs` now includes Tracer copying, with new separate `Timing/TracerMirrorMs`
   and `Timing/PhoenixReplayMs`. Do not sum inclusive timers: CommandScheduler contains subsystem
   timings. CTRE callback work, background NT/disk threads and GC also affect overall CPU.
5. Working headroom targets (bench goals, not guarantees): loops comfortably below their 20 ms
   deadline, ideally p99 below 15 ms; CPU below about 70% sustained; CAN below about 70% sustained
   with no recurring errors. Keep peak/overrun measurements even if averages meet those goals.
6. Combine demonstrated wins; validate drive, mechanism transitions and shooting readiness before
   keeping a lower-diagnostic profile. Switches that remove evidence are isolation experiments,
   not a substitute for fixing excessive overhead.

## References and verification

- [Phoenix 2026 changes](https://v6.docs.ctr-electronics.com/en/stable/docs/yearly-changes/yearly-changelog.html)
- [Phoenix status signals and shared-frame/follower requirements](https://v6.docs.ctr-electronics.com/en/stable/docs/api-reference/api-usage/status-signals.html)
- [WPILib DataLogManager](https://github.wpilib.org/allwpilib/docs/release/java/edu/wpi/first/wpilibj/DataLogManager.html)
- Tests: `PeriodicGateTest`, `CoprocessorHealthLoggerTest`, `CanLoadSwitchesTest`. Tests no longer assert
  that intentionally user-adjustable experiment switches must equal historical defaults.

## Console follow-up

See [console load and 20 ms diagnostics](console-load-ab-test.md) for the October 20 warning samples,
quiet-console switches, persistent controller alerts, and timing counters that remain active when
verbose scheduler reporting is reduced. Fewer warning messages do not establish lower CPU or CAN load.
