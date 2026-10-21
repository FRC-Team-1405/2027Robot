package frc.robot.subsystems;

import org.littletonrobotics.junction.AutoLog;

import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Rotation2d;
import edu.wpi.first.math.kinematics.ChassisSpeeds;
import edu.wpi.first.math.kinematics.SwerveModulePosition;
import edu.wpi.first.math.kinematics.SwerveModuleState;

/**
 * Replay boundary for the CTRE swerve drivetrain ("Approach B" in docs/akit-swerve-integration.md).
 *
 * <p>CTRE's odometry thread and pose estimator stay inside {@link CommandSwerveDrivetrain}; this IO
 * only snapshots the resulting drive state once per loop so that everything downstream (vision
 * fusion bookkeeping, AutoPilot, PathPlanner, aim math) reads logged values and replays exactly.
 * Use {@link CommandSwerveDrivetrain#getLoggedState()} rather than {@code getState()} to read it.
 */
public interface DriveIO {
    @AutoLog
    public static class DriveIOInputs {
        /** True whenever a real/sim IO filled these inputs; absent in logs recorded before DriveIO. */
        public boolean valid = false;
        /** CTRE's fused pose estimate (wheel odometry + vision as applied on the robot). */
        public Pose2d pose = Pose2d.kZero;
        /** Robot-relative chassis speeds from wheel odometry. */
        public ChassisSpeeds speeds = new ChassisSpeeds();
        public SwerveModuleState[] moduleStates = new SwerveModuleState[] {};
        public SwerveModuleState[] moduleTargets = new SwerveModuleState[] {};
        public SwerveModulePosition[] modulePositions = new SwerveModulePosition[] {};
        /** Gyro yaw, not adjusted for operator perspective or pose resets. */
        public Rotation2d rawHeading = Rotation2d.kZero;
        /** Timestamp of the latest odometry sample, in FPGA time (CTRE reports its own timebase). */
        public double odometryTimestampSec = 0.0;
        public double odometryPeriodSec = 0.0;
        public int successfulDaqs = 0;
        public int failedDaqs = 0;
    }

    public default void updateInputs(DriveIOInputs inputs) {}
}
