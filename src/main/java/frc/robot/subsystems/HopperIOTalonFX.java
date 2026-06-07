package frc.robot.subsystems;

import com.ctre.phoenix6.StatusCode;
import com.ctre.phoenix6.configs.TalonFXConfiguration;
import com.ctre.phoenix6.controls.MotionMagicVelocityVoltage;
import com.ctre.phoenix6.controls.NeutralOut;
import com.ctre.phoenix6.hardware.TalonFX;
import com.ctre.phoenix6.signals.InvertedValue;

import edu.wpi.first.units.measure.AngularVelocity;
import frc.robot.Constants;

public class HopperIOTalonFX implements HopperIO {
    private final TalonFX motor = new TalonFX(Constants.CANBus.HOPPER_MOTOR);
    private final MotionMagicVelocityVoltage velocityVoltage = new MotionMagicVelocityVoltage(0);
    private final NeutralOut brakeRequest = new NeutralOut();

    public HopperIOTalonFX() {
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
        configs.MotorOutput.Inverted = InvertedValue.Clockwise_Positive;

        StatusCode status = StatusCode.StatusCodeNotInitialized;
        for (int i = 0; i < 5; ++i) {
            status = motor.getConfigurator().apply(configs);
            if (status.isOK()) break;
        }
        if (!status.isOK()) {
            System.out.println("Could not configure hopper motor. Error: " + status);
        }
    }

    @Override
    public void updateInputs(HopperIOInputs inputs) {
        inputs.velocityRPS = motor.getVelocity().getValueAsDouble();
        inputs.statorCurrentAmps = motor.getStatorCurrent().getValueAsDouble();
        inputs.supplyCurrentAmps = motor.getSupplyCurrent().getValueAsDouble();
        inputs.outputVoltage = motor.getMotorVoltage().getValueAsDouble();
        inputs.closedLoopError = motor.getClosedLoopError().getValueAsDouble();
        inputs.closedLoopReference = motor.getClosedLoopReference().getValueAsDouble();
    }

    @Override
    public void setVelocity(double velocityRPS) {
        motor.setControl(velocityVoltage.withVelocity(velocityRPS));
    }

    public void setVelocity(AngularVelocity velocity) {
        motor.setControl(velocityVoltage.withVelocity(velocity));
    }

    @Override
    public void stop() {
        motor.setControl(brakeRequest);
    }
}
