package frc.robot.subsystems;

import java.util.function.Supplier;

import edu.wpi.first.units.measure.AngularVelocity;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.SubsystemBase;
import frc.robot.Constants;
import org.littletonrobotics.junction.AutoLogOutput;
import org.littletonrobotics.junction.Logger;

public class Indexer extends SubsystemBase {
    private final IndexerIO io;
    private final IndexerIOInputsAutoLogged inputs = new IndexerIOInputsAutoLogged();

    @AutoLogOutput(key = "Indexer/Active")
    private boolean isIndexerActive = false;

    public Indexer(IndexerIO io) {
        this.io = io;
    }

    @Override
    public void periodic() {
        io.updateInputs(inputs);
        Logger.processInputs("Indexer", inputs);
    }

    // ── Motor Actions ────────────────────────────────────────────────────────

    private void setIndexerSpeed(Supplier<AngularVelocity> speed) {
        isIndexerActive = true;
        io.setVelocity(speed.get().baseUnitMagnitude());
    }

    private void setIndexerSpeed() {
        isIndexerActive = true;
        io.setVelocity(Constants.ShooterPreferences.INDEXER_VELOCITY.baseUnitMagnitude());
    }

    private void indexerStop() {
        isIndexerActive = false;
        io.stop();
    }

    /** Start feeding balls at the given speed. For use by external commands. */
    public void startFeeding(Supplier<AngularVelocity> speed) {
        setIndexerSpeed(speed);
    }

    /** Stop feeding balls. For use by external commands. */
    public void stopFeeding() {
        indexerStop();
    }

    @AutoLogOutput(key = "Indexer/VelocityRPS")
    public double getVelocityRPS() {
        return inputs.velocityRPS;
    }

    // ── Public Commands ──────────────────────────────────────────────────────

    public Command runIndexer(Supplier<AngularVelocity> speed) {
        return runOnce(() -> setIndexerSpeed(speed)).withName("Run Indexer");
    }

    public Command runIndexer() {
        return runOnce(() -> setIndexerSpeed()).withName("Run Indexer Default");
    }

    public Command runStopIndexer() {
        return runOnce(this::indexerStop).withName("Stop Indexer");
    }

    // ── State Queries ────────────────────────────────────────────────────────

    public boolean isIndexerRunning() {
        return isIndexerActive;
    }

    /** Returns rotor position in rotations. */
    public double getRotations() {
        return inputs.rotorPositionRots;
    }
}
