package frc.robot.util;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class WallClockEpochTest {
    // A real boot from Ruckus 2026: the Driver Station synced the clock 300 s after boot.
    private static final long SYNCED_WALL_MS = 1_792_240_575_000L;      // 2026-10-17 ~12:36:15 UTC
    private static final long FPGA_US_AT_SYNC = 300_000_000L;
    private static final long STALE_WALL_MS = 1_775_000_000_000L;       // April, before the sync

    @Test
    void epochIsWallClockMinusTimeSinceBoot() {
        assertEquals(SYNCED_WALL_MS - 300_000L, WallClockEpoch.epochMs(SYNCED_WALL_MS, FPGA_US_AT_SYNC));
    }

    @Test
    void firstReadingIsAlwaysRecorded() {
        assertTrue(new WallClockEpoch().update(STALE_WALL_MS, 5_000_000L));
    }

    @Test
    void aSteadyClockIsNotRecordedAgain() {
        var epoch = new WallClockEpoch();
        assertTrue(epoch.update(SYNCED_WALL_MS, FPGA_US_AT_SYNC));
        // 20 ms loops, both clocks advancing together, with a few ms of jitter.
        for (int i = 1; i <= 1000; i++) {
            long jitterMs = i % 3;
            assertFalse(epoch.update(SYNCED_WALL_MS + i * 20L + jitterMs, FPGA_US_AT_SYNC + i * 20_000L));
        }
    }

    @Test
    void slowDriftBelowTheThresholdIsIgnored() {
        var epoch = new WallClockEpoch();
        epoch.update(SYNCED_WALL_MS, FPGA_US_AT_SYNC);
        assertFalse(epoch.update(SYNCED_WALL_MS + 900, FPGA_US_AT_SYNC));
    }

    @Test
    void theDriverStationClockStepIsRecordedOnceAndTheNewEpochWins() {
        var epoch = new WallClockEpoch();
        assertTrue(epoch.update(STALE_WALL_MS, 20_000_000L));
        long stale = epoch.lastRecordedMs();
        assertFalse(epoch.update(STALE_WALL_MS + 1000, 21_000_000L));
        // The clock is set from the Driver Station: wall jumps, FPGA time does not.
        assertTrue(epoch.update(SYNCED_WALL_MS, FPGA_US_AT_SYNC));
        assertNotEquals(stale, epoch.lastRecordedMs());
        assertEquals(SYNCED_WALL_MS - 300_000L, epoch.lastRecordedMs());
        assertFalse(epoch.update(SYNCED_WALL_MS + 20, FPGA_US_AT_SYNC + 20_000L));
    }

    @Test
    void eachRunGetsItsOwnBootId() {
        var a = new WallClockEpoch();
        var b = new WallClockEpoch();
        assertEquals(a.bootId(), a.bootId());
        assertNotEquals(a.bootId(), b.bootId());
    }
}
