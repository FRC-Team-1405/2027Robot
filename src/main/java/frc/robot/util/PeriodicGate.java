package frc.robot.util;

/** A nonblocking sample gate. Missed samples are skipped, never caught up in a burst. */
public final class PeriodicGate {
    private double last = Double.NEGATIVE_INFINITY;

    public boolean ready(double now, double periodSeconds) {
        if (now >= last && now - last < periodSeconds - 1e-9) return false;
        last = now;
        return true;
    }
}
