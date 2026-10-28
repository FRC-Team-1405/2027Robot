package frc.robot.subsystems;

import com.ctre.phoenix6.Utils;
import com.ctre.phoenix6.swerve.SwerveDrivetrain;

/** Reads the drive state from CTRE's swerve drivetrain (real hardware). */
public class DriveIOTalonFX implements DriveIO {
    protected final SwerveDrivetrain<?, ?, ?> drivetrain;

    public DriveIOTalonFX(SwerveDrivetrain<?, ?, ?> drivetrain) {
        this.drivetrain = drivetrain;
    }

    @Override
    public void updateInputs(DriveIOInputs inputs) {
        // Copy: getState() hands back an object the odometry thread keeps updating.
        var state = drivetrain.getStateCopy();
        inputs.valid = true;
        inputs.pose = state.Pose;
        inputs.speeds = state.Speeds;
        inputs.moduleStates = state.ModuleStates;
        inputs.moduleTargets = state.ModuleTargets;
        inputs.modulePositions = state.ModulePositions;
        inputs.rawHeading = state.RawHeading;
        inputs.odometryTimestampSec = Utils.currentTimeToFPGATime(state.Timestamp);
        inputs.odometryPeriodSec = state.OdometryPeriod;
        inputs.successfulDaqs = state.SuccessfulDaqs;
        inputs.failedDaqs = state.FailedDaqs;
    }
}
