package frc.robot.subsystems;

import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.SubsystemBase;
import frc.robot.Constants.IntakePreferences;
import org.littletonrobotics.junction.AutoLogOutput;
import org.littletonrobotics.junction.Logger;

public class Pickup extends SubsystemBase {
    private final PickupIO io;
    private final PickupIOInputsAutoLogged inputs = new PickupIOInputsAutoLogged();

    @AutoLogOutput(key = "Pickup/Active")
    private boolean isPickupActive = false;

    public Pickup(PickupIO io) {
        this.io = io;
    }

    @Override
    public void periodic() {
        io.updateInputs(inputs);
        Logger.processInputs("Pickup", inputs);
    }

    // ── State Queries ────────────────────────────────────────────────────────

    public boolean isPickupRunning() {
        return isPickupActive;
    }

    @AutoLogOutput(key = "Pickup/VelocityRPS")
    public double getVelocityRPS() {
        return inputs.velocityRPS;
    }

    public double getPidError() {
        return inputs.closedLoopError;
    }

    // ── Low-Level Motor Actions ──────────────────────────────────────────────

    private void pickupRollIn() {
        io.setVelocity(IntakePreferences.PICKUP_MOTOR_IN);
        isPickupActive = true;
    }

    private void pickupRollOut() {
        io.setVelocity(IntakePreferences.PICKUP_MOTOR_OUT);
        isPickupActive = true;
    }

    private void stopPickupMotor() {
        io.stop();
        isPickupActive = false;
    }

    // ── Public Commands ──────────────────────────────────────────────────────

    public Command runPickupIn() {
        return run(() -> pickupRollIn())
                .finallyDo(() -> stopPickupMotor())
                .withName("Run Pickup In");
    }

    public Command runPickupOut() {
        return runOnce(() -> pickupRollOut())
                .withName("Run Pickup Out");
    }

    public Command runPickupStop() {
        return runOnce(() -> stopPickupMotor())
                .withName("Run Pickup Stop");
    }

    public Command runPickupOut(String name) {
        Command cmd = runPickupOut().withName(name);
        SmartDashboard.putData(cmd);
        return cmd;
    }

    public Command runPickupIn(String name) {
        Command cmd = runPickupIn().withName(name);
        SmartDashboard.putData(cmd);
        return cmd;
    }

    public Command runPickupStop(String name) {
        Command cmd = runPickupStop().withName(name);
        SmartDashboard.putData(cmd);
        return cmd;
    }

    public void publishMotorCurrents() {
        SmartDashboard.putNumber("Pickup/StatorCurrent", inputs.statorCurrentAmps);
        SmartDashboard.putNumber("Pickup/SupplyCurrent", inputs.supplyCurrentAmps);
    }
}
