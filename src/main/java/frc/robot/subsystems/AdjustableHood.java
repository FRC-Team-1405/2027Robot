// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot.subsystems;

import java.util.function.DoubleSupplier;

import edu.wpi.first.wpilibj.Servo;
import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.Commands;
import edu.wpi.first.wpilibj2.command.SubsystemBase;
import frc.robot.Constants;
import frc.robot.Constants.HoodPreferences.HoodAngles;
import frc.robot.commands.SetHoodPosition;

public class AdjustableHood extends SubsystemBase {
  private final Servo servo1 = new Servo(4);
  private final Servo servo2 = new Servo(5);
  private double target = 0.0;

  private HoodAngles currentHoodPosition = HoodAngles.ZERO;

  /** Creates a new AdjustableHood. */
  /**
   * Hood that adjusts angle using a servo.
   */
  public AdjustableHood() {
    double pos = 0.0;
    servo1.setBoundsMicroseconds(2000, 1000, 1500, 1200, 1000);
    servo2.setBoundsMicroseconds(2000, 1000, 1500, 1200, 1000);
    SmartDashboard.putNumber("Hood/pos", pos);

    Command cmd = this.runSet(() -> SmartDashboard.getNumber("Hood/pos", pos)).withName("SetPosition")
        .ignoringDisable(true);
    SmartDashboard.putData("Hood/setPos", cmd);

  }

  @Override
  public void periodic() {

  }

  // private function to set servo position (double)
  public void setServo(DoubleSupplier position) {
    target = position.getAsDouble();
    SmartDashboard.putNumber("Hood/Hood Target", target);
    servo1.set(target);
    servo2.set(target);
  }

  public void stopServo() {
    servo1.setDisabled();
    servo2.setDisabled();
  }

  /**
   * @return the last set servo target, used to calculate distance to next target.
   */
  public double getTarget() {
    return target;
  }

  /**
   * Sets the servo and then waits for the hood to reach the position.
   * 
   * @param position
   * @return
   */
  public Command runSet(DoubleSupplier position) {
    return runOnce(() -> setServo(position))
        .andThen(Commands.waitSeconds(position.getAsDouble() * Constants.HoodPreferences.SERVO_FULL_RANGE_SECONDS));
  }

  public Command rotateHoodPosition() {
    switch (currentHoodPosition) {
      case ZERO:
        return new SetHoodPosition(this, HoodAngles.SHORT);

      case SHORT:
        return new SetHoodPosition(this, HoodAngles.MEDIUM);

      case MEDIUM:
        return new SetHoodPosition(this, HoodAngles.LONG);

      case LONG:
        return new SetHoodPosition(this, HoodAngles.SHORT);

      default:
        return Commands.none();
    }

  }
}
