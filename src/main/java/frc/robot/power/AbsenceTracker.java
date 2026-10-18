package frc.robot.power;

/**
 * Decides when a motor controller that keeps reporting a bad CAN status should stop being refreshed
 * every loop. A dead or unplugged device costs time on every read; after it has been bad for
 * {@link #GRACE_SEC} it is only probed every {@link #REPROBE_SEC} until it answers again.
 *
 * <p>Pure time-based logic (the caller passes the clock) so it can be tested without hardware. Used by
 * PowerTelemetry behind FeatureSwitches.SKIP_ABSENT_DEVICES.
 */
final class AbsenceTracker {
    static final double GRACE_SEC = 5.0;
    static final double REPROBE_SEC = 5.0;

    private double badSince = Double.NaN;
    private double lastProbe = Double.NEGATIVE_INFINITY;
    private boolean absent;

    /** Whether the device should be refreshed now. A healthy or recently-bad device always is. */
    boolean shouldRefresh(double now) {
        if (!absent) return true;
        if (now - lastProbe >= REPROBE_SEC) {
            lastProbe = now;
            return true;
        }
        return false;
    }

    /** Report the outcome of a refresh (only call after shouldRefresh returned true). */
    void record(boolean ok, double now) {
        if (ok) {
            absent = false;
            badSince = Double.NaN;
            return;
        }
        if (Double.isNaN(badSince)) badSince = now;
        if (!absent && now - badSince >= GRACE_SEC) {
            absent = true;
            lastProbe = now;
        }
    }

    boolean isAbsent() {
        return absent;
    }
}
