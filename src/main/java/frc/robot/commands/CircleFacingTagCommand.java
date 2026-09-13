// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot.commands;

import com.ctre.phoenix6.swerve.SwerveRequest;
import com.ctre.phoenix6.swerve.SwerveRequest.ForwardPerspectiveValue;

import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Rotation2d;
import edu.wpi.first.math.geometry.Translation2d;
import edu.wpi.first.math.util.Units;
import edu.wpi.first.wpilibj.Timer;
import edu.wpi.first.wpilibj2.command.Command;
import frc.robot.lib.AprilTags;
import frc.robot.subsystems.CommandSwerveDrivetrain;

/**
 * Vision test auto. Treats wherever the robot is placed at the start as the
 * center of a circle, drives straight out to the edge of that circle, then
 * orbits the center while continuously turning to face a fixed AprilTag and
 * ramping tangential speed up to a max, then stops on a fixed cutoff.
 *
 * <p>
 * The point is to exercise vision pose estimation while the robot is both
 * translating (with increasing speed/acceleration) and rotating, with the
 * tag guaranteed to stay in view the whole time since heading is always
 * pointed at it.
 *
 * <p>
 * A fixed cutoff (rather than running until the DS ends autonomous) keeps the
 * run comparable across A/B log comparisons: an unbounded orbit means a run
 * left going longer spends more of its average in the faster, later part of
 * the speed ramp, which skews metrics independently of whatever is actually
 * being tested (e.g. a camera recalibration). Normally that cutoff is a fixed
 * lap count; see the TEMPORARY note on the constants below for why this is
 * currently an elapsed-time cutoff instead.
 */
public class CircleFacingTagCommand extends Command {
    // TEMPORARY: reverted to the pre-2026-09-06 speed/accel values (were 1.0 / 0.2) and
    // swapped the stop condition from a 5-lap distance cap to a 17.6419s elapsed-time cap,
    // purely so this run reproduces the exact maneuver in
    // logs/offseason/9-5/akit_26-09-05_14-27-33_CircleFacingTag_PreCalibration.wpilog
    // (same speed profile, cut at the same point) with the corrected camera intrinsics as
    // the only variable that's changed -- see notes/9-8 calibration exports and
    // VisionConstants.java. Once that baseline-vs-corrected-intrinsics comparison log is
    // captured, revert this whole block back to:
    //   MAX_TANGENTIAL_SPEED_MPS = 1.0, ACCELERATION_MPS2 = 0.2,
    //   and isFinished() keyed off a NUM_LAPS-based TOTAL_PATH_LENGTH_METERS again
    //   (see git history of this file for the exact prior version).
    private static final double CIRCLE_DIAMETER_METERS = Units.feetToMeters(5.0);
    private static final double CIRCLE_RADIUS_METERS = CIRCLE_DIAMETER_METERS / 2.0;
    private static final double MAX_TANGENTIAL_SPEED_MPS = 2.0;
    private static final double ACCELERATION_MPS2 = 0.5; // ramp to max speed over ~4s
    private static final double POSITION_CORRECTION_KP = 3.0; // (m/s) per (m) of drift off the reference path
    // Matches the auto-mode span duration measured out of the 9/5 baseline log via
    // `logbench compare --mode auto` (156.48997s -> 174.13185s window).
    private static final double BASELINE_MATCH_DURATION_SECONDS = 17.6419;

    private final CommandSwerveDrivetrain drivetrain;
    private final int tagId;

    // All position/velocity math here works in absolute (blue-origin) field
    // coordinates, so force that frame explicitly. Otherwise this request
    // defaults to OperatorPerspective, which CommandSwerveDrivetrain rotates
    // 180 degrees on red alliance, flipping every velocity command we send.
    private final SwerveRequest.FieldCentricFacingAngle request = new SwerveRequest.FieldCentricFacingAngle()
            .withForwardPerspective(ForwardPerspectiveValue.BlueAlliance)
            .withHeadingPID(10.0, 0.0, 0.2);

    private Translation2d center;
    private double startAngleRadians;
    private double elapsedTime;
    private double pathLength;
    private double lastTimestamp;

    public CircleFacingTagCommand(CommandSwerveDrivetrain drivetrain, int tagId) {
        this.drivetrain = drivetrain;
        this.tagId = tagId;
        addRequirements(drivetrain);
    }

    @Override
    public void initialize() {
        Pose2d startPose = drivetrain.getState().Pose;
        center = startPose.getTranslation();
        // Leave the center heading toward the tag, so the initial straight-line leg
        // out to the edge doubles as the entry point onto the circle.
        startAngleRadians = AprilTags.getAprilTagPose(tagId).getTranslation().minus(center).getAngle().getRadians();
        elapsedTime = 0.0;
        pathLength = 0.0;
        lastTimestamp = Timer.getFPGATimestamp();
    }

    @Override
    public void execute() {
        double now = Timer.getFPGATimestamp();
        double dt = now - lastTimestamp;
        lastTimestamp = now;

        double speed = Math.min(MAX_TANGENTIAL_SPEED_MPS, ACCELERATION_MPS2 * elapsedTime);
        elapsedTime += dt;
        pathLength += speed * dt;

        Translation2d referencePoint;
        Translation2d directionOfTravel;
        if (pathLength <= CIRCLE_RADIUS_METERS) {
            // Phase 1: straight line from the center out to the edge of the circle.
            Rotation2d direction = Rotation2d.fromRadians(startAngleRadians);
            referencePoint = center.plus(new Translation2d(pathLength, direction));
            directionOfTravel = new Translation2d(1.0, direction);
        } else {
            // Phase 2: orbit the center at a fixed radius.
            double arcLength = pathLength - CIRCLE_RADIUS_METERS;
            Rotation2d angleOnCircle = Rotation2d.fromRadians(startAngleRadians + arcLength / CIRCLE_RADIUS_METERS);
            referencePoint = center.plus(new Translation2d(CIRCLE_RADIUS_METERS, angleOnCircle));
            directionOfTravel = new Translation2d(1.0, angleOnCircle.plus(Rotation2d.fromDegrees(90)));
        }

        Pose2d currentPose = drivetrain.getState().Pose;
        Translation2d positionError = referencePoint.minus(currentPose.getTranslation());
        Translation2d velocity = directionOfTravel.times(speed).plus(positionError.times(POSITION_CORRECTION_KP));

        Rotation2d targetDirection = AprilTags.getAprilTagPose(tagId).getTranslation()
                .minus(currentPose.getTranslation()).getAngle();

        drivetrain.setControl(request
                .withVelocityX(velocity.getX())
                .withVelocityY(velocity.getY())
                .withTargetDirection(targetDirection));
    }

    @Override
    public void end(boolean interrupted) {
        drivetrain.setControl(new SwerveRequest.SwerveDriveBrake());
    }

    @Override
    public boolean isFinished() {
        // TEMPORARY: see the baseline-match note on the constants above.
        return elapsedTime >= BASELINE_MATCH_DURATION_SECONDS;
    }
}
