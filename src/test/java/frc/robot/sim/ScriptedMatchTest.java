package frc.robot.sim;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;

import org.junit.jupiter.api.Test;

class ScriptedMatchTest {
    @Test
    void defaultScriptIsAFullMatchWithPreMatchAndTail() {
        List<ScriptedMatch.Phase> phases = ScriptedMatch.parseScript("default");
        assertEquals(List.of("disabled", "auto", "disabled", "teleop", "disabled"),
                phases.stream().map(ScriptedMatch.Phase::mode).toList());
        assertEquals(140.0, phases.get(3).seconds());
    }

    @Test
    void blankMeansDefault() {
        assertEquals(ScriptedMatch.parseScript("default"), ScriptedMatch.parseScript(" "));
    }

    @Test
    void parsesCustomScriptsIgnoringCaseAndSpaces() {
        List<ScriptedMatch.Phase> phases = ScriptedMatch.parseScript("Disabled: 2.5, AUTO:10 ,teleop:30");
        assertEquals(new ScriptedMatch.Phase("disabled", 2.5), phases.get(0));
        assertEquals(new ScriptedMatch.Phase("auto", 10.0), phases.get(1));
        assertEquals(new ScriptedMatch.Phase("teleop", 30.0), phases.get(2));
    }

    @Test
    void rejectsMalformedScripts() {
        assertThrows(IllegalArgumentException.class, () -> ScriptedMatch.parseScript("auto"));
        assertThrows(IllegalArgumentException.class, () -> ScriptedMatch.parseScript("test:10"));
        assertThrows(IllegalArgumentException.class, () -> ScriptedMatch.parseScript("auto:0"));
        assertThrows(IllegalArgumentException.class, () -> ScriptedMatch.parseScript("auto:-3"));
    }
}
