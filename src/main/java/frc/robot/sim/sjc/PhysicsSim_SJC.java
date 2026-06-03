package frc.robot.sim.sjc;

import java.util.ArrayList;

import com.ctre.phoenix6.Utils;
import com.ctre.phoenix6.hardware.TalonFX;

/**
 * Manages physics simulation for CTRE products.
 */
public class PhysicsSim_SJC {
    private static final PhysicsSim_SJC sim = new PhysicsSim_SJC();

    /**
     * Gets the robot simulator instance.
     */
    public static PhysicsSim_SJC getInstance() {
        return sim;
    }

    /**
     * Adds a TalonFX controller to the simulator.
     * 
     * @param talonFX
     *                     The TalonFX device
     * @param rotorInertia
     *                     Rotational Inertia of the mechanism at the rotor
     */
    public void addTalonFX(TalonFX talonFX, final double rotorInertia) {
        if (talonFX != null) {
            TalonFXSimProfile_SJC simTalonFX = new TalonFXSimProfile_SJC(talonFX, rotorInertia);
            _simProfiles.add(simTalonFX);
        }
    }

    /**
     * Adds a TalonFX controller with a modeled load (gravity + viscous). The gear
     * ratio is output to input.
     */
    public void addTalonFX(TalonFX talonFX, final double rotorInertia, final double loadMassKg, final double armMeters,
            final double viscousCoeff, final int numberOfMotors, final double gearRatio) {
        if (talonFX != null) {
            TalonFXSimProfile_SJC simTalonFX = new TalonFXSimProfile_SJC(talonFX, rotorInertia, loadMassKg, armMeters,
                    viscousCoeff, 0.018, numberOfMotors, gearRatio);
            _simProfiles.add(simTalonFX);
        }
    }

    /**
     * Runs the simulator:
     * - enable the robot
     * - simulate sensors
     */
    public void run() {
        // Simulate devices
        for (SimProfile simProfile : _simProfiles) {
            simProfile.run();
        }
    }

    private final ArrayList<SimProfile> _simProfiles = new ArrayList<SimProfile>();

    /**
     * Holds information about a simulated device.
     */
    static class SimProfile {
        private double _lastTime;
        private boolean _running = false;

        /**
         * Runs the simulation profile.
         * Implemented by device-specific profiles.
         */
        public void run() {
        }

        /**
         * Returns the time since last call, in seconds.
         */
        protected double getPeriod() {
            // set the start time if not yet running
            if (!_running) {
                _lastTime = Utils.getCurrentTimeSeconds();
                _running = true;
            }

            double now = Utils.getCurrentTimeSeconds();
            final double period = now - _lastTime;
            _lastTime = now;

            return period;
        }
    }
}