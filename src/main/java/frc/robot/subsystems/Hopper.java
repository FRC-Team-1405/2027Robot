package frc.robot.subsystems;

import edu.wpi.first.units.measure.AngularVelocity;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.SubsystemBase;
import frc.robot.Constants;
import org.littletonrobotics.junction.AutoLogOutput;
import org.littletonrobotics.junction.Logger;

public class Hopper extends SubsystemBase {
    private final HopperIO io;
    private final HopperIOInputsAutoLogged inputs = new HopperIOInputsAutoLogged();

    @AutoLogOutput(key = "Hopper/Active")
    private boolean isHopperActive = false;

    public Hopper(HopperIO io) {
        this.io = io;
    }

    @Override
    public void periodic() {
        io.updateInputs(inputs);
        Logger.processInputs("Hopper", inputs);
    }

    // ── Motor Actions ────────────────────────────────────────────────────────

    private void forwardHopper() {
        isHopperActive = true;
        io.setVelocity(Constants.HopperPreferences.HOPPER_FORWARD_SPEED.baseUnitMagnitude());
    }

    private void reverseHopper() {
        isHopperActive = true;
        io.setVelocity(Constants.HopperPreferences.HOPPER_REVERSE_SPEED.baseUnitMagnitude());
    }

    private void stopHopper() {
        isHopperActive = false;
        io.stop();
    }

    public void setSpeed(AngularVelocity velocity) {
        isHopperActive = true;
        io.setVelocity(velocity.baseUnitMagnitude());
    }

    /** Start feeding balls forward. For use by external commands. */
    public void startFeeding() {
        forwardHopper();
    }

    /** Stop feeding balls. For use by external commands. */
    public void stopFeeding() {
        stopHopper();
    }

    @AutoLogOutput(key = "Hopper/VelocityRPS")
    public double getVelocityRPS() {
        return inputs.velocityRPS;
    }

    // ── Public Commands ──────────────────────────────────────────────────────

    public Command runForwardHopper() {
        return runOnce(() -> forwardHopper()).withName("Run Forward Hopper");
    }

    public Command runReverseHopper() {
        return startEnd(() -> reverseHopper(), () -> stopHopper()).withName("Run Reverse Hopper");
    }

    public Command runStopHopper() {
        return runOnce(() -> stopHopper()).withName("Run Stop Hopper");
    }
}
