package frc.robot.commands;

import java.util.Optional;
import java.util.Set;
import java.util.function.Supplier;

import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Rotation2d;
import edu.wpi.first.math.geometry.Translation2d;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.Commands;
import frc.robot.lib.FinneyCommand;
import frc.robot.lib.FinneyLogger;
import frc.robot.subsystems.CommandSwerveDrivetrain;

public class DriveToHubDistance extends FinneyCommand {
    private final FinneyLogger fLogger = new FinneyLogger(this.getClass().getSimpleName());

    private final CommandSwerveDrivetrain drivetrain;
    private final Supplier<Pose2d> hubPoseSupplier;
    private final Supplier<Supplier<Double>> desiredDistanceMeters;

    private Pose2d targetPose;

    private Command driveToPoseCommand;

    public DriveToHubDistance(
            CommandSwerveDrivetrain drivetrain,
            Supplier<Pose2d> hubPoseSupplier,
            Supplier<Supplier<Double>> desiredDistanceMeters) {

        this.drivetrain = drivetrain;
        this.hubPoseSupplier = hubPoseSupplier;
        this.desiredDistanceMeters = desiredDistanceMeters;

        addRequirements(drivetrain);
    }

    @Override
    public void initialize() {

        Pose2d robotPose = drivetrain.getState().Pose;
        Pose2d hubPose = hubPoseSupplier.get();

        Translation2d robotToHub = hubPose.getTranslation().minus(robotPose.getTranslation());

        // Direction from robot → hub
        Translation2d direction = robotToHub.div(robotToHub.getNorm());

        // Compute the target point at the desired distance from the hub
        Translation2d targetTranslation = hubPose.getTranslation()
                .minus(direction.times(desiredDistanceMeters.get().get()));

        Rotation2d targetRotation = hubPose.getTranslation()
                .minus(targetTranslation)
                .getAngle();

        targetPose = new Pose2d(targetTranslation, targetRotation);

        driveToPoseCommand = Commands.defer(() -> drivetrain.driveToPoseAP(() -> Optional.of(targetPose), false),
                Set.of(drivetrain));
        driveToPoseCommand.initialize();
        // CommandScheduler.getInstance().schedule(driveToPoseCommand);
        fLogger.log("[%s] INIT", getName());

    }

    @Override
    public void execute() {
        fLogger.log("[%s] EXECUTE", getName());
        driveToPoseCommand.execute();
    }

    @Override
    public boolean isFinished() {
        // Pose2d current = drivetrain.getState().Pose;
        // double dist =
        // current.getTranslation().getDistance(targetPose.getTranslation());
        // fLogger.log(
        // "[%s] isFinished(), isAPv2Finished: %s, dist: %s, currentX: %s, currentY: %s,
        // targetX: %s, targetY: %s",
        // getName(), driveToPoseCommand.isFinished(), dist,
        // current.getX(), current.getY(), targetPose.getX(), targetPose.getY());
        return driveToPoseCommand.isFinished(); // 5 cm tolerance
    }

    @Override
    public void end(boolean interrupted) {
        fLogger.log("[%s] END, interrupt: %s", getName(), interrupted);
        if (driveToPoseCommand != null) {
            driveToPoseCommand.end(interrupted);
        }
    }
}