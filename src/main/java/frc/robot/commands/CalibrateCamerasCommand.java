package frc.robot.commands;

import java.util.ArrayList;
import java.util.List;

import org.littletonrobotics.junction.Logger;

import com.ctre.phoenix6.swerve.SwerveRequest;

import edu.wpi.first.math.util.Units;
import edu.wpi.first.wpilibj.Timer;
import edu.wpi.first.wpilibj2.command.Command;
import frc.robot.subsystems.CommandSwerveDrivetrain;

/**
 * "Calibrate Cameras": the robot moves in a known way in front of an AprilTag so the camera
 * calibration tool (tools/camera-calibration, "Quick (spin &amp; drive)") can solve each camera's
 * mount from the log, with no tape measuring. See docs/camera-autocal-plan.md.
 *
 * <p>
 * Setup: robot level on the floor, roughly facing the tag(s), about 2-2.5 m away, with about
 * 1 m of clear floor around it. Cover any tags you do not want seen. Run it as an autonomous
 * from the chooser ("CalibrateCameras"), then fetch the log.
 *
 * <p>
 * What it does (robot-relative, so it works wherever the robot is placed):
 * <ol>
 * <li>Hold still 2 s.</li>
 * <li>Sweep: turn +25 deg, then -50 deg, then back +25 deg, in place. The camera swings around
 * the robot's rotation centre, which gives the camera's x and y on the robot.</li>
 * <li>Drive straight: 0.6 m forward and back, then 0.6 m left, 1.2 m right, 0.6 m left (back to
 * the start). The camera moves along the robot's own axes, which fixes the heading and so the
 * camera's yaw.</li>
 * <li>Hold still 1 s.</li>
 * </ol>
 * About 25 s in all. It stays within about 0.6 m of where it started.
 *
 * <p>
 * Vision corrections are switched OFF while it runs, so Drivetrain/Pose is pure wheel + gyro
 * odometry (the solver needs that: it compares odometry with what the camera sees). They are
 * switched back to whatever they were when the command ends or is interrupted.
 *
 * <p>
 * Logged: Calibration/Phase (string) and Calibration/VisionCorrectionsOff (boolean). The tool
 * uses these to find the run in the log.
 */
public class CalibrateCamerasCommand extends Command {
    // Tune these if the cameras lose the tag during the run (log shows few samples).
    private static final double SWEEP_DEG = 25.0;
    private static final double SWEEP_RATE_DEG_PER_S = 20.0;
    private static final double DRIVE_M = 0.6;
    private static final double DRIVE_SPEED_MPS = 0.4;
    private static final double HOLD_START_S = 2.0;
    private static final double HOLD_END_S = 1.0;

    private record Segment(String name, double vx, double vy, double omegaRadPerS, double seconds) {
    }

    private static List<Segment> buildSegments() {
        double w = Units.degreesToRadians(SWEEP_RATE_DEG_PER_S);
        double sweepS = SWEEP_DEG / SWEEP_RATE_DEG_PER_S;
        double driveS = DRIVE_M / DRIVE_SPEED_MPS;
        List<Segment> s = new ArrayList<>();
        s.add(new Segment("Hold", 0, 0, 0, HOLD_START_S));
        s.add(new Segment("SweepCCW", 0, 0, w, sweepS));
        s.add(new Segment("SweepCW", 0, 0, -w, 2 * sweepS));
        s.add(new Segment("SweepBack", 0, 0, w, sweepS));
        s.add(new Segment("DriveForward", DRIVE_SPEED_MPS, 0, 0, driveS));
        s.add(new Segment("DriveBack", -DRIVE_SPEED_MPS, 0, 0, driveS));
        s.add(new Segment("StrafeLeft", 0, DRIVE_SPEED_MPS, 0, driveS));
        s.add(new Segment("StrafeRight", 0, -DRIVE_SPEED_MPS, 0, 2 * driveS));
        s.add(new Segment("StrafeCenter", 0, DRIVE_SPEED_MPS, 0, driveS));
        s.add(new Segment("HoldEnd", 0, 0, 0, HOLD_END_S));
        return s;
    }

    private final CommandSwerveDrivetrain drivetrain;
    private final List<Segment> segments = buildSegments();
    private final double totalSeconds = segments.stream().mapToDouble(Segment::seconds).sum();
    private final SwerveRequest.RobotCentric request = new SwerveRequest.RobotCentric();
    private final Timer timer = new Timer();
    private boolean visionWasEnabled = true;

    public CalibrateCamerasCommand(CommandSwerveDrivetrain drivetrain) {
        this.drivetrain = drivetrain;
        addRequirements(drivetrain);
    }

    @Override
    public void initialize() {
        visionWasEnabled = drivetrain.areVisionOdometryUpdatesEnabled();
        drivetrain.setVisionOdometryUpdatesEnabled(false);
        Logger.recordOutput("Calibration/VisionCorrectionsOff", true);
        timer.restart();
    }

    @Override
    public void execute() {
        double t = timer.get();
        double acc = 0;
        Segment current = segments.get(segments.size() - 1);
        for (Segment s : segments) {
            if (t < acc + s.seconds()) {
                current = s;
                break;
            }
            acc += s.seconds();
        }
        Logger.recordOutput("Calibration/Phase", current.name());
        drivetrain.setControl(request
                .withVelocityX(current.vx())
                .withVelocityY(current.vy())
                .withRotationalRate(current.omegaRadPerS()));
    }

    @Override
    public void end(boolean interrupted) {
        drivetrain.setControl(new SwerveRequest.SwerveDriveBrake());
        drivetrain.setVisionOdometryUpdatesEnabled(visionWasEnabled);
        Logger.recordOutput("Calibration/VisionCorrectionsOff", false);
        Logger.recordOutput("Calibration/Phase", interrupted ? "Interrupted" : "Done");
    }

    @Override
    public boolean isFinished() {
        return timer.hasElapsed(totalSeconds);
    }
}
