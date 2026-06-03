package frc.robot.lib;

import java.util.HashSet;
import java.util.Set;

import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.Subsystem;

public abstract class FinneyCommand extends Command {
    private final Set<Subsystem> requirements = new HashSet<>();

    // @Override
    // public Set<Subsystem> getRequirements() {
    //     return requirements;
    // }

    @Override
    public void initialize() {
        CommandTracker.onStart(this);
        SmartDashboard.putBoolean("Commands/" + getName(), true);

    }

    @Override
    public void end(boolean interrupted) {
        CommandTracker.onEnd(this, interrupted);
        SmartDashboard.putBoolean("Commands/" + getName(), false);
    }
}
