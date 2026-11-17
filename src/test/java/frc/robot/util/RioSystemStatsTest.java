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

    @Test
    void procStatParsesNamesWithSpacesAndParentheses() {
        // pid (comm) state ppid pgrp session tty tpgid flags minflt cminflt majflt cmajflt utime stime ...
        String line = "812 (Java (Thread) 1) S 1 812 812 0 -1 4194560 100 0 0 0 250 50 0 0 20 0 30 0 1000 1 2 3\n";
        Object[] f = RioSystemStats.parseProcStat(line);
        assertEquals("Java (Thread) 1", f[0]);
        assertEquals(300L, f[1]);
        assertNull(RioSystemStats.parseProcStat("garbage"));
        assertNull(RioSystemStats.parseProcStat("1 (x) S 1 2"));     // too short
    }

    @Test
    void trackerReportsPercentOfAllCoresBusiestFirstAndSkipsOneId() {
        var tracker = new RioSystemStats.CpuTracker();
        java.util.Map<String, long[]> t0 = new java.util.HashMap<>();
        t0.put("100", new long[] {1000});
        t0.put("200", new long[] {500});
        t0.put("300", new long[] {10});
        assertTrue(tracker.update(t0, 0, 5, null).isEmpty());          // first call: no interval yet
        java.util.Map<String, long[]> t1 = new java.util.HashMap<>();
        t1.put("100", new long[] {1100});    // +100 of 200 total = 50 %
        t1.put("200", new long[] {520});     // +20 = 10 %
        t1.put("300", new long[] {10});      // idle: left out
        t1.put("400", new long[] {99});      // new process: no baseline, ignored
        var top = tracker.update(t1, 200, 5, null);
        assertEquals(2, top.size());
        assertTrue(top.get(0).endsWith(":100:50.0"));
        assertTrue(top.get(1).endsWith(":200:10.0"));
        assertEquals(50.0, tracker.lastPct("100"));
        // skipping our own id leaves the others
        java.util.Map<String, long[]> t2 = new java.util.HashMap<>();
        t2.put("100", new long[] {1150});
        t2.put("200", new long[] {540});
        var others = tracker.update(t2, 200, 5, "100");
        assertEquals(1, others.size());
        assertEquals(25.0, tracker.lastPct("100"));
    }
}
