// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot.commands.AutoPilot;

import static edu.wpi.first.units.Units.Centimeters;
import static edu.wpi.first.units.Units.Degrees;
import static edu.wpi.first.units.Units.RadiansPerSecond;

import java.util.ArrayList;
import java.util.List;
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
import edu.wpi.first.networktables.StructArrayPublisher;
import edu.wpi.first.networktables.StructPublisher;
import edu.wpi.first.units.measure.AngularVelocity;
import edu.wpi.first.wpilibj.DriverStation;
import frc.robot.lib.AllianceSymmetry;
import frc.robot.lib.FinneyCommand;
import frc.robot.lib.FinneyLogger;
import frc.robot.subsystems.CommandSwerveDrivetrain;

/**
 * Command that chains multiple AutoPilot waypoints together, preserving
 * momentum between transitions for smooth, continuous paths.
 * 
 * <p>
 * Unlike running sequential AutoPilotCommands which stop at each waypoint,
 * this command transitions smoothly from one target to the next while
 * maintaining velocity.
 * 
 * <p>
 * Use the Builder pattern to create instances:
 * 
 * <pre>
 * // Simple chained path with 3 waypoints
 * new ChainedAutoPilotCommand.Builder(drivetrain, "MyChainedPath")
 *         .addWaypoint(() -> new Pose2d(2, 2, Rotation2d.fromDegrees(90)))
 *         .addWaypoint(() -> new Pose2d(4, 4, Rotation2d.fromDegrees(45)))
 *         .addWaypoint(() -> new Pose2d(6, 2, Rotation2d.fromDegrees(0)))
 *         .build();
 * 
 * // With alliance flipping (all waypoints auto-flip for red alliance)
 * new ChainedAutoPilotCommand.Builder(drivetrain, "RedBlueChain")
 *         .withFlipPoseForAlliance(true)
 *         .addWaypoint(() -> startPose)
 *         .addWaypoint(() -> midPose)
 *         .addWaypoint(() -> endPose)
 *         .build();
 * 
 * // With custom constraints and tighter finish threshold
 * APConstraints fastConstraints = new APConstraints()
 *         .withAcceleration(6.0)
 *         .withVelocity(5.0)
 *         .withJerk(15.0);
 * 
 * new ChainedAutoPilotCommand.Builder(drivetrain, "FastChain")
 *         .addWaypoint(() -> pose1)
 *         .addWaypoint(() -> pose2)
 *         .addWaypoint(() -> pose3)
 *         .withConstraints(fastConstraints)
 *         .withWaypointTransitionThreshold(5.0) // switch at 5cm from waypoint
 *         .withProfileThresholds(1.0, 0.3, 10.0) // tighter final threshold
 *         .build();
 * 
 * // Point towards a moving target throughout entire path
 * new ChainedAutoPilotCommand.Builder(drivetrain, "TrackingChain")
 *         .addWaypoint(() -> pose1)
 *         .addWaypoint(() -> pose2)
 *         .withPointTowardsDuringMotion(() -> gamePiecePose)
 *         .build();
 * </pre>
 */
public class ChainedAutoPilotCommand extends FinneyCommand {
    private final FinneyLogger fLogger = new FinneyLogger(this.getClass().getSimpleName());

    // Publishers for visualization
    private final StructPublisher<Pose2d> currentTargetPublisher = NetworkTableInstance.getDefault()
            .getStructTopic("SmartDashboard/Auto/CHAINED_AP/CurrentTarget", Pose2d.struct).publish();
    private final StructArrayPublisher<Pose2d> allWaypointsPublisher = NetworkTableInstance.getDefault()
            .getStructArrayTopic("SmartDashboard/Auto/CHAINED_AP/AllWaypoints", Pose2d.struct).publish();
    private final StructPublisher<Pose2d> pointTowardsTargetPublisher = NetworkTableInstance.getDefault()
            .getStructTopic("SmartDashboard/Auto/CHAINED_AP/PointTowardsTarget", Pose2d.struct).publish();

    public final SwerveRequest.ApplyRobotSpeeds applyRobotSpeeds = new SwerveRequest.ApplyRobotSpeeds()
            .withDriveRequestType(DriveRequestType.Velocity);

    // Default constraints
    private static final APConstraints kDefaultConstraints = new APConstraints()
            .withAcceleration(4.0)
            .withVelocity(4.0)
            .withJerk(10.0);

    // Instance-specific AutoPilot components
    private final APConstraints kConstraints;
    private final APProfile kProfile;
    private final Autopilot kAutopilot;

    // Waypoint management
    private final List<Supplier<Pose2d>> waypointSuppliers;
    private List<APTarget> waypoints;
    private int currentWaypointIndex;
    private final double waypointTransitionThreshold; // Distance in meters to switch to next waypoint

    // Configuration
    private final CommandSwerveDrivetrain drivetrain;
    private final boolean flipPoseForAlliance;
    private final Optional<Supplier<Pose2d>> pointTowardsDuringMotionSupplier;
    private Optional<Supplier<Pose2d>> pointTowardsDuringMotion;
    private final double pointTowardsTransitionThreshold;
    private final String commandName;

    // Runtime state
    private Pose2d startingPosition;
    private ProfiledPIDController thetaController;
    private final ProfiledPIDController thetaController_endMotion;

    private final SwerveRequest.FieldCentricFacingAngle request = new SwerveRequest.FieldCentricFacingAngle()
            .withForwardPerspective(ForwardPerspectiveValue.BlueAlliance)
            .withDriveRequestType(DriveRequestType.Velocity)
            .withHeadingPID(2, 0, 0);

    /**
     * Private constructor - use Builder to create instances
     */
    private ChainedAutoPilotCommand(Builder builder) {
        this.waypointSuppliers = builder.waypoints;
        this.drivetrain = builder.drivetrain;
        this.flipPoseForAlliance = builder.flipPoseForAlliance;
        this.pointTowardsDuringMotionSupplier = builder.pointTowardsDuringMotion;
        this.pointTowardsTransitionThreshold = builder.pointTowardsTransitionThreshold;
        this.waypointTransitionThreshold = builder.waypointTransitionThreshold;
        this.commandName = builder.commandName;

        // Initialize AutoPilot components
        this.kConstraints = builder.constraints;
        this.kProfile = new APProfile(kConstraints)
                .withErrorXY(Centimeters.of(builder.errorXYCentimeters))
                .withErrorTheta(Degrees.of(builder.errorThetaDegrees))
                .withBeelineRadius(Centimeters.of(builder.beelineRadiusCentimeters));
        this.kAutopilot = new Autopilot(kProfile);

        // Initialize PID controllers
        thetaController = new ProfiledPIDController(
                8, 0.0, 0,
                new TrapezoidProfile.Constraints(20, 25));
        thetaController.enableContinuousInput(-Math.PI, Math.PI);

        thetaController_endMotion = new ProfiledPIDController(
                10, 0.0, 0.1,
                new TrapezoidProfile.Constraints(10, 15));
        thetaController_endMotion.enableContinuousInput(-Math.PI, Math.PI);

        addRequirements(drivetrain);
    }

    public static class Builder {
        // Required parameters
        private final CommandSwerveDrivetrain drivetrain;
        private final String commandName;
        private final List<Supplier<Pose2d>> waypoints = new ArrayList<>();

        // Optional parameters with default values
        private boolean flipPoseForAlliance = false;
        private Optional<Supplier<Pose2d>> pointTowardsDuringMotion = Optional.empty();
        private double pointTowardsTransitionThreshold = 0.8;
        private double waypointTransitionThreshold = 0.10; // 10cm - switch to next waypoint
        private APConstraints constraints = kDefaultConstraints;
        private double errorXYCentimeters = 2.0;
        private double errorThetaDegrees = 0.5;
        private double beelineRadiusCentimeters = 16.0;

        public Builder(CommandSwerveDrivetrain drivetrain, String commandName) {
            this.drivetrain = drivetrain;
            this.commandName = commandName;
        }

        /**
         * Add a waypoint to the chained path.
         * Waypoints are visited in the order they are added.
         * 
         * @param waypointSupplier Supplier providing the waypoint pose
         * @return this Builder
         */
        public Builder addWaypoint(Supplier<Pose2d> waypointSupplier) {
            this.waypoints.add(waypointSupplier);
            return this;
        }

        /**
         * Add multiple waypoints at once.
         * 
         * @param waypointSuppliers Suppliers providing waypoint poses
         * @return this Builder
         */
        @SafeVarargs
        public final Builder addWaypoints(Supplier<Pose2d>... waypointSuppliers) {
            for (Supplier<Pose2d> supplier : waypointSuppliers) {
                this.waypoints.add(supplier);
            }
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
         * Set the distance threshold (in meters) at which to transition to the next
         * waypoint.
         * Lower values make sharper turns, higher values create smoother arcs.
         * Default: 0.10m (10cm)
         * 
         * @param thresholdMeters Distance in meters
         * @return this Builder
         */
        public Builder withWaypointTransitionThreshold(double thresholdMeters) {
            this.waypointTransitionThreshold = thresholdMeters;
            return this;
        }

        public Builder withConstraints(APConstraints constraints) {
            this.constraints = constraints;
            return this;
        }

        public Builder withProfileThresholds(double errorXYCentimeters, double errorThetaDegrees,
                double beelineRadiusCentimeters) {
            this.errorXYCentimeters = errorXYCentimeters;
            this.errorThetaDegrees = errorThetaDegrees;
            this.beelineRadiusCentimeters = beelineRadiusCentimeters;
            return this;
        }

        public ChainedAutoPilotCommand build() {
            if (waypoints.isEmpty()) {
                throw new IllegalStateException("ChainedAutoPilotCommand requires at least one waypoint");
            }
            return new ChainedAutoPilotCommand(this);
        }
    }

    @Override
    public void initialize() {
        super.initialize();

        // Convert suppliers to actual targets, applying alliance flip if needed
        waypoints = new ArrayList<>();
        pointTowardsDuringMotion = pointTowardsDuringMotionSupplier;

        boolean shouldFlip = flipPoseForAlliance
                && DriverStation.Alliance.Red.equals(DriverStation.getAlliance().get());

        for (Supplier<Pose2d> supplier : waypointSuppliers) {
            Pose2d pose = supplier.get();
            if (shouldFlip) {
                pose = AllianceSymmetry.flip(pose);
            }
            waypoints.add(new APTarget(pose));
        }

        if (shouldFlip && pointTowardsDuringMotionSupplier.isPresent()) {
            pointTowardsDuringMotion = Optional
                    .of(() -> AllianceSymmetry.flip(pointTowardsDuringMotionSupplier.get().get()));
        }

        // Start at first waypoint
        currentWaypointIndex = 0;
        startingPosition = drivetrain.getState().Pose;

        // Reset controllers
        thetaController.reset(startingPosition.getRotation().getRadians());
        thetaController_endMotion.reset(startingPosition.getRotation().getRadians());

        // Publish all waypoints for visualization
        Pose2d[] waypointArray = waypoints.stream()
                .map(APTarget::getReference)
                .toArray(Pose2d[]::new);
        allWaypointsPublisher.set(waypointArray);

        // Publish point-towards target if present
        if (pointTowardsDuringMotion.isPresent()) {
            pointTowardsTargetPublisher.set(pointTowardsDuringMotion.get().get());
        }

        fLogger.log("Initializing %s with %d waypoints, starting at waypoint 0 (x: %.1f, y: %.1f, rot: %.1f deg)",
                getName(),
                waypoints.size(),
                waypoints.get(0).getReference().getX(),
                waypoints.get(0).getReference().getY(),
                waypoints.get(0).getReference().getRotation().getDegrees());
    }

    @Override
    public void execute() {
        ChassisSpeeds robotRelativeSpeeds = drivetrain.getState().Speeds;
        Pose2d pose = drivetrain.getState().Pose;

        // Debug: publish autopilot outputs vs drivetrain measured speeds to help find
        // scaling issues (why robot is limited to ~0.3 m/s)
        // out is computed later; to get early visibility, we'll compute a tentative
        // APResult here and log requested velocities and measured speeds.

        // Check if we should transition to next waypoint (but not on final waypoint)
        if (currentWaypointIndex < waypoints.size() - 1) {
            APTarget currentTarget = waypoints.get(currentWaypointIndex);
            double distanceToCurrentWaypoint = pose.getTranslation()
                    .getDistance(currentTarget.getReference().getTranslation());

            if (distanceToCurrentWaypoint < waypointTransitionThreshold) {
                currentWaypointIndex++;
                fLogger.log("Transitioning to waypoint %d/%d (x: %.1f, y: %.1f, rot: %.1f deg)",
                        currentWaypointIndex + 1,
                        waypoints.size(),
                        waypoints.get(currentWaypointIndex).getReference().getX(),
                        waypoints.get(currentWaypointIndex).getReference().getY(),
                        waypoints.get(currentWaypointIndex).getReference().getRotation().getDegrees());
            }
        }

        APTarget currentTarget = waypoints.get(currentWaypointIndex);
        currentTargetPublisher.set(currentTarget.getReference());

        // Calculate autopilot output to current target
        APResult out = kAutopilot.calculate(pose, robotRelativeSpeeds, currentTarget.withoutEntryAngle());

        // Log requested vs actual speeds for debugging scale/mismatch issues
        try {
            double requestedVx = out.vx().baseUnitMagnitude();
            double requestedVy = out.vy().baseUnitMagnitude();
            double measuredVx = robotRelativeSpeeds.vxMetersPerSecond;
            double measuredVy = robotRelativeSpeeds.vyMetersPerSecond;
            fLogger.log(
                    "AP requested vx: %.3f m/s, vy: %.3f m/s | measured vx: %.3f m/s, vy: %.3f m/s | kConstraints: %s",
                    requestedVx, requestedVy, measuredVx, measuredVy, String.valueOf(kConstraints));
        } catch (Exception ex) {
            // keep execute resilient
            fLogger.log("Error logging AP debug values: %s", ex.getMessage());
        }

        Rotation2d currentRotation = pose.getRotation();
        Rotation2d targetRotation = out.targetAngle();

        // Determine rotation based on point-towards feature
        Rotation2d rotationToUse = targetRotation;
        boolean isOnFinalWaypoint = currentWaypointIndex == waypoints.size() - 1;
        double distanceToFinalTarget = pose.getTranslation()
                .getDistance(waypoints.get(waypoints.size() - 1).getReference().getTranslation());

        // Calculate percentage to final destination (for point-towards transition)
        double startingDistanceToFinal = startingPosition.getTranslation()
                .getDistance(waypoints.get(waypoints.size() - 1).getReference().getTranslation());
        double percentageToFinal = (startingDistanceToFinal - distanceToFinalTarget) / startingDistanceToFinal;

        boolean shouldPointTowardsTarget = pointTowardsDuringMotion.isPresent()
                && percentageToFinal < pointTowardsTransitionThreshold;

        if (shouldPointTowardsTarget) {
            Translation2d pointTowardsTranslation = pointTowardsDuringMotion.get().get().getTranslation();
            Translation2d delta = pointTowardsTranslation.minus(pose.getTranslation());
            rotationToUse = delta.getAngle();
        }

        Rotation2d rotationalError = rotationToUse.minus(currentRotation);
        double linearVelocity = Math.hypot(robotRelativeSpeeds.vxMetersPerSecond,
                robotRelativeSpeeds.vyMetersPerSecond);

        // Use different control strategies based on proximity to FINAL waypoint
        if (isOnFinalWaypoint && distanceToFinalTarget < 0.5) {
            // Near final waypoint - use end-motion PID for precision
            double thetaOutput = thetaController_endMotion.calculate(
                    currentRotation.getRadians(),
                    rotationToUse.getRadians());

            ChassisSpeeds outRobotRelativeSpeeds = ChassisSpeeds.fromFieldRelativeSpeeds(
                    out.vx(),
                    out.vy(),
                    AngularVelocity.ofBaseUnits(thetaOutput, RadiansPerSecond),
                    drivetrain.getState().Pose.getRotation());

            drivetrain.setControl(applyRobotSpeeds.withSpeeds(outRobotRelativeSpeeds));

            fLogger.log("End-motion PID (waypoint %d/%d), error: %.1fdeg, linearVel: %.3f m/s",
                    currentWaypointIndex + 1, waypoints.size(),
                    rotationalError.getDegrees(), linearVelocity);
        } else if (shouldPointTowardsTarget && Math.abs(rotationalError.getDegrees()) < 20) {
            // Pointing towards target with custom PID
            double thetaOutput = thetaController.calculate(
                    currentRotation.getRadians(),
                    rotationToUse.getRadians());

            ChassisSpeeds outRobotRelativeSpeeds = ChassisSpeeds.fromFieldRelativeSpeeds(
                    out.vx(),
                    out.vy(),
                    AngularVelocity.ofBaseUnits(thetaOutput, RadiansPerSecond),
                    drivetrain.getState().Pose.getRotation());

            drivetrain.setControl(applyRobotSpeeds.withSpeeds(outRobotRelativeSpeeds));

            fLogger.log("Tracking target (waypoint %d/%d), error: %.1fdeg, linearVel: %.3f m/s",
                    currentWaypointIndex + 1, waypoints.size(),
                    rotationalError.getDegrees(), linearVelocity);
        } else {
            // Use autopilot's angle output
            drivetrain.setControl(request
                    .withVelocityX(out.vx())
                    .withVelocityY(out.vy())
                    .withTargetDirection(rotationToUse));

            fLogger.log("AP control (waypoint %d/%d), error: %.1fdeg, linearVel: %.3f m/s",
                    currentWaypointIndex + 1, waypoints.size(),
                    rotationalError.getDegrees(), linearVelocity);

            thetaController.reset(currentRotation.getRadians());
        }

        thetaController_endMotion.reset(currentRotation.getRadians());
    }

    @Override
    public boolean isFinished() {
        // Only finish when we've reached the FINAL waypoint
        if (currentWaypointIndex != waypoints.size() - 1) {
            return false;
        }

        APTarget finalTarget = waypoints.get(waypoints.size() - 1);
        return kAutopilot.atTarget(drivetrain.getState().Pose, finalTarget);
    }

    @Override
    public void end(boolean interrupted) {
        super.end(interrupted);

        drivetrain.setControl(request
                .withVelocityX(0)
                .withVelocityY(0)
                .withTargetDirection(drivetrain.getState().Pose.getRotation()));

        Pose2d finalPose = drivetrain.getState().Pose;
        APTarget finalTarget = waypoints.get(waypoints.size() - 1);

        fLogger.log(
                "%s ended, visited %d/%d waypoints, final Pose (x: %.1f, y: %.1f, rot: %.1f deg), target (x: %.1f, y: %.1f, rot: %.1f deg), interrupted: %s",
                getName(),
                currentWaypointIndex + 1, waypoints.size(),
                finalPose.getX(), finalPose.getY(), finalPose.getRotation().getDegrees(),
                finalTarget.getReference().getX(), finalTarget.getReference().getY(),
                finalTarget.getReference().getRotation().getDegrees(),
                interrupted);
    }

    @Override
    public String getName() {
        return "ChainedAutoPilot(" + commandName + ")";
    }
}
