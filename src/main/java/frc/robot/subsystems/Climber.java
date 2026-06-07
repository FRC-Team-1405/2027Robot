package frc.robot.subsystems;

import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.Commands;
import edu.wpi.first.wpilibj2.command.SubsystemBase;
import frc.robot.Constants;
import org.littletonrobotics.junction.AutoLogOutput;
import org.littletonrobotics.junction.Logger;

public class Climber extends SubsystemBase {
    private final ClimberIO io;
    private final ClimberIOInputsAutoLogged inputs = new ClimberIOInputsAutoLogged();

    @AutoLogOutput(key = "Climber/ArmPositionTarget")
    private double climberPositionTarget = 0;

    @AutoLogOutput(key = "Climber/GrabberPositionTarget")
    private double grabberPositionTarget = 0;

    private int climberSettleCount = 0;
    private int grabberSettleCount = 0;

    public Climber(ClimberIO io) {
        this.io = io;
    }

    @Override
    public void periodic() {
        io.updateInputs(inputs);
        Logger.processInputs("Climber", inputs);

        // Climber settle tracking
        if (Math.abs(climberPositionTarget - inputs.climberClosedLoopReference)
                < Constants.ClimberPreferences.POSITION_TOLERANCE
                && Math.abs(inputs.climberClosedLoopError) < Constants.ClimberPreferences.POSITION_TOLERANCE) {
            climberSettleCount++;
        } else {
            climberSettleCount = 0;
        }

        // Grabber settle tracking
        if (Math.abs(grabberPositionTarget - inputs.grabberClosedLoopReference)
                < Constants.ClimberPreferences.POSITION_TOLERANCE
                && Math.abs(inputs.grabberClosedLoopError) < Constants.ClimberPreferences.POSITION_TOLERANCE) {
            grabberSettleCount++;
        } else {
            grabberSettleCount = 0;
        }
    }

    @AutoLogOutput(key = "Climber/ArmAtTarget")
    private boolean isClimberAtTarget() {
        return climberSettleCount >= Constants.ClimberPreferences.SETTLE_MAX;
    }

    @AutoLogOutput(key = "Climber/GrabberAtTarget")
    private boolean isGrabberAtTarget() {
        return grabberSettleCount >= Constants.ClimberPreferences.SETTLE_MAX;
    }

    public void move(double position) {
        io.setClimberPosition(position);
        climberPositionTarget = position;
    }

    public void moveGrabber(double position) {
        io.setGrabberPosition(position);
        grabberPositionTarget = position;
    }

    private void climbUp() {
        move(Constants.ClimberPreferences.CLIMBER_EXTEND_POSITION);
    }

    private void climbDown() {
        move(Constants.ClimberPreferences.CLIMBER_RETRACT_POSITION);
    }

    private void stop() {
        io.stopClimber();
    }

    public Command runClimbUp() {
        return runOnce(() -> climbUp())
                .andThen(Commands.waitUntil(() -> isClimberAtTarget()))
                .withName("Climb Up");
    }

    public Command runClimbDown() {
        return runOnce(() -> climbDown())
                .andThen(Commands.waitUntil(() -> isClimberAtTarget()))
                .withName("Climb Down");
    }

    public Command runStop() {
        return runOnce(() -> stop())
                .andThen(Commands.waitUntil(() -> isClimberAtTarget()))
                .withName("Climb Stop");
    }

    private void openClaw() {
        moveGrabber(Constants.ClimberPreferences.GRABBER_OPEN_POSITION);
    }

    private void closeClaw() {
        moveGrabber(Constants.ClimberPreferences.GRABBER_CLOSED_POSITION);
    }

    private void stopClaw() {
        io.stopGrabber();
    }

    public Command runOpenClaw() {
        return runOnce(() -> openClaw())
                .andThen(Commands.waitUntil(() -> isGrabberAtTarget()))
                .withName("Open Claw");
    }

    public Command runCloseClaw() {
        return runOnce(() -> closeClaw())
                .andThen(Commands.waitUntil(() -> isGrabberAtTarget()))
                .withName("Close Claw");
    }

    public Command runStopClaw() {
        return runOnce(() -> stopClaw())
                .andThen(Commands.waitUntil(() -> isClimberAtTarget()))
                .withName("Stop Claw");
    }

    public Command runExtendClimber() {
        return runClimbUp().andThen(runOpenClaw()).withName("Extend Climber");
    }

    public Command runRetractClimber() {
        return runCloseClaw().andThen(runClimbDown()).withName("Retract Climber");
    }
}
