package frc.robot.util;

import static org.junit.jupiter.api.Assertions.*;
import org.junit.jupiter.api.Test;

class RioSystemStatsTest {
    private static String stat(long user, long idle, long core0User, long core0Idle, long core1User, long core1Idle) {
        // user nice system idle iowait irq softirq steal guest guest_nice
        return "cpu  " + user + " 0 0 " + idle + " 0 0 0 0 0 0\n"
                + "cpu0 " + core0User + " 0 0 " + core0Idle + " 0 0 0 0 0 0\n"
                + "cpu1 " + core1User + " 0 0 " + core1Idle + " 0 0 0 0 0 0\n"
                + "intr 12345 0 0\nctxt 999\n";
    }

    private static final String MEMINFO = "MemTotal:         1000000 kB\nMemFree:           100000 kB\n"
            + "MemAvailable:      250000 kB\nBuffers:            1000 kB\n";

    private static String netDev(long rx, long tx) {
        return "Inter-|   Receive                                                |  Transmit\n"
                + " face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed\n"
                + "    lo:  500 5 0 0 0 0 0 0  500 5 0 0 0 0 0 0\n"
                + "  eth0: " + rx + " 100 2 7 0 0 0 0 " + tx + " 90 0 0 0 0 0 0\n";
    }

    @Test
    void firstSampleHasNoIntervalThenCpuAndTrafficAreDeltas() {
        var reader = new RioSystemStats.Reader();
        assertNull(reader.sample(stat(100, 100, 50, 50, 50, 50), MEMINFO, netDev(1_000_000, 2_000_000), 0));
        // +150 busy / +200 total overall; core0 fully busy, core1 half
        var s = reader.sample(stat(250, 150, 150, 50, 100, 100), MEMINFO, netDev(1_500_000, 2_250_000), 2_000_000_000L);
        assertEquals(75.0, s.cpuPct());
        assertArrayEquals(new double[] {100.0, 50.0}, s.corePct());
        assertEquals(75.0, s.memUsedPct());
        assertEquals(244.1, s.memAvailableMb());
        assertEquals(2.0, s.netRxMbps());      // 500 kB over 2 s
        assertEquals(1.0, s.netTxMbps());      // 250 kB over 2 s
        assertEquals(2, s.netRxErrors());
        assertEquals(7, s.netRxDropped());
    }

    @Test
    void counterResetReportsZeroTrafficNotASpike() {
        var reader = new RioSystemStats.Reader();
        reader.sample(stat(1, 1, 1, 1, 1, 1), MEMINFO, netDev(9_000_000, 9_000_000), 0);
        var s = reader.sample(stat(2, 2, 2, 2, 2, 2), MEMINFO, netDev(10, 10), 1_000_000_000L);
        assertEquals(0.0, s.netRxMbps());
        assertEquals(0.0, s.netTxMbps());
    }

    @Test
    void missingInterfaceOrMeminfoFieldsAreMinusOne() {
        assertNull(RioSystemStats.parseNetDev("  wlan0: 1 2 3 4 5 6 7 8 9 10\n", "eth0"));
        assertArrayEquals(new double[] {-1, -1}, RioSystemStats.parseMeminfo("MemTotal: 10 kB\n"));
        var reader = new RioSystemStats.Reader();
        reader.sample(stat(1, 1, 1, 1, 1, 1), "", "", 0);
        var s = reader.sample(stat(2, 2, 2, 2, 2, 2), "", "", 1_000_000_000L);
        assertEquals(-1, s.netRxErrors());
        assertEquals(-1.0, s.memUsedPct());
    }
}
