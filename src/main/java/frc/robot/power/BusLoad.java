package frc.robot.power;

import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.Map;
import java.util.Set;

import com.ctre.phoenix6.BaseStatusSignal;
import com.ctre.phoenix6.hardware.TalonFX;

import edu.wpi.first.wpilibj.RobotBase;
import org.littletonrobotics.junction.Logger;
import frc.robot.constants.FeatureSwitches;

/**
 * Lowers the CAN status-signal load of the simple mechanism motors (Hopper, Indexer, Pickup and the
 * Intake's pickup roller), behind FeatureSwitches.MECHANISM_STATUS_SIGNAL_HZ and
 * OPTIMIZE_BUS_UTILIZATION. See the compiled FeatureSwitches metadata for this deployment.
 *
 * <p>Why only those: a Phoenix status signal's rate belongs to the device, not to whoever asked for it,
 * so lowering one that another reader depends on slows that reader. The swerve modules (odometry) and
 * the shooter (velocity lock) need 100 Hz+ and are never touched. The four mechanism motors are only
 * read for their own inputs and for logging, so a modest rate is safe.
 *
 * <p>Order matters: each IO class calls {@link #tuneMechanismMotor} after configuring its motor, listing
 * every signal its updateInputs reads; {@code PowerTelemetry.initialize()} then calls
 * {@link #finishMechanismMotor} with its own signals, and only then (if enabled) optimizes the bus.
 * optimizeBusUtilization() slows every signal not given an explicit rate (4 Hz on Phoenix 2026,
 * or 0 Hz with ZERO_UNUSED_MECHANISM_STATUS_SIGNALS), so list all consumers first.
 */
public final class BusLoad {
    private BusLoad() {}

    /** Explicit rate for signals kept alive when optimizing and no rate was configured. */
    public static final double DEFAULT_OPTIMIZED_HZ = 50.0;
    /** Rate the fault signals keep (Phoenix's default for them), so they survive optimizing. */
    public static final double FAULT_HZ = 4.0;

    private static final Set<TalonFX> tuned = Collections.newSetFromMap(new IdentityHashMap<>());
    private static final Map<TalonFX, BaseStatusSignal[]> ioSignals = new IdentityHashMap<>();

    /** The rate to give mechanism-motor signals: the configured one, else 50 Hz if optimizing, else 0 (no change). */
    public static double mechanismHz(double configuredHz, boolean optimize) {
        if (configuredHz > 0) return configuredHz;
        return optimize ? DEFAULT_OPTIMIZED_HZ : 0.0;
    }

    static double mechanismHz() {
        return mechanismHz(FeatureSwitches.MECHANISM_STATUS_SIGNAL_HZ, FeatureSwitches.OPTIMIZE_BUS_UTILIZATION);
    }

    /**
     * Call from a mechanism IO's constructor after the motor is configured, passing every status
     * signal its updateInputs reads. No-op unless a switch asks for a change (and never in simulation).
     */
    public static void tuneMechanismMotor(TalonFX motor, BaseStatusSignal... readByIo) {
        double hz = mechanismHz();
        if (hz <= 0 || !RobotBase.isReal()) return;
        boolean configured = true;
        for (BaseStatusSignal signal : readByIo) configured &= signal.setUpdateFrequency(hz).isOK();
        ioSignals.put(motor, readByIo);
        String prefix = "Performance/CAN/" + PowerTelemetry.identity(motor.getNetwork().getName(), motor.getDeviceID());
        Logger.recordOutput(prefix + "/RequestedIoRateHz", hz);
        Logger.recordOutput(prefix + "/IoRateConfigurationOK", configured);
        tuned.add(motor);
        if (!FeatureSwitches.ENABLE_POWER_TELEMETRY) finishMechanismMotor(motor, Map.of());
    }

    /**
     * Called by PowerTelemetry once its signals exist. Gives them the same explicit rate (faults keep
     * 4 Hz), then optimizes the device if OPTIMIZE_BUS_UTILIZATION is on. Only for motors that
     * {@link #tuneMechanismMotor} accepted.
     */
    static void finishMechanismMotor(TalonFX motor, Map<String, BaseStatusSignal> telemetrySignals) {
        if (!tuned.contains(motor)) return;
        double hz = mechanismHz();
        for (Map.Entry<String, BaseStatusSignal> entry : telemetrySignals.entrySet()) {
            entry.getValue().setUpdateFrequency(isFault(entry.getKey()) ? FAULT_HZ : hz);
        }
        if (FeatureSwitches.OPTIMIZE_BUS_UTILIZATION) {
            var status = FeatureSwitches.ZERO_UNUSED_MECHANISM_STATUS_SIGNALS
                    ? motor.optimizeBusUtilization(0.0) : motor.optimizeBusUtilization();
            Logger.recordOutput("Performance/CAN/" + PowerTelemetry.identity(motor.getNetwork().getName(), motor.getDeviceID())
                    + "/OptimizeStatus", status.toString());
        }
        BaseStatusSignal[] signals = ioSignals.get(motor);
        for (int i = 0; signals != null && i < signals.length; i++) {
            Logger.recordOutput("Performance/CAN/" + PowerTelemetry.identity(motor.getNetwork().getName(), motor.getDeviceID())
                    + "/IoSignal" + i + "AppliedHz", signals[i].getAppliedUpdateFrequency());
        }
    }

    /** Telemetry keys backed by fault signals (a few Hz is enough; Phoenix's default). */
    static boolean isFault(String telemetryKey) {
        return telemetryKey.equals("SupplyLimited") || telemetryKey.equals("StatorLimited")
                || telemetryKey.equals("Undervoltage");
    }

    static boolean isTuned(TalonFX motor) {
        return tuned.contains(motor);
    }
}
