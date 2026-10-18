package frc.robot.util;

import org.littletonrobotics.junction.Logger;

import edu.wpi.first.networktables.NetworkTableEntry;
import edu.wpi.first.networktables.NetworkTableInstance;
import frc.robot.constants.FeatureSwitches;

import java.util.HashMap;
import java.util.Map;

/**
 * Logs how long each part of the robot loop takes, as {@code RealOutputs/Timing/<Name>Ms}, when
 * FeatureSwitches.LOG_SUBSYSTEM_TIMINGS is on. With it off, {@link #begin()} returns 0 and
 * {@link #end} does nothing, so the cost is a constant-folded branch.
 *
 * <p>Usage, around a section or a subsystem's periodic():
 * <pre>
 *   long t = LoopTimings.begin();
 *   try { ... } finally { LoopTimings.end("Timing/Shooter", t); }
 * </pre>
 * The values appear in the log next to {@code LoggedRobot/UserCodeMS}, so a ~38 ms loop can be broken
 * down by subsystem. {@link #mirrorTracer()} also copies the {@code Tracer} NetworkTables table (the
 * Vision per-camera traces) into the log under {@code Timing/Tracer}.
 */
public final class LoopTimings {
    private LoopTimings() {}

    private static final boolean ENABLED = FeatureSwitches.LOG_SUBSYSTEM_TIMINGS;
    private static final Map<String, NetworkTableEntry> tracerEntries = new HashMap<>();

    public static boolean enabled() {
        return ENABLED;
    }

    /** Start time in nanoseconds, or 0 when timings are off. */
    public static long begin() {
        return ENABLED ? System.nanoTime() : 0L;
    }

    /** Record milliseconds since {@code begin()} under {@code key}, e.g. "Timing/Shooter" -> Timing/ShooterMs. */
    public static void end(String key, long startNanos) {
        if (ENABLED) record(key, (System.nanoTime() - startNanos) / 1e6);
    }

    private static void record(String key, double millis) {
        Logger.recordOutput(key + "Ms", millis);
    }

    /** Copy the Tracer table's current values into the log; call once per loop when timings are on. */
    public static void mirrorTracer() {
        if (!ENABLED || Logger.hasReplaySource()) return;
        CoprocessorHealthLogger.mirror(NetworkTableInstance.getDefault().getTable("Tracer"), "Timing/Tracer",
                CoprocessorHealthLogger::record, tracerEntries);
    }
}
