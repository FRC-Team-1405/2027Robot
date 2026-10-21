package frc.robot.util;

import edu.wpi.first.wpilibj.Alert;
import edu.wpi.first.wpilibj.Alert.AlertType;
import edu.wpi.first.wpilibj.DriverStation;
import edu.wpi.first.wpilibj.Timer;
import frc.robot.constants.FeatureSwitches;
import org.littletonrobotics.junction.Logger;

/** Low-volume diagnostics independent of verbose console output and optional timing traces. */
public final class RuntimeDiagnostics {
    private final DeadlineCounter loop = new DeadlineCounter();
    private final DeadlineCounter scheduler = new DeadlineCounter();
    private final PeriodicGate controllerGate = new PeriodicGate();
    private final Alert[] controllerAlerts = {
        new Alert("Driver controller (port 0) missing or incomplete: check DS mapping", AlertType.kWarning),
        new Alert("Operator controller (port 1) missing or incomplete: check DS mapping", AlertType.kWarning),
        new Alert("Shooter test controller (port 2) missing or incomplete", AlertType.kWarning)
    };
    private final Alert overrunAlert = new Alert("Robot loop has exceeded 20 ms in the last 5 seconds; see Diagnostics timings",
            AlertType.kWarning);
    private long lastOverrunNanos = Long.MIN_VALUE;

    public void recordLoop(double millis, double budgetMs) {
        loop.add(millis, budgetMs);
        if (millis > budgetMs) lastOverrunNanos = System.nanoTime();
        overrunAlert.set(lastOverrunNanos != Long.MIN_VALUE
                && System.nanoTime() - lastOverrunNanos < 5_000_000_000L);
        record("Loop", loop, millis);
    }

    public void recordScheduler(double millis, double budgetMs) {
        scheduler.add(millis, budgetMs);
        record("Scheduler", scheduler, millis);
    }

    private static void record(String name, DeadlineCounter counter, double millis) {
        Logger.recordOutput("Diagnostics/" + name + "Ms", millis);
        Logger.recordOutput("Diagnostics/" + name + "OverrunCount", counter.overruns);
        Logger.recordOutput("Diagnostics/" + name + "MaxMs", counter.maxMs);
    }

    /** No repeating console reports. Alerts recover automatically after reconnecting. */
    public void updateControllers() {
        if (!controllerGate.ready(Timer.getFPGATimestamp(), 1.0)) return;
        for (int port = 0; port < controllerAlerts.length; port++) {
            int axes = DriverStation.getStickAxisCount(port);
            int buttons = DriverStation.getStickButtonCount(port);
            int povs = DriverStation.getStickPOVCount(port);
            String key = "Diagnostics/Controllers/Port" + port;
            Logger.recordOutput(key + "/Axes", axes);
            Logger.recordOutput(key + "/Buttons", buttons);
            Logger.recordOutput(key + "/POVs", povs);
            boolean expected = port < 2 || FeatureSwitches.ENABLE_SHOOTER_TEST_CONTROLLER;
            controllerAlerts[port].set(DriverStation.isDSAttached() && expected
                    && !hasXboxControls(axes, buttons, povs));
        }
    }

    static boolean hasXboxControls(int axes, int buttons, int povs) {
        return axes >= 6 && buttons >= 10 && povs >= 1;
    }

    static final class DeadlineCounter {
        long overruns;
        double maxMs;

        void add(double millis, double budgetMs) {
            if (millis > budgetMs) overruns++;
            maxMs = Math.max(maxMs, millis);
        }
    }
}
