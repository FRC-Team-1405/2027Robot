package frc.robot.subsystems;

import java.util.function.DoubleSupplier;

import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.Commands;
import edu.wpi.first.wpilibj2.command.SubsystemBase;
import frc.robot.Constants;
import frc.robot.Constants.HoodPreferences.HoodAngles;
import frc.robot.commands.SetHoodPosition;
import org.littletonrobotics.junction.AutoLogOutput;
import org.littletonrobotics.junction.Logger;

public class AdjustableHood extends SubsystemBase {
    private final HoodIO io;
    private final HoodIOInputsAutoLogged inputs = new HoodIOInputsAutoLogged();

    private HoodAngles currentHoodPosition = HoodAngles.ZERO;

    @AutoLogOutput(key = "Hood/CurrentPosition")
    public String getCurrentPositionName() {
        return currentHoodPosition.name();
    }

    public AdjustableHood(HoodIO io) {
        this.io = io;
        double pos = 0.0;
        SmartDashboard.putNumber("Hood/pos", pos);
        Command cmd = this.runSet(() -> SmartDashboard.getNumber("Hood/pos", pos))
                .withName("SetPosition")
                .ignoringDisable(true);
        SmartDashboard.putData("Hood/setPos", cmd);
    }

    @Override
    public void periodic() {
        io.updateInputs(inputs);
        Logger.processInputs("Hood", inputs);
    }

    public void setServo(DoubleSupplier position) {
        double pos = position.getAsDouble();
        io.setPosition(pos);
    }

    public void stopServo() {
        io.disable();
    }

    @AutoLogOutput(key = "Hood/Target")
    public double getTarget() {
        return inputs.targetPosition;
    }

    public Command runSet(DoubleSupplier position) {
        return runOnce(() -> setServo(position))
                .andThen(Commands.waitSeconds(
                        position.getAsDouble() * Constants.HoodPreferences.SERVO_FULL_RANGE_SECONDS));
    }

    public Command rotateHoodPosition() {
        switch (currentHoodPosition) {
            case ZERO:
                return new SetHoodPosition(this, HoodAngles.SHORT);
            case SHORT:
                return new SetHoodPosition(this, HoodAngles.MEDIUM);
            case MEDIUM:
                return new SetHoodPosition(this, HoodAngles.LONG);
            case LONG:
                return new SetHoodPosition(this, HoodAngles.SHORT);
            default:
                return Commands.none();
        }
    }
}
