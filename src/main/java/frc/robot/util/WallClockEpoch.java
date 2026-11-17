package frc.robot.util;

import java.util.UUID;

import org.littletonrobotics.junction.Logger;

import edu.wpi.first.networktables.NetworkTableInstance;
import edu.wpi.first.wpilibj.RobotController;

/**
 * Records which roboRIO boot a log belongs to, so LogBench can tie Orange Pi vision frames to it
 * exactly instead of guessing from the log's file name.
 *
 * <p>Log timestamps and the Pis' frame timestamps (t_sec) are both FPGA seconds since the roboRIO
 * booted, so they restart at every boot. The wall-clock time at that zero, the <b>epoch</b> (wall
 * clock minus FPGA time), is therefore constant for a whole boot and differs between boots. A Pi
 * session is named with the same roboRIO clock, so the same epoch can be worked out from either side.
 * The AdvantageKit file name cannot say it: that time is when the Driver Station first synced the
 * roboRIO's clock, anywhere from seconds to many minutes after boot.
 *
 * <p>Written on change only (the first value, then again if the clock is stepped by the Driver
 * Station sync, which moves it from a stale date to the right one): the log keeps the first and the
 * last, and LogBench reads the last. Mirrored onto NetworkTables as {@code /RobotTime/EpochMs} and
 * {@code /RobotTime/BootId} so the plain WPILib log of the same boot carries them as well, which is
 * how the two logs of one boot are known to be twins. Does nothing in replay (the values already
 * in the replayed log are the true ones).
 */
public final class WallClockEpoch {
    public static final String EPOCH_KEY = "RobotTime/EpochMs";
    public static final String BOOT_ID_KEY = "RobotTime/BootId";
    /** Smaller steps are clock drift, not a new epoch; a Driver Station sync moves it by far more. */
    public static final long CHANGE_THRESHOLD_MS = 1000;

    private static final WallClockEpoch INSTANCE = new WallClockEpoch();

    private final String bootId = UUID.randomUUID().toString();
    private long lastRecordedMs;
    private boolean recorded;

    WallClockEpoch() {}

    /** Wall-clock epoch ms at FPGA time zero. */
    static long epochMs(long wallClockMs, long fpgaTimeMicros) {
        return wallClockMs - fpgaTimeMicros / 1000;
    }

    /** Fresh, per-robot-code-run identifier (shared by the two logs this run writes). */
    String bootId() {
        return bootId;
    }

    /**
     * Feeds one reading; returns true when it differs enough from the last recorded epoch (or is the
     * first) that it should be recorded now.
     */
    boolean update(long wallClockMs, long fpgaTimeMicros) {
        long epoch = epochMs(wallClockMs, fpgaTimeMicros);
        if (recorded && Math.abs(epoch - lastRecordedMs) < CHANGE_THRESHOLD_MS) {
            return false;
        }
        recorded = true;
        lastRecordedMs = epoch;
        return true;
    }

    long lastRecordedMs() {
        return lastRecordedMs;
    }

    /** Call every robot loop; costs two clock reads and a compare unless the epoch changed. */
    public static void periodic() {
        if (Logger.hasReplaySource()) return;
        long wall = System.currentTimeMillis();
        if (INSTANCE.update(wall, RobotController.getFPGATime())) {
            Logger.recordOutput(EPOCH_KEY, INSTANCE.lastRecordedMs());
            Logger.recordOutput(BOOT_ID_KEY, INSTANCE.bootId());
            var table = NetworkTableInstance.getDefault().getTable("RobotTime");
            table.getEntry("EpochMs").setInteger(INSTANCE.lastRecordedMs());
            table.getEntry("BootId").setString(INSTANCE.bootId());
        }
    }
}
