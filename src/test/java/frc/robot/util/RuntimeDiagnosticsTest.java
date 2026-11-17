package frc.robot.util;

import static org.junit.jupiter.api.Assertions.*;
import org.junit.jupiter.api.Test;

class RuntimeDiagnosticsTest {
    @Test
    void countsTwentyMillisecondMissesEvenBelowQuietWatchdogThreshold() {
        var counter = new RuntimeDiagnostics.DeadlineCounter();
        for (double ms : new double[] {4, 20, 20.01, 34, 1001}) counter.add(ms, 20);
        assertEquals(3, counter.overruns);
        assertEquals(1001, counter.maxMs);
    }

    @Test
    void detectsConnectedControllersWithMissingControls() {
        assertFalse(RuntimeDiagnostics.hasXboxControls(0, 0, 0));
        assertFalse(RuntimeDiagnostics.hasXboxControls(6, 10, 0));
        assertFalse(RuntimeDiagnostics.hasXboxControls(5, 10, 1));
        assertFalse(RuntimeDiagnostics.hasXboxControls(6, 9, 1));
        assertTrue(RuntimeDiagnostics.hasXboxControls(6, 10, 1));
        assertTrue(RuntimeDiagnostics.hasXboxControls(8, 12, 2));
    }
}
