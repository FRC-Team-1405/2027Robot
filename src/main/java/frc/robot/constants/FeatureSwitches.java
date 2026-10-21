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

    //#region CanBusLoadSwitches
    // -------------------------------------------------------------------------
    // CAN bus load and loop time A/B switches (see docs/can-bus-load-ab-test.md)
    // -------------------------------------------------------------------------
    // Ruckus 2026 logs: the roboRIO CAN bus ran at ~65% with the robot DISABLED and still (~77%
    // enabled, 100% at peaks), and the robot loop took ~38 ms against its 20 ms period, ~90% of it
    // robot code. These switches let each suspect be turned off or down one at a time and compared
    // on Health Check ("CAN utilization while disabled", "Mean robot loop time"). Every default
    // started from the Ruckus behavior; the values below include ongoing bench experiments.
    // Flip one, redeploy, compare Metadata/FeatureSwitches and the resulting metrics.

    /** Subscribe PowerTelemetry to its ~14 status signals on every motor (all 16 CAN devices) and
     *  refresh/log them each loop. Subscribing turns each signal's CAN frame on at Phoenix's default
     *  rate (mostly 100 Hz). OFF = devices are still declared and their configuration read once, but
     *  no status signals, so no extra bus traffic and no per-loop reads. Motor current, temperature and
     *  health then vanish from logs: use for testing, not for matches. */
    public static final boolean POWER_TELEMETRY_SIGNALS = false;

    /** Status-signal rate (Hz) for the Hopper, Indexer, Pickup and Intake-pickup motors: the signals
     *  their IO classes read and PowerTelemetry's. 0 = leave Phoenix's default (usually 100 Hz).
     *  Try 20. The swerve modules and the shooter are never touched (odometry and shooter lock need
     *  their own 100 Hz+ rates). */
    public static final double MECHANISM_STATUS_SIGNAL_HZ = 0.0;

    /** On those same four mechanism motors, call optimizeBusUtilization() once every signal the code
     *  reads has an explicit rate (MECHANISM_STATUS_SIGNAL_HZ, or 50 Hz if that is 0). Everything else
     *  the device would send slows to 4 Hz on Phoenix 2026 (or 0 Hz with the explicit zero switch).
     *  OFF = no optimization. */
    public static final boolean OPTIMIZE_BUS_UTILIZATION = true;

    /** PowerTelemetry stops refreshing a motor that has reported a bad CAN status (e.g. RxTimeout)
     *  for 5 s, re-checking every 5 s, so an unplugged or dead motor stops costing time every loop.
     *  OFF = every motor is refreshed every loop. */
    public static final boolean SKIP_ABSENT_DEVICES = true;

    /** Log how long each part of robotPeriodic and each subsystem's periodic() took, every loop, as
     *  RealOutputs/Timing/<Name>Ms, and mirror the Tracer (Vision) timings into the log. Shows in the
     *  log where the ~38 ms loop goes. Costs a little itself, so it is OFF until you are measuring. */
    public static final boolean LOG_SUBSYSTEM_TIMINGS = true;

    // CPU/logging experiments. Defaults preserve the current beta behavior.
    /** OFF bypasses PowerTelemetry initialization, request decoding and periodic logging entirely.
     *  Existing IO/control and built-in AKit battery logging continue. Diagnostic test only. */
    public static final boolean ENABLE_POWER_TELEMETRY = false;
    /** Sample/log PowerTelemetry at 10 Hz instead of every loop (not a CAN frame-rate change).
     *  Short current spikes can be missed. Replay still consumes recorded inputs every loop. */
    public static final boolean POWER_TELEMETRY_10_HZ = false;
    /** OFF removes request-map/string decoding at motor.setControl call sites. Requests still run. */
    public static final boolean POWER_REQUEST_DETAILS = true;
    /** OFF removes OrangePi -> AKit mirroring; Pi NT publishers and live health still run. */
    public static final boolean COPROCESSOR_HEALTH_LOGGING = true;
    /** Use a flat topic discovery every 5 s and mirror at most 8 entries per robot loop.
     *  Avoids recursive 0.5 s bursts; a full sweep takes ceil(topic count / 8) loops. */
    public static final boolean BATCH_COPROCESSOR_HEALTH_LOGGING = false;
    /** OFF keeps direct subsystem timings but removes the every-loop recursive Tracer NT mirror. */
    public static final boolean MIRROR_TRACER_TIMINGS = true;
    /** OFF stops DataLogManager duplicating all NT changes into FRC_*.wpilog. The main AKit
     *  .wpilog and DriverStation logging remain. Select the akit_ log for analysis/replay. */
    public static final boolean LOG_NETWORKTABLES_TO_WPILOG = false;
    /** OFF disables automatic and explicit Phoenix .hoot logging. AKit .wpilog stays enabled. */
    public static final boolean PHOENIX_SIGNAL_LOGGING = false;
    /** Throttle only Telemetry.telemeterize's NT/Mechanism2d/custom-Hoot outputs to 10 Hz.
     *  Does not change CTRE odometry, control-loop frequency or automatic Phoenix signal capture. */
    public static final boolean SWERVE_TELEMETRY_10_HZ = true;
    /** Throttle diagnostic dashboard publishing to 10 Hz; subsystem IO and RobotTime clock stay 50 Hz. */
    public static final boolean ROBOT_DASHBOARD_10_HZ = true;

    // Additional CAN experiments; independent of CPU-side sampling.
    /** Phoenix 2026 defaults unused optimized signals to 4 Hz. With OPTIMIZE_BUS_UTILIZATION,
     *  explicitly use 0 Hz on the already-tuned simple mechanisms only. */
    public static final boolean ZERO_UNUSED_MECHANISM_STATUS_SIGNALS = true;
    /** Give shooter diagnostic currents/voltage/temperature explicit slower rates. All three
     *  velocities, leader error/reference, and leader follower-output signals stay at 100 Hz.
     *  Shared status frames run at the fastest member's rate, so savings must be measured. */
    public static final boolean LOW_RATE_SHOOTER_DIAGNOSTICS = true;
    //#endregion

    //#region VisionTestSwitches
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
    //#endregion
}
