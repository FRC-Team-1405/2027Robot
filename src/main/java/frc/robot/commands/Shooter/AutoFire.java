// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot.commands.Shooter;

import java.util.function.BooleanSupplier;
import java.util.function.DoubleSupplier;
import java.util.function.Supplier;

import edu.wpi.first.units.measure.AngularVelocity;
import edu.wpi.first.wpilibj.Timer;
import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.CommandScheduler;
import edu.wpi.first.wpilibj2.command.Commands;
import edu.wpi.first.wpilibj2.command.SequentialCommandGroup;
import edu.wpi.first.wpilibj2.command.WaitCommand;
import edu.wpi.first.wpilibj2.command.button.Trigger;
import frc.robot.Robot;
import frc.robot.commands.DynamicWaitCommand;
import frc.robot.constants.FeatureSwitches;
import frc.robot.subsystems.Hopper;
import frc.robot.subsystems.Indexer;
import frc.robot.subsystems.Intake;
import frc.robot.subsystems.Shooter;

public class AutoFire {

  private static double INDEXER_ROTATION_THRESHOLD = 150.0;

  private AutoFire() {
  }

  /**
   * Teleop fire command. Spins up the flywheel, waits for the first lock, then
   * feeds the indexer continuously until cancelled by button release. The hopper
   * is driven by the hopper-trigger (follows indexer state) so it is NOT
   * required here — claiming it would conflict with the trigger's commands.
   * Designed for {@code whileTrue}.
   */
  public static Command teleop(
      Shooter shooter,
      Indexer indexer,
      Supplier<AngularVelocity> indexerVelocity, Intake intake) {
    return new TeleopFireCommand(shooter, indexer, indexerVelocity, intake);
  }

  public static Command DynamicTeleop(
      Shooter shooter,
      Indexer indexer,
      Supplier<AngularVelocity> indexerVelocity, Intake intake, DoubleSupplier distanceToHub,
      Trigger activateShooting) {
    return new DynamicTeleopFireCommand(shooter, indexer, indexerVelocity, intake, distanceToHub, activateShooting);
  }

  public static Command autonomous(
      Shooter shooter,
      Indexer indexer,
      Supplier<AngularVelocity> indexerVelocity) {

    double requestedDuration = 5.0;

    return Commands.sequence(
        Commands.waitUntil(() -> Robot.getAutonomousTimeLeft() > 1.0),
        Commands.deadline(
            new DynamicWaitCommand(
                () -> Math.min(requestedDuration, Robot.getAutonomousTimeLeft() - 1.0)),
            new TeleopFireCommand(shooter, indexer, indexerVelocity)));
  }

  public static Command dynamicAutonomous(
      Shooter shooter,
      Indexer indexer,
      Supplier<AngularVelocity> indexerVelocity, DoubleSupplier distanceToHub) {

    double requestedDuration = 5.0;

    return Commands.sequence(
        Commands.waitUntil(() -> Robot.getAutonomousTimeLeft() > 1.0),
        Commands.deadline(
            new DynamicWaitCommand(
                () -> Math.min(requestedDuration, Robot.getAutonomousTimeLeft() - 1.0)),
            new DynamicTeleopFireCommand(shooter, indexer, indexerVelocity, distanceToHub, new Trigger(() -> true))));
  }

  /**
   * Autonomous single-shot fire sequence. Spins up, waits for lock, fires one
   * ball, then stops.
   */
  // TODO change this to a time based shooting sequence
  // public static Command autonomous(
  // Shooter shooter,
  // Indexer indexer,
  // Hopper hopper,
  // Supplier<AngularVelocity> indexerVelocity) {
  // return new SequentialCommandGroup(
  // shooter.runShooter(),
  // Commands.waitUntil(shooter::isReadyToFire),
  // indexer.runIndexer(indexerVelocity),
  // Commands.waitSeconds(5),
  // shooter.stopShooter(),
  // indexer.runStopIndexer(),
  // hopper.runStopHopper());
  // }

  /**
   * Continuous fire command for teleop use. Spins up the flywheel, waits for
   * the first lock, then feeds the indexer continuously until the command is
   * cancelled (button release). The hopper is managed by the hopper-trigger
   * (follows indexer state) and is intentionally NOT required here to avoid
   * subsystem conflicts with the trigger's commands.
   */
  private static class TeleopFireCommand extends Command {
    private final Shooter shooter;
    private final Indexer indexer;
    private Intake intake = null;
    private final Supplier<AngularVelocity> indexerVelocity;
    private boolean feeding;
    private double shooterStartTimestamp = 0.0;
    private double startRotation;

    TeleopFireCommand(Shooter shooter, Indexer indexer,
        Supplier<AngularVelocity> indexerVelocity) {
      this.shooter = shooter;
      this.indexer = indexer;
      this.indexerVelocity = indexerVelocity;
      addRequirements(shooter, indexer);
      setName("AutoFire_Teleop");
    }

    TeleopFireCommand(Shooter shooter, Indexer indexer,
        Supplier<AngularVelocity> indexerVelocity, Intake intake) {
      this(shooter, indexer, indexerVelocity);
      this.intake = intake;
    }

    @Override
    public void initialize() {
      shooter.spinUp();
      feeding = false;
      shooterStartTimestamp = Timer.getFPGATimestamp();
      System.out.println("[AutoFire] initialize: spinning up");

      indexer.getRotations();
      startRotation = indexer.getRotations();
    }

    @Override
    public void execute() {
      shooter.updateSpeed();
      if (!feeding && shooter.isReadyToFire()) {
        indexer.startFeeding(indexerVelocity);
        feeding = true;
        // System.out.println("[AutoFire] locked - feeding started");
      } else if (!shooter.isReadyToFire() && feeding) {
        indexer.stopFeeding();
        feeding = false;
        // System.out.println("[AutoFire] unlocked - feeding stopped");

      }

      // retract intake after 3 seconds
      if (this.intake != null) {
        if (FeatureSwitches.RETRACT_INTAKE_WITH_TIME) {
          double currentTimeShooting = Timer.getFPGATimestamp() - shooterStartTimestamp;
          if (currentTimeShooting > 3) {
            CommandScheduler.getInstance().schedule(intake.runIntakeCenter()); // TODO are you rescheduling every loop?
          }
        }

        if (FeatureSwitches.RETRACT_INTAKE_USING_INDEXER_ROTATIONS) {
          // current rotations minus rotation in beginning
          double currentRotations = indexer.getRotations() - startRotation;
          SmartDashboard.putNumber("AutoFire/IndexerRotations", currentRotations);
          if (currentRotations > INDEXER_ROTATION_THRESHOLD) {
            CommandScheduler.getInstance().schedule(intake.runIntakeCenter()); // TODO are you rescheduling every loop?
          }
        }
      }

    }

    @Override
    public void end(boolean interrupted) {
      indexer.stopFeeding();
      shooter.stopShooter(); // TODO maybe remove this or make it only on autonomous
      System.out.println("[AutoFire] end: interrupted=" + interrupted);
    }

    @Override
    public boolean isFinished() {
      return false;
    }
  }

  // Teleop command for dynamic shooting

  private static class DynamicTeleopFireCommand extends Command {
    private final Shooter shooter;
    private final Indexer indexer;
    private Intake intake = null;
    private final Supplier<AngularVelocity> indexerVelocity;
    private boolean feeding;
    private double shooterStartTimestamp = 0.0;
    private double startRotation;
    DoubleSupplier distanceToHub;

    private Trigger activateShooting;

    DynamicTeleopFireCommand(Shooter shooter, Indexer indexer,
        Supplier<AngularVelocity> indexerVelocity, DoubleSupplier distanceToHub, Trigger activateShooting) {
      this.shooter = shooter;
      this.indexer = indexer;
      this.indexerVelocity = indexerVelocity;
      this.distanceToHub = distanceToHub;
      this.activateShooting = activateShooting;
      addRequirements(shooter, indexer);
      setName("AutoFire_Dynamic_Teleop");
    }

    DynamicTeleopFireCommand(Shooter shooter, Indexer indexer,
        Supplier<AngularVelocity> indexerVelocity, Intake intake, DoubleSupplier distanceToHub,
        Trigger activateShooting) {
      this(shooter, indexer, indexerVelocity, distanceToHub, activateShooting);
      this.intake = intake;
    }

    @Override
    public void initialize() {
      shooter.setDynamicShooterSpeed(distanceToHub);
      shooter.spinUp();
      feeding = false;
      shooterStartTimestamp = Timer.getFPGATimestamp();
      System.out.println("[AutoFire] initialize: spinning up");

      indexer.getRotations();
      startRotation = indexer.getRotations();
    }

    @Override
    public void execute() {
      shooter.setDynamicShooterSpeed(distanceToHub);
      shooter.updateSpeed();
      if (!feeding && shooter.isReadyToFire()) {
        if (activateShooting.getAsBoolean()) {
          indexer.startFeeding(indexerVelocity);
          feeding = true;
        }
        // System.out.println("[AutoFire] locked - feeding started");
      } else if (!shooter.isReadyToFire() && feeding) {
        indexer.stopFeeding();
        feeding = false;
        // System.out.println("[AutoFire] unlocked - feeding stopped");

      }

      // retract intake after 3 seconds
      if (this.intake != null) {
        if (FeatureSwitches.RETRACT_INTAKE_WITH_TIME) {
          double currentTimeShooting = Timer.getFPGATimestamp() - shooterStartTimestamp;
          if (currentTimeShooting > 3) {
            CommandScheduler.getInstance().schedule(intake.runIntakeCenter()); // TODO are you rescheduling every loop?
          }
        }

        if (FeatureSwitches.RETRACT_INTAKE_USING_INDEXER_ROTATIONS) {
          // current rotations minus rotation in beginning
          double currentRotations = indexer.getRotations() - startRotation;
          SmartDashboard.putNumber("AutoFire/IndexerRotations", currentRotations);
          if (currentRotations > INDEXER_ROTATION_THRESHOLD) {
            CommandScheduler.getInstance().schedule(intake.runIntakeCenter()); // TODO are you rescheduling every loop?
          }
        }
      }

    }

    @Override
    public void end(boolean interrupted) {
      indexer.stopFeeding();
      shooter.stopShooter(); // TODO maybe remove this or make it only on autonomous
      System.out.println("[AutoFire] end: interrupted=" + interrupted);
    }

    @Override
    public boolean isFinished() {
      return false;
    }
  }
}
