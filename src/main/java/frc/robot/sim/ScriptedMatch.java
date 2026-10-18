package frc.robot.sim;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

import org.littletonrobotics.junction.Logger;

import edu.wpi.first.networktables.NetworkTableInstance;
import edu.wpi.first.wpilibj.RobotBase;
import edu.wpi.first.wpilibj.Timer;
import edu.wpi.first.wpilibj.simulation.DriverStationSim;

/**
 * Plays a scripted match in simulation: drives the simulated Driver Station through
 * disabled -> auto -> pause -> teleop -> disabled and wiggles the driver joystick with random
 * input so the simulated drivetrain moves. Simulation only, and inert unless the environment
 * variable {@code SIM_MATCH_SCRIPT} is set, so it cannot affect a real robot or a normal
 * {@code simulateJava}.
 *
 * <p>This exists so the whole vision-recording path (Orange Pi recorder -> Fetch Bundle ->
 * LogBench) can be exercised on a laptop with no robot: the Pi's recorder connects to this
 * simulation's NetworkTables server, so the AdvantageKit log and the recordings share one clock
 * and one wall clock, exactly as on the real robot. See coprocessor/sim/README.md.
 *
 * <p>Environment (all optional):
 * <ul>
 *   <li>{@code SIM_MATCH_SCRIPT} - {@code default}, or {@code mode:seconds,...} with modes
 *       {@code disabled}, {@code auto}, {@code teleop}; e.g. {@code disabled:10,auto:20,disabled:3,teleop:140}.
 *       The default is a real match with 10 s of pre-match.</li>
 *   <li>{@code SIM_MATCH_FAST} - divide every duration by this (default 1).</li>
 *   <li>{@code SIM_MATCH_WAIT_CLIENTS} - stay disabled, with the timeline not started, until this
 *       many NetworkTables clients are connected (default 0). Use it to wait for the Pi.</li>
 *   <li>{@code SIM_MATCH_SEED} - seed for the random joystick input (default 1405).</li>
 *   <li>{@code SIM_MATCH_EXIT} - when {@code 1}, flush the log and exit the JVM shortly after the
 *       script ends (default: keep running).</li>
 * </ul>
 * Each phase change is printed as {@code SIMMATCH phase=<mode> t=<seconds> ...} so a wrapper
 * script can follow along.
 */
public final class ScriptedMatch {
    public static final String SCRIPT_ENV = "SIM_MATCH_SCRIPT";
    static final String DEFAULT_SCRIPT = "disabled:10,auto:20,disabled:3,teleop:140,disabled:10";
    private static final double EXIT_TAIL_SEC = 5.0;
    private static final int DRIVER_PORT = 0;
    // Standard Xbox axes the drivetrain reads: left X/Y strafe, right X rotate.
    private static final int[] DRIVER_AXES = {0, 1, 4};

    /** One step of the script. */
    record Phase(String mode, double seconds) {}

    private static List<Phase> phases;
    private static double speedUp = 1.0;
    private static int waitClients = 0;
    private static boolean exitWhenDone = false;
    private static Random random;
    private static boolean initialized = false;

    private static double timelineStart = Double.NaN;
    private static int phaseIndex = -1;
    private static double phaseStart;
    private static double doneAt = Double.NaN;
    private static double[] axisTarget = new double[DRIVER_AXES.length];
    private static double[] axisValue = new double[DRIVER_AXES.length];
    private static double nextRetarget;

    private ScriptedMatch() {}

    /** True when this run was asked to play a scripted match (simulation only). */
    public static boolean enabled() {
        String script = System.getenv(SCRIPT_ENV);
        return RobotBase.isSimulation() && script != null && !script.isBlank();
    }

    /** Parses "mode:seconds,mode:seconds". "default" (or blank) is the full default match. */
    static List<Phase> parseScript(String text) {
        String source = (text == null || text.isBlank() || text.trim().equalsIgnoreCase("default"))
                ? DEFAULT_SCRIPT : text;
        List<Phase> out = new ArrayList<>();
        for (String part : source.split(",")) {
            String[] kv = part.trim().split(":");
            if (kv.length != 2) {
                throw new IllegalArgumentException("bad " + SCRIPT_ENV + " entry '" + part + "'; want mode:seconds");
            }
            String mode = kv[0].trim().toLowerCase();
            if (!mode.equals("disabled") && !mode.equals("auto") && !mode.equals("teleop")) {
                throw new IllegalArgumentException("unknown mode '" + mode + "' in " + SCRIPT_ENV);
            }
            double seconds = Double.parseDouble(kv[1].trim());
            if (!(seconds > 0)) {
                throw new IllegalArgumentException("non-positive duration in " + SCRIPT_ENV + ": " + part);
            }
            out.add(new Phase(mode, seconds));
        }
        return out;
    }

    private static void init() {
        phases = parseScript(System.getenv(SCRIPT_ENV));
        speedUp = envDouble("SIM_MATCH_FAST", 1.0);
        waitClients = (int) envDouble("SIM_MATCH_WAIT_CLIENTS", 0);
        exitWhenDone = "1".equals(System.getenv("SIM_MATCH_EXIT"));
        random = new Random((long) envDouble("SIM_MATCH_SEED", 1405));
        initialized = true;
        System.out.println("SIMMATCH script=" + phases + " fast=" + speedUp + " waitClients=" + waitClients);
        DriverStationSim.setDsAttached(true);
        DriverStationSim.setFmsAttached(false);
        for (int axis : DRIVER_AXES) {
            DriverStationSim.setJoystickAxisCount(DRIVER_PORT, Math.max(axis + 1, 6));
        }
        applyMode("disabled");
    }

    private static double envDouble(String name, double fallback) {
        String v = System.getenv(name);
        if (v == null || v.isBlank()) return fallback;
        return Double.parseDouble(v.trim());
    }

    private static void applyMode(String mode) {
        DriverStationSim.setEnabled(!mode.equals("disabled"));
        DriverStationSim.setAutonomous(mode.equals("auto"));
        DriverStationSim.setTest(false);
        DriverStationSim.notifyNewData();
    }

    /** Call from Robot.simulationPeriodic(); does nothing unless {@link #enabled()}. */
    public static void update() {
        if (!enabled()) return;
        if (!initialized) init();
        double now = Timer.getFPGATimestamp();

        if (Double.isNaN(timelineStart)) {
            int clients = NetworkTableInstance.getDefault().getConnections().length;
            if (clients < waitClients) return;
            timelineStart = now;
            System.out.printf("SIMMATCH start clients=%d%n", clients);
            advancePhase(now);
        }

        if (phaseIndex >= phases.size()) {
            if (exitWhenDone && now - doneAt >= EXIT_TAIL_SEC) {
                System.out.println("SIMMATCH exit");
                Logger.end();
                System.exit(0);
            }
            return;
        }

        Phase current = phases.get(phaseIndex);
        if (now - phaseStart >= current.seconds() / speedUp) {
            advancePhase(now);
            if (phaseIndex >= phases.size()) return;
            current = phases.get(phaseIndex);
        }
        drive(now, current.mode());
    }

    private static void advancePhase(double now) {
        phaseIndex++;
        if (phaseIndex >= phases.size()) {
            applyMode("disabled");
            doneAt = now;
            System.out.printf("SIMMATCH phase=done t=%.2f%n", now - timelineStart);
            return;
        }
        Phase next = phases.get(phaseIndex);
        phaseStart = now;
        applyMode(next.mode());
        Logger.recordOutput("SimMatch/Phase", next.mode());
        System.out.printf("SIMMATCH phase=%s t=%.2f wall_ms=%d%n", next.mode(), now - timelineStart,
                System.currentTimeMillis());
    }

    /** Random, smoothly varying stick input so the drivetrain moves during auto-free teleop. */
    private static void drive(double now, String mode) {
        boolean driving = mode.equals("teleop");
        if (now >= nextRetarget) {
            nextRetarget = now + 1.0 + 2.0 * random.nextDouble();
            for (int i = 0; i < axisTarget.length; i++) {
                axisTarget[i] = driving ? (random.nextDouble() * 2 - 1) * (i == 2 ? 0.4 : 0.6) : 0.0;
            }
        }
        for (int i = 0; i < axisValue.length; i++) {
            double target = driving ? axisTarget[i] : 0.0;
            axisValue[i] += (target - axisValue[i]) * 0.05;
            DriverStationSim.setJoystickAxis(DRIVER_PORT, DRIVER_AXES[i], axisValue[i]);
        }
        DriverStationSim.notifyNewData();
    }
}
