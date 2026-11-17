package frc.robot.constants;

import org.littletonrobotics.junction.networktables.LoggedNetworkBoolean;

/**
 * Switches that can be flipped <b>while the robot code is running</b>, so an experiment can turn a change on and
 * off without a redeploy: the experiment runner ({@code python -m exprunner}, tools/exprunner) sets them from the
 * laptop, reads them back, and records the state with each run.
 *
 * <p>These are for changes <i>under validation</i>. A settled behavior belongs in {@link FeatureSwitches} as a
 * compile-time constant (the compiler removes the dead branch). A switch lives here only until its effect has been
 * measured; then delete it (and keep or drop the code behind it), and drop it from TODO.md.
 *
 * <p>How it works: each switch is an AdvantageKit {@link LoggedNetworkBoolean} at
 * {@code /Tuning/ExperimentSwitches/<NAME>}. The value is a NetworkTables entry the runner can write; AdvantageKit
 * records it in the log every loop ({@code NetworkInputs/Tuning/ExperimentSwitches/<NAME>}), so a log always says
 * which way a switch was while it ran, and replay uses the logged value. The value resets to {@code defaultValue}
 * whenever the robot code starts; the runner puts back what it found when the session ends.
 *
 * <p>To add one: add a field here with its default (the value to compete with, usually {@code false}), read it with
 * {@code .get()} where the change takes effect (cheap, but not in a hot inner loop: read it once per loop), mark
 * it VALIDATE-THEN-REMOVE in its comment, and give it a runs.toml in docs/experiments/ that toggles it.
 */
public final class ExperimentSwitches {
    private ExperimentSwitches() {}

    /** One runtime-flippable boolean. */
    public static final class Switch {
        private final LoggedNetworkBoolean value;

        Switch(String name, boolean defaultValue) {
            this.value = new LoggedNetworkBoolean("/Tuning/ExperimentSwitches/" + name, defaultValue);
        }

        public boolean get() {
            return value.get();
        }
    }

    /** VALIDATE-THEN-REMOVE. Log which process and which of our own threads uses the roboRIO's CPU once a second
     *  (RIO/SelfCpuPct, RIO/TopProcesses, RIO/SelfTopThreads). Needs FeatureSwitches.RIO_SYSTEM_STATS_LOGGING.
     *  true  = logged. false = not logged.
     *  Default false until its own cost is measured (slow-loop share and RIO/CpuPct with it on vs off).
     *  Experiment: docs/experiments/roborio/loop-overruns/runs.toml. */
    public static final Switch RIO_PROCESS_CPU_LOGGING = new Switch("RIO_PROCESS_CPU_LOGGING", false);
}
