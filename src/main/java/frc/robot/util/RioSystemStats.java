package frc.robot.util;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import org.littletonrobotics.junction.Logger;

import edu.wpi.first.wpilibj.RobotBase;
import frc.robot.constants.FeatureSwitches;

/**
 * roboRIO CPU, memory and network traffic into the AdvantageKit log as {@code RealOutputs/RIO/...}.
 *
 * <p>AdvantageKit logs loop timing but not how busy the roboRIO's two cores are, and nothing logs how
 * much the roboRIO sends and receives. The Driver Station log has CPU, but not in the .wpilog the
 * Health Check reads. With this, LogBench can flag a match where the CPU sat near 100 % (loop
 * overruns that no single subsystem explains) or the robot network was busy.
 *
 * <p>A daemon thread reads /proc once a second; the robot loop only logs the latest sample, and only
 * when there is a new one, so the loop never touches the filesystem. Does nothing in simulation or
 * replay.
 *
 * <p>Network traffic is the roboRIO's own ethernet port ({@value #IFACE}): everything it exchanges
 * with the Orange Pis, the radio and through the radio with the Driver Station and dashboards. The
 * field's 7 Mbit/s limit applies to the radio, which AdvantageKit already logs as
 * {@code RadioStatus/Status} (its {@code bandwidthUsedMbps}).
 */
public final class RioSystemStats {
    static final String IFACE = "eth0";
    private static final long PERIOD_MS = 1000;

    /** One reading. CPU values are percent of the interval since the previous reading. */
    record Sample(double cpuPct, double[] corePct, double memUsedPct, double memAvailableMb,
            double netRxMbps, double netTxMbps, long netRxErrors, long netRxDropped, long seq) {}

    private static volatile Sample latest;
    private static long loggedSeq = -1;
    private static Thread thread;

    private RioSystemStats() {}

    /** Call every robot loop. Starts the reader thread on first call. */
    public static void periodic() {
        if (!FeatureSwitches.RIO_SYSTEM_STATS_LOGGING || !RobotBase.isReal() || Logger.hasReplaySource()) return;
        if (thread == null) start();
        Sample s = latest;
        if (s == null || s.seq() == loggedSeq) return;
        loggedSeq = s.seq();
        Logger.recordOutput("RIO/CpuPct", s.cpuPct());
        Logger.recordOutput("RIO/CpuCorePct", s.corePct());
        Logger.recordOutput("RIO/MemUsedPct", s.memUsedPct());
        Logger.recordOutput("RIO/MemAvailableMB", s.memAvailableMb());
        Logger.recordOutput("RIO/NetRxMbps", s.netRxMbps());
        Logger.recordOutput("RIO/NetTxMbps", s.netTxMbps());
        Logger.recordOutput("RIO/NetRxErrors", s.netRxErrors());
        Logger.recordOutput("RIO/NetRxDropped", s.netRxDropped());
    }

    private static void start() {
        thread = new Thread(new Reader(), "RioSystemStats");
        thread.setDaemon(true);
        thread.setPriority(Thread.MIN_PRIORITY);
        thread.start();
    }

    /** Samples /proc every {@value #PERIOD_MS} ms. Any read error skips that sample, never the thread. */
    static final class Reader implements Runnable {
        private long[][] prevCpu;
        private long[] prevNet;
        private long prevNanos;
        private long seq;

        @Override
        public void run() {
            while (true) {
                try {
                    Sample s = sample(read("/proc/stat"), read("/proc/meminfo"), read("/proc/net/dev"), System.nanoTime());
                    if (s != null) latest = s;
                } catch (IOException | RuntimeException e) {
                    // /proc unreadable this second; try again next second.
                }
                try {
                    Thread.sleep(PERIOD_MS);
                } catch (InterruptedException e) {
                    return;
                }
            }
        }

        private static String read(String path) throws IOException {
            return Files.readString(Path.of(path));
        }

        /** A sample from the three files' text, or null for the first call (no interval yet). */
        Sample sample(String stat, String meminfo, String netDev, long nanos) {
            long[][] cpu = parseCpuTimes(stat);
            long[] net = parseNetDev(netDev, IFACE);
            double[] mem = parseMeminfo(meminfo);
            Sample out = null;
            if (prevCpu != null && prevCpu.length == cpu.length) {
                double cpuPct = busyPct(prevCpu[0], cpu[0]);
                double[] cores = new double[cpu.length - 1];
                for (int i = 1; i < cpu.length; i++) cores[i - 1] = busyPct(prevCpu[i], cpu[i]);
                double seconds = (nanos - prevNanos) / 1e9;
                double rx = 0, tx = 0;
                if (net != null && prevNet != null && seconds > 0 && net[0] >= prevNet[0] && net[1] >= prevNet[1]) {
                    rx = (net[0] - prevNet[0]) * 8 / 1e6 / seconds;
                    tx = (net[1] - prevNet[1]) * 8 / 1e6 / seconds;
                }
                out = new Sample(cpuPct, cores, mem[0], mem[1], round(rx), round(tx),
                        net == null ? -1 : net[2], net == null ? -1 : net[3], seq++);
            }
            prevCpu = cpu;
            prevNet = net;
            prevNanos = nanos;
            return out;
        }
    }

    private static double round(double x) {
        return Math.round(x * 1000) / 1000.0;
    }

    /** [total, cpu0, cpu1, ...] each as {busy, total} jiffies, from /proc/stat. */
    static long[][] parseCpuTimes(String stat) {
        List<long[]> rows = new ArrayList<>();
        for (String line : stat.split("\n")) {
            if (!line.startsWith("cpu")) continue;
            String[] f = line.trim().split("\\s+");
            long total = 0;
            for (int i = 1; i < f.length; i++) total += Long.parseLong(f[i]);
            long idle = Long.parseLong(f[4]) + (f.length > 5 ? Long.parseLong(f[5]) : 0); // idle + iowait
            rows.add(new long[] {total - idle, total});
        }
        return rows.toArray(new long[0][]);
    }

    static double busyPct(long[] before, long[] after) {
        long total = after[1] - before[1];
        if (total <= 0) return 0;
        return Math.round(1000.0 * (after[0] - before[0]) / total) / 10.0;
    }

    /** {used %, available MB} from /proc/meminfo; {-1, -1} if it lacks MemTotal or MemAvailable. */
    static double[] parseMeminfo(String meminfo) {
        double totalKb = -1, availKb = -1;
        for (String line : meminfo.split("\n")) {
            String[] f = line.trim().split("\\s+");
            if (f.length < 2) continue;
            if (f[0].equals("MemTotal:")) totalKb = Double.parseDouble(f[1]);
            if (f[0].equals("MemAvailable:")) availKb = Double.parseDouble(f[1]);
        }
        if (totalKb <= 0 || availKb < 0) return new double[] {-1, -1};
        return new double[] {Math.round(1000 * (1 - availKb / totalKb)) / 10.0, Math.round(availKb / 102.4) / 10.0};
    }

    /** {rx bytes, tx bytes, rx errors, rx dropped} for one interface in /proc/net/dev, or null. */
    static long[] parseNetDev(String netDev, String iface) {
        for (String line : netDev.split("\n")) {
            int colon = line.indexOf(':');
            if (colon < 0 || !line.substring(0, colon).trim().equals(iface)) continue;
            String[] f = line.substring(colon + 1).trim().split("\\s+");
            // receive: bytes packets errs drop fifo frame compressed multicast | transmit: bytes ...
            if (f.length < 9) return null;
            return new long[] {Long.parseLong(f[0]), Long.parseLong(f[8]), Long.parseLong(f[2]), Long.parseLong(f[3])};
        }
        return null;
    }
}
