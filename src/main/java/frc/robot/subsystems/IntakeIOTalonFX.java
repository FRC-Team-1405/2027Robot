package frc.robot.subsystems;

import com.ctre.phoenix6.StatusCode;
import com.ctre.phoenix6.configs.TalonFXConfiguration;
import com.ctre.phoenix6.controls.MotionMagicVelocityVoltage;
import com.ctre.phoenix6.controls.MotionMagicVoltage;
import com.ctre.phoenix6.controls.NeutralOut;
import com.ctre.phoenix6.hardware.TalonFX;
import com.ctre.phoenix6.signals.InvertedValue;
import com.ctre.phoenix6.signals.NeutralModeValue;

import frc.robot.Constants;
import frc.robot.Constants.IntakePreferences;

public class IntakeIOTalonFX implements IntakeIO {
    private final TalonFX deployMotor = new TalonFX(Constants.CANBus.INTAKE_MOTOR);
    private final TalonFX pickupMotor = new TalonFX(Constants.CANBus.PICKUP_MOTOR);

    private final MotionMagicVoltage deployPositionRequest = new MotionMagicVoltage(0);
    private final MotionMagicVelocityVoltage pickupVelocityRequest = new MotionMagicVelocityVoltage(0);
    private final NeutralOut neutralRequest = new NeutralOut();

    public IntakeIOTalonFX() {
        setupDeployMotor();
        setupPickupMotor();
    }

    private void setupDeployMotor() {
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

        applyConfig(deployMotor, config, "intake deploy motor");
        deployMotor.getPosition().setUpdateFrequency(10);
        deployMotor.optimizeBusUtilization();
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
        applyConfig(pickupMotor, config, "intake pickup motor");
    }

    private void applyConfig(TalonFX motor, TalonFXConfiguration cfg, String name) {
        StatusCode status = StatusCode.StatusCodeNotInitialized;
        for (int i = 0; i < 5; ++i) {
            status = motor.getConfigurator().apply(cfg);
            if (status.isOK()) break;
        }
        if (!status.isOK()) {
            System.out.println("Could not configure " + name + ". Error: " + status);
        }
    }

    @Override
    public void updateInputs(IntakeIOInputs inputs) {
        inputs.deployPositionRots = deployMotor.getPosition().getValueAsDouble();
        inputs.deployVelocityRPS = deployMotor.getVelocity().getValueAsDouble();
        inputs.deployStatorCurrentAmps = deployMotor.getStatorCurrent().getValueAsDouble();
        inputs.deploySupplyCurrentAmps = deployMotor.getSupplyCurrent().getValueAsDouble();
        inputs.deployOutputVoltage = deployMotor.getMotorVoltage().getValueAsDouble();
        inputs.deployClosedLoopError = deployMotor.getClosedLoopError().getValueAsDouble();
        inputs.deployClosedLoopReference = deployMotor.getClosedLoopReference().getValueAsDouble();

        inputs.pickupVelocityRPS = pickupMotor.getVelocity().getValueAsDouble();
        inputs.pickupStatorCurrentAmps = pickupMotor.getStatorCurrent().getValueAsDouble();
        inputs.pickupSupplyCurrentAmps = pickupMotor.getSupplyCurrent().getValueAsDouble();
        inputs.pickupOutputVoltage = pickupMotor.getMotorVoltage().getValueAsDouble();
        inputs.pickupClosedLoopError = pickupMotor.getClosedLoopError().getValueAsDouble();
    }

    @Override
    public void setDeployPosition(double positionRots) {
        deployMotor.setControl(deployPositionRequest.withPosition(positionRots));
    }

    @Override
    public void setPickupVelocity(double velocityRPS) {
        pickupMotor.setControl(pickupVelocityRequest.withVelocity(velocityRPS));
    }

    @Override
    public void stopDeploy() {
        deployMotor.setControl(neutralRequest);
    }

    @Override
    public void stopPickup() {
        pickupMotor.setControl(neutralRequest);
    }

    @Override
    public void zeroDeployEncoder() {
        deployMotor.setPosition(0);
    }
}
