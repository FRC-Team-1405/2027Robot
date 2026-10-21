package frc.robot.util;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.HashMap;
import java.util.Map;
import java.util.TreeMap;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import edu.wpi.first.networktables.NetworkTableEntry;
import edu.wpi.first.networktables.NetworkTableInstance;
import edu.wpi.first.networktables.NetworkTableValue;

class CoprocessorHealthLoggerTest {
    private NetworkTableInstance inst;

    @BeforeEach
    void setUp() {
        inst = NetworkTableInstance.create();
    }

    @AfterEach
    void tearDown() {
        inst.close();
    }

    private Map<String, Object> mirrored() {
        Map<String, Object> out = new TreeMap<>();
        Map<String, NetworkTableEntry> cache = new HashMap<>();
        CoprocessorHealthLogger.mirror(inst.getTable("OrangePi"), "OrangePi", out::put, cache);
        return out;
    }

    @Test
    void copiesMetricsAndNestedRecorderHeartbeatsUnderTheirOwnKeys() {
        var left = inst.getTable("OrangePi/LeftPi");
        left.getEntry("CPU_Pct").setDouble(41.5);
        left.getEntry("Host").setString("leftpi.local");
        var recorder = inst.getTable("OrangePi/LeftPi/Recorders/LeftCam");
        recorder.getEntry("State").setString("recording");
        recorder.getEntry("StreamOk").setBoolean(true);
        recorder.getEntry("Errors").setInteger(2);

        Map<String, Object> out = mirrored();

        assertEquals(41.5, out.get("OrangePi/LeftPi/CPU_Pct"));
        assertEquals("leftpi.local", out.get("OrangePi/LeftPi/Host"));
        assertEquals("recording", out.get("OrangePi/LeftPi/Recorders/LeftCam/State"));
        assertEquals(true, out.get("OrangePi/LeftPi/Recorders/LeftCam/StreamOk"));
        assertEquals(2L, out.get("OrangePi/LeftPi/Recorders/LeftCam/Errors"));
    }

    @Test
    void walksEveryBoardAndSingleBoardsPublishingStraightUnderTheRoot() {
        inst.getTable("OrangePi/LeftPi").getEntry("CPU_Pct").setDouble(1);
        inst.getTable("OrangePi/RightPi").getEntry("CPU_Pct").setDouble(2);
        inst.getTable("OrangePi").getEntry("Temp_C").setDouble(55);   // a lone Pi with no board name

        Map<String, Object> out = mirrored();

        assertEquals(1.0, out.get("OrangePi/LeftPi/CPU_Pct"));
        assertEquals(2.0, out.get("OrangePi/RightPi/CPU_Pct"));
        assertEquals(55.0, out.get("OrangePi/Temp_C"));
        assertEquals(3, out.size());
    }

    @Test
    void arraysKeepTheirType() {
        var t = inst.getTable("OrangePi/X");
        t.getEntry("Doubles").setDoubleArray(new double[] {1.5, 2.5});
        t.getEntry("Ints").setIntegerArray(new long[] {3, 4});
        t.getEntry("Strings").setStringArray(new String[] {"a", "b"});
        t.getEntry("Bools").setBooleanArray(new boolean[] {true, false});

        Map<String, Object> out = mirrored();

        assertArrayEquals(new double[] {1.5, 2.5}, (double[]) out.get("OrangePi/X/Doubles"));
        assertArrayEquals(new long[] {3, 4}, (long[]) out.get("OrangePi/X/Ints"));
        assertArrayEquals(new String[] {"a", "b"}, (String[]) out.get("OrangePi/X/Strings"));
        assertArrayEquals(new boolean[] {true, false}, (boolean[]) out.get("OrangePi/X/Bools"));
    }

    @Test
    void anEmptyTableMirrorsNothingAndANewValueAppearsOnTheNextWalk() {
        assertTrue(mirrored().isEmpty());
        inst.getTable("OrangePi/LeftPi").getEntry("CPU_Pct").setDouble(9);
        assertEquals(9.0, mirrored().get("OrangePi/LeftPi/CPU_Pct"));
    }

    @Test
    void valuesThatCannotBeLoggedAreSkipped() {
        assertNull(CoprocessorHealthLogger.toLoggable(null));
        assertNull(CoprocessorHealthLogger.toLoggable(NetworkTableValue.makeRaw(new byte[] {1})));
        assertFalse(CoprocessorHealthLogger.toLoggable(NetworkTableValue.makeBoolean(true)) == null);
    }

    @Test
    void batchedMirrorBoundsEachLoopAndEventuallyVisitsEveryTopic() {
        for (int i = 0; i < 23; i++) inst.getEntry("/OrangePi/Test/value" + i).setDouble(i);
        var mirror = new CoprocessorHealthLogger.BatchedMirror();
        Map<String, Object> all = new HashMap<>();
        for (int loop = 0; loop < 3; loop++) {
            Map<String, Object> batch = new HashMap<>();
            mirror.update(inst, "OrangePi", batch::put, loop * 0.02, 8);
            assertTrue(batch.size() <= 8);
            all.putAll(batch);
        }
        assertEquals(23, all.size());
        Map<String, Object> unchanged = new HashMap<>();
        mirror.update(inst, "OrangePi", unchanged::put, 0.1, 23);
        assertTrue(unchanged.isEmpty(), "unchanged topics must not be logged again");
    }

    @Test
    void batchedMirrorDiscoversLateTopicsAndMirrorsChangedValues() {
        var mirror = new CoprocessorHealthLogger.BatchedMirror();
        Map<String, Object> out = new HashMap<>();
        mirror.update(inst, "OrangePi", out::put, 0, 8);
        inst.getEntry("/OrangePi/Late/State").setString("idle");
        inst.getEntry("/NotOrangePi/State").setString("ignored");
        mirror.update(inst, "OrangePi", out::put, 4.9, 8);
        assertTrue(out.isEmpty());
        mirror.update(inst, "OrangePi", out::put, 5, 8);
        assertEquals(Map.of("OrangePi/Late/State", "idle"), out);
        inst.getEntry("/OrangePi/Late/State").setString("recording");
        mirror.update(inst, "OrangePi", out::put, 5.02, 8);
        assertEquals("recording", out.get("OrangePi/Late/State"));
    }
}
