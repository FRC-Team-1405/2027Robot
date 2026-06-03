// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot.commands.PidToPose;

import java.util.function.Supplier;

import com.pathplanner.lib.auto.NamedCommands;

import edu.wpi.first.apriltag.AprilTag;
import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Rotation2d;
import edu.wpi.first.math.trajectory.TrapezoidProfile;
import edu.wpi.first.networktables.NetworkTableInstance;
import edu.wpi.first.networktables.StructPublisher;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.SequentialCommandGroup;
import edu.wpi.first.wpilibj2.command.WaitCommand;
import frc.robot.lib.AprilTags;
import frc.robot.subsystems.CommandSwerveDrivetrain;

/* You should consider using the more terse Command factories API instead https://docs.wpilib.org/en/stable/docs/software/commandbased/organizing-command-based.html#defining-commands */
public class PidToPoseCommands {
  public static final double SCORE_TOLERANCE = 1.2; // inches
  private static final double TOLERANCE = 2; // inches

  private static final TrapezoidProfile.Constraints drivingContraints = new TrapezoidProfile.Constraints(5, 6);

  /*
   * Debug Pose used for finding a position on the field in Advantage scope.
   * You can edit the location in network tables via shuffleboard
   */
  private static StructPublisher<Pose2d> posePublisher = NetworkTableInstance.getDefault()
      .getStructTopic("DebugPose", Pose2d.struct).publish();

  /* Poses */
  public static Supplier<Pose2d> pos1 = () -> AprilTags.getAprilTagPose(1);

  public static void registerCommands(CommandSwerveDrivetrain drivetrain) {
    Pose2d debugPose = new Pose2d(4.22, 3.22, Rotation2d.fromDegrees(60));
    posePublisher.set(debugPose);

    /* Commands */
    // Uses command suppliers instead of commands so that we can reuse the same
    // command in an autonomous
    Supplier<Command> MoveTo_pos1 = () -> new PidToPoseCommand.Builder(
        () -> pos1.get(), drivetrain, "MoveTo_pos1")
        .withTolerance(SCORE_TOLERANCE)
        .build();

    /* Full Autos */
    Command P2P_auto1 = new SequentialCommandGroup(
        MoveTo_pos1.get(),
        new WaitCommand(1));

    /* Register Commands */
    NamedCommands.registerCommand("P2P_auto1", P2P_auto1);
  }
}
