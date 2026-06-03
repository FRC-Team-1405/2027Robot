package frc.robot.subsystems;

import static edu.wpi.first.units.Units.MetersPerSecond;
import static edu.wpi.first.units.Units.RadiansPerSecond;
import static edu.wpi.first.units.Units.RotationsPerSecond;

import java.util.function.Supplier;

import com.ctre.phoenix6.swerve.SwerveModule.DriveRequestType;
import com.ctre.phoenix6.swerve.SwerveRequest;

import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Rotation2d;
import edu.wpi.first.math.geometry.Translation2d;
import edu.wpi.first.math.kinematics.ChassisSpeeds;
import edu.wpi.first.networktables.NetworkTableInstance;
import edu.wpi.first.networktables.StructPublisher;
import edu.wpi.first.wpilibj.smartdashboard.Mechanism2d;
import edu.wpi.first.wpilibj.smartdashboard.MechanismLigament2d;
import edu.wpi.first.wpilibj.smartdashboard.MechanismRoot2d;
import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import edu.wpi.first.wpilibj.util.Color;
import edu.wpi.first.wpilibj.util.Color8Bit;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.Commands;
import edu.wpi.first.wpilibj2.command.button.CommandXboxController;
import edu.wpi.first.wpilibj2.command.button.Trigger;
import frc.robot.generated.TunerConstants;
import frc.robot.lib.FinneyLogger;

/**
 * Additional features and utilities for the swerve drivetrain.
 * Handles aim calculations with velocity compensation and visualization.
 */
public class SwerveFeatures {
    FinneyLogger fLogger = new FinneyLogger("SwerveFeatures");

    private static double DEADBAND = 0.1; // Deadband for joystick input detection

    private final CommandSwerveDrivetrain m_drivetrain;

    public static double MaxSpeed = 1.0 * TunerConstants.kSpeedAt12Volts.in(MetersPerSecond); // kSpeedAt12Volts desired
                                                                                              // top
    // speed
    public static double MaxAngularRate = RotationsPerSecond.of(1.0).in(RadiansPerSecond); // 3/4 of a rotation per
                                                                                           // second
    // max angular velocity

    /* Setting up bindings for necessary control of the swerve drive platform */
    public static final SwerveRequest.FieldCentric drive = new SwerveRequest.FieldCentric()
            .withDeadband(MaxSpeed * 0.1).withRotationalDeadband(MaxAngularRate * 0.1) // Add a 10% deadband
            .withDriveRequestType(DriveRequestType.OpenLoopVoltage); // Use open-loop control for drive motors
    public static final SwerveRequest.SwerveDriveBrake brake = new SwerveRequest.SwerveDriveBrake();
    public static final SwerveRequest.PointWheelsAt point = new SwerveRequest.PointWheelsAt();

    /* Mechanism2d for visualizing aim angles */
    private final Mechanism2d m_aimMechanism = new Mechanism2d(3, 3);
    private final MechanismRoot2d m_aimRoot = m_aimMechanism.getRoot("Robot", 1.5, 1.5);
    // Blue line: Standard angle to target (no compensation)
    private final MechanismLigament2d m_standardAngleLigament = m_aimRoot
            .append(new MechanismLigament2d("StandardAngle", 1.0, 0, 6, new Color8Bit(Color.kBlue)));
    // Red line: Velocity-compensated angle (with lead)
    private final MechanismLigament2d m_compensatedAngleLigament = m_aimRoot
            .append(new MechanismLigament2d("CompensatedAngle", 1.0, 0, 8, new Color8Bit(Color.kRed)));
    // Green line: Robot velocity vector (scaled for visibility)
    private final MechanismLigament2d m_velocityVectorLigament = m_aimRoot
            .append(new MechanismLigament2d("VelocityVector", 0, 0, 4, new Color8Bit(Color.kGreen)));
    // Track last update time for auto-clearing
    private double m_lastAimUpdateTime = 0.0;
    private static final double AIM_VISUALIZATION_TIMEOUT = 0.5; // seconds

    // State for acceleration calculation
    private double m_lastSpeed = 0.0;
    private double m_lastSpeedTimestamp = -1.0;

    /* Publisher for estimated aim point pose */
    private final StructPublisher<Pose2d> m_estimatedAimPointPublisher = NetworkTableInstance.getDefault()
            .getStructTopic("Drivetrain/EstimatedAimPoint", Pose2d.struct).publish();

    private final StructPublisher<Pose2d> m_estimatedAimPointPublisher_velocityCompensated = NetworkTableInstance
            .getDefault()
            .getStructTopic("Drivetrain/EstimatedAimPoint_VelocityCompensated", Pose2d.struct).publish();

    // TODO: Replace this sample lookup table with actual measured data
    // TODO: move this into the shooter subsystem
    /**
     * Array of {distance, time} pairs, sorted by distance
     * Example: {{1.0, 0.3}, {2.0, 0.5}, {3.0, 0.65}, {4.0, 0.78}}
     */
    private double[][] flightTimeLookup = {
            { 1.0, 0.30 }, // At 1m, takes 0.30s
            { 2.0, 0.48 }, // At 2m, takes 0.48s
            { 3.0, 0.62 }, // At 3m, takes 0.62s
            { 4.0, 0.74 }, // At 4m, takes 0.74s
            { 5.0, 0.85 } // At 5m, takes 0.85s
    };

    /**
     * Constructs a SwerveFeatures object with the given drivetrain.
     * 
     * @param drivetrain The CommandSwerveDrivetrain to provide features for
     */
    public SwerveFeatures(CommandSwerveDrivetrain drivetrain) {
        m_drivetrain = drivetrain;
        initAimVisualization();
    }

    /**
     * Initialize the aim visualization mechanism and publish to SmartDashboard
     */
    private void initAimVisualization() {
        SmartDashboard.putData("Aim Visualization", m_aimMechanism);
    }

    /**
     * Clear the aim visualization by setting all ligament lengths to zero.
     * Call this when aim calculations are not actively being used.
     */
    public void clearAimVisualization() {
        m_standardAngleLigament.setLength(0);
        m_compensatedAngleLigament.setLength(0);
        m_velocityVectorLigament.setLength(0);
    }

    /**
     * Should be called periodically to handle auto-clearing of visualizations.
     * Call this from the drivetrain's periodic() method.
     */
    public void periodic() {
        // Auto-clear aim visualization if not used recently
        double currentTime = edu.wpi.first.wpilibj.Timer.getFPGATimestamp();
        if (m_lastAimUpdateTime > 0 && (currentTime - m_lastAimUpdateTime) > AIM_VISUALIZATION_TIMEOUT) {
            clearAimVisualization();
            m_lastAimUpdateTime = 0.0; // Reset so we don't keep clearing
        }

        publishRobotVelocity();
        // publishRobotAcceleration();
        // Publish command NAME only — do NOT use putData with a live Command object.
        // putData creates a bidirectional .running property that can cancel the command
        // when the NT entry retains a stale value from the previous command at this
        // key.
        if (m_drivetrain != null && m_drivetrain.getCurrentCommand() != null) {
            SmartDashboard.putString("Commands/SwerveDriveCommand", m_drivetrain.getCurrentCommand().getName());
        }
    }

    public static Command teleopDriveCommand(CommandSwerveDrivetrain drivetrain, MoveMode moveMode,
            final CommandXboxController joystick) {
        return drivetrain.applyRequest(() -> teleopDriveRequest(drivetrain, moveMode, joystick));
    }

    /**
     * Calculates the angle from the robot to a target pose.
     * Returns the angle in field coordinates, adjusted for operator perspective.
     * 
     * @param targetPose The target pose (should be already flipped for alliance if
     *                   needed)
     * @return The angle the robot should face, relative to operator perspective
     */
    public Rotation2d getAngleToTarget(Pose2d targetPose) {
        Pose2d currentPose = m_drivetrain.getState().Pose;
        Rotation2d fieldAngle = targetPose.getTranslation().minus(currentPose.getTranslation()).getAngle();

        // if (DriverStation.getAlliance().orElse(Alliance.Blue) == Alliance.Red) {
        // fieldAngle = AllianceSymmetry.flip(fieldAngle);
        // }
        fLogger.log("Angle to target (field coords): " + fieldAngle.getDegrees() + " deg");

        // Update visualization - show standard angle in blue
        m_standardAngleLigament.setLength(1.0); // Make visible
        m_standardAngleLigament.setAngle(fieldAngle.getDegrees() + 90);
        m_compensatedAngleLigament.setLength(0); // Hide compensated angle
        m_velocityVectorLigament.setLength(0); // Hide velocity vector

        // Track update time for auto-clearing
        m_lastAimUpdateTime = edu.wpi.first.wpilibj.Timer.getFPGATimestamp();

        return fieldAngle;
    }

    /**
     * Calculates the angle from the robot to a target pose, accounting for the
     * robot's velocity.
     * Uses a lookup table of distances and flight times for more accurate
     * interpolation.
     * This is the most accurate method for accounting for varying launch angles at
     * different distances.
     * 
     * The lookup table should contain actual measured flight times at various
     * distances.
     * The method will interpolate between the nearest data points.
     * 
     * @param targetPose The target pose (should be already flipped for
     *                   alliance if needed)
     * @return The angle the robot should face to hit the target, accounting for
     *         robot velocity, this is a field-relative angle adjusted for driver
     *         perspective
     */
    public Rotation2d getAngleToTargetWithVelocityCompensation(Pose2d targetPose) {
        Pose2d currentPose = m_drivetrain.getState().Pose;
        ChassisSpeeds currentSpeeds = m_drivetrain.getState().Speeds;

        // Convert robot-relative speeds to field-relative speeds
        ChassisSpeeds fieldRelativeSpeeds = ChassisSpeeds.fromRobotRelativeSpeeds(
                currentSpeeds.vxMetersPerSecond,
                currentSpeeds.vyMetersPerSecond,
                currentSpeeds.omegaRadiansPerSecond,
                currentPose.getRotation());

        // Get the vector from robot to target
        double dx = targetPose.getX() - currentPose.getX();
        double dy = targetPose.getY() - currentPose.getY();
        double distanceToTarget = Math.hypot(dx, dy);

        // Calculate standard angle (no compensation) for visualization
        Rotation2d standardAngleVisualization = new Rotation2d(dx, dy);
        Rotation2d standardAngle = standardAngleVisualization;

        // NOTE: No alliance flip needed here. The caller is responsible for passing a
        // targetPose already flipped to the correct alliance side. dx/dy are therefore
        // already in the correct field-relative frame. Flipping again would invert the
        // angle and point the robot backwards on red alliance.

        // Interpolate flight time from lookup table
        double timeToTarget = interpolateFlightTime(distanceToTarget, flightTimeLookup);

        // Calculate where to aim accounting for robot's motion
        // We subtract the velocity because we're finding where to aim NOW
        // so that the projectile lands where the target is AFTER the flight time
        double compensatedX = dx - (fieldRelativeSpeeds.vxMetersPerSecond * timeToTarget);
        double compensatedY = dy - (fieldRelativeSpeeds.vyMetersPerSecond * timeToTarget);

        // Calculate the angle to the compensated position.
        // Again, no alliance flip — same reasoning as above; the vector is already in
        // the correct field frame because targetPose was pre-flipped by the caller.
        Rotation2d fieldAngleVisualization = new Rotation2d(compensatedX, compensatedY);
        Rotation2d fieldAngle = fieldAngleVisualization;

        // Update visualization
        // Blue line: Standard angle (no compensation)
        m_standardAngleLigament.setLength(1.0); // Make visible
        m_standardAngleLigament.setAngle(standardAngle.getDegrees() + 90);
        m_estimatedAimPointPublisher_velocityCompensated.set(new Pose2d(
                new Translation2d(distanceToTarget,
                        standardAngleVisualization).plus(currentPose.getTranslation()),
                standardAngleVisualization));

        // Red line: Compensated angle (with lead)
        m_compensatedAngleLigament.setLength(1.0); // Make visible
        m_compensatedAngleLigament.setAngle(fieldAngle.getDegrees() + 90);

        // Green line: Robot velocity vector (scaled for visibility) - use
        // field-relative speeds
        double velocityMagnitude = Math.hypot(fieldRelativeSpeeds.vxMetersPerSecond,
                fieldRelativeSpeeds.vyMetersPerSecond);
        double velocityAngle = Math.toDegrees(
                Math.atan2(fieldRelativeSpeeds.vyMetersPerSecond, fieldRelativeSpeeds.vxMetersPerSecond));
        m_velocityVectorLigament.setLength(velocityMagnitude * 0.3); // Scale for visibility
        m_velocityVectorLigament.setAngle(velocityAngle + 90);

        // Calculate and publish estimated aim point pose
        // This is where the projectile is expected to land based on the compensated
        // angle and distance
        double compensatedDistance = Math.hypot(compensatedX, compensatedY);
        Translation2d aimPointTranslation = new Translation2d(compensatedDistance,
                fieldAngleVisualization)
                .plus(currentPose.getTranslation());
        Pose2d estimatedAimPoint = new Pose2d(aimPointTranslation, fieldAngle);
        m_estimatedAimPointPublisher.set(estimatedAimPoint);

        // Track update time for auto-clearing
        m_lastAimUpdateTime = edu.wpi.first.wpilibj.Timer.getFPGATimestamp();

        fLogger.log(String.format(
                "Vel-comp: %.1f°, standardAngle: %.1f° (dist: %.2fm, time: %.3fs, field vel: [%.2f, %.2f] m/s, lead: [%.3f, %.3f] m)",
                fieldAngle.getDegrees(),
                standardAngle.getDegrees(),
                distanceToTarget,
                timeToTarget,
                fieldRelativeSpeeds.vxMetersPerSecond,
                fieldRelativeSpeeds.vyMetersPerSecond,
                fieldRelativeSpeeds.vxMetersPerSecond * timeToTarget,
                fieldRelativeSpeeds.vyMetersPerSecond * timeToTarget));

        return fieldAngle;
    }

    /**
     * Sets the flight time lookup table for projectile calculations.
     * 
     * @param lookupTable Array of {distance, time} pairs, sorted by distance
     *                    ascending
     */
    public void setFlightTimeLookup(double[][] lookupTable) {
        this.flightTimeLookup = lookupTable;
    }

    /**
     * Helper method to interpolate flight time from a distance-time lookup table.
     * Uses linear interpolation between the two nearest data points.
     * Extrapolates linearly if the distance is outside the table range.
     * 
     * @param distance    The distance to the target in meters
     * @param lookupTable Array of {distance, time} pairs, sorted by distance
     *                    ascending
     * @return The interpolated flight time in seconds
     */
    private double interpolateFlightTime(double distance, double[][] lookupTable) {
        // Handle edge cases
        if (lookupTable == null || lookupTable.length == 0) {
            fLogger.log("Warning: Empty lookup table, using default time estimate");
            return distance / 5.0; // Fallback: assume 5 m/s average
        }

        if (lookupTable.length == 1) {
            // Only one data point, use linear scaling
            return lookupTable[0][1] * (distance / lookupTable[0][0]);
        }

        // Check if distance is below the first entry (extrapolate downward)
        if (distance <= lookupTable[0][0]) {
            double d0 = lookupTable[0][0];
            double t0 = lookupTable[0][1];
            double d1 = lookupTable[1][0];
            double t1 = lookupTable[1][1];
            return t0 + (distance - d0) * (t1 - t0) / (d1 - d0);
        }

        // Check if distance is above the last entry (extrapolate upward)
        int lastIdx = lookupTable.length - 1;
        if (distance >= lookupTable[lastIdx][0]) {
            double d0 = lookupTable[lastIdx - 1][0];
            double t0 = lookupTable[lastIdx - 1][1];
            double d1 = lookupTable[lastIdx][0];
            double t1 = lookupTable[lastIdx][1];
            return t1 + (distance - d1) * (t1 - t0) / (d1 - d0);
        }

        // Find the two points to interpolate between
        for (int i = 0; i < lookupTable.length - 1; i++) {
            double d0 = lookupTable[i][0];
            double d1 = lookupTable[i + 1][0];

            if (distance >= d0 && distance <= d1) {
                double t0 = lookupTable[i][1];
                double t1 = lookupTable[i + 1][1];

                // Linear interpolation
                double t = t0 + (distance - d0) * (t1 - t0) / (d1 - d0);
                return t;
            }
        }

        // Should never reach here, but provide fallback
        fLogger.log("Warning: Interpolation failed, using fallback");
        return distance / 5.0;
    }

    public static double getRobotVelocity(CommandSwerveDrivetrain drivetrain) {
        ChassisSpeeds currentSpeeds = drivetrain.getState().Speeds;
        return Math.hypot(currentSpeeds.vxMetersPerSecond, currentSpeeds.vyMetersPerSecond);
    }

    public static double getRobotAngularVelocity(CommandSwerveDrivetrain drivetrain) {
        ChassisSpeeds currentSpeeds = drivetrain.getState().Speeds;
        return currentSpeeds.omegaRadiansPerSecond;
    }

    /**
     * Calculate and publish the robot's overall translational velocity (m/s) to
     * SmartDashboard under the "SwerveDrive/" namespace.
     */
    public void publishRobotVelocity() {
        try {
            SmartDashboard.putNumber("SwerveDrive/Velocity", getRobotVelocity(m_drivetrain));
            SmartDashboard.putNumber("SwerveDrive/AngularVelocity", getRobotAngularVelocity(m_drivetrain));
        } catch (Exception ex) {
            // In case drivetrain state is not available yet, avoid crashing
            fLogger.log("publishRobotVelocity: failed to read drivetrain state: %s", ex.getMessage());
        }
    }

    /**
     * Calculate and publish the robot's overall translational acceleration (m/s²)
     * to SmartDashboard under the "SwerveDrive/" namespace.
     * Uses finite difference (Δspeed / Δtime) from the previous periodic call.
     */
    public void publishRobotAcceleration() {
        try {
            ChassisSpeeds currentSpeeds = m_drivetrain.getState().Speeds;
            double speed = Math.hypot(currentSpeeds.vxMetersPerSecond, currentSpeeds.vyMetersPerSecond);
            double now = edu.wpi.first.wpilibj.Timer.getFPGATimestamp();

            double acceleration = 0.0;
            if (m_lastSpeedTimestamp >= 0.0) {
                double dt = now - m_lastSpeedTimestamp;
                if (dt > 0.0) {
                    acceleration = (speed - m_lastSpeed) / dt;
                }
            }

            m_lastSpeed = speed;
            m_lastSpeedTimestamp = now;

            SmartDashboard.putNumber("SwerveDrive/Acceleration", acceleration);
        } catch (Exception ex) {
            // In case drivetrain state is not available yet, avoid crashing
            fLogger.log("publishRobotAcceleration: failed to read drivetrain state: %s", ex.getMessage());
        }
    }

    /**
     * 
     * @param drivetrain
     * @param hubPosition alliance-flipped position of the hub
     * @return The distance to the hub in meters
     */
    public static double getDistanceToHub(CommandSwerveDrivetrain drivetrain, Supplier<Pose2d> hubPosition) {
        return drivetrain.getState().Pose.getTranslation().getDistance(hubPosition.get().getTranslation());
    }

    public double getDistancePoses(Pose2d firstPose, Pose2d secondPose) {
        return firstPose.getTranslation().getDistance(secondPose.getTranslation());
    }

    public static Trigger isStationary(CommandSwerveDrivetrain drivetrain) {
        return new Trigger(() -> isStationaryNow(drivetrain));
    }

    public static boolean isStationaryNow(CommandSwerveDrivetrain drivetrain) {
        double stationaryThreshold = 0.1; // m/s

        double velocity = getRobotVelocity(drivetrain);
        double angularVelocity = getRobotAngularVelocity(drivetrain);
        return velocity < stationaryThreshold && angularVelocity < stationaryThreshold;
    }

    private static SwerveRequest.FieldCentric teleopDriveRequest(CommandSwerveDrivetrain drivetrain, MoveMode moveMode,
            final CommandXboxController joystick) {
        return drive
                .withVelocityX(MaxSpeed
                        * moveMode.selectSpeedMode(joystick::getLeftY, true)
                                .getAsDouble())
                .withVelocityY(MaxSpeed
                        * moveMode.selectSpeedMode(joystick::getLeftX, false)
                                .getAsDouble())
                .withRotationalRate(
                        moveMode.selectRotationMode(joystick, drivetrain, MaxAngularRate).getAsDouble());
    }

    public static Command brakeWhenStationaryOrDrive(CommandSwerveDrivetrain drivetrain, MoveMode moveMode,
            final CommandXboxController joystick) {
        return Commands.run(
                () -> drivetrain.setControl(
                        isStationaryNow(drivetrain) && !hasJoystickInputNow(joystick)
                                ? brake
                                : teleopDriveRequest(drivetrain, moveMode, joystick)),
                drivetrain);
    }

    /**
     * Returns a Trigger that is true when any drive axis on the joystick exceeds
     * the deadband threshold (left X/Y for translation, right X for rotation).
     * Used to exit brake mode when the driver resumes input during AutoFire.
     */
    public static Trigger hasJoystickInput(CommandXboxController joystick) {
        return new Trigger(() -> hasJoystickInputNow(joystick));
    }

    public static boolean hasJoystickInputNow(CommandXboxController joystick) {
        return Math.abs(joystick.getLeftX()) > DEADBAND ||
                Math.abs(joystick.getLeftY()) > DEADBAND ||
                Math.abs(joystick.getRightX()) > DEADBAND;
    }
}
