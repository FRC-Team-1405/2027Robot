package frc.robot.subsystems;

import com.ctre.phoenix6.Utils;
import com.ctre.phoenix6.swerve.SwerveDrivetrain;

import edu.wpi.first.wpilibj.Notifier;
import edu.wpi.first.wpilibj.RobotController;

/**
 * Simulation: runs CTRE's swerve sim and reads the drive state the same way as on the robot.
 * Not used in log replay, where the drive state comes from the log instead.
 */
public class DriveIOSim extends DriveIOTalonFX {
    private static final double kSimLoopPeriod = 0.004; // 4 ms
    private final Notifier simNotifier;
    private double lastSimTime;

    public DriveIOSim(SwerveDrivetrain<?, ?, ?> drivetrain) {
        super(drivetrain);
        lastSimTime = Utils.getCurrentTimeSeconds();

        /* Run simulation at a faster rate so PID gains behave more reasonably */
        simNotifier = new Notifier(() -> {
            final double currentTime = Utils.getCurrentTimeSeconds();
            double deltaTime = currentTime - lastSimTime;
            lastSimTime = currentTime;

            /* use the measured time delta, get battery voltage from WPILib */
            drivetrain.updateSimState(deltaTime, RobotController.getBatteryVoltage());
        });
        simNotifier.startPeriodic(kSimLoopPeriod);
    }
}
