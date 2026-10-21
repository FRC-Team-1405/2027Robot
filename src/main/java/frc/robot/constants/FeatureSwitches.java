package frc.robot.constants;

/**
 * Feature switches to enable or disable robot features.
 * All fields should be public static final booleans (one double: MECHANISM_STATUS_SIGNAL_HZ).
 *
 * <p>Every switch sits in one of six categories and is documented the same way:
 * <pre>
 *   true / false   what each value does
 *   SET            the recommended value: one value (KEEP), or one for COMPETITION and one for TESTING
 *   CHANGE WHEN    the reason to flip it away from SET
 *   MEASURED       what bench testing showed (notes/10-20/notes.md), if it was measured
 * </pre>
 *
 * <ol>
 *   <li><b>Robot behavior</b>: changes what the robot does on the field. Same value for testing and
 *       competition; change it deliberately, as a strategy/driver decision.</li>
 *   <li><b>Mechanical protection</b>: temporary while a mechanism is broken, missing or being worked on.
 *       COMPETITION: all false, unless that mechanism is physically off the robot.</li>
 *   <li><b>Settled performance</b>: measured wins (or harmless defaults). KEEP as set; only flip one to
 *       chase a specific problem, then flip it back.</li>
 *   <li><b>Diagnostics</b>: extra data that costs loop time. Off at competition, on when you need the
 *       data to diagnose something.</li>
 *   <li><b>Experiments to retest</b>: CAN-load switches that showed no effect on 2026-10-20. Retest them
 *       once the drive base is on the CANivore, then settle them into 3 or remove them.</li>
 *   <li><b>Unused</b>: read nowhere in the code. Changing them does nothing. Candidates for removal.</li>
 * </ol>
 *
 * <p>The deployed values are logged at startup as Metadata/FeatureSwitches (PerformanceProfile), and
 * LogBench's Health Check shows them under roboRIO -> Build. Check them there before comparing two logs.
 *
 * <p>PRE-COMPETITION CHECK: category 2 all false (unless a mechanism is off the robot);
 * ENABLE_SHOOTER_TEST_CONTROLLER false; ENABLE_SUBSYSTEM_DEBUG_PRINTS false; the other diagnostics as
 * their SET COMPETITION says.
 */
public class FeatureSwitches {

    //#region 1. Robot behavior
    // =========================================================================
    // 1. ROBOT BEHAVIOR - changes what the robot does. Same value for testing and competition.
    // =========================================================================

    /** Turn vision odometry corrections off while AutoPilot is inside its beeline radius of the target,
     *  so a late vision jump can't knock the final approach off.
     *  true  = odometry only near the AutoPilot target.
     *  false = vision keeps correcting all the way in.
     *  SET: KEEP true.
     *  CHANGE WHEN: the robot consistently ends AutoPilot short of/offset from the target because odometry drifted. */
    public static final boolean DISABLE_VISION_ODOM_NEAR_AUTOPILOT_TARGET = true;

    /** What the operator's right bumper (stop shooter) also does.
     *  true  = stop shooter + indexer, then deploy the intake (ready to pick up again).
     *  false = stop shooter + indexer only.
     *  SET: KEEP true (driver preference).
     *  CHANGE WHEN: drivers want to stop shooting without dropping the intake. */
    public static final boolean DEPLOY_INTAKE_WHEN_STOPPING_SHOOTER = true;

    /** During AutoFire, bring the intake back to center after 3 s of shooting.
     *  true  = time-based retract. false = no time-based retract.
     *  SET: KEEP false. Use at most one of the two RETRACT_INTAKE_* switches.
     *  CHANGE WHEN: trying a retract strategy. Note: as written it re-schedules the retract every loop after 3 s. */
    public static final boolean RETRACT_INTAKE_WITH_TIME = false;

    /** During AutoFire, bring the intake back to center after the indexer has turned a set number of rotations.
     *  true  = rotation-based retract. false = no rotation-based retract.
     *  SET: KEEP false. Use at most one of the two RETRACT_INTAKE_* switches.
     *  CHANGE WHEN: trying a retract strategy. */
    public static final boolean RETRACT_INTAKE_USING_INDEXER_ROTATIONS = false;

    // Vision filters (see docs/vision-testing-protocol.md). These change the pose the robot drives on.
    // Each is A/B-tested against replayed match logs; flip one at a time.

    /** P1: Reject vision estimates whose 3D pose falls outside field boundaries.
     *  true  = reject out-of-bounds poses. false = 2026 behavior (no boundary check).
     *  SET: KEEP true. CHANGE WHEN: replay A/B testing the filter. */
    public static final boolean VISION_FIELD_BOUNDARY_REJECTION = true;

    /** P1: Theta stddev from a smooth LerpTable instead of the binary weight>0.9 threshold.
     *  true  = smooth curve. false = 2026 behavior (binary: >0.9 -> 10.0 rad, else 99999.0).
     *  SET: KEEP true. CHANGE WHEN: replay A/B testing the filter. */
    public static final boolean VISION_SMOOTH_THETA_STDDEV = true;

    /** P2: XY stddev from distance to the tag (meters) instead of the tag-area proxy.
     *  true  = distance LerpTable. false = 2026 area-based weight.
     *  SET: KEEP true. CHANGE WHEN: replay A/B testing the filter. */
    public static final boolean VISION_DISTANCE_BASED_STDDEV = true;

    /** P2: Use TAG_RANKINGS to zero-weight non-scoring tags (local estimator mode).
     *  true  = only scoring-zone tags trusted. false = 2026 behavior (all tags contribute).
     *  SET: KEEP false until TAG_RANKINGS is updated for 2027 and researched.
     *  CHANGE WHEN: replay A/B testing it with 2027 rankings. */
    public static final boolean VISION_TAG_RANKINGS_FILTER = false; // TODO do more research on this before using

    /** P3: Reject single-tag estimates with ambiguity score >= 0.2.
     *  true  = ambiguity filter active. false = 2026 behavior (no ambiguity threshold).
     *  SET: KEEP true. CHANGE WHEN: replay A/B testing the filter. */
    public static final boolean VISION_AMBIGUITY_THRESHOLD = true;
    //#endregion

    //#region 2. Mechanical protection
    // =========================================================================
    // 2. MECHANICAL PROTECTION - temporary while a mechanism is broken, missing or being worked on.
    //    COMPETITION: all false, unless that mechanism is physically off the robot.
    // =========================================================================

    /** Never move the intake's deploy/retract axis, and report it as always at target.
     *  true  = intake position locked (rollers can still run). false = normal intake.
     *  SET: COMPETITION false. TESTING true only while the deploy mechanism is unsafe to move.
     *  CHANGE WHEN: the intake deploy is broken or being worked on. */
    public static final boolean INTAKE_SAFTEY_MODE_NO_DEPLOY = false;

    /** Ignore every intake position command.
     *  true  = intake doesn't move. false = normal intake.
     *  SET: COMPETITION false. TESTING true only while the intake is broken or off the robot.
     *  CHANGE WHEN: the intake is broken, missing or being worked on. */
    public static final boolean DISABLE_INTAKE = false;

    /** Ignore every indexer command.
     *  true  = indexer never runs. false = normal indexer.
     *  SET: COMPETITION false (if the indexer is on the robot). TESTING true only while it's broken or missing.
     *  NOTE: currently true. Check before an event. */
    public static final boolean DISABLE_INDEXER = true;

    /** Ignore every hopper command.
     *  true  = hopper never runs. false = normal hopper.
     *  SET: COMPETITION false (if the hopper is on the robot). TESTING true only while it's broken or missing.
     *  NOTE: currently true. Check before an event. */
    public static final boolean DISABLE_HOPPER = true;
    //#endregion

    //#region 3. Settled performance
    // =========================================================================
    // 3. SETTLED PERFORMANCE - measured wins or harmless defaults. KEEP as set.
    //    Flip one only to chase a specific problem, then flip it back.
    //    Bench 2026-10-20 (notes/10-20/notes.md): together with the diagnostics below, these took the
    //    mean robot loop from 65 ms to 15.6 ms and the loops over 20 ms from 100 % to 7 %.
    // =========================================================================

    /** Throttle the diagnostic dashboard publishing in robotPeriodic to 10 Hz. Subsystem IO and the
     *  RobotTime clock stay 50 Hz. Real robot only: simulation always publishes every loop.
     *  true  = 10 Hz on the real robot. false = every loop (50 Hz).
     *  SET: KEEP true.
     *  CHANGE WHEN: a dashboard value needs to update faster than 10 Hz.
     *  MEASURED: PublishingMs 2.1 -> 0.7 ms per loop. */
    public static final boolean ROBOT_DASHBOARD_10_HZ = true;

    /** Throttle Telemetry.telemeterize's NT/Mechanism2d/custom-Hoot outputs to 10 Hz. Doesn't change CTRE
     *  odometry, the control-loop rate or automatic Phoenix signal capture. Real robot only: simulation
     *  always publishes every odometry update, so the sim field view stays smooth.
     *  true  = 10 Hz on the real robot. false = every odometry update.
     *  SET: KEEP true.
     *  CHANGE WHEN: you need the swerve dashboard widgets at full rate.
     *  MEASURED: too small to see in the main loop (it runs on CTRE's odometry thread); cheap to keep. */
    public static final boolean SWERVE_TELEMETRY_10_HZ = false;

    /** Suppress WPILib's repeated missing-axis/button/POV warnings. Controller alerts and logged
     *  capabilities remain; WPILib ignores this suppression under FMS.
     *  true  = quiet. false = WPILib's warning every few seconds per missing control.
     *  SET: KEEP true.
     *  CHANGE WHEN: never needed. The controller alerts already say what's missing.
     *  MEASURED: with QUIET_SCHEDULER_OVERRUN_WARNINGS, loop p95 35 -> 21.5 ms, worst 97 -> 61 ms.
     *  Console printing is expensive. */
    public static final boolean QUIET_JOYSTICK_WARNINGS = true;

    /** Raise only the scheduler diagnostic watchdog from 20 ms to 1 s. The robot period and outer
     *  watchdog stay 20 ms; Diagnostics/SchedulerOverrunCount still counts 20 ms misses.
     *  true  = no per-overrun epoch dump to the console. false = stock verbose dumps.
     *  SET: KEEP true.
     *  CHANGE WHEN: you want the per-command console dump for one overrun (LOG_SUBSYSTEM_TIMINGS usually
     *  answers the same question without the cost).
     *  MEASURED: see QUIET_JOYSTICK_WARNINGS. The dump causes the next overrun. */
    public static final boolean QUIET_SCHEDULER_OVERRUN_WARNINGS = true;

    /** Have DataLogManager also copy every NT change into the FRC_*.wpilog. The main AKit .wpilog and
     *  DriverStation logging remain.
     *  true  = NT duplicated into FRC_*.wpilog. false = not.
     *  SET: KEEP false. Use the akit_ log for analysis/replay.
     *  CHANGE WHEN: you need an NT value that AKit doesn't log (e.g. something a coprocessor publishes).
     *  MEASURED: maybe ~2 ms (background thread, so no timer of its own; within run-to-run noise). */
    public static final boolean LOG_NETWORKTABLES_TO_WPILOG = false;

    /** Build a request-map/string description at every motor.setControl call site for PowerTelemetry.
     *  Requests still run either way. Has no effect while ENABLE_POWER_TELEMETRY is false.
     *  true  = control requests described in the log. false = not.
     *  SET: KEEP false.
     *  CHANGE WHEN: debugging which control request a motor was given.
     *  MEASURED: switched off together with two others for ~5 ms total; it has no timer of its own. */
    public static final boolean POWER_REQUEST_DETAILS = false;

    /** Mirror the Tracer (Vision) timings into NT recursively every loop. Direct subsystem timings
     *  (LOG_SUBSYSTEM_TIMINGS) are unaffected.
     *  true  = mirror. false = no mirror.
     *  SET: KEEP false.
     *  CHANGE WHEN: you need the Tracer's sub-epochs live on a dashboard.
     *  MEASURED: TracerMirrorMs 3.8 ms per loop -> 0. */
    public static final boolean MIRROR_TRACER_TIMINGS = false;

    /** PowerTelemetry stops refreshing a motor that has reported a bad CAN status (e.g. RxTimeout) for 5 s,
     *  re-checking every 5 s, so an unplugged or dead motor stops costing time every loop.
     *  true  = skip absent motors. false = refresh every motor every loop.
     *  SET: KEEP true. Only matters while ENABLE_POWER_TELEMETRY is true.
     *  CHANGE WHEN: never needed. */
    public static final boolean SKIP_ABSENT_DEVICES = true;

    /** With COPROCESSOR_HEALTH_LOGGING on: discover Pi topics flat every 5 s and mirror at most 8 entries
     *  per loop, instead of a recursive sweep in 0.5 s bursts. A full sweep takes ceil(topics / 8) loops.
     *  true  = batched. false = recursive bursts.
     *  SET: KEEP true.
     *  CHANGE WHEN: Pi values in the log look too stale (each one updates once per full sweep).
     *  MEASURED: not yet. Every 10-20 run had it false, where the logger cost ~1.4 ms per loop. */
    public static final boolean BATCH_COPROCESSOR_HEALTH_LOGGING = true;
    //#endregion

    //#region 4. Diagnostics
    // =========================================================================
    // 4. DIAGNOSTICS - extra data that costs loop time. Off at competition (unless noted), on when you
    //    need that data. Turn on one at a time, and turn it back off when you're done.
    // =========================================================================

    /** PowerTelemetry: per-motor current, temperature, CAN health and request logging for every motor.
     *  Existing IO/control and AKit's built-in battery logging continue either way.
     *  true  = motor power/health in logs and the Health Check Robot section. false = bypassed entirely.
     *  SET: COMPETITION false. TESTING false; true when you need it.
     *  CHANGE WHEN: chasing brownouts, a hot or stalled motor, a motor dropping off CAN, battery draw.
     *  Pair it with POWER_TELEMETRY_10_HZ to cut its cost.
     *  MEASURED: the single biggest cost. PowerTelemetryMs ~20 ms per loop; the mean loop went 65 -> 33 ms
     *  with it off. */
    public static final boolean ENABLE_POWER_TELEMETRY = false;

    /** With ENABLE_POWER_TELEMETRY on: subscribe to ~14 status signals on every motor (all 16 CAN
     *  devices) and refresh/log them. Subscribing turns each signal's CAN frame on at Phoenix's default
     *  rate (mostly 100 Hz).
     *  true  = current/temperature/health signals (more CAN traffic). false = devices declared and config
     *  read once, but no status signals.
     *  SET: COMPETITION false. TESTING true together with ENABLE_POWER_TELEMETRY when you want motor data.
     *  CHANGE WHEN: same as ENABLE_POWER_TELEMETRY. Without this, PowerTelemetry has almost nothing to log. */
    public static final boolean POWER_TELEMETRY_SIGNALS = false;

    /** With ENABLE_POWER_TELEMETRY on: sample/log PowerTelemetry at 10 Hz instead of every loop. Not a
     *  CAN frame-rate change. Replay still consumes recorded inputs every loop.
     *  true  = 10 Hz (short current spikes can be missed). false = every loop.
     *  SET: true whenever ENABLE_POWER_TELEMETRY is true, unless you need every spike.
     *  CHANGE WHEN: chasing a current spike shorter than 100 ms.
     *  MEASURED: not yet. Should cut most of PowerTelemetry's ~20 ms; measure before relying on it in a match. */
    public static final boolean POWER_TELEMETRY_10_HZ = false;

    /** Mirror the Orange Pi health topics (/OrangePi/**) into the AKit log, for the Health Check's Orange
     *  Pi section on a match log (reboots, link flaps, camera drops). Pi publishers and the live Health
     *  Check work either way.
     *  true  = Pi health in match logs. false = live only.
     *  SET: COMPETITION true once BATCH_COPROCESSOR_HEALTH_LOGGING's cost is measured (it's the evidence
     *  for "why did vision drop in Q12"); false until then. TESTING false unless diagnosing a Pi.
     *  CHANGE WHEN: diagnosing a Pi/camera dropout after the fact.
     *  MEASURED: CoprocessorHealthLoggerMs ~1.4 ms per loop with batching off. */
    public static final boolean COPROCESSOR_HEALTH_LOGGING = false;

    /** Phoenix .hoot signal logging (automatic and explicit). The AKit .wpilog is unaffected.
     *  true  = .hoot logs for Tuner X / CTRE analysis. false = no .hoot.
     *  SET: COMPETITION false. TESTING false; true when you need it.
     *  CHANGE WHEN: tuning or debugging a CTRE device with Tuner X's log tools, or CTRE support asks for a .hoot.
     *  MEASURED: PhoenixReplayMs 1.2 ms per loop directly; mean loop -6 ms, partly noise. */
    public static final boolean PHOENIX_SIGNAL_LOGGING = false;

    /** Log how long each part of robotPeriodic and each subsystem's periodic() took, every loop, as
     *  RealOutputs/Timing/<Name>Ms (the Health Check's loop-time breakdown).
     *  true  = per-section timings in every log. false = none.
     *  SET: KEEP true for now, competition included: it's how a slow match gets diagnosed afterwards.
     *  CHANGE WHEN: the loop is stable for a few events and you want its (small) cost back.
     *  MEASURED: on in every 10-20 run, so its own cost wasn't isolated; small (a timestamp and a log entry per section). */
    public static final boolean LOG_SUBSYSTEM_TIMINGS = true;

    /** Publish per-filter NT/log values for every vision sample (tag count, area, pixel offset, aspect
     *  ratio, trust pre/post, distance, velocity weights, rejection counters, correction magnitude,
     *  XY/theta stddevs). Logging only; doesn't change the pose.
     *  true  = full vision debug data. false = 2026 minimal logging.
     *  SET: KEEP true, competition included: match logs are what the vision filters get tuned on.
     *  CHANGE WHEN: Vision.periodic shows up as a large share of the loop and you're not tuning vision. */
    public static final boolean VISION_EXTENDED_NT_LOGGING = true;

    /** Debug printing in PointAtTarget, RumbleJoystick and FinneyLogger.
     *  true  = prints to the console. false = quiet.
     *  SET: COMPETITION false. TESTING false; true briefly when you need it.
     *  CHANGE WHEN: debugging one of those classes on the bench. Console printing costs loop time
     *  (see QUIET_JOYSTICK_WARNINGS). */
    public static final boolean ENABLE_SUBSYSTEM_DEBUG_PRINTS = false;

    /** Publish each drive motor's stator/supply/torque current to SmartDashboard every loop.
     *  true  = 12 extra dashboard values per loop. false = only the summed current.
     *  SET: COMPETITION false. TESTING false; true when you need it.
     *  CHANGE WHEN: one swerve module draws more current than the others. */
    public static final boolean PUBLISH_INDIVIDUAL_DRIVE_CURRENTS = false;

    /** Shooter test controls on joystick port 2 (test RPS, stop, preset speeds).
     *  true  = port-2 bindings active and a missing port-2 controller is reported. false = no bindings.
     *  SET: COMPETITION false. TESTING true when tuning the shooter with a third controller.
     *  CHANGE WHEN: shooter tuning sessions.
     *  NOTE: currently true. Set false before an event. */
    public static final boolean ENABLE_SHOOTER_TEST_CONTROLLER = true;
    //#endregion

    //#region 5. Experiments to retest
    // =========================================================================
    // 5. EXPERIMENTS TO RETEST - CAN-load switches (docs/can-bus-load-ab-test.md). On 2026-10-20 none of
    //    them moved roboRIO CAN utilization (64-70 % idle, 74-80 % enabled in every run): the drive base
    //    dominates that bus. Once the drive base is on the CANivore, the mechanisms are most of what's
    //    left on the roboRIO bus, so retest these then. Settle each into category 3, or remove it.
    //    Until then: leave them as they are.
    // =========================================================================

    /** Status-signal rate (Hz) for the Hopper, Indexer, Pickup and Intake-pickup motors: the signals
     *  their IO classes read and PowerTelemetry's. 0 = leave Phoenix's default (usually 100 Hz).
     *  The swerve modules and the shooter are never touched (odometry and shooter lock need their own
     *  100 Hz+ rates).
     *  20 = slower mechanism signals (less CAN). 0 = Phoenix defaults.
     *  SET: KEEP 20 until retested.
     *  CHANGE WHEN: a mechanism's control or sensing looks laggy (20 Hz = a new reading every 50 ms).
     *  MEASURED: 20 in every 10-20 run, so not A/B tested yet. */
    public static final double MECHANISM_STATUS_SIGNAL_HZ = 20.0;

    /** On those same four mechanism motors, call optimizeBusUtilization() once every signal the code reads
     *  has an explicit rate (MECHANISM_STATUS_SIGNAL_HZ, or 50 Hz if that is 0). Everything else the device
     *  sends slows to 4 Hz on Phoenix 2026 (or 0 Hz with ZERO_UNUSED_MECHANISM_STATUS_SIGNALS).
     *  true  = optimized. false = no optimization.
     *  SET: KEEP true until retested.
     *  CHANGE WHEN: Tuner X or a log is missing a signal from one of those motors.
     *  MEASURED: true in every 10-20 run, so not A/B tested yet. */
    public static final boolean OPTIMIZE_BUS_UTILIZATION = true;

    /** With OPTIMIZE_BUS_UTILIZATION: unused signals on the simple mechanisms go to 0 Hz instead of 4 Hz.
     *  true  = 0 Hz. false = Phoenix 2026's 4 Hz.
     *  SET: KEEP true until retested.
     *  CHANGE WHEN: Tuner X shows stale values for those motors while you're debugging them.
     *  MEASURED: no effect (CAN idle 70 -> 67 %, within the ±3-point run-to-run noise). */
    public static final boolean ZERO_UNUSED_MECHANISM_STATUS_SIGNALS = true;

    /** Give the shooter's diagnostic currents/voltage/temperature explicit slower rates. All three
     *  velocities, leader error/reference and leader follower-output signals stay at 100 Hz. Shared
     *  status frames run at the fastest member's rate, so it may save nothing.
     *  true  = slower shooter diagnostics. false = Phoenix defaults.
     *  SET: KEEP true until retested.
     *  CHANGE WHEN: you need shooter current at full rate (spin-up/jam diagnosis).
     *  MEASURED: no effect (CAN idle 69 -> 70 %). */
    public static final boolean LOW_RATE_SHOOTER_DIAGNOSTICS = true;
    //#endregion

    //#region 6. Unused
    // =========================================================================
    // 6. UNUSED - read nowhere in the code; changing them does nothing. Candidates for removal.
    // =========================================================================

    /** Not read anywhere. Changing it does nothing. Candidate for removal. */
    public static final boolean ENABLE_SUBSYSTEM_NT_LOGGING = true;

    /** Not read anywhere (the brake-while-shooting behavior isn't implemented). Changing it does nothing.
     *  Candidate for removal, or implement it. */
    public static final boolean BRAKE_WHILE_SHOOTING = false;

    /** Not read anywhere (sim shooter PIDs are not switched). Changing it does nothing. Candidate for removal. */
    public static final boolean CUSTOM_SIMULATION_SHOOTER_PIDS = false;
    //#endregion
}
