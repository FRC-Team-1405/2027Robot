package frc.robot.subsystems;

import edu.wpi.first.math.MathUtil;
import edu.wpi.first.math.controller.PIDController;
import edu.wpi.first.math.system.plant.DCMotor;
import edu.wpi.first.math.system.plant.LinearSystemId;
import edu.wpi.first.wpilibj.simulation.DCMotorSim;
import frc.robot.Constants.IntakePreferences;

public class IntakeIOSim implements IntakeIO {
    // Deploy arm: position-controlled, higher inertia, geared
    private final DCMotorSim deploySim = new DCMotorSim(
            LinearSystemId.createDCMotorSystem(DCMotor.getKrakenX60(1), 0.002, 20.0),
            DCMotor.getKrakenX60(1));

    // Pickup roller: velocity-controlled, low inertia
    private final DCMotorSim pickupSim = new DCMotorSim(
            LinearSystemId.createDCMotorSystem(DCMotor.getKrakenX60(1), 0.0002, 0.5),
            DCMotor.getKrakenX60(1));

    private final PIDController deployPid = new PIDController(
            IntakePreferences.DEPLOY_KP, IntakePreferences.DEPLOY_KI, IntakePreferences.DEPLOY_KD);

    private double deployTargetRots = 0.0;
    private double pickupTargetRPS = 0.0;
    private boolean pickupRunning = false;

    private static final double PICKUP_KV = IntakePreferences.PICKUP_KV;
    private static final double PICKUP_KP = IntakePreferences.PICKUP_KP;
    private static final double PICKUP_KS = IntakePreferences.PICKUP_KS;

    @Override
    public void updateInputs(IntakeIOInputs inputs) {
        // Deploy position PID
        double deployPosCurrent = deploySim.getAngularPositionRotations();
        double deployVoltage = MathUtil.clamp(
                deployPid.calculate(deployPosCurrent, deployTargetRots), -12.0, 12.0);
        deploySim.setInputVoltage(deployVoltage);
        deploySim.update(0.02);

        inputs.deployPositionRots = deploySim.getAngularPositionRotations();
        inputs.deployVelocityRPS = deploySim.getAngularVelocityRPM() / 60.0;
        inputs.deployStatorCurrentAmps = deploySim.getCurrentDrawAmps();
        inputs.deploySupplyCurrentAmps = deploySim.getCurrentDrawAmps();
        inputs.deployOutputVoltage = deployVoltage;
        inputs.deployClosedLoopError = deployTargetRots - inputs.deployPositionRots;
        inputs.deployClosedLoopReference = deployTargetRots;

        // Pickup velocity
        double pickupRPS = pickupSim.getAngularVelocityRPM() / 60.0;
        double pickupVoltage = 0.0;
        if (pickupRunning && Math.abs(pickupTargetRPS) > 0.01) {
            double ff = PICKUP_KV * pickupTargetRPS + Math.signum(pickupTargetRPS) * PICKUP_KS;
            double fb = PICKUP_KP * (pickupTargetRPS - pickupRPS);
            pickupVoltage = MathUtil.clamp(ff + fb, -12.0, 12.0);
        }
        pickupSim.setInputVoltage(pickupVoltage);
        pickupSim.update(0.02);

        inputs.pickupVelocityRPS = pickupSim.getAngularVelocityRPM() / 60.0;
        inputs.pickupStatorCurrentAmps = pickupSim.getCurrentDrawAmps();
        inputs.pickupSupplyCurrentAmps = pickupSim.getCurrentDrawAmps();
        inputs.pickupOutputVoltage = pickupVoltage;
        inputs.pickupClosedLoopError = pickupTargetRPS - inputs.pickupVelocityRPS;
    }

    @Override
    public void setDeployPosition(double positionRots) {
        deployTargetRots = positionRots;
    }

    @Override
    public void setPickupVelocity(double velocityRPS) {
        pickupTargetRPS = velocityRPS;
        pickupRunning = true;
    }

    @Override
    public void stopDeploy() {
        deployTargetRots = deploySim.getAngularPositionRotations();
    }

    @Override
    public void stopPickup() {
        pickupTargetRPS = 0.0;
        pickupRunning = false;
    }

    @Override
    public void zeroDeployEncoder() {
        // no-op in sim — position is already tracked correctly
    }
}
