// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot.subsystems;

import com.ctre.phoenix6.controls.MotionMagicVoltage;
import com.ctre.phoenix6.controls.NeutralOut;
import com.ctre.phoenix6.hardware.TalonFX;

import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.Commands;
import edu.wpi.first.wpilibj2.command.SubsystemBase;
import frc.robot.Constants;
import frc.robot.lib.FinneyLogger;
import frc.robot.sim.SimProfiles;

public class Climber extends SubsystemBase {
  private final FinneyLogger fLogger = new FinneyLogger(this.getClass().getSimpleName());
  /** Creates a new Climber. */
  private TalonFX motor = new TalonFX(Constants.CANBus.CLIMBER_MOTOR);
  private final MotionMagicVoltage motorPosition = new MotionMagicVoltage(0);
  private final NeutralOut stop = new NeutralOut();
  private TalonFX grabber = new TalonFX(Constants.CANBus.CLIMBER_GRABBER);
  private final MotionMagicVoltage grabberPosition = new MotionMagicVoltage(0);

  private int climberSettleCount = 0;
  private double climberPositionTarget = 0;
  private int grabberSettleCount = 0;
  private double grabberPositionTarget = 0;

  private static final double CLIMBER_CURRENT_LIMIT = 40.0;

  @Override
  public void periodic() {
    if (Math.abs(climberPositionTarget
        - motor.getClosedLoopReference().getValueAsDouble()) < Constants.ClimberPreferences.POSITION_TOLERANCE) {
      if (Math.abs(motor.getClosedLoopError().getValueAsDouble()) < Constants.ClimberPreferences.POSITION_TOLERANCE) {
        climberSettleCount += 1;
      } else {
        climberSettleCount = 0;
      }
    } else {
      climberSettleCount = 0;
    }

    if (Math.abs(grabberPositionTarget
        - grabber.getClosedLoopReference().getValueAsDouble()) < Constants.ClimberPreferences.POSITION_TOLERANCE) {
      if (Math.abs(grabber.getClosedLoopError().getValueAsDouble()) < Constants.ClimberPreferences.POSITION_TOLERANCE) {
        grabberSettleCount += 1;
      } else {
        grabberSettleCount = 0;
      }
    } else {
      grabberSettleCount = 0;
    }
  }

  private boolean isClimberAtTarget() {
    return (climberSettleCount >= Constants.ClimberPreferences.SETTLE_MAX);
  }

  private boolean isGrabberAtTarget() {
    return (grabberSettleCount >= Constants.ClimberPreferences.SETTLE_MAX);
  }

  public void move(double position) {
    motor.setControl(motorPosition.withPosition(position));
    climberPositionTarget = position;
  }

  public void moveGrabber(double position) {
    grabber.setControl(grabberPosition.withPosition(position));
    grabberPositionTarget = position;
  }

  public Climber() {
    SimProfiles.initClimber(motor);
    SimProfiles.initGrabber(grabber);
  }

  // function to climb up - motor forward direction
  private void climbUp() {
    move(Constants.ClimberPreferences.CLIMBER_EXTEND_POSITION);
    fLogger.log("Climb up ");
  }

  // function to climb down -- motor backwards direction
  private void climbDown() {
    move(Constants.ClimberPreferences.CLIMBER_RETRACT_POSITION);
    fLogger.log("Climb down ");
  }

  private void stop() {
    motor.setControl(stop);
    fLogger.log("Stop ");
  }

  /**
   * This command runs the climb up action
   * by extending the climber arm.
   * 
   * @return Command
   */
  public Command runClimbUp() {
    return runOnce(() -> climbUp()).andThen(Commands.waitUntil(() -> isClimberAtTarget())).withName("Climb Up");
  }

  /**
   * This command runs the climb down action
   * by retracting the climber arm.
   * 
   * @return Command
   */
  public Command runClimbDown() {
    return runOnce(() -> climbDown()).andThen(Commands.waitUntil(() -> isClimberAtTarget())).withName("Climb Down");
  }

  /**
   * This command runs the stop action.
   * 
   * @return Command
   */
  public Command runStop() {
    return runOnce(() -> stop()).andThen(Commands.waitUntil(() -> isClimberAtTarget())).withName("Climb Stop");

  }

  // grabber motors

  private void openClaw() {
    moveGrabber(Constants.ClimberPreferences.GRABBER_OPEN_POSITION);
    fLogger.log("Open Claw ");
  }

  private void closeClaw() {
    moveGrabber(Constants.ClimberPreferences.GRABBER_CLOSED_POSITION);
    fLogger.log("Close Claw ");
  }

  private void stopClaw() {
    grabber.setControl(stop);
    fLogger.log("Stop Claw ");
  }

  /**
   * This command runs the open claw action.
   * 
   * @return Command
   */
  public Command runOpenClaw() {
    return runOnce(() -> openClaw()).andThen(Commands.waitUntil(() -> isGrabberAtTarget())).withName("Open Claw");
  }

  /**
   * This command runs the close claw action.
   * 
   * @return Command
   */
  public Command runCloseClaw() {
    return runOnce(() -> closeClaw()).andThen(Commands.waitUntil(() -> isGrabberAtTarget())).withName("Close Claw");
  }

  /**
   * This command runs the stop claw action.
   * 
   * @return Command
   */
  public Command runStopClaw() {
    return runOnce(() -> stopClaw()).andThen(Commands.waitUntil(() -> isClimberAtTarget())).withName("Stop Claw");
  }

  /**
   * This command will extend the climber and then open the claw.
   * 
   * @return
   */
  public Command runExtendClimber() {
    return runClimbUp().andThen(runOpenClaw()).withName("Extend Climber");
  }

  public Command runRetractClimber() {
    return runCloseClaw().andThen(runClimbDown()).withName("Retract Climber");
  }
}
