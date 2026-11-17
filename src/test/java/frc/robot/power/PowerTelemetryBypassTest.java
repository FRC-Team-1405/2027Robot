package frc.robot.power;

import static org.junit.jupiter.api.Assertions.*;
import static org.junit.jupiter.api.Assumptions.assumeTrue;
import com.ctre.phoenix6.controls.NeutralOut;
import frc.robot.constants.FeatureSwitches;
import org.junit.jupiter.api.Test;

class PowerTelemetryBypassTest {
    @Test
    void disabledInstrumentationReturnsTheExactControlRequestWithoutTouchingHardware() {
        assumeTrue(!FeatureSwitches.ENABLE_POWER_TELEMETRY || !FeatureSwitches.POWER_REQUEST_DETAILS,
                "Run with the bypass or request-detail experiment enabled");
        NeutralOut request = new NeutralOut();
        assertSame(request, PowerTelemetry.request(null, request));
    }

    @Test
    void completeBypassDoesNotNeedLoggerOrHardwareInitialization() {
        assumeTrue(!FeatureSwitches.ENABLE_POWER_TELEMETRY, "Run with the complete bypass enabled");
        assertDoesNotThrow(PowerTelemetry::initialize);
        assertDoesNotThrow(PowerTelemetry::periodic);
    }
}
