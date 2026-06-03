package frc.robot.subsystems;

import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.CommandScheduler;
import edu.wpi.first.wpilibj2.command.Commands;
import edu.wpi.first.wpilibj2.command.InstantCommand;
import edu.wpi.first.wpilibj2.command.button.CommandXboxController;
import edu.wpi.first.wpilibj2.command.button.Trigger;
import frc.robot.Constants.ShooterPreferences;
import frc.robot.commands.Shooter.AutoFire;
import frc.robot.constants.FieldConstants;

public class ShootMode {
    private SwerveFeatures swerveFeatures;
    private CommandSwerveDrivetrain drivetrain;
    private Intake intake;
    private Indexer indexer;
    private Shooter shooter;
    private CommandXboxController joystick;

    private Mode activeMode = Mode.MEDIUM;
    private Command dynamicShootCommand;

    public ShootMode(CommandSwerveDrivetrain drivetrain, SwerveFeatures swerveFeatures, Intake intake, Indexer indexer,
            Shooter shooter,
            CommandXboxController joystick) {
        this.shooter = shooter;
        this.joystick = joystick;
        this.intake = intake;
        this.indexer = indexer;
        this.drivetrain = drivetrain;
        this.swerveFeatures = swerveFeatures;

        dynamicShootCommand = AutoFire.DynamicTeleop(shooter, indexer,
                () -> ShooterPreferences.INDEXER_VELOCITY, intake, () -> swerveFeatures
                        .getDistanceToHub(drivetrain,
                                FieldConstants.ALLIANCE_HUB_POSITION),
                joystick.rightBumper());
    }

    public enum Mode {
        SHORT,
        MEDIUM,
        LONG,
        LUDICROUS,
        DYNAMIC
    }

    public Command setMode(Mode mode) {
        if (mode.equals(Mode.SHORT)) {
            // dynamicShootCommand.end(false);
            // shooter.stopShooter();
            return shooter.runSetRequestedSpeed(() -> ShooterPreferences.SHORT)
                    .finallyDo(() -> dynamicShootCommand.end(false));
        } else if (mode.equals(Mode.MEDIUM)) {
            return shooter.runSetRequestedSpeed(() -> ShooterPreferences.MEDIUM)
                    .finallyDo(() -> dynamicShootCommand.end(false));
            // dynamicShootCommand.end(false);
        } else if (mode.equals(Mode.LONG)) {
            return shooter.runSetRequestedSpeed(() -> ShooterPreferences.LONG)
                    .finallyDo(() -> dynamicShootCommand.end(false));
            // dynamicShootCommand.end(false);
        } else if (mode.equals(Mode.LUDICROUS)) {
            return shooter.runSetRequestedSpeed(() -> ShooterPreferences.LUDICROUS_SPEED)
                    .finallyDo(() -> dynamicShootCommand.end(false));
            // dynamicShootCommand.end(false);
        } else if (mode.equals(Mode.DYNAMIC)) {
            return dynamicShootCommand;
        } else {
            return Commands.none();
        }
    }

    public Trigger isNonDynamicShootMode() {
        return new Trigger(() -> !activeMode.equals(Mode.DYNAMIC));
    }
}
