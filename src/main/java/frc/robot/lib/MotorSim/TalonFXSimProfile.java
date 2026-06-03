package frc.robot.lib.MotorSim;

import com.ctre.phoenix6.hardware.TalonFX;
import com.ctre.phoenix6.sim.TalonFXSimState;

import edu.wpi.first.math.system.plant.DCMotor;
import edu.wpi.first.math.system.plant.LinearSystemId;
import edu.wpi.first.math.util.Units;
import edu.wpi.first.wpilibj.simulation.DCMotorSim;
import frc.robot.lib.MotorSim.PhysicsSim.SimProfile;

/**
 * Holds information about a simulated TalonFX.
 */
class TalonFXSimProfile extends SimProfile {
    private static final double kMotorResistance = 0.002; // Assume 2mOhm resistance for voltage drop calculation
    private final TalonFXSimState _talonFXSim;

    private final DCMotorSim _motorSim;

    // load parameters (optional)
    private final double _loadMassKg;
    private final double _armMeters;
    private final double _viscousCoeff;

    // motor torque constant (N*m per amp). Replace with your motor's Kt if known.
    private final double _motorKt;

    // number of motors and gearbox ratio
    private final int _numMotors;
    private final double _gearRatio;

    /**
     * Creates a new simulation profile for a TalonFX device.
     * 
     * @param talonFX
     *                        The TalonFX device
     * @param rotorInertia
     *                        Rotational Inertia of the mechanism at the rotor
     */
    public TalonFXSimProfile(final TalonFX talonFX, final double rotorInertia) {
        // default: no external load, default motor Kt, 1 motor, 1:1 gear ratio
        this(talonFX, rotorInertia, 0.0, 0.0, 0.0, 0.018, 1, 1.0);
    }

    /**
     * Creates a new simulation profile for a TalonFX device with optional load.
     * 
     * @param talonFX
     *                        The TalonFX device
     * @param rotorInertia
     *                        Rotational Inertia of the mechanism at the rotor
     * @param loadMassKg
     *                        Mass (kg) of a load producing gravity torque
     * @param armMeters
     *                        Moment arm length (m) from pivot to load center
     * @param viscousCoeff
     *                        Viscous friction coefficient (N*m per rad/s)
     * @param numMotors
     *                        Number of motors in the gearbox
     * @param gearRatio
     *                        Gear ratio used when creating the linear system
     * @param motorKt
     *                       Motor torque constant (N*m per amp)
     */
    public TalonFXSimProfile(final TalonFX talonFX, final double rotorInertia, final double loadMassKg, final double armMeters, final double viscousCoeff, final double motorKt, final int numMotors, final double gearRatio) {
        this._talonFXSim = talonFX.getSimState();
        DCMotor gearbox = DCMotor.getKrakenX60Foc(numMotors);
        this._motorSim = new DCMotorSim(LinearSystemId.createDCMotorSystem(gearbox, rotorInertia, gearRatio), gearbox);

        this._loadMassKg = loadMassKg;
        this._armMeters = armMeters;
        this._viscousCoeff = viscousCoeff;
        this._motorKt = motorKt;

        this._numMotors = numMotors;
        this._gearRatio = gearRatio;
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

        _motorSim.setInputVoltage(_talonFXSim.getMotorVoltage());

        // compute load torque from gravity and viscous friction based on current state
        double currentAngleRad = Units.rotationsToRadians(_motorSim.getAngularPositionRotations());
        double currentVelRadPerSec = _motorSim.getAngularVelocityRadPerSec();

        double gravityTorque = _loadMassKg * 9.81 * _armMeters * Math.sin(currentAngleRad); // N*m (sign follows sin)
        double viscousTorque = -_viscousCoeff * currentVelRadPerSec; // N*m opposing motion

        double totalLoadTorque = gravityTorque + viscousTorque;

        // Convert external load torque to an equivalent voltage the motor must overcome:
        // V_eq = (tau_load * R) / Kt
        // Subtract that from the motor voltage so DCMotorSim "sees" the load without requiring a non-existent API.
        double motorVoltage = _talonFXSim.getMotorVoltage();
        double voltageOffset = 0.0;
        if (Math.abs(_motorKt) > 1e-12) {
            voltageOffset = totalLoadTorque * kMotorResistance / _motorKt;
        }
        double effectiveVoltage = motorVoltage - voltageOffset;

        // feed the adjusted voltage into the motor sim
        _motorSim.setInputVoltage(effectiveVoltage);
        _motorSim.update(getPeriod());

        /// SET SIM PHYSICS INPUTS
        final double position_rot = _motorSim.getAngularPositionRotations();
        final double velocity_rps = Units.radiansToRotations(_motorSim.getAngularVelocityRadPerSec());

        _talonFXSim.setRawRotorPosition(position_rot);
        _talonFXSim.setRotorVelocity(velocity_rps);


        // System.out.print("Motor Voltage: " + String.format("%.2f", motorVoltage) + " V, Effective Voltage: " + String.format("%.2f", effectiveVoltage) + " V, Load Torque: " + String.format("%.4f", totalLoadTorque) + " N*m\t\t");
        // System.out.println("kMotorResistance: " + kMotorResistance + " Ohm, Motor Current: " + String.format("%.2f", _talonFXSim.getSupplyCurrent()) + " A" + ", Voltage Drop: " + String.format("%.2f", _talonFXSim.getSupplyCurrent() * kMotorResistance) + " V");
        _talonFXSim.setSupplyVoltage(12 - _talonFXSim.getSupplyCurrent() * kMotorResistance);
    }
}