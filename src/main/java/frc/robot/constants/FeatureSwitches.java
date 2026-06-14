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

    // Drive base
    public static final boolean PUBLISH_INDIVIDUAL_DRIVE_CURRENTS = false;

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
