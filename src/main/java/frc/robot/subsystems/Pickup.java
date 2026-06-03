package frc.robot.subsystems;

import com.ctre.phoenix6.StatusCode;
import com.ctre.phoenix6.configs.TalonFXConfiguration;
import com.ctre.phoenix6.controls.MotionMagicVelocityVoltage;
import com.ctre.phoenix6.controls.NeutralOut;
import com.ctre.phoenix6.hardware.TalonFX;
import com.ctre.phoenix6.signals.NeutralModeValue;

import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.SubsystemBase;
import frc.robot.Constants;
import frc.robot.Constants.IntakePreferences;
import frc.robot.constants.FeatureSwitches;
import frc.robot.lib.FinneyLogger;
import frc.robot.sim.sjc.PhysicsSim_SJC;

public class Pickup extends SubsystemBase {
    private final FinneyLogger fLogger = new FinneyLogger(this.getClass().getSimpleName());

    private final TalonFX pickupMotor = new TalonFX(Constants.CANBus.PICKUP_MOTOR);

    private final MotionMagicVelocityVoltage pickupVelocityRequest = new MotionMagicVelocityVoltage(0);

    private boolean isPickupActive = false;

    private final NeutralOut neutralRequest = new NeutralOut();

    public Pickup() {
        setupMotors();
        simulationInit();
    }

    /** Run the pickup rollers inward (intaking game pieces). */
    // public Command runPickupIn() {
    // return startEnd(() -> pickupRollIn(), () -> stopPickupMotor())
    // .withName("Run Pickup In");
    // }

    // ── Motor Configuration ──────────────────────────────────────────────────

    private void setupMotors() {
        setupPickupMotor();
    }

    private void setupPickupMotor() {
        TalonFXConfiguration config = new TalonFXConfiguration();

        config.Slot0.kP = IntakePreferences.PICKUP_KP;
        config.Slot0.kI = IntakePreferences.PICKUP_KI;
        config.Slot0.kD = IntakePreferences.PICKUP_KD;
        config.Slot0.kS = IntakePreferences.PICKUP_KS;
        config.Slot0.kV = IntakePreferences.PICKUP_KV;

        config.MotionMagic.MotionMagicAcceleration = IntakePreferences.PICKUP_ACCELERATION;
        config.MotionMagic.MotionMagicJerk = IntakePreferences.PICKUP_JERK;

        config.Voltage.PeakForwardVoltage = IntakePreferences.PEAK_FORWARD_VOLTAGE;
        config.Voltage.PeakReverseVoltage = IntakePreferences.PEAK_REVERSE_VOLTAGE;

        config.CurrentLimits.StatorCurrentLimitEnable = true;
        config.CurrentLimits.StatorCurrentLimit = IntakePreferences.PICKUP_STATOR_LIMIT;
        config.CurrentLimits.SupplyCurrentLimitEnable = true;
        config.CurrentLimits.SupplyCurrentLimit = IntakePreferences.PICKUP_SUPPLY_LIMIT;

        config.MotorOutput.NeutralMode = NeutralModeValue.Coast;

        StatusCode status = StatusCode.StatusCodeNotInitialized;
        for (int i = 0; i < 5; ++i) {
            status = pickupMotor.getConfigurator().apply(config);
            if (status.isOK())
                break;
        }
        if (!status.isOK()) {
            System.out.println("Could not configure pickup motor. Error: " + status.toString());
        }
        fLogger.log("Pickup motor configured (roller)");
    }

    // ── Simulation ───────────────────────────────────────────────────────────

    public void simulationInit() {
        // Pickup roller: small inertia, light load, direct drive
        PhysicsSim_SJC.getInstance().addTalonFX(pickupMotor,
                /* rotorInertia= */0.0002, /* loadMassKg= */0.5, /* armMeters= */0.05,
                /* viscousCoeff= */0.01, /* numberOfMotors= */1, /* gearRatio= */0.5);
    }

    // old pickup motor gear ratio = 0.5
    // new pickup motor gear ratio = 0.3333333
    @Override
    public void simulationPeriodic() {
        PhysicsSim_SJC.getInstance().run();
    }

    // ── State Queries ────────────────────────────────────────────────────────

    public boolean isPickupRunning() {
        return isPickupActive;
    }

    // ── Low-Level Motor Actions ──────────────────────────────────────────────

    private void setPickupVelocity(double velocity) {
        pickupMotor.setControl(pickupVelocityRequest.withVelocity(velocity));
        isPickupActive = true;
    }

    private void stopPickupMotor() {
        pickupMotor.setControl(neutralRequest);
        isPickupActive = false;
    }

    // ── Pickup Roller Speeds ─────────────────────────────────────────────────

    private void pickupRollIn() {
        setPickupVelocity(IntakePreferences.PICKUP_MOTOR_IN);
        fLogger.log("Pickup IN (%.1f rps)", IntakePreferences.PICKUP_MOTOR_IN);
    }

    private void pickupRollOut() {
        setPickupVelocity(IntakePreferences.PICKUP_MOTOR_OUT);
        fLogger.log("Pickup OUT (%.1f rps)", IntakePreferences.PICKUP_MOTOR_OUT);
    }

    // ── Public Commands ──────────────────────────────────────────────────────

    public Command runPickupIn() {
        return run(() -> pickupRollIn())
                .finallyDo(() -> stopPickupMotor())
                .withName("Run Pickup In");
    }

    /** Run the pickup rollers outward (ejecting game pieces). */
    public Command runPickupOut() {
        return runOnce(() -> pickupRollOut())
                .withName("Run Pickup Out");
    }

    /** Stop the pickup rollers. */
    public Command runPickupStop() {
        return runOnce(() -> stopPickupMotor())
                .withName("Run Pickup Stop");
    }

    // Named/SmartDashboard-publishing overloads
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

    // ── Telemetry ────────────────────────────────────────────────────────────

    private void publishTelemetry() {
        if (FeatureSwitches.ENABLE_SUBSYSTEM_NT_LOGGING) {
            SmartDashboard.putNumber("Intake/PickupStatorCurrent", pickupMotor.getStatorCurrent().getValueAsDouble());
            SmartDashboard.putNumber("Intake/PickupSupplyCurrent", pickupMotor.getSupplyCurrent().getValueAsDouble());
            SmartDashboard.putNumber("Intake/PickupVelocity", pickupMotor.getVelocity().getValueAsDouble());
            SmartDashboard.putNumber("Intake/PickupError", pickupMotor.getClosedLoopError().getValueAsDouble());
            SmartDashboard.putBoolean("Intake/IsPickupActive", isPickupActive);
        }
    }

    public void publishMotorCurrents() {
        SmartDashboard.putNumber("Intake/PickupCurrent", pickupMotor.getStatorCurrent().getValueAsDouble());
    }

    public double getPidError() {
        return pickupMotor.getClosedLoopError().getValueAsDouble();
    }
}
