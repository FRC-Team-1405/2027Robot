// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot.lib;

import com.ctre.phoenix6.swerve.SwerveModule.DriveRequestType;
import com.ctre.phoenix6.swerve.SwerveRequest;

import edu.wpi.first.math.geometry.Rotation2d;

/**
 * Helper class that manages field-centric driving with automatic pointing
 * toward a target direction. Driver rotation input overrides the auto-pointing.
 * 
 * <p>
 * This class wraps Phoenix 6's built-in SwerveRequest types to provide seamless
 * switching between auto-rotation and manual rotation control.
 * 
 * <p>
 * Usage example:
 * 
 * <pre>
 * private final FieldCentricAutoPoint autoPoint = new FieldCentricAutoPoint()
 *         .withDeadband(0.1)
 *         .withRotationalDeadband(0.1)
 *         .withRotationOverrideThreshold(0.15)
 *         .withHeadingPID(5.0, 0.0, 0.1);
 * 
 * // In periodic or command:
 * drivetrain.setControl(
 *         autoPoint.getRequest(
 *                 -joystick.getLeftY() * maxSpeed,
 *                 -joystick.getLeftX() * maxSpeed,
 *                 -joystick.getRightX() * maxAngularRate,
 *                 Rotation2d.fromDegrees(0)));
 * </pre>
 */
public class FieldCentricAutoPoint {
    /**
     * The allowable deadband of the request for the translational axes.
     */
    private double m_deadband = 0;

    /**
     * The allowable deadband of the request for the rotational axis.
     */
    private double m_rotationalDeadband = 0;

    /**
     * The threshold above which driver rotation input overrides auto-pointing.
     * Should be slightly higher than rotationalDeadband to prevent flickering.
     */
    private double m_rotationOverrideThreshold = 0.15;

    /**
     * The type of control request to use for the drive motor.
     */
    private DriveRequestType m_driveRequestType = DriveRequestType.OpenLoopVoltage;

    /**
     * Swerve request for manual field-centric driving with rotation control.
     */
    private final SwerveRequest.FieldCentric m_fieldCentricRequest = new SwerveRequest.FieldCentric();

    /**
     * Swerve request for field-centric driving with auto-rotation to target angle.
     */
    private final SwerveRequest.FieldCentricFacingAngle m_facingAngleRequest = new SwerveRequest.FieldCentricFacingAngle();

    /**
     * Whether the driver is currently overriding auto-point with manual rotation.
     */
    private boolean m_isOverriding = false;

    /**
     * Constructor - initializes the swerve requests with default values.
     */
    public FieldCentricAutoPoint() {
        // Configure default PID for auto-rotation
        m_facingAngleRequest.withHeadingPID(10.0, 0.0, 0.2);
    }

    /**
     * Gets the appropriate swerve request based on driver input.
     * Automatically switches between manual rotation and auto-pointing.
     * 
     * @param velocityX       Velocity in the X direction (forward), in m/s
     * @param velocityY       Velocity in the Y direction (left), in m/s
     * @param rotationalRate  Driver's rotation input in radians per second
     * @param targetDirection Target direction for auto-pointing
     * @return The swerve request to apply to the drivetrain
     */
    public SwerveRequest getRequest(
            double velocityX,
            double velocityY,
            double rotationalRate,
            Rotation2d targetDirection) {

        // Determine if driver wants manual rotation
        boolean driverWantsManualRotation = Math.abs(rotationalRate) > m_rotationOverrideThreshold;

        // Update override state with hysteresis to prevent flickering
        if (driverWantsManualRotation) {
            m_isOverriding = true;
        } else if (Math.abs(rotationalRate) < m_rotationalDeadband) {
            // Only exit override mode when input is back within deadband
            m_isOverriding = false;
        }

        if (m_isOverriding) {
            // Driver has manual control - use FieldCentric request
            return m_fieldCentricRequest
                    .withVelocityX(velocityX)
                    .withVelocityY(velocityY)
                    .withRotationalRate(rotationalRate)
                    .withDeadband(m_deadband)
                    .withRotationalDeadband(m_rotationalDeadband)
                    .withDriveRequestType(m_driveRequestType);
        } else {
            // Auto-point to target direction - use FieldCentricFacingAngle request
            return m_facingAngleRequest
                    .withVelocityX(velocityX)
                    .withVelocityY(velocityY)
                    .withTargetDirection(targetDirection)
                    .withDeadband(m_deadband)
                    .withDriveRequestType(m_driveRequestType);
        }
    }

    /**
     * Sets the allowable deadband of the translational axes.
     * 
     * @param deadband Allowable deadband of the translational axes
     * @return this object for method chaining
     */
    public FieldCentricAutoPoint withDeadband(double deadband) {
        m_deadband = deadband;
        return this;
    }

    /**
     * Sets the allowable deadband of the rotational axis.
     * 
     * @param rotationalDeadband Allowable deadband of the rotational axis
     * @return this object for method chaining
     */
    public FieldCentricAutoPoint withRotationalDeadband(double rotationalDeadband) {
        m_rotationalDeadband = rotationalDeadband;
        return this;
    }

    /**
     * Sets the threshold above which driver rotation input overrides auto-pointing.
     * Should be slightly higher than rotationalDeadband to prevent flickering.
     * 
     * @param threshold Override threshold in radians per second
     * @return this object for method chaining
     */
    public FieldCentricAutoPoint withRotationOverrideThreshold(double threshold) {
        m_rotationOverrideThreshold = threshold;
        return this;
    }

    /**
     * Sets the type of control request to use for the drive motor.
     * 
     * @param driveRequestType The type of control request to use for the drive
     *                         motor
     * @return this object for method chaining
     */
    public FieldCentricAutoPoint withDriveRequestType(DriveRequestType driveRequestType) {
        m_driveRequestType = driveRequestType;
        return this;
    }

    /**
     * Configures the PID controller for auto-pointing.
     * 
     * @param kP Proportional gain
     * @param kI Integral gain
     * @param kD Derivative gain
     * @return this object for method chaining
     */
    public FieldCentricAutoPoint withHeadingPID(double kP, double kI, double kD) {
        m_facingAngleRequest.withHeadingPID(kP, kI, kD);
        return this;
    }

    /**
     * Returns whether the driver is currently overriding the auto-point feature.
     * 
     * @return true if driver has manual rotation control, false if auto-pointing is
     *         active
     */
    public boolean isOverriding() {
        return m_isOverriding;
    }
}
