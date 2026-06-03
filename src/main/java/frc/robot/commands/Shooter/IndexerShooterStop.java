// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot.commands.Shooter;

import edu.wpi.first.wpilibj2.command.SequentialCommandGroup;
import frc.robot.subsystems.Indexer;
import frc.robot.subsystems.Shooter;

/* You should consider using the more terse Command factories API instead https://docs.wpilib.org/en/stable/docs/software/commandbased/organizing-command-based.html#defining-commands */
public class IndexerShooterStop extends SequentialCommandGroup {
  /** Creates a new IndexerShooterStop. */
  public IndexerShooterStop(Shooter shooterSubsytem, Indexer indexerSubsystem) {
    addCommands(
        shooterSubsytem.stopShooter(),
        indexerSubsystem.runStopIndexer());
  };
}