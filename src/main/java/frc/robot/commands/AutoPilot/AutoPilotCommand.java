// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot.commands.AutoPilot;

import static edu.wpi.first.units.Units.Centimeters;
import static edu.wpi.first.units.Units.Degrees;
import static edu.wpi.first.units.Units.RadiansPerSecond;

import java.util.Optional;
import java.util.function.Supplier;

import com.ctre.phoenix6.swerve.SwerveModule.DriveRequestType;
import com.ctre.phoenix6.swerve.SwerveRequest;
import com.ctre.phoenix6.swerve.SwerveRequest.ForwardPerspectiveValue;
import com.therekrab.autopilot.APConstraints;
import com.therekrab.autopilot.APProfile;
import com.therekrab.autopilot.APTarget;
import com.therekrab.autopilot.Autopilot;
import com.therekrab.autopilot.Autopilot.APResult;

import edu.wpi.first.math.controller.ProfiledPIDController;
import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Rotation2d;
import edu.wpi.first.math.geometry.Translation2d;
import edu.wpi.first.math.kinematics.ChassisSpeeds;
import edu.wpi.first.math.trajectory.TrapezoidProfile;
import edu.wpi.first.networktables.NetworkTableInstance;
import edu.wpi.first.networktables.StructPublisher;
import edu.wpi.first.units.measure.AngularVelocity;
import edu.wpi.first.wpilibj.DriverStation;
import frc.robot.lib.AllianceSymmetry;
import frc.robot.lib.FinneyCommand;
import frc.robot.lib.FinneyLogger;
import frc.robot.subsystems.CommandSwerveDrivetrain;

// AutoPilot Documentation: https://therekrab.github.io/autopilot/index.html
/**
 * Command that uses AutoPilot to navigate the robot to a target pose.
 * 
 * <p>
 * Use the Builder pattern to create instances:
 * 
 * <pre>
 * // Simple usage
 * new AutoPilotCommand.Builder(targetSupplier, drivetrain, "commandName")
 *         .build();
 * 
 * // With entry angle
 * new AutoPilotCommand.Builder(targetSupplier, drivetrain, "commandName")
 *         .withEntryAngle(Rotation2d.fromDegrees(90))
 *         .build();
 * 
 * // With alliance flipping
 * new AutoPilotCommand.Builder(targetSupplier, drivetrain, "commandName")
 *         .withFlipPoseForAlliance(true)
 *         .build();
 * 
 * // Point towards a target during motion (e.g., track a game piece)
 * new AutoPilotCommand.Builder(targetSupplier, drivetrain, "commandName")
 *         .withPointTowardsDuringMotion(() -> gamePiecePose)
 *         .build();
 * 
 * // Point towards target with custom transition threshold
 * new AutoPilotCommand.Builder(targetSupplier, drivetrain, "commandName")
 *         .withPointTowardsDuringMotion(() -> gamePiecePose)
 *         .withPointTowardsTransitionThreshold(0.9) // transition at 90% distance
 *         .build();
 * 
 * // With custom constraints (acceleration, velocity, jerk)
 * APConstraints customConstraints = new APConstraints()
 *         .withAcceleration(6.0)
 *         .withVelocity(5.0)
 *         .withJerk(15.0);
 * new AutoPilotCommand.Builder(targetSupplier, drivetrain, "commandName")
 *         .withConstraints(customConstraints)
 *         .build();
 *
 * // With custom profile thresholds (when a path is considered finished)
 * // Parameters: errorXY (cm), errorTheta (deg), beelineRadius (cm)
 * new AutoPilotCommand.Builder(targetSupplier, drivetrain, "commandName")
 *         .withProfileThresholds(3.0, 1.0, 20.0)
 *         .build();
 * </pre>
 */
public class AutoPilotCommand extends FinneyCommand {
    private final FinneyLogger fLogger = new FinneyLogger(this.getClass().getSimpleName());

    // Publishes AP's target position
    private StructPublisher<Pose2d> apTargetPublisher = NetworkTableInstance.getDefault()
            .getStructTopic("SmartDashboard/Auto/AUTOPILOT/TargetPose", Pose2d.struct).publish();

    // Publishes AP's point-towards target position
    private StructPublisher<Pose2d> apPointTowardsTargetPublisher = NetworkTableInstance.getDefault()
            .getStructTopic("SmartDashboard/Auto/AUTOPILOT/PointTowardsTargetPose", Pose2d.struct).publish();

    public final SwerveRequest.ApplyRobotSpeeds applyRobotSpeeds = new SwerveRequest.ApplyRobotSpeeds()
            .withDriveRequestType(DriveRequestType.Velocity);

    // Default constraints
    private static final APConstraints kDefaultConstraints = new APConstraints()
            .withAcceleration(2.0) // TUNE THIS TO YOUR ROBOT!
            .withVelocity(2.0)
            .withJerk(10.0);

    // Instance-specific AutoPilot components (final but constructed per instance)
    private final APConstraints kConstraints;
    private final APProfile kProfile;
    private final Autopilot kAutopilot;

    private APTarget m_target;
    private final Supplier<Pose2d> m_targetSupplier;
    private final CommandSwerveDrivetrain m_drivetrain;
    private final Optional<Rotation2d> m_entryAngle;
    private final boolean m_flipPoseForAlliance;
    private final Optional<Supplier<Pose2d>> m_pointTowardsDuringMotionSupplier;
    private Optional<Supplier<Pose2d>> m_pointTowardsDuringMotion;
    private final double m_pointTowardsTransitionThreshold;
    private double startingDistanceFromTarget;
    private Pose2d startingPosition;
    private final String commandName;

    private ProfiledPIDController m_thetaController;
    private final ProfiledPIDController m_thetaController_endMotion;

    private final SwerveRequest.FieldCentricFacingAngle m_request = new SwerveRequest.FieldCentricFacingAngle()
            .withForwardPerspective(ForwardPerspectiveValue.BlueAlliance)
            .withDriveRequestType(DriveRequestType.Velocity)
            .withHeadingPID(2, 0, 0); /* auto pilots angle PID, TUNE THIS TO YOUR ROBOT! */

    /**
     * Private constructor - use Builder to create instances
     */
    private AutoPilotCommand(Builder builder) {
        m_targetSupplier = builder.targetSupplier;
        m_drivetrain = builder.drivetrain;
        m_entryAngle = builder.entryAngle;
        m_flipPoseForAlliance = builder.flipPoseForAlliance;
        m_pointTowardsDuringMotionSupplier = builder.pointTowardsDuringMotion;
        m_pointTowardsTransitionThreshold = builder.pointTowardsTransitionThreshold;
        this.commandName = builder.commandName;

        // Initialize AutoPilot components with custom or default constraints
        // These are the ENDING THREASHOLDS
        this.kConstraints = builder.constraints;
        this.kProfile = new APProfile(kConstraints)
                .withErrorXY(Centimeters.of(builder.errorXYCentimeters))
                .withErrorTheta(Degrees.of(builder.errorThetaDegrees))
                .withBeelineRadius(Centimeters.of(builder.beelineRadiusCentimeters));
        this.kAutopilot = new Autopilot(kProfile);

        // TODO:Tune PID Loop
        m_thetaController = new ProfiledPIDController(
                8, 0.0, 0, // PID gains, TUNE THIS TO YOUR ROBOT!
                new TrapezoidProfile.Constraints(20, 25) // max velocity (rad/s) and acceleration (rad/s^2)
        );
        m_thetaController.enableContinuousInput(-Math.PI, Math.PI); // Enable angle wrapping

        m_thetaController_endMotion = new ProfiledPIDController(
                10, 0.0, 0.1, // PID gains for end motion, TUNE THIS TO YOUR ROBOT!
                new TrapezoidProfile.Constraints(10, 15) // max velocity (rad/s) and acceleration (rad/s^2)
        );
        m_thetaController_endMotion.enableContinuousInput(-Math.PI, Math.PI); // Enable angle wrapping

        addRequirements(m_drivetrain);
    }

    public static class Builder {
        // Required parameters
        private final Supplier<Pose2d> targetSupplier;
        private final CommandSwerveDrivetrain drivetrain;
        private final String commandName;

        // Optional parameters with default values
        private Optional<Rotation2d> entryAngle = Optional.empty();
        private boolean flipPoseForAlliance = false;
        private Optional<Supplier<Pose2d>> pointTowardsDuringMotion = Optional.empty();
        private double pointTowardsTransitionThreshold = 0.8; // 80% of distance
        private APConstraints constraints = kDefaultConstraints;
        // Profile threshold defaults (units: centimeters / degrees)
        private double errorXYCentimeters = 2.0;
        private double errorThetaDegrees = 0.5;
        private double beelineRadiusCentimeters = 16.0;

        public Builder(Supplier<Pose2d> targetSupplier, CommandSwerveDrivetrain drivetrain, String commandName) {
            this.targetSupplier = targetSupplier;
            this.drivetrain = drivetrain;
            this.commandName = commandName;
        }

        public Builder withEntryAngle(Rotation2d entryAngle) {
            this.entryAngle = Optional.of(entryAngle);
            return this;
        }

        public Builder withFlipPoseForAlliance(boolean flipPoseForAlliance) {
            this.flipPoseForAlliance = flipPoseForAlliance;
            return this;
        }

        public Builder withPointTowardsDuringMotion(Supplier<Pose2d> pointTowardsPose) {
            this.pointTowardsDuringMotion = Optional.of(pointTowardsPose);
            return this;
        }

        public Builder withPointTowardsTransitionThreshold(double threshold) {
            this.pointTowardsTransitionThreshold = threshold;
            return this;
        }

        /**
         * Override the default profile thresholds used to determine when a path
         * is considered finished.
         *
         * @param errorXYCentimeters       XY error threshold in centimeters
         * @param errorThetaDegrees        theta error threshold in degrees
         * @param beelineRadiusCentimeters beeline radius in centimeters
         * @return this Builder
         */
        public Builder withProfileThresholds(double errorXYCentimeters, double errorThetaDegrees,
                double beelineRadiusCentimeters) {
            this.errorXYCentimeters = errorXYCentimeters;
            this.errorThetaDegrees = errorThetaDegrees;
            this.beelineRadiusCentimeters = beelineRadiusCentimeters;
            return this;
        }

        /**
         * Set custom AutoPilot constraints for acceleration, velocity, and jerk.
         * 
         * @param constraints Custom APConstraints
         * @return this Builder
         */
        public Builder withConstraints(APConstraints constraints) {
            this.constraints = constraints;
            return this;
        }

        public AutoPilotCommand build() {
            return new AutoPilotCommand(this);
        }
    }

    @Override
    public void initialize() {
        super.initialize();

        m_pointTowardsDuringMotion = m_pointTowardsDuringMotionSupplier;
        if (m_flipPoseForAlliance && DriverStation.Alliance.Red.equals(DriverStation.getAlliance().get())) {
            // flip pose for red alliance
            m_target = new APTarget(AllianceSymmetry.flip(m_targetSupplier.get()));

            if (m_pointTowardsDuringMotionSupplier.isPresent()) {
                m_pointTowardsDuringMotion = Optional
                        .of(() -> AllianceSymmetry.flip(m_pointTowardsDuringMotionSupplier.get().get()));
            }
        } else {
            m_target = new APTarget(m_targetSupplier.get());
        }
        apTargetPublisher.set(m_target.getReference());
        if (m_pointTowardsDuringMotion.isPresent()) {
            apPointTowardsTargetPublisher.set(m_pointTowardsDuringMotion.get().get());
        }

        startingDistanceFromTarget = getDistanceToTarget();
        startingPosition = m_drivetrain.getState().Pose;

        m_thetaController.reset(startingPosition.getRotation().getRadians());
        m_thetaController_endMotion.reset(startingPosition.getRotation().getRadians());

        fLogger.log("Initializing %s to target Pose (x: %.1f, y: %.1f, rot: %.1f deg)",
                getName(),
                m_target.getReference().getX(), m_target.getReference().getY(),
                m_target.getReference().getRotation().getDegrees());
    }

    @Override
    public void execute() {
        ChassisSpeeds robotRelativeSpeeds = m_drivetrain.getState().Speeds;
        Pose2d pose = m_drivetrain.getState().Pose;
        // System.out.println(String.format("Robot Pose (x: %.1f, y: %.1f)",
        // pose.getX(), pose.getY()));

        double vxMetersPerSecond = robotRelativeSpeeds.vxMetersPerSecond;
        double vyMetersPerSecond = robotRelativeSpeeds.vyMetersPerSecond;
        // double omegaRadiansPerSecond = robotRelativeSpeeds.omegaRadiansPerSecond;

        double linearVelocity = Math.hypot(vxMetersPerSecond, vyMetersPerSecond);
        // double linearAcceleration = m_drivetrain.getFilteredAcceleration();

        Optional<Rotation2d> correctedEntryAngle = m_entryAngle;

        if (correctedEntryAngle.isPresent()) {
            // convert from input of robot relative entry angle to field relative entry
            // angle
            correctedEntryAngle = Optional.of(
                    correctedEntryAngle.get().plus(m_target.getReference().getRotation()));
        }

        APResult out;
        if (m_entryAngle.isPresent()) {
            out = kAutopilot.calculate(pose, robotRelativeSpeeds, m_target.withEntryAngle(correctedEntryAngle.get()));
        } else {
            out = kAutopilot.calculate(pose, robotRelativeSpeeds, m_target.withoutEntryAngle());
        }

        Rotation2d currentRotation = pose.getRotation();
        Rotation2d targetRotation = out.targetAngle(); // from Autopilot

        // Determine which rotation to use based on point-towards feature
        Rotation2d rotationToUse = targetRotation;
        Rotation2d rotationalError = targetRotation.minus(currentRotation);
        boolean shouldPointTowardsTarget = m_pointTowardsDuringMotion.isPresent()
                && getPercentageOfDistanceToTarget() < m_pointTowardsTransitionThreshold;
        if (shouldPointTowardsTarget) {
            // Calculate rotation to point towards the specified pose
            Translation2d currentTranslation = pose.getTranslation();

            Translation2d pointTowardsTranslation = m_pointTowardsDuringMotion.get().get().getTranslation();

            Translation2d delta = pointTowardsTranslation.minus(currentTranslation);
            rotationToUse = delta.getAngle();

            rotationalError = rotationToUse.minus(currentRotation);
        } else if (m_pointTowardsDuringMotion.isPresent()) {
            // We've crossed the threshold, use final target rotation
            fLogger.log("Transitioning to final rotation, error: %.1fdeg (at %.1f%% distance)",
                    rotationalError.getDegrees(),
                    getPercentageOfDistanceToTarget() * 100);
        }

        if (0.9 < getPercentageOfDistanceToTarget()) {
            // Nearing the end of motion towards target, use end-motion theta PID
            double thetaOutput = m_thetaController_endMotion.calculate(
                    currentRotation.getRadians(),
                    rotationToUse.getRadians());

            ChassisSpeeds outRobotRelativeSpeeds = ChassisSpeeds.fromFieldRelativeSpeeds(
                    out.vx(),
                    out.vy(),
                    AngularVelocity.ofBaseUnits(thetaOutput, RadiansPerSecond),
                    m_drivetrain.getState().Pose.getRotation());

            m_drivetrain.setControl(applyRobotSpeeds.withSpeeds(outRobotRelativeSpeeds));

            fLogger.log(
                    "End-motion PID, kP=%.1f, error: %.1fdeg (e: %.3frad) (e: %.3f), linearVelocity: %.3f - (at %.1f%% distance)",
                    m_thetaController_endMotion.getP(),
                    rotationalError.getDegrees(),
                    m_thetaController_endMotion.getPositionError(),
                    m_thetaController_endMotion.getAccumulatedError(),
                    linearVelocity,
                    getPercentageOfDistanceToTarget() * 100);
        } else if (0.1 < getPercentageOfDistanceToTarget()) {
            // System.out.println("percentageToTarget: +10%");
            if (shouldPointTowardsTarget && Math.abs(rotationalError.getDegrees()) < 20) {
                // use custom theta PID when close to target rotation

                double thetaOutput = m_thetaController.calculate(
                        currentRotation.getRadians(),
                        rotationToUse.getRadians());

                ChassisSpeeds outRobotRelativeSpeeds = ChassisSpeeds.fromFieldRelativeSpeeds(
                        out.vx(),
                        out.vy(),
                        AngularVelocity.ofBaseUnits(thetaOutput, RadiansPerSecond),
                        m_drivetrain.getState().Pose.getRotation());

                m_drivetrain.setControl(applyRobotSpeeds.withSpeeds(outRobotRelativeSpeeds));

                fLogger.log(
                        "Custom PID, Pointing towards target kP=%.1f, error: %.1fdeg (e: %.3frad) (e: %.3f), linearVelocity: %.3f - (at %.1f%% distance)",
                        m_thetaController.getP(),
                        rotationalError.getDegrees(),
                        m_thetaController.getPositionError(),
                        m_thetaController.getAccumulatedError(),
                        linearVelocity,
                        getPercentageOfDistanceToTarget() * 100);
            } else {
                // use autopilot's angle output
                m_drivetrain.setControl(m_request
                        .withVelocityX(out.vx())
                        .withVelocityY(out.vy())
                        .withTargetDirection(rotationToUse));

                fLogger.log(
                        "AP output, error: %.1fdeg, linearVelocity: %.3f - (at %.1f%% distance)",
                        rotationalError.getDegrees(),
                        linearVelocity,
                        getPercentageOfDistanceToTarget() * 100);

                // keep resetting custom theta controller to avoid sudden jumps when switching
                m_thetaController.reset(currentRotation.getRadians());
            }

            // keep resetting end-motion controller to avoid sudden jumps when switching
            m_thetaController_endMotion.reset(currentRotation.getRadians());
        } else {
            // Beginning of motion towards target, don't start rotation yet
            // to allow for movement away from walls before rotation begins.

            fLogger.log("vx: %.3f, vy: %.3f, noRotationOutput, rotationDifference(deg): %.2f",
                    out.vx().baseUnitMagnitude(),
                    out.vy().baseUnitMagnitude(),
                    (m_target.getReference().getRotation().getDegrees() -
                            pose.getRotation().getDegrees()));

            m_drivetrain.setControl(m_request
                    .withVelocityX(out.vx())
                    .withVelocityY(out.vy())
                    .withTargetDirection(startingPosition.getRotation()));
        }
    }

    @Override
    public boolean isFinished() {
        // fLogger.log(String.format("Angle Difference: %.1f, Target
        // angle: %.1f, Current Angle: %.1f",
        // m_target.getReference().getRotation().minus(m_drivetrain.getState().Pose.getRotation()).getDegrees(),
        // m_target.getReference().getRotation().getDegrees(),
        // m_drivetrain.getState().Pose.getRotation().getDegrees()));
        // fLogger.log(String.format("Location Difference: %.1f, Angle Difference:
        // %.1f",
        // m_target.getReference().getTranslation().getDistance(m_drivetrain.getState().Pose.getTranslation()),
        // m_target.getReference().getRotation().minus(m_drivetrain.getState().Pose.getRotation()).getDegrees()));
        return kAutopilot.atTarget(m_drivetrain.getState().Pose, m_target);
    }

    @Override
    public void end(boolean interrupted) {
        super.end(interrupted);
        m_drivetrain.setControl(m_request
                .withVelocityX(0)
                .withVelocityY(0)
                .withTargetDirection(m_drivetrain.getState().Pose.getRotation()));

        fLogger.log(
                "%s ended, final Pose (x: %.1f, y: %.1f, rot: %.1f deg), target Pose (x: %.1f, y: %.1f, rot: %.1f deg), interrupted: %s",
                getName(),
                m_drivetrain.getState().Pose.getX(), m_drivetrain.getState().Pose.getY(),
                m_drivetrain.getState().Pose.getRotation().getDegrees(),
                m_target.getReference().getX(), m_target.getReference().getY(),
                m_target.getReference().getRotation().getDegrees(),
                interrupted);
    }

    @Override
    public String getName() {
        String instanceSpecificValue = commandName;
        return "AutoPilot(" + instanceSpecificValue + ")";
    }

    public double getDistanceToTarget() {
        Pose2d currentPose = m_drivetrain.getState().Pose;
        double distance = currentPose.getTranslation().getDistance(m_target.getReference().getTranslation());
        return Math.abs(distance);
    }

    public double getPercentageOfDistanceToTarget() {
        return Math.abs(startingDistanceFromTarget - getDistanceToTarget()) / startingDistanceFromTarget;
    }
}