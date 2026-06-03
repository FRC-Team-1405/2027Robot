package frc.robot.lib;

import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

import edu.wpi.first.wpilibj2.command.Command;

public class CommandTracker {

    private static final Set<Command> running = new HashSet<>();

    private CommandTracker() {
    }

    public static void onStart(Command cmd) {
        running.add(cmd);
    }

    public static void onEnd(Command cmd, boolean interrupted) {
        running.remove(cmd);
    }

    public static Set<Command> getRunning() {
        return Collections.unmodifiableSet(running);
    }
}