package frc.robot.subsystems;

import edu.wpi.first.math.MathUtil;
import edu.wpi.first.math.system.plant.DCMotor;
import edu.wpi.first.math.system.plant.LinearSystemId;
import edu.wpi.first.wpilibj.simulation.DCMotorSim;
import frc.robot.Constants;
import frc.robot.Constants.ShooterPhysicalProperties;
import frc.robot.Constants.ShooterPIDConfig;

public class ShooterIOSim implements ShooterIO {
    // Three motors driving one flywheel — represent as combined effective inertia.
    // I_rotor = I_flywheel / gearRatio^2, then divided across 3 motors.
    private static final double GEAR_RATIO = ShooterPhysicalProperties.MOTOR_TO_WHEEL_GEAR_RATIO;
    private static final double FLYWHEEL_INERTIA = ShooterPhysicalProperties.FLYWHEEL_MOMENT_OF_INERTIA;
    private static final double ROTOR_INERTIA = FLYWHEEL_INERTIA / (GEAR_RATIO * GEAR_RATIO * 3.0);

    private final DCMotorSim flywheelSim = new DCMotorSim(
            LinearSystemId.createDCMotorSystem(DCMotor.getKrakenX60(3), ROTOR_INERTIA, GEAR_RATIO),
            DCMotor.getKrakenX60(3));

    private double targetRPS = 0.0;
    private boolean running = false;

    private static final double KV = ShooterPIDConfig.KV;
    private static final double KP = ShooterPIDConfig.KP;
    private static final double KS = ShooterPIDConfig.KS;

    @Override
    public void updateInputs(ShooterIOInputs inputs) {
        double currentRPS = flywheelSim.getAngularVelocityRPM() / 60.0;
        double voltageOut = 0.0;
        if (running && Math.abs(targetRPS) > 0.01) {
            double ff = KV * targetRPS + Math.signum(targetRPS) * KS;
            double fb = KP * (targetRPS - currentRPS);
            voltageOut = MathUtil.clamp(ff + fb, -12.0, 12.0);
        }
        flywheelSim.setInputVoltage(voltageOut);
        flywheelSim.update(0.02);

        double rps = flywheelSim.getAngularVelocityRPM() / 60.0;
        double current = flywheelSim.getCurrentDrawAmps() / 3.0;

        inputs.motor1VelocityRPS = rps;
        inputs.motor2VelocityRPS = rps;
        inputs.motor3VelocityRPS = rps;
        inputs.motor1SupplyCurrentAmps = current;
        inputs.motor2SupplyCurrentAmps = current;
        inputs.motor3SupplyCurrentAmps = current;
        inputs.motor1StatorCurrentAmps = current;
        inputs.motor2StatorCurrentAmps = current;
        inputs.motor3StatorCurrentAmps = current;
        inputs.motor1TorqueCurrentAmps = current;
        inputs.motor2TorqueCurrentAmps = current;
        inputs.motor3TorqueCurrentAmps = current;
        inputs.motor1OutputVoltage = voltageOut;
        inputs.motor2OutputVoltage = voltageOut;
        inputs.motor3OutputVoltage = voltageOut;
        inputs.supplyVoltage = 12.0;
        inputs.closedLoopError = targetRPS - rps;
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
