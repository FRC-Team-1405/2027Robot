// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot.subsystems;

import java.util.function.Supplier;

import com.ctre.phoenix6.StatusCode;
import com.ctre.phoenix6.StatusSignal;
import com.ctre.phoenix6.configs.TalonFXConfiguration;
import com.ctre.phoenix6.controls.MotionMagicVelocityVoltage;
import com.ctre.phoenix6.controls.NeutralOut;
import com.ctre.phoenix6.hardware.TalonFX;
import com.ctre.phoenix6.signals.InvertedValue;

import edu.wpi.first.units.measure.Angle;
import edu.wpi.first.units.measure.AngularVelocity;
import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.SubsystemBase;
import frc.robot.Constants;
import frc.robot.Constants.CANBus;
import frc.robot.constants.FeatureSwitches;
import frc.robot.lib.FinneyLogger;
import frc.robot.sim.sjc.MotorSim_Mech_SJC;
import frc.robot.sim.sjc.PhysicsSim_SJC;

public class Indexer extends SubsystemBase {
    private final FinneyLogger fLogger = new FinneyLogger(this.getClass().getSimpleName());

    private final TalonFX indexerMotor = new TalonFX(CANBus.INDEXER_MOTOR);

    private final MotorSim_Mech_SJC indexer_motorSimMech = new MotorSim_Mech_SJC("Indexer/Mech");

    private final MotionMagicVelocityVoltage velocityVoltage = new MotionMagicVelocityVoltage(0);
    private final NeutralOut m_Brake = new NeutralOut();

    private boolean isIndexerActive = false;

    public Indexer() {
        setupMotors();
        simulationInit();
    }

    // ── Motor Configuration ──────────────────────────────────────────────────

    private void setupMotors() {
        TalonFXConfiguration configs = new TalonFXConfiguration();

        configs.Slot0.kS = Constants.IndexerPreferences.KS;
        configs.Slot0.kV = Constants.IndexerPreferences.KV;
        configs.Slot0.kP = Constants.IndexerPreferences.KP;
        configs.Slot0.kI = Constants.IndexerPreferences.KI;
        configs.Slot0.kD = Constants.IndexerPreferences.KD;

        configs.Voltage.PeakForwardVoltage = Constants.IndexerPreferences.PEAK_FORWARD_VOLTAGE;
        configs.Voltage.PeakReverseVoltage = Constants.IndexerPreferences.PEAK_REVERSE_VOLTAGE;

        configs.MotionMagic.MotionMagicCruiseVelocity = Constants.IndexerPreferences.CRUISE_VELOCITY;
        configs.MotionMagic.MotionMagicAcceleration = Constants.IndexerPreferences.ACCELERATION;

        // configs.CurrentLimits.StatorCurrentLimit =
        // Constants.IndexerPreferences.STATOR_CURRENT_LIMIT;
        // configs.CurrentLimits.SupplyCurrentLimit =
        // Constants.IndexerPreferences.SUPPLY_CURRENT_LIMIT;

        configs.MotorOutput.Inverted = InvertedValue.Clockwise_Positive;

        StatusCode status = StatusCode.StatusCodeNotInitialized;
        for (int i = 0; i < 5; ++i) {
            status = indexerMotor.getConfigurator().apply(configs);
            if (status.isOK())
                break;
        }
        if (!status.isOK()) {
            System.out.println("Could not configure indexer motor. Error: " + status.toString());
        }
        fLogger.log("Indexer motor configured");
    }

    public double getRotations() {
        indexer_motorSimMech.update(indexerMotor.getPosition(), indexerMotor.getVelocity());

        StatusSignal<Angle> statusSignalRotation = indexerMotor.getRotorPosition();
        statusSignalRotation.getValueAsDouble();

        double rotations = statusSignalRotation.getValueAsDouble();

        return rotations;
    }

    // ── Periodic ─────────────────────────────────────────────────────────────

    @Override
    public void periodic() {
        if (FeatureSwitches.ENABLE_SUBSYSTEM_NT_LOGGING) {
            SmartDashboard.putNumber("Indexer/StatorCurrent", indexerMotor.getStatorCurrent().getValueAsDouble());
            SmartDashboard.putNumber("Indexer/Velocity", indexerMotor.getVelocity().getValueAsDouble());
            SmartDashboard.putNumber("Indexer/PIDError", indexerMotor.getClosedLoopError().getValueAsDouble());
            SmartDashboard.putBoolean("Indexer/IsActive", isIndexerActive);
        }
    }

    // ── Simulation ───────────────────────────────────────────────────────────

    public void simulationInit() {
        // Indexer roller: low inertia, light load, direct drive
        PhysicsSim_SJC.getInstance().addTalonFX(indexerMotor,
                /* rotorInertia= */0.001, /* loadMassKg= */0.05, /* armMeters= */0.05,
                /* viscousCoeff= */0.01, /* numberOfMotors= */1, /* gearRatio= */1.0);
    }

    @Override
    public void simulationPeriodic() {
        PhysicsSim_SJC.getInstance().run();
    }

    // ── Motor Actions ────────────────────────────────────────────────────────

    private void setIndexerSpeed(Supplier<AngularVelocity> speed) {
        isIndexerActive = true;
        indexerMotor.setControl(velocityVoltage.withVelocity(speed.get()));
        fLogger.log("Indexer speed set to %s", speed.get());
    }

    private void setIndexerSpeed() {
        isIndexerActive = true;
        indexerMotor.setControl(velocityVoltage.withVelocity(Constants.ShooterPreferences.INDEXER_VELOCITY));
        fLogger.log("Indexer speed set to default");
    }

    private void indexerStop() {
        isIndexerActive = false;
        indexerMotor.setControl(m_Brake);
        fLogger.log("Indexer stopped");
    }

    /** Start feeding balls at the given speed. For use by external commands. */
    public void startFeeding(Supplier<AngularVelocity> speed) {
        setIndexerSpeed(speed);
    }

    /** Stop feeding balls. For use by external commands. */
    public void stopFeeding() {
        indexerStop();
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
}
