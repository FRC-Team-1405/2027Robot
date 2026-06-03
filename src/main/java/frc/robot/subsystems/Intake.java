// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot.subsystems;

import com.ctre.phoenix6.StatusCode;
import com.ctre.phoenix6.configs.TalonFXConfiguration;
import com.ctre.phoenix6.controls.MotionMagicVelocityVoltage;
import com.ctre.phoenix6.controls.MotionMagicVoltage;
import com.ctre.phoenix6.controls.NeutralOut;
import com.ctre.phoenix6.hardware.TalonFX;
import com.ctre.phoenix6.signals.InvertedValue;
import com.ctre.phoenix6.signals.NeutralModeValue;

import edu.wpi.first.wpilibj.DriverStation;
import edu.wpi.first.wpilibj.RobotBase;
import edu.wpi.first.wpilibj.GenericHID.RumbleType;
import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.CommandScheduler;
import edu.wpi.first.wpilibj2.command.Commands;
import edu.wpi.first.wpilibj2.command.InstantCommand;
import edu.wpi.first.wpilibj2.command.SequentialCommandGroup;
import edu.wpi.first.wpilibj2.command.SubsystemBase;
import edu.wpi.first.wpilibj2.command.button.CommandXboxController;
import frc.robot.commands.RumbleJoystick;
import frc.robot.Constants;
import frc.robot.Constants.IntakePreferences;
import frc.robot.constants.FeatureSwitches;
import frc.robot.lib.FinneyLogger;
import frc.robot.sim.sjc.MotorSim_Mech_SJC;
import frc.robot.sim.sjc.PhysicsSim_SJC;

// todo add a button on elastic to zero the intake
public class Intake extends SubsystemBase {
  private final FinneyLogger fLogger = new FinneyLogger(this.getClass().getSimpleName());

  private final TalonFX intakeMotor = new TalonFX(Constants.CANBus.INTAKE_MOTOR);
  private final TalonFX pickupMotor = new TalonFX(Constants.CANBus.PICKUP_MOTOR);

  private final MotorSim_Mech_SJC intake_motorSimMech = new MotorSim_Mech_SJC("Intake/DeployMech");
  // private final MotorSim_Mech_SJC pickup_motorSimMech = new
  // MotorSim_Mech_SJC("Intake/PickupMech");

  private final MotionMagicVoltage intakePositionRequest = new MotionMagicVoltage(0);
  private final NeutralOut neutralRequest = new NeutralOut();

  private int settleCount = 0;
  private int stallCount = 0;
  private double intakePositionTarget = 0;
  private boolean isIntakeDeployed = false;

  // Mechanical protection
  private boolean isIntakeMovementDisabled = false;

  public Intake() {
    setupMotors();
    simulationInit();

    SmartDashboard.putBoolean("Intake/IntakeMovementEnabled", !isIntakeMovementDisabled);
    SmartDashboard.putBoolean("Intake/Zero Intake Position", false);
  }

  // ── Motor Configuration ──────────────────────────────────────────────────

  private void setupMotors() {
    setupIntakeMotor();
    setupPickupMotor();
  }

  private void setupIntakeMotor() {
    TalonFXConfiguration config = new TalonFXConfiguration();

    config.Slot0.kP = IntakePreferences.DEPLOY_KP;
    config.Slot0.kI = IntakePreferences.DEPLOY_KI;
    config.Slot0.kD = IntakePreferences.DEPLOY_KD;
    config.Slot0.kS = IntakePreferences.DEPLOY_KS;
    config.Slot0.kV = IntakePreferences.DEPLOY_KV;
    config.Slot0.kG = IntakePreferences.DEPLOY_KG;

    config.MotionMagic.MotionMagicCruiseVelocity = IntakePreferences.DEPLOY_CRUISE_VELOCITY;
    config.MotionMagic.MotionMagicAcceleration = IntakePreferences.DEPLOY_ACCELERATION;
    config.MotionMagic.MotionMagicJerk = IntakePreferences.DEPLOY_JERK;

    config.Voltage.PeakForwardVoltage = IntakePreferences.PEAK_FORWARD_VOLTAGE;
    config.Voltage.PeakReverseVoltage = IntakePreferences.PEAK_REVERSE_VOLTAGE;

    config.CurrentLimits.StatorCurrentLimitEnable = true;
    config.CurrentLimits.StatorCurrentLimit = IntakePreferences.DEPLOY_STATOR_LIMIT;
    config.CurrentLimits.SupplyCurrentLimitEnable = true;
    config.CurrentLimits.SupplyCurrentLimit = IntakePreferences.DEPLOY_SUPPLY_LIMIT;

    // Soft limits prevent driving beyond mechanical range
    double softForward = Math.max(IntakePreferences.INTAKE_MOTOR_OUT, IntakePreferences.INTAKE_MOTOR_IN)
        + IntakePreferences.SOFT_LIMIT_MARGIN;
    double softReverse = Math.min(IntakePreferences.INTAKE_MOTOR_OUT, IntakePreferences.INTAKE_MOTOR_IN)
        - IntakePreferences.SOFT_LIMIT_MARGIN;
    config.SoftwareLimitSwitch.ForwardSoftLimitEnable = true;
    config.SoftwareLimitSwitch.ForwardSoftLimitThreshold = softForward;
    config.SoftwareLimitSwitch.ReverseSoftLimitEnable = true;
    config.SoftwareLimitSwitch.ReverseSoftLimitThreshold = softReverse;

    config.MotorOutput.NeutralMode = NeutralModeValue.Coast;
    config.MotorOutput.Inverted = InvertedValue.Clockwise_Positive;

    StatusCode status = StatusCode.StatusCodeNotInitialized;
    for (int i = 0; i < 5; ++i) {
      status = intakeMotor.getConfigurator().apply(config);
      if (status.isOK())
        break;
    }
    if (!status.isOK()) {
      System.out.println("Could not configure intake motor. Error: " + status.toString());
    }

    intakeMotor.getPosition().setUpdateFrequency(10);
    intakeMotor.optimizeBusUtilization();

    fLogger.log("Intake motor configured (deploy)");
  }

  private void setupPickupMotor() {
    TalonFXConfiguration config = new TalonFXConfiguration();

    config.Slot0.kP = IntakePreferences.PICKUP_KP;
    config.Slot0.kI = IntakePreferences.PICKUP_KI;
    config.Slot0.kD = IntakePreferences.PICKUP_KD;
    config.Slot0.kS = IntakePreferences.PICKUP_KS;
    config.Slot0.kV = IntakePreferences.PICKUP_KV;

    config.MotionMagic.MotionMagicAcceleration = IntakePreferences.PICKUP_ACCELERATION;
    config.MotionMagic.MotionMagicJerk = IntakePreferences.PICKUP_JERK;

    config.Voltage.PeakForwardVoltage = IntakePreferences.PEAK_FORWARD_VOLTAGE;
    config.Voltage.PeakReverseVoltage = IntakePreferences.PEAK_REVERSE_VOLTAGE;

    config.CurrentLimits.StatorCurrentLimitEnable = true;
    config.CurrentLimits.StatorCurrentLimit = IntakePreferences.PICKUP_STATOR_LIMIT;
    config.CurrentLimits.SupplyCurrentLimitEnable = true;
    config.CurrentLimits.SupplyCurrentLimit = IntakePreferences.PICKUP_SUPPLY_LIMIT;

    config.MotorOutput.NeutralMode = NeutralModeValue.Coast;

    StatusCode status = StatusCode.StatusCodeNotInitialized;
    for (int i = 0; i < 5; ++i) {
      status = pickupMotor.getConfigurator().apply(config);
      if (status.isOK())
        break;
    }
    if (!status.isOK()) {
      System.out.println("Could not configure pickup motor. Error: " + status.toString());
    }
    fLogger.log("Pickup motor configured (roller)");
  }

  // ── Periodic ─────────────────────────────────────────────────────────────

  @Override
  public void periodic() {
    double currentPosition = intakeMotor.getPosition().getValueAsDouble();
    double positionError = Math.abs(currentPosition - intakePositionTarget);

    // Settle counting: require N consecutive cycles within tolerance
    if (positionError < IntakePreferences.POSITION_TOLERANCE) {
      settleCount++;
    } else {
      settleCount = 0;
    }

    // Stall detection for the deploy motor
    double statorCurrent = intakeMotor.getStatorCurrent().getValueAsDouble();
    double velocity = intakeMotor.getVelocity().getValueAsDouble();
    boolean motorCommanded = Math.abs(intakeMotor.getClosedLoopReference().getValueAsDouble()
        - currentPosition) > IntakePreferences.POSITION_TOLERANCE;

    if (RobotBase.isReal() && motorCommanded && Math.abs(velocity) < 0.5
        && statorCurrent > IntakePreferences.STALL_CURRENT_THRESHOLD) {
      stallCount++;
      if (stallCount >= IntakePreferences.STALL_CYCLES_THRESHOLD) {
        fLogger.log("STALL DETECTED — stopping intake deploy motor (%.1fA)", statorCurrent);
        intakeMotor.setControl(neutralRequest);
        // Accept wherever we are as the new target to prevent re-stalling
        intakePositionTarget = currentPosition;
        stallCount = 0;
      }
    } else {
      stallCount = 0;
    }

    checkForResetEncoder();
    publishTelemetry();

    intake_motorSimMech.update(intakeMotor.getPosition(), intakeMotor.getVelocity());
    // pickup_motorSimMech.update(pickupMotor.getPosition(),
    // pickupMotor.getVelocity());
  }

  // ── Simulation ───────────────────────────────────────────────────────────

  public void simulationInit() {
    // Configure simulated TalonFX profiles with reasonable estimates for an FRC
    // intake
    // Deploy arm (pivoting): modest rotor inertia, moderate mass at a lever arm,
    // geared
    PhysicsSim_SJC.getInstance().addTalonFX(intakeMotor,
        /* rotorInertia= */0.002, /* loadMassKg= */0.8, /* armMeters= */0.18,
        /* viscousCoeff= */0.02, /* numberOfMotors= */1, /* gearRatio= */20.0);

    // Pickup roller: small inertia, light load, direct drive
    PhysicsSim_SJC.getInstance().addTalonFX(pickupMotor,
        /* rotorInertia= */0.0002, /* loadMassKg= */0.05, /* armMeters= */0.05,
        /* viscousCoeff= */0.01, /* numberOfMotors= */1, /* gearRatio= */0.5);
  }

  // old pickup motor gear ratio = 0.5
  // new pickup motor gear ratio = 0.3333333
  @Override
  public void simulationPeriodic() {
    PhysicsSim_SJC.getInstance().run();
  }

  // ── State Queries ────────────────────────────────────────────────────────

  private boolean isAtTarget() {
    if (FeatureSwitches.INTAKE_SAFTEY_MODE_NO_DEPLOY) {
      return true;
    }
    return settleCount >= IntakePreferences.SETTLE_COUNT;
  }

  public boolean isIntakeExtended() {
    return isIntakeDeployed;
  }

  // ── Low-Level Motor Actions ──────────────────────────────────────────────

  private void setIntakePosition(double position) {
    if (FeatureSwitches.INTAKE_SAFTEY_MODE_NO_DEPLOY) {
      return;
    }

    if (isIntakeMovementDisabled) {
      return;
    }

    intakeMotor.setControl(intakePositionRequest.withPosition(position));
    intakePositionTarget = position;
    settleCount = 0;
    stallCount = 0;
  }

  // ── Intake Deploy Positions ──────────────────────────────────────────────

  private void deployOut() {
    isIntakeDeployed = true;
    setIntakePosition(IntakePreferences.INTAKE_MOTOR_OUT);
    fLogger.log("Intake → OUT (%.1f)", IntakePreferences.INTAKE_MOTOR_OUT);
  }

  private void deployIn() {
    isIntakeDeployed = false;
    setIntakePosition(IntakePreferences.INTAKE_MOTOR_IN);
    fLogger.log("Intake → IN (%.1f)", IntakePreferences.INTAKE_MOTOR_IN);
  }

  private void deployCenter() {
    isIntakeDeployed = true;
    setIntakePosition(IntakePreferences.INTAKE_MOTOR_CENTER);
    fLogger.log("Intake CENTER (%.1f)", IntakePreferences.INTAKE_MOTOR_CENTER);
  }

  // ── Public Commands ──────────────────────────────────────────────────────

  /**
   * Deploy the intake to the OUT position and hold there.
   * The motor continues holding position after the command finishes.
   */
  public Command runIntakeOut() {
    return Commands.sequence(
        runOnce(() -> deployOut()),
        Commands.waitUntil(this::isAtTarget))
        .withName("Run Intake Out");
  }

  /**
   * Retract the intake to the IN position and hold there.
   * The motor continues holding position after the command finishes.
   */
  public Command runIntakeIn() {
    return Commands.sequence(
        runOnce(() -> deployIn()),
        Commands.waitUntil(this::isAtTarget))
        .withName("Run Intake In");
  }

  /**
   * Move the intake to the CENTER position and hold there.
   */
  public Command runIntakeCenter() {
    return Commands.sequence(
        runOnce(() -> deployCenter()),
        Commands.waitUntil(this::isAtTarget))
        .withName("Run Intake Center");
  }

  public void checkForResetEncoder() {
    boolean value = SmartDashboard.getBoolean("Intake/Zero Intake Position", false);
    if (value) {
      intakeMotor.setPosition(0);
      SmartDashboard.putBoolean("Intake/Zero Intake Position", false);
    }
  }

  public void toggleIntakeMovementDisabledFlag(CommandXboxController joystick) {
    isIntakeMovementDisabled = !isIntakeMovementDisabled;

    SmartDashboard.putBoolean("Intake/IntakeMovementEnabled", !isIntakeMovementDisabled);

    if (isIntakeMovementDisabled) {
      CommandScheduler.getInstance().schedule(new RumbleJoystick(joystick, RumbleType.kBothRumble, 0.3, 0.5));
    } else {
      CommandScheduler.getInstance().schedule(RumbleJoystick.leftRightLeftRight(joystick));
    }
  }

  // ── Telemetry ────────────────────────────────────────────────────────────

  private void publishTelemetry() {
    if (FeatureSwitches.ENABLE_SUBSYSTEM_NT_LOGGING) {
      double position = intakeMotor.getPosition().getValueAsDouble();
      SmartDashboard.putNumber("Intake/DeployPosition", position);
      SmartDashboard.putNumber("Intake/DeployTarget", intakePositionTarget);
      SmartDashboard.putNumber("Intake/DeployError", Math.abs(position - intakePositionTarget));
      SmartDashboard.putNumber("Intake/DeployVelocity", intakeMotor.getVelocity().getValueAsDouble());
      SmartDashboard.putNumber("Intake/DeployStatorCurrent", intakeMotor.getStatorCurrent().getValueAsDouble());
      SmartDashboard.putNumber("Intake/PickupStatorCurrent", pickupMotor.getStatorCurrent().getValueAsDouble());
      SmartDashboard.putNumber("Intake/PickupSupplyCurrent", pickupMotor.getSupplyCurrent().getValueAsDouble());
      SmartDashboard.putNumber("Intake/PickupVelocity", pickupMotor.getVelocity().getValueAsDouble());
      SmartDashboard.putNumber("Intake/PickupError", pickupMotor.getClosedLoopError().getValueAsDouble());
      SmartDashboard.putBoolean("Intake/IsDeployed", isIntakeDeployed);
      SmartDashboard.putBoolean("Intake/AtTarget", isAtTarget());
      SmartDashboard.putNumber("Intake/SettleCount", settleCount);
      SmartDashboard.putNumber("Intake/StallCount", stallCount);
    }
  }

  public void publishMotorCurrents() {
    SmartDashboard.putNumber("Intake/IntakeCurrent", intakeMotor.getStatorCurrent().getValueAsDouble());
    SmartDashboard.putNumber("Intake/PickupCurrent", pickupMotor.getStatorCurrent().getValueAsDouble());
  }
}
