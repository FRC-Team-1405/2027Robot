package frc.robot.subsystems;

import com.ctre.phoenix6.StatusCode;
import com.ctre.phoenix6.configs.TalonFXConfiguration;
import com.ctre.phoenix6.controls.MotionMagicVelocityVoltage;
import com.ctre.phoenix6.controls.NeutralOut;
import com.ctre.phoenix6.hardware.TalonFX;
import com.ctre.phoenix6.signals.InvertedValue;

import edu.wpi.first.units.measure.AngularVelocity;
import frc.robot.Constants;

public class IndexerIOTalonFX implements IndexerIO {
    private final TalonFX motor = new TalonFX(Constants.CANBus.INDEXER_MOTOR);
    private final MotionMagicVelocityVoltage velocityVoltage = new MotionMagicVelocityVoltage(0);
    private final NeutralOut brakeRequest = new NeutralOut();

    public IndexerIOTalonFX() {
        TalonFXConfiguration configs = new TalonFXConfiguration();
        configs.Slot0.kS = Constants.IndexerPreferences.KS;
        configs.Slot0.kV = Constants.IndexerPreferences.KV;
        configs.Slot0.kP = Constants.IndexerPreferences.KP;
        configs.Slot0.kI = Constants.IndexerPreferences.KI;
        configs.Slot0.kD = Constants.IndexerPreferences.KD;
        configs.Voltage.PeakForwardVoltage = Constants.IndexerPreferences.PEAK_FORWARD_VOLTAGE;
        configs.Voltage.PeakReverseVoltage = Constants.IndexerPreferences.PEAK_REVERSE_VOLTAGE;
        configs.MotionMagic.MotionMagicCruiseVelocity = Constants.IndexerPreferences.CRUISE_VELOCITY;
        configs.MotionMagic.MotionMagicAcceleration = Constants.IndexerPreferences.ACCELERATION;
        configs.MotorOutput.Inverted = InvertedValue.Clockwise_Positive;

        StatusCode status = StatusCode.StatusCodeNotInitialized;
        for (int i = 0; i < 5; ++i) {
            status = motor.getConfigurator().apply(configs);
            if (status.isOK()) break;
        }
        if (!status.isOK()) {
            System.out.println("Could not configure indexer motor. Error: " + status);
        }
    }

    @Override
    public void updateInputs(IndexerIOInputs inputs) {
        inputs.velocityRPS = motor.getVelocity().getValueAsDouble();
        inputs.statorCurrentAmps = motor.getStatorCurrent().getValueAsDouble();
        inputs.supplyCurrentAmps = motor.getSupplyCurrent().getValueAsDouble();
        inputs.outputVoltage = motor.getMotorVoltage().getValueAsDouble();
        inputs.closedLoopError = motor.getClosedLoopError().getValueAsDouble();
        inputs.closedLoopReference = motor.getClosedLoopReference().getValueAsDouble();
        inputs.rotorPositionRots = motor.getRotorPosition().getValueAsDouble();
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
