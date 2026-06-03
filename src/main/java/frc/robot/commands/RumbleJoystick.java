// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot.commands;

import edu.wpi.first.wpilibj.Joystick;
import edu.wpi.first.wpilibj.GenericHID.RumbleType;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.CommandScheduler;
import edu.wpi.first.wpilibj2.command.Commands;
import edu.wpi.first.wpilibj2.command.PrintCommand;
import edu.wpi.first.wpilibj2.command.SequentialCommandGroup;
import edu.wpi.first.wpilibj2.command.WaitCommand;
import edu.wpi.first.wpilibj2.command.button.CommandXboxController;
import frc.robot.util.GamePeriod;

// NOTE:  Consider using this command inline, rather than writing a subclass.  For more
// information, see:
// https://docs.wpilib.org/en/stable/docs/software/commandbased/convenience-features.html
/**
 * Give a general description
 */
public class RumbleJoystick extends SequentialCommandGroup {
  /**
   * Give a description of the class
   * 
   * @param joystick
   * @param rumbleType
   * @param rumbleStrength
   * 
   */
  public RumbleJoystick(CommandXboxController joystick, RumbleType rumbleType, double rumbleStrength,
      double rumbleDuration) {
    addCommands(
        Commands.print(String.format("Running RumbleJoystick rumbleType: %s, rumbleStrenth: %s, rumbleDuration: %s",
            rumbleType.name(), rumbleStrength, rumbleDuration)),
        runRumbleStart(joystick, rumbleType, rumbleStrength),
        new WaitCommand(rumbleDuration),
        runRumbleStop(joystick));
  }

  /**
   * Rumble for 3 seconds.
   * 
   * @param joystick
   */
  public RumbleJoystick(CommandXboxController joystick) {
    this(joystick, RumbleType.kBothRumble, 0.5, 1.0);
  }

  private Command runRumbleStart(CommandXboxController joystick, RumbleType rumbleType, double rumbleStrength) {
    return Commands.runOnce(() -> {
      if (joystick != null) {
        joystick.setRumble(rumbleType, rumbleStrength);
      }
    });
  }

  public Command runRumbleStop(CommandXboxController joystick) {
    return runRumbleStart(joystick, RumbleType.kBothRumble, 0.0);
  }

  // ---DO NOT EDIT setRumbleOccasion(). IT IS VERY FRAGILE
  /**
   * Sets the occasion, or when the joystick will rumble. The joystick will rumble
   * whenever the period of the match changes.
   * 
   * @param joystick the joystick that will rumble
   */
  public static void setPeriodChangeOccasion(CommandXboxController joystick) {
    GamePeriod.setPeriodChangeListener(() -> {
      CommandScheduler.getInstance().schedule(new RumbleJoystick(joystick, RumbleType.kBothRumble, 0.8, 0.5));
    });
  }

  public static void setPeriodChangeWarningOccasion(CommandXboxController joystick) {
    GamePeriod.setPeriodChangeWarningListener(() -> {
      CommandScheduler.getInstance().schedule(new RumbleJoystick(joystick, RumbleType.kBothRumble, 0.5, 0.5));
    });
  }

  //
  // Presets
  //

  public static Command leftRightLeftRight(CommandXboxController joystick) {
    return new SequentialCommandGroup(
        new RumbleJoystick(joystick, RumbleType.kLeftRumble, 1.0, 0.15),
        new RumbleJoystick(joystick, RumbleType.kRightRumble, 1.0, 0.15),
        new RumbleJoystick(joystick, RumbleType.kLeftRumble, 1.0, 0.15),
        new RumbleJoystick(joystick, RumbleType.kRightRumble, 1.0, 0.15));
  }

  /**
   * Rumbles continously, remember to call stopRumble!
   */
  public static Command continousRumble(CommandXboxController joystick) {
    return Commands.runOnce(() -> {
      if (joystick != null) {
        joystick.setRumble(RumbleType.kBothRumble, 0.5);
      }
    });
  }

  public static Command stopRumble(CommandXboxController joystick) {
    return Commands.runOnce(() -> {
      if (joystick != null) {
        joystick.setRumble(RumbleType.kBothRumble, 0);
      }
    });
  }
}
