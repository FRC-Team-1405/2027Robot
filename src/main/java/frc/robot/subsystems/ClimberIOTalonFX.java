package frc.robot.subsystems;

import com.ctre.phoenix6.controls.MotionMagicVoltage;
import com.ctre.phoenix6.controls.NeutralOut;
import com.ctre.phoenix6.hardware.TalonFX;

import frc.robot.Constants;

public class ClimberIOTalonFX implements ClimberIO {
    private final TalonFX climberMotor = new TalonFX(Constants.CANBus.CLIMBER_MOTOR);
    private final TalonFX grabberMotor = new TalonFX(Constants.CANBus.CLIMBER_GRABBER);

    private final MotionMagicVoltage climberPositionRequest = new MotionMagicVoltage(0);
    private final MotionMagicVoltage grabberPositionRequest = new MotionMagicVoltage(0);
    private final NeutralOut stopRequest = new NeutralOut();

    // Motor gains are stored in Phoenix Tuner X flash on the real robot.
    public ClimberIOTalonFX() {}

    @Override
    public void updateInputs(ClimberIOInputs inputs) {
        inputs.climberPositionRots = climberMotor.getPosition().getValueAsDouble();
        inputs.climberVelocityRPS = climberMotor.getVelocity().getValueAsDouble();
        inputs.climberStatorCurrentAmps = climberMotor.getStatorCurrent().getValueAsDouble();
        inputs.climberSupplyCurrentAmps = climberMotor.getSupplyCurrent().getValueAsDouble();
        inputs.climberOutputVoltage = climberMotor.getMotorVoltage().getValueAsDouble();
        inputs.climberClosedLoopError = climberMotor.getClosedLoopError().getValueAsDouble();
        inputs.climberClosedLoopReference = climberMotor.getClosedLoopReference().getValueAsDouble();

        inputs.grabberPositionRots = grabberMotor.getPosition().getValueAsDouble();
        inputs.grabberVelocityRPS = grabberMotor.getVelocity().getValueAsDouble();
        inputs.grabberStatorCurrentAmps = grabberMotor.getStatorCurrent().getValueAsDouble();
        inputs.grabberSupplyCurrentAmps = grabberMotor.getSupplyCurrent().getValueAsDouble();
        inputs.grabberOutputVoltage = grabberMotor.getMotorVoltage().getValueAsDouble();
        inputs.grabberClosedLoopError = grabberMotor.getClosedLoopError().getValueAsDouble();
        inputs.grabberClosedLoopReference = grabberMotor.getClosedLoopReference().getValueAsDouble();
    }

    @Override
    public void setClimberPosition(double positionRots) {
        climberMotor.setControl(climberPositionRequest.withPosition(positionRots));
    }

    @Override
    public void setGrabberPosition(double positionRots) {
        grabberMotor.setControl(grabberPositionRequest.withPosition(positionRots));
    }

    @Override
    public void stopClimber() {
        climberMotor.setControl(stopRequest);
    }

    @Override
    public void stopGrabber() {
        grabberMotor.setControl(stopRequest);
    }
}
