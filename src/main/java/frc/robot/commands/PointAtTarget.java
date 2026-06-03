// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot.commands;

import java.util.function.Supplier;

import edu.wpi.first.math.controller.PIDController;
import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.wpilibj2.command.Command;
import frc.robot.RobotContainer;
import frc.robot.subsystems.CommandSwerveDrivetrain;
import frc.robot.subsystems.SwerveFeatures;

/* You should consider using the more terse Command factories API instead https://docs.wpilib.org/en/stable/docs/software/commandbased/organizing-command-based.html#defining-commands */
public class PointAtTarget extends Command {
  CommandSwerveDrivetrain drivetrain;
  Supplier<Pose2d> targetSupplier;
  Pose2d targetPose;
  private final PIDController rotationController = new PIDController(12, 0, 0);

  public PointAtTarget(CommandSwerveDrivetrain drivetrain, Supplier<Pose2d> targetSupplier) {
    this.drivetrain = drivetrain;
    this.targetSupplier = targetSupplier;

    rotationController.enableContinuousInput(-Math.PI, Math.PI);
    addRequirements(drivetrain);
  }

  // Called when the command is initially scheduled.
  @Override
  public void initialize() {
    this.targetPose = this.targetSupplier.get();
    rotationController.setSetpoint(targetPose.getRotation().getRadians());
  }

  // Called every time the scheduler runs while the command is scheduled.
  @Override
  public void execute() {
    double currentAngle = drivetrain.getState().Pose.getRotation().getRadians();

    double rateToRotate = rotationController.calculate(currentAngle);
    System.out.printf("PID error: %.3f, target: %.3f, current: %.3f, rateToRotate: %.3f\n",
        rotationController.getError(),
        rotationController.getSetpoint(), currentAngle, rateToRotate);
    drivetrain.applyRequest(() -> SwerveFeatures.drive.withRotationalRate(rateToRotate));
  }

  // Called once the command ends or is interrupted.
  @Override
  public void end(boolean interrupted) {

  }

  // Returns true when the command should end.
  @Override
  public boolean isFinished() {
    return false;
  }
}
