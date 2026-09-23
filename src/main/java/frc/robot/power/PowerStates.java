package frc.robot.power;

import java.util.LinkedHashMap;
import java.util.Map;
import org.littletonrobotics.junction.Logger;

/** Robot-defined policy context only; no actuator writes or automatic priorities. */
public final class PowerStates {
    private PowerStates() {}
    private static final Map<String, Map<String, Integer>> definitions = new LinkedHashMap<>();
    private static String active = "Unassigned";
    private static String reason = "No state selected";
    static { definitions.put("Unassigned", Map.of()); }

    public static void define(String name, Map<String, Integer> subsystemTiers) {
        if (name == null || name.isBlank() || name.contains("/") || name.equals("Unassigned"))
            throw new IllegalArgumentException("Use a nonempty state name without '/' (Unassigned is reserved)");
        subsystemTiers.forEach((subsystem, tier) -> {
            if (subsystem == null || subsystem.isBlank() || subsystem.contains("/") || tier == null || tier < 0)
                throw new IllegalArgumentException("Subsystem names must be nonempty; tiers must be nonnegative");
        });
        if (definitions.containsKey(name)) throw new IllegalArgumentException("State already defined: " + name);
        definitions.put(name, Map.copyOf(subsystemTiers));
    }

    public static void select(String name, String selectionReason) {
        if (!definitions.containsKey(name)) throw new IllegalArgumentException("Unknown power state: " + name);
        if (selectionReason == null) throw new IllegalArgumentException("State reason is required");
        active = name;
        reason = selectionReason;
    }

    public static String active() { return active; }
    public static Map<String, Integer> priorities() { return definitions.get(active); }

    public static void periodic() {
        Logger.recordOutput("Power/State/Active", active);
        Logger.recordOutput("Power/State/Reason", reason);
        definitions.forEach((name, tiers) -> tiers.forEach((subsystem, tier) ->
                Logger.recordOutput("Power/State/Definitions/" + name + "/" + subsystem, tier)));
    }

    /** Future allocator telemetry contract. A proposal never implies applied limits.
     * Call only when an allocator exists; missing records mean allocation is unknown.
     */
    public static void recordAllocation(String subsystem, String policyVersion, String mode,
            double requestedAmps, double grantedAmps, double proposedLimitAmps,
            double appliedLimitAmps, String applicationStatus, String allocationReason) {
        if (!java.util.Set.of("off", "shadow", "enforced").contains(mode))
            throw new IllegalArgumentException("Allocation mode must be off, shadow, or enforced");
        if (subsystem == null || subsystem.isBlank() || subsystem.contains("/"))
            throw new IllegalArgumentException("Invalid subsystem");
        String key = "Power/Allocation/" + subsystem + "/";
        Logger.recordOutput(key + "PolicyVersion", policyVersion);
        Logger.recordOutput(key + "Mode", mode);
        Logger.recordOutput(key + "RequestedAmps", requestedAmps);
        Logger.recordOutput(key + "GrantedAmps", grantedAmps);
        Logger.recordOutput(key + "ProposedLimitAmps", proposedLimitAmps);
        Logger.recordOutput(key + "AppliedLimitAmps", appliedLimitAmps);
        Logger.recordOutput(key + "ApplicationStatus", applicationStatus);
        Logger.recordOutput(key + "Reason", allocationReason);
    }
}
