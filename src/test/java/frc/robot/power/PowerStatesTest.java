package frc.robot.power;

import static org.junit.jupiter.api.Assertions.*;
import java.util.Map;
import org.junit.jupiter.api.Test;

class PowerStatesTest {
    @Test void genericStatesHaveExplicitPrioritiesAndImmutableDefinitions() {
        PowerStates.define("TestScoring", Map.of("Shooter", 0, "Drivetrain", 1, "Pickup", 1));
        PowerStates.select("TestScoring", "Test");
        assertEquals("TestScoring", PowerStates.active());
        assertEquals(0, PowerStates.priorities().get("Shooter"));
        assertEquals(PowerStates.priorities().get("Drivetrain"), PowerStates.priorities().get("Pickup"));
        assertThrows(UnsupportedOperationException.class, () -> PowerStates.priorities().put("Shooter", 5));
        PowerStates.select("Unassigned", "Reset");
        assertTrue(PowerStates.priorities().isEmpty());
    }
    @Test void invalidStateSelectionDoesNotSilentlyInventAPriority() {
        assertThrows(IllegalArgumentException.class, () -> PowerStates.select("DoesNotExist", "Test"));
        assertThrows(IllegalArgumentException.class, () -> PowerStates.define("Bad", Map.of("Shooter", -1)));
        assertThrows(IllegalArgumentException.class, () -> PowerStates.define("Unassigned", Map.of()));
        assertEquals(PowerTelemetry.identity("", 29), PowerTelemetry.identity("rio", 29));
        assertNotEquals(PowerTelemetry.identity("canivore", 29), PowerTelemetry.identity("rio", 29));
        assertNotEquals(PowerTelemetry.identity("a/b", 29), PowerTelemetry.identity("a_b", 29));
    }
}
