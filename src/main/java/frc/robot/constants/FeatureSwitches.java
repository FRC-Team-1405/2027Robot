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
}
