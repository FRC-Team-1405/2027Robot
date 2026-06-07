package frc.robot.subsystems;

import edu.wpi.first.math.MathUtil;
import edu.wpi.first.math.controller.PIDController;
import edu.wpi.first.math.system.plant.DCMotor;
import edu.wpi.first.math.system.plant.LinearSystemId;
import edu.wpi.first.wpilibj.simulation.DCMotorSim;

public class ClimberIOSim implements ClimberIO {
    private static final double CLIMBER_KP = 0.66;
    private static final double GRABBER_KP = 0.66;

    private final DCMotorSim climberSim = new DCMotorSim(
            LinearSystemId.createDCMotorSystem(DCMotor.getKrakenX60(1), 0.001, 10.0),
            DCMotor.getKrakenX60(1));
    private final DCMotorSim grabberSim = new DCMotorSim(
            LinearSystemId.createDCMotorSystem(DCMotor.getKrakenX60(1), 0.001, 5.0),
            DCMotor.getKrakenX60(1));

    private final PIDController climberPid = new PIDController(CLIMBER_KP, 0, 0);
    private final PIDController grabberPid = new PIDController(GRABBER_KP, 0, 0);

    private double climberTargetRots = 0.0;
    private double grabberTargetRots = 0.0;
    private boolean climberStopped = true;
    private boolean grabberStopped = true;

    @Override
    public void updateInputs(ClimberIOInputs inputs) {
        double climberVoltage = 0.0;
        if (!climberStopped) {
            climberVoltage = MathUtil.clamp(
                    climberPid.calculate(climberSim.getAngularPositionRotations(), climberTargetRots),
                    -8.0, 8.0);
        }
        climberSim.setInputVoltage(climberVoltage);
        climberSim.update(0.02);

        inputs.climberPositionRots = climberSim.getAngularPositionRotations();
        inputs.climberVelocityRPS = climberSim.getAngularVelocityRPM() / 60.0;
        inputs.climberStatorCurrentAmps = climberSim.getCurrentDrawAmps();
        inputs.climberSupplyCurrentAmps = climberSim.getCurrentDrawAmps();
        inputs.climberOutputVoltage = climberVoltage;
        inputs.climberClosedLoopError = climberTargetRots - inputs.climberPositionRots;
        inputs.climberClosedLoopReference = climberTargetRots;

        double grabberVoltage = 0.0;
        if (!grabberStopped) {
            grabberVoltage = MathUtil.clamp(
                    grabberPid.calculate(grabberSim.getAngularPositionRotations(), grabberTargetRots),
                    -8.0, 8.0);
        }
        grabberSim.setInputVoltage(grabberVoltage);
        grabberSim.update(0.02);

        inputs.grabberPositionRots = grabberSim.getAngularPositionRotations();
        inputs.grabberVelocityRPS = grabberSim.getAngularVelocityRPM() / 60.0;
        inputs.grabberStatorCurrentAmps = grabberSim.getCurrentDrawAmps();
        inputs.grabberSupplyCurrentAmps = grabberSim.getCurrentDrawAmps();
        inputs.grabberOutputVoltage = grabberVoltage;
        inputs.grabberClosedLoopError = grabberTargetRots - inputs.grabberPositionRots;
        inputs.grabberClosedLoopReference = grabberTargetRots;
    }

    @Override
    public void setClimberPosition(double positionRots) {
        climberTargetRots = positionRots;
        climberStopped = false;
    }

    @Override
    public void setGrabberPosition(double positionRots) {
        grabberTargetRots = positionRots;
        grabberStopped = false;
    }

    @Override
    public void stopClimber() {
        climberStopped = true;
    }

    @Override
    public void stopGrabber() {
        grabberStopped = true;
    }
}
