package frc.robot.constants;

/**
 * Feature switches to enable or disable robot features
 * All fields should be public static final booleans
 */
public class FeatureSwitches {

    public static final boolean ENABLE_SUBSYSTEM_NT_LOGGING = true;
    public static final boolean ENABLE_SUBSYSTEM_DEBUG_PRINTS = false;
    public static final boolean BRAKE_WHILE_SHOOTING = false;
    public static final boolean DISABLE_VISION_ODOM_NEAR_AUTOPILOT_TARGET = true;
    public static final boolean RETRACT_INTAKE_USING_INDEXER_ROTATIONS = false;
    public static final boolean RETRACT_INTAKE_WITH_TIME = false;
    public static final boolean CUSTOM_SIMULATION_SHOOTER_PIDS = false;
    public static final boolean DEPLOY_INTAKE_WHEN_STOPPING_SHOOTER = true;

    // Mechanical protections
    public static final boolean INTAKE_SAFTEY_MODE_NO_DEPLOY = false;
    public static final boolean DISABLE_INTAKE = false;
    public static final boolean DISABLE_INDEXER = true;
    public static final boolean DISABLE_HOPPER = true;

    // Drive base
    public static final boolean PUBLISH_INDIVIDUAL_DRIVE_CURRENTS = false;

    // -------------------------------------------------------------------------
    // CAN bus load and loop time A/B switches (see docs/can-bus-load-ab-test.md)
    // -------------------------------------------------------------------------
    // Ruckus 2026 logs: the roboRIO CAN bus ran at ~65% with the robot DISABLED and still (~77%
    // enabled, 100% at peaks), and the robot loop took ~38 ms against its 20 ms period, ~90% of it
    // robot code. These switches let each suspect be turned off or down one at a time and compared
    // on Health Check ("CAN utilization while disabled", "Mean robot loop time"). Every default
    // below is the behavior the robot had at Ruckus; flip one, redeploy, compare.

    /** Subscribe PowerTelemetry to its ~14 status signals on every motor (all 16 CAN devices) and
     *  refresh/log them each loop. Subscribing turns each signal's CAN frame on at Phoenix's default
     *  rate (mostly 100 Hz). OFF = devices are still declared and their configuration read once, but
     *  no status signals, so no extra bus traffic and no per-loop reads. Motor current, temperature and
     *  health then vanish from logs: use for testing, not for matches. */
    public static final boolean POWER_TELEMETRY_SIGNALS = true;

    /** Status-signal rate (Hz) for the Hopper, Indexer, Pickup and Intake-pickup motors: the signals
     *  their IO classes read and PowerTelemetry's. 0 = leave Phoenix's default (usually 100 Hz).
     *  Try 20. The swerve modules and the shooter are never touched (odometry and shooter lock need
     *  their own 100 Hz+ rates). */
    public static final double MECHANISM_STATUS_SIGNAL_HZ = 0.0;

    /** On those same four mechanism motors, call optimizeBusUtilization() once every signal the code
     *  reads has an explicit rate (MECHANISM_STATUS_SIGNAL_HZ, or 50 Hz if that is 0). Everything else
     *  the device would send (accelerations, rotor velocity, ...) stops. OFF = no change. */
    public static final boolean OPTIMIZE_BUS_UTILIZATION = false;

    /** PowerTelemetry stops refreshing a motor that has reported a bad CAN status (e.g. RxTimeout)
     *  for 5 s, re-checking every 5 s, so an unplugged or dead motor stops costing time every loop.
     *  OFF = every motor is refreshed every loop. */
    public static final boolean SKIP_ABSENT_DEVICES = false;

    /** Log how long each part of robotPeriodic and each subsystem's periodic() took, every loop, as
     *  RealOutputs/Timing/<Name>Ms, and mirror the Tracer (Vision) timings into the log. Shows in the
     *  log where the ~38 ms loop goes. Costs a little itself, so it is OFF until you are measuring. */
    public static final boolean LOG_SUBSYSTEM_TIMINGS = false;

    // -------------------------------------------------------------------------
    // Vision A/B Test Switches (all OFF by default - baseline is 2026 behavior)
    // -------------------------------------------------------------------------
    // Enable/disable individual filters independently so each can be measured
    // against the baseline in AdvantageScope. See docs/vision-testing-protocol.md.

    /** P1: Reject vision estimates whose 3D pose falls outside field boundaries.
     *  OFF = 2026 behavior (no boundary check). ON = reject out-of-bounds poses. */
    public static final boolean VISION_FIELD_BOUNDARY_REJECTION = true;

    /** P1: Use a smooth LerpTable for theta stddev instead of the binary weight>0.9 threshold.
     *  OFF = 2026 behavior (binary: >0.9 -> 10.0 rad, else 99999.0). ON = smooth curve. */
    public static final boolean VISION_SMOOTH_THETA_STDDEV = true;

    /** P2: Publish per-filter NT topics for every vision sample (tag count, area,
     *  pixel offset, aspect ratio, trust pre/post, avg distance, velocity weights,
     *  rejection counters, correction magnitude, XY/theta stddevs).
     *  ON by default - logging does not affect robot behavior, and the data is
     *  needed to scientifically A/B test the other vision switches.
     *  OFF = 2026 minimal logging. ON = full debug logging. */
    public static final boolean VISION_EXTENDED_NT_LOGGING = true;

    /** P2: Use TAG_RANKINGS to zero-weight non-scoring tags (local estimator mode).
     *  OFF = 2026 behavior (all tags contribute). ON = only scoring-zone tags trusted. */
    public static final boolean VISION_TAG_RANKINGS_FILTER = false; // TODO do more research on this before using

    /** P2: Use distance-based stddev (meters from tag) instead of area-proxy.
     *  OFF = 2026 area-based weight. ON = distance LerpTable for XY stddev. */
    public static final boolean VISION_DISTANCE_BASED_STDDEV = true;

    /** P3: Reject single-tag estimates with ambiguity score >= 0.2.
     *  OFF = 2026 behavior (no ambiguity threshold). ON = ambiguity filter active. */
    public static final boolean VISION_AMBIGUITY_THRESHOLD = true;
}
