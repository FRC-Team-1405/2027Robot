package frc.robot.util;

import java.lang.reflect.Modifier;
import java.util.TreeMap;
import frc.robot.constants.FeatureSwitches;

/** Startup-only provenance: record what was compiled/deployed, not what a laptop file now says. */
public final class PerformanceProfile {
    private PerformanceProfile() {}

    public static String describe() {
        var values = new TreeMap<String, String>();
        for (var field : FeatureSwitches.class.getFields()) {
            if (!Modifier.isStatic(field.getModifiers())) continue;
            try {
                values.put(field.getName(), String.valueOf(field.get(null)));
            } catch (IllegalAccessException e) {
                values.put(field.getName(), "unavailable");
            }
        }
        return values.toString();
    }
}
