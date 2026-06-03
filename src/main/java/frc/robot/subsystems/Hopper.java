// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot.subsystems;

import com.ctre.phoenix6.StatusCode;
import com.ctre.phoenix6.configs.TalonFXConfiguration;
import com.ctre.phoenix6.controls.MotionMagicVelocityVoltage;
import com.ctre.phoenix6.controls.NeutralOut;
import com.ctre.phoenix6.hardware.TalonFX;
import com.ctre.phoenix6.signals.InvertedValue;

import edu.wpi.first.units.measure.AngularVelocity;
import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.SubsystemBase;
import frc.robot.Constants;
import frc.robot.constants.FeatureSwitches;
import frc.robot.lib.FinneyLogger;
import frc.robot.sim.sjc.MotorSim_Mech_SJC;
import frc.robot.sim.sjc.PhysicsSim_SJC;

public class Hopper extends SubsystemBase {
  private final FinneyLogger fLogger = new FinneyLogger(this.getClass().getSimpleName());

  private final TalonFX motor = new TalonFX(Constants.CANBus.HOPPER_MOTOR);

  private final MotorSim_Mech_SJC hopper_motorSimMech = new MotorSim_Mech_SJC("Hopper/Mech");

  private final MotionMagicVelocityVoltage speed = new MotionMagicVelocityVoltage(0);
  private final NeutralOut stop = new NeutralOut();

  public Hopper() {
    setupMotors();
    simulationInit();
  }

  // ── Motor Configuration ──────────────────────────────────────────────────

  private void setupMotors() {
    TalonFXConfiguration configs = new TalonFXConfiguration();

    configs.Slot0.kS = Constants.HopperPreferences.KS;
    configs.Slot0.kV = Constants.HopperPreferences.KV;
    configs.Slot0.kP = Constants.HopperPreferences.KP;
    configs.Slot0.kI = Constants.HopperPreferences.KI;
    configs.Slot0.kD = Constants.HopperPreferences.KD;

    configs.Voltage.PeakForwardVoltage = Constants.HopperPreferences.PEAK_FORWARD_VOLTAGE;
    configs.Voltage.PeakReverseVoltage = Constants.HopperPreferences.PEAK_REVERSE_VOLTAGE;

    configs.MotionMagic.MotionMagicCruiseVelocity = Constants.HopperPreferences.CRUISE_VELOCITY;
    configs.MotionMagic.MotionMagicAcceleration = Constants.HopperPreferences.ACCELERATION;

    // configs.CurrentLimits.StatorCurrentLimit =
    // Constants.HopperPreferences.STATOR_CURRENT_LIMIT;
    // configs.CurrentLimits.SupplyCurrentLimit =
    // Constants.HopperPreferences.SUPPLY_CURRENT_LIMIT;

    configs.MotorOutput.Inverted = InvertedValue.Clockwise_Positive;

    StatusCode status = StatusCode.StatusCodeNotInitialized;
    for (int i = 0; i < 5; ++i) {
      status = motor.getConfigurator().apply(configs);
      if (status.isOK())
        break;
    }
    if (!status.isOK()) {
      System.out.println("Could not configure hopper motor. Error: " + status.toString());
    }
    fLogger.log("Hopper motor configured");
  }

  // ── Periodic ─────────────────────────────────────────────────────────────

  @Override
  public void periodic() {
    if (FeatureSwitches.ENABLE_SUBSYSTEM_NT_LOGGING) {
      SmartDashboard.putNumber("Hopper/StatorCurrent", motor.getStatorCurrent().getValueAsDouble());
      SmartDashboard.putNumber("Hopper/Velocity", motor.getVelocity().getValueAsDouble());
      SmartDashboard.putNumber("Hopper/PIDError", motor.getClosedLoopError().getValueAsDouble());
    }

    hopper_motorSimMech.update(motor.getPosition(), motor.getVelocity());
  }

  // ── Simulation ───────────────────────────────────────────────────────────

  public void simulationInit() {
    // Hopper roller: low inertia, light load, direct drive
    PhysicsSim_SJC.getInstance().addTalonFX(motor,
        /* rotorInertia= */0.001, /* loadMassKg= */0.05, /* armMeters= */0.05,
        /* viscousCoeff= */0.01, /* numberOfMotors= */1, /* gearRatio= */1.0);
  }

  @Override
  public void simulationPeriodic() {
    PhysicsSim_SJC.getInstance().run();
  }

  // ── Motor Actions ────────────────────────────────────────────────────────

  public void setSpeed(AngularVelocity velocity) {
    motor.setControl(speed.withVelocity(velocity));
  }

  private void forwardHopper() {
    setSpeed(Constants.HopperPreferences.HOPPER_FORWARD_SPEED);
    fLogger.log("Forward Hopper");
  }

  private void reverseHopper() {
    setSpeed(Constants.HopperPreferences.HOPPER_REVERSE_SPEED);
    fLogger.log("Reverse Hopper");
  }

  private void stopHopper() {
    motor.setControl(stop);
    fLogger.log("Stop Hopper");
  }

  /** Start feeding balls forward. For use by external commands. */
  public void startFeeding() {
    forwardHopper();
  }

  /** Stop feeding balls. For use by external commands. */
  public void stopFeeding() {
    stopHopper();
  }

  // ── Public Commands ──────────────────────────────────────────────────────

  public Command runForwardHopper() {
    return runOnce(() -> forwardHopper()).withName("Run Forward Hopper");
  }

  public Command runReverseHopper() {
    return startEnd(() -> reverseHopper(), () -> stopHopper()).withName("Run Reverse Hopper");
  }

  public Command runStopHopper() {
    return runOnce(() -> stopHopper()).withName("Run Stop Hopper");
  }
}
