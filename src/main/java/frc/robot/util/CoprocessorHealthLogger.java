package frc.robot.util;

import java.util.HashMap;
import java.util.Map;
import java.util.function.BiConsumer;

import org.littletonrobotics.junction.Logger;

import edu.wpi.first.networktables.NetworkTable;
import edu.wpi.first.networktables.NetworkTableEntry;
import edu.wpi.first.networktables.NetworkTableInstance;
import edu.wpi.first.networktables.NetworkTableValue;
import edu.wpi.first.wpilibj.Timer;

/**
 * Copies everything the Orange Pis publish under /OrangePi/ (CPU, RAM, disk and temperature from
 * orangepi-nt-publisher.py, and each camera recorder's heartbeat from orangepi-vision-recorder.py)
 * into the AdvantageKit log as {@code RealOutputs/OrangePi/...}.
 *
 * <p>The Pis publish to NetworkTables only, and AdvantageKit does not log arbitrary NT tables, so
 * without this the match log says nothing about whether a Pi was overloaded or a recorder had
 * stopped. With it, LogBench's Health Check page can run the same Orange Pi checks over a finished
 * match that it runs live in the pits (tools/logbench/server/health_checks.toml).
 *
 * <p>Cheap by design: it looks twice a second, and AdvantageKit only writes a value when it
 * changes. Does nothing in replay (the logged values are already in the log being replayed).
 */
public final class CoprocessorHealthLogger {
    public static final String ROOT = "OrangePi";
    private static final double PERIOD_SEC = 0.5;

    private static double lastRun = Double.NEGATIVE_INFINITY;
    private static final Map<String, NetworkTableEntry> entries = new HashMap<>();

    private CoprocessorHealthLogger() {}

    /** Call every robot loop; mirrors at most every {@value #PERIOD_SEC} s. */
    public static void periodic() {
        double now = Timer.getFPGATimestamp();
        if (now - lastRun < PERIOD_SEC || Logger.hasReplaySource()) return;
        lastRun = now;
        mirror(NetworkTableInstance.getDefault().getTable(ROOT), ROOT, CoprocessorHealthLogger::record, entries);
    }

    /** Hands a mirrored value to the matching typed Logger.recordOutput overload. */
    private static void record(String key, Object value) {
        if (value instanceof Boolean b) {
            Logger.recordOutput(key, b.booleanValue());
        } else if (value instanceof Long l) {
            Logger.recordOutput(key, l.longValue());
        } else if (value instanceof Double d) {
            Logger.recordOutput(key, d.doubleValue());
        } else if (value instanceof String str) {
            Logger.recordOutput(key, str);
        } else if (value instanceof boolean[] a) {
            Logger.recordOutput(key, a);
        } else if (value instanceof long[] a) {
            Logger.recordOutput(key, a);
        } else if (value instanceof double[] a) {
            Logger.recordOutput(key, a);
        } else if (value instanceof String[] a) {
            Logger.recordOutput(key, a);
        }
    }

    /**
     * Walks {@code table} and every sub-table, handing each readable value to {@code sink} under a
     * key like {@code OrangePi/LeftPi/Recorders/LeftCam/State}. Package-visible for tests, which pass
     * their own sink and NetworkTables instance.
     */
    static void mirror(NetworkTable table, String keyPrefix, BiConsumer<String, Object> sink,
            Map<String, NetworkTableEntry> cache) {
        for (String key : table.getKeys()) {
            String full = keyPrefix + "/" + key;
            NetworkTableEntry entry = cache.computeIfAbsent(table.getPath() + "/" + key, p -> table.getEntry(key));
            Object value = toLoggable(entry.getValue());
            if (value != null) {
                sink.accept(full, value);
            }
        }
        for (String sub : table.getSubTables()) {
            mirror(table.getSubTable(sub), keyPrefix + "/" + sub, sink, cache);
        }
    }

    /** The value as a type AdvantageKit's recordOutput accepts, or null if it cannot be logged. */
    static Object toLoggable(NetworkTableValue value) {
        if (value == null || !value.isValid()) return null;
        switch (value.getType()) {
            case kBoolean:
                return value.getBoolean();
            case kInteger:
                return value.getInteger();
            case kFloat:
                return (double) value.getFloat();
            case kDouble:
                return value.getDouble();
            case kString:
                return value.getString();
            case kBooleanArray:
                return value.getBooleanArray();
            case kIntegerArray:
                return value.getIntegerArray();
            case kDoubleArray:
                return value.getDoubleArray();
            case kStringArray:
                return value.getStringArray();
            default:
                return null;
        }
    }
}
