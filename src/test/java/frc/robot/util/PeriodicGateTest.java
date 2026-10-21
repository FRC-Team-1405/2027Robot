package frc.robot.util;

import static org.junit.jupiter.api.Assertions.*;
import org.junit.jupiter.api.Test;

class PeriodicGateTest {
    @Test
    void samplesImmediatelyThenAtTenHertzWithoutCatchupBursts() {
        var gate = new PeriodicGate();
        assertTrue(gate.ready(0, 0.1));
        assertFalse(gate.ready(0.02, 0.1));
        assertTrue(gate.ready(0.1, 0.1));
        assertFalse(gate.ready(0.1, 0.1));
        assertTrue(gate.ready(9, 0.1));
        assertFalse(gate.ready(9.02, 0.1));
        assertTrue(gate.ready(0, 0.1)); // new clock epoch
    }
}
