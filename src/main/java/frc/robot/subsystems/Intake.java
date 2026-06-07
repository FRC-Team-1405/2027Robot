package frc.robot.subsystems;

import edu.wpi.first.wpilibj.RobotBase;
import edu.wpi.first.wpilibj.GenericHID.RumbleType;
import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.CommandScheduler;
import edu.wpi.first.wpilibj2.command.Commands;
import edu.wpi.first.wpilibj2.command.SubsystemBase;
import edu.wpi.first.wpilibj2.command.button.CommandXboxController;
import frc.robot.Constants.IntakePreferences;
import frc.robot.commands.RumbleJoystick;
import frc.robot.constants.FeatureSwitches;
import org.littletonrobotics.junction.AutoLogOutput;
import org.littletonrobotics.junction.Logger;

public class Intake extends SubsystemBase {
    private final IntakeIO io;
    private final IntakeIOInputsAutoLogged inputs = new IntakeIOInputsAutoLogged();

    private int settleCount = 0;
    private int stallCount = 0;

    @AutoLogOutput(key = "Intake/PositionTarget")
    private double intakePositionTarget = 0;

    @AutoLogOutput(key = "Intake/IsDeployed")
    private boolean isIntakeDeployed = false;

    private boolean isIntakeMovementDisabled = false;

    public Intake(IntakeIO io) {
        this.io = io;
        SmartDashboard.putBoolean("Intake/IntakeMovementEnabled", !isIntakeMovementDisabled);
        SmartDashboard.putBoolean("Intake/Zero Intake Position", false);
    }

    @Override
    public void periodic() {
        io.updateInputs(inputs);
        Logger.processInputs("Intake", inputs);

        double positionError = Math.abs(inputs.deployPositionRots - intakePositionTarget);
        if (positionError < IntakePreferences.POSITION_TOLERANCE) {
            settleCount++;
        } else {
            settleCount = 0;
        }

        // Stall detection (real robot only)
        boolean motorCommanded = Math.abs(inputs.deployClosedLoopReference
                - inputs.deployPositionRots) > IntakePreferences.POSITION_TOLERANCE;
        if (RobotBase.isReal() && motorCommanded
                && Math.abs(inputs.deployVelocityRPS) < 0.5
                && inputs.deployStatorCurrentAmps > IntakePreferences.STALL_CURRENT_THRESHOLD) {
            stallCount++;
            if (stallCount >= IntakePreferences.STALL_CYCLES_THRESHOLD) {
                io.stopDeploy();
                intakePositionTarget = inputs.deployPositionRots;
                stallCount = 0;
            }
        } else {
            stallCount = 0;
        }

        checkForResetEncoder();
    }

    // ── State Queries ────────────────────────────────────────────────────────

    @AutoLogOutput(key = "Intake/AtTarget")
    private boolean isAtTarget() {
        if (FeatureSwitches.INTAKE_SAFTEY_MODE_NO_DEPLOY) return true;
        return settleCount >= IntakePreferences.SETTLE_COUNT;
    }

    public boolean isIntakeExtended() {
        return isIntakeDeployed;
    }

    // ── Low-Level Motor Actions ──────────────────────────────────────────────

    private void setIntakePosition(double position) {
        if (FeatureSwitches.INTAKE_SAFTEY_MODE_NO_DEPLOY) return;
        if (isIntakeMovementDisabled) return;

        io.setDeployPosition(position);
        intakePositionTarget = position;
        settleCount = 0;
        stallCount = 0;
    }

    // ── Intake Deploy Positions ──────────────────────────────────────────────

    private void deployOut() {
        isIntakeDeployed = true;
        setIntakePosition(IntakePreferences.INTAKE_MOTOR_OUT);
    }

    private void deployIn() {
        isIntakeDeployed = false;
        setIntakePosition(IntakePreferences.INTAKE_MOTOR_IN);
    }

    private void deployCenter() {
        isIntakeDeployed = true;
        setIntakePosition(IntakePreferences.INTAKE_MOTOR_CENTER);
    }

    // ── Public Commands ──────────────────────────────────────────────────────

    public Command runIntakeOut() {
        return Commands.sequence(
                runOnce(() -> deployOut()),
                Commands.waitUntil(this::isAtTarget))
                .withName("Run Intake Out");
    }

    public Command runIntakeIn() {
        return Commands.sequence(
                runOnce(() -> deployIn()),
                Commands.waitUntil(this::isAtTarget))
                .withName("Run Intake In");
    }

    public Command runIntakeCenter() {
        return Commands.sequence(
                runOnce(() -> deployCenter()),
                Commands.waitUntil(this::isAtTarget))
                .withName("Run Intake Center");
    }

    public void checkForResetEncoder() {
        boolean value = SmartDashboard.getBoolean("Intake/Zero Intake Position", false);
        if (value) {
            io.zeroDeployEncoder();
            SmartDashboard.putBoolean("Intake/Zero Intake Position", false);
        }
    }

    public void toggleIntakeMovementDisabledFlag(CommandXboxController joystick) {
        isIntakeMovementDisabled = !isIntakeMovementDisabled;
        SmartDashboard.putBoolean("Intake/IntakeMovementEnabled", !isIntakeMovementDisabled);
        if (isIntakeMovementDisabled) {
            CommandScheduler.getInstance().schedule(new RumbleJoystick(joystick, RumbleType.kBothRumble, 0.3, 0.5));
        } else {
            CommandScheduler.getInstance().schedule(RumbleJoystick.leftRightLeftRight(joystick));
        }
    }

    public void publishMotorCurrents() {
        SmartDashboard.putNumber("Intake/IntakeCurrent", inputs.deployStatorCurrentAmps);
        SmartDashboard.putNumber("Intake/PickupCurrent", inputs.pickupStatorCurrentAmps);
    }
}
