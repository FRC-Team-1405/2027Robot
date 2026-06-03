package frc.robot.commands;

import java.util.function.DoubleSupplier;

import edu.wpi.first.wpilibj.Timer;
import edu.wpi.first.wpilibj2.command.Command;

public class DynamicWaitCommand extends Command {

    private final DoubleSupplier durationSupplier;
    private double endTime;

    public DynamicWaitCommand(DoubleSupplier durationSupplier) {
        this.durationSupplier = durationSupplier;
    }

    @Override
    public void initialize() {
        double duration = durationSupplier.getAsDouble();
        endTime = Timer.getFPGATimestamp() + duration;
    }

    @Override
    public boolean isFinished() {
        return Timer.getFPGATimestamp() >= endTime;
    }
}
