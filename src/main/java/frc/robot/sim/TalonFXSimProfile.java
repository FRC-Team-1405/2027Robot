package frc.robot.sim;

import com.ctre.phoenix6.hardware.TalonFX;
import com.ctre.phoenix6.sim.TalonFXSimState;

import edu.wpi.first.math.system.plant.DCMotor;
import edu.wpi.first.math.system.plant.LinearSystemId;
import edu.wpi.first.math.util.Units;
import edu.wpi.first.wpilibj.simulation.DCMotorSim;
import frc.robot.sim.PhysicsSim.SimProfile;

/**
 * Holds information about a simulated TalonFX.
 */
public class TalonFXSimProfile extends SimProfile {
    private static final double kMotorResistance = 0.002; // Assume 2mOhm resistance for voltage drop calculation
    protected TalonFXSimState _talonFXSim;
    protected DCMotorSim _motorSim;

    /**
     * Creates a new simulation profile for a TalonFX device.
     * 
     * @param talonFX
     *                     The TalonFX device
     * @param rotorInertia
     *                     Rotational Inertia of the mechanism at the rotor
     */
    private final TalonFX talonFX;

    public TalonFXSimProfile(final TalonFX talonFX) {
        this.talonFX = talonFX;
    }

    private int motorCount = 1;

    public TalonFXSimProfile withMotorCount(int motorCount) {
        this.motorCount = motorCount;
        return this;
    }

    private double rotorInertia = 1.0;

    public TalonFXSimProfile withRotorInertia(double rotorInertia) {
        this.rotorInertia = rotorInertia;
        return this;
    }

    private double gearRatio = 1.0;

    public TalonFXSimProfile withGearRatio(double gearRatio) {
        this.gearRatio = gearRatio;
        return this;
    }

    public TalonFXSimProfile build() {
        var motor = DCMotor.getKrakenX60Foc(motorCount);
        this._motorSim = new DCMotorSim(
                LinearSystemId.createDCMotorSystem(motor, rotorInertia, gearRatio), motor);
        this._talonFXSim = talonFX.getSimState();
        return this;
    }

    /**
     * Runs the simulation profile.
     * 
     * This uses very rudimentary physics simulation and exists to allow users to
     * test features of our products in simulation using our examples out of the
     * box. Users may modify this to utilize more accurate physics simulation.
     */
    public void run() {
        /// DEVICE SPEED SIMULATION

        _motorSim.setInputVoltage(_talonFXSim.getMotorVoltage() * ((loadCount-- > -0) ? loadPercent : 1.0));

        _motorSim.update(getPeriod());

        /// SET SIM PHYSICS INPUTS
        final double position_rot = _motorSim.getAngularPositionRotations();
        final double velocity_rps = Units.radiansToRotations(_motorSim.getAngularVelocityRadPerSec());

        _talonFXSim.setRawRotorPosition(position_rot);
        _talonFXSim.setRotorVelocity(velocity_rps);

        _talonFXSim.setSupplyVoltage(12 - _talonFXSim.getSupplyCurrent() * kMotorResistance);
    }

    private double loadPercent = 1.0;
    private int loadCount = 0;

    public void temporaryLoad(double percent, int ticks) {
        loadPercent = percent;
        loadCount = ticks;
    }
}