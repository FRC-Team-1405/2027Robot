package frc.robot.subsystems;

import com.ctre.phoenix6.StatusCode;
import com.ctre.phoenix6.configs.TalonFXConfiguration;
import com.ctre.phoenix6.controls.MotionMagicVelocityVoltage;
import com.ctre.phoenix6.controls.NeutralOut;
import com.ctre.phoenix6.hardware.TalonFX;
import com.ctre.phoenix6.signals.NeutralModeValue;

import frc.robot.Constants;
import frc.robot.Constants.IntakePreferences;

public class PickupIOTalonFX implements PickupIO {
    private final TalonFX motor = new TalonFX(Constants.CANBus.PICKUP_MOTOR);
    private final MotionMagicVelocityVoltage velocityVoltage = new MotionMagicVelocityVoltage(0);
    private final NeutralOut neutralRequest = new NeutralOut();

    public PickupIOTalonFX() {
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
            status = motor.getConfigurator().apply(config);
            if (status.isOK()) break;
        }
        if (!status.isOK()) {
            System.out.println("Could not configure pickup motor. Error: " + status);
        }
    }

    @Override
    public void updateInputs(PickupIOInputs inputs) {
        inputs.velocityRPS = motor.getVelocity().getValueAsDouble();
        inputs.statorCurrentAmps = motor.getStatorCurrent().getValueAsDouble();
        inputs.supplyCurrentAmps = motor.getSupplyCurrent().getValueAsDouble();
        inputs.outputVoltage = motor.getMotorVoltage().getValueAsDouble();
        inputs.closedLoopError = motor.getClosedLoopError().getValueAsDouble();
    }

    @Override
    public void setVelocity(double velocityRPS) {
        motor.setControl(velocityVoltage.withVelocity(velocityRPS));
    }

    @Override
    public void stop() {
        motor.setControl(neutralRequest);
    }
}
