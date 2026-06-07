package frc.robot.subsystems;

import edu.wpi.first.math.MathUtil;
import edu.wpi.first.math.system.plant.DCMotor;
import edu.wpi.first.math.system.plant.LinearSystemId;
import edu.wpi.first.wpilibj.simulation.DCMotorSim;
import frc.robot.Constants;

public class HopperIOSim implements HopperIO {
    private final DCMotorSim motorSim = new DCMotorSim(
            LinearSystemId.createDCMotorSystem(DCMotor.getKrakenX60(1), 0.001, 1.0),
            DCMotor.getKrakenX60(1));

    private double targetRPS = 0.0;
    private boolean running = false;

    private static final double KV = Constants.HopperPreferences.KV;
    private static final double KP = Constants.HopperPreferences.KP;
    private static final double KS = Constants.HopperPreferences.KS;

    @Override
    public void updateInputs(HopperIOInputs inputs) {
        double currentRPS = motorSim.getAngularVelocityRPM() / 60.0;
        double voltageOut = 0.0;
        if (running && Math.abs(targetRPS) > 0.01) {
            double ff = KV * targetRPS + Math.signum(targetRPS) * KS;
            double fb = KP * (targetRPS - currentRPS);
            voltageOut = MathUtil.clamp(ff + fb, -12.0, 12.0);
        }
        motorSim.setInputVoltage(voltageOut);
        motorSim.update(0.02);

        inputs.velocityRPS = motorSim.getAngularVelocityRPM() / 60.0;
        inputs.statorCurrentAmps = motorSim.getCurrentDrawAmps();
        inputs.supplyCurrentAmps = motorSim.getCurrentDrawAmps();
        inputs.outputVoltage = voltageOut;
        inputs.closedLoopError = targetRPS - inputs.velocityRPS;
        inputs.closedLoopReference = targetRPS;
    }

    @Override
    public void setVelocity(double velocityRPS) {
        targetRPS = velocityRPS;
        running = true;
    }

    @Override
    public void stop() {
        targetRPS = 0.0;
        running = false;
    }
}
