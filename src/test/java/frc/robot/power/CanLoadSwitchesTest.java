package frc.robot.power;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

import frc.robot.constants.FeatureSwitches;

/** Pure logic behind the CAN-load switches: signal-rate selection and the absent-device tracker. */
class CanLoadSwitchesTest {
    @Test
    void shippedDefaultsKeepTheRuckusBehavior() {
        assertTrue(FeatureSwitches.POWER_TELEMETRY_SIGNALS);
        assertEquals(0.0, FeatureSwitches.MECHANISM_STATUS_SIGNAL_HZ);
        assertFalse(FeatureSwitches.OPTIMIZE_BUS_UTILIZATION);
        assertFalse(FeatureSwitches.SKIP_ABSENT_DEVICES);
        assertFalse(FeatureSwitches.LOG_SUBSYSTEM_TIMINGS);
    }

    @Test
    void mechanismRateIsUntouchedUnlessASwitchAsksForOne() {
        assertEquals(0.0, BusLoad.mechanismHz(0, false));
    }

    @Test
    void configuredRateWinsAndOptimizingAloneFallsBackToFiftyHertz() {
        assertEquals(20.0, BusLoad.mechanismHz(20, false));
        assertEquals(20.0, BusLoad.mechanismHz(20, true));
        assertEquals(BusLoad.DEFAULT_OPTIMIZED_HZ, BusLoad.mechanismHz(0, true));
    }

    @Test
    void faultSignalsKeepTheirSlowRate() {
        assertTrue(BusLoad.isFault("SupplyLimited"));
        assertTrue(BusLoad.isFault("StatorLimited"));
        assertTrue(BusLoad.isFault("Undervoltage"));
        assertFalse(BusLoad.isFault("VelocityRPS"));
    }

    @Test
    void aHealthyDeviceIsAlwaysRefreshed() {
        AbsenceTracker t = new AbsenceTracker();
        for (double now = 0; now < 30; now += 0.02) {
            assertTrue(t.shouldRefresh(now));
            t.record(true, now);
        }
        assertFalse(t.isAbsent());
    }

    @Test
    void aBriefGlitchIsNotTreatedAsAbsent() {
        AbsenceTracker t = new AbsenceTracker();
        for (double now = 0; now < 2.0; now += 0.02) {
            t.record(false, now);
        }
        t.record(true, 2.0);
        assertFalse(t.isAbsent());
        assertTrue(t.shouldRefresh(2.02));
    }

    @Test
    void aDeviceBadForTheGracePeriodIsParkedAndOnlyProbedPeriodically() {
        AbsenceTracker t = new AbsenceTracker();
        double now = 0;
        for (; now <= AbsenceTracker.GRACE_SEC + 0.1; now += 0.02) {
            if (t.shouldRefresh(now)) t.record(false, now);
        }
        assertTrue(t.isAbsent());

        int refreshes = 0;
        double end = now + 4 * AbsenceTracker.REPROBE_SEC;
        for (; now < end; now += 0.02) {
            if (t.shouldRefresh(now)) {
                refreshes++;
                t.record(false, now);
            }
        }
        assertTrue(refreshes >= 3 && refreshes <= 5, "probed " + refreshes + " times in 4 probe intervals");
        assertTrue(t.isAbsent());
    }

    @Test
    void aParkedDeviceThatAnswersAProbeIsRefreshedEveryLoopAgain() {
        AbsenceTracker t = new AbsenceTracker();
        double now = 0;
        for (; now <= AbsenceTracker.GRACE_SEC + 0.1; now += 0.02) {
            if (t.shouldRefresh(now)) t.record(false, now);
        }
        assertTrue(t.isAbsent());
        now += AbsenceTracker.REPROBE_SEC;
        assertTrue(t.shouldRefresh(now));
        t.record(true, now);
        assertFalse(t.isAbsent());
        assertTrue(t.shouldRefresh(now + 0.02));
    }
}
