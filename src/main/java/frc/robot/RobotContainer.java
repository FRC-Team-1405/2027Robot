// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot;

import java.util.Arrays;
import java.util.List;
import java.util.Set;
import java.util.function.Supplier;

import com.ctre.phoenix6.swerve.SwerveRequest;

import edu.wpi.first.math.VecBuilder;
import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.networktables.NetworkTableInstance;
import edu.wpi.first.networktables.StructPublisher;
import edu.wpi.first.wpilibj.RobotController;
import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.Commands;
import edu.wpi.first.wpilibj2.command.InstantCommand;
import edu.wpi.first.wpilibj2.command.SequentialCommandGroup;
import edu.wpi.first.wpilibj2.command.button.CommandXboxController;
import edu.wpi.first.wpilibj2.command.button.RobotModeTriggers;
import edu.wpi.first.wpilibj2.command.button.Trigger;
import frc.robot.Constants.HoodPreferences.HoodAngles;
import frc.robot.Constants.ShooterPreferences;
import frc.robot.commands.DriveToHubDistance;
import frc.robot.commands.RumbleJoystick;
import frc.robot.commands.SetHoodPosition;
import frc.robot.commands.Autos.CommandsForAutos;
import frc.robot.commands.Autos.Full_Autos;
import frc.robot.commands.Shooter.AutoFire;
import frc.robot.constants.FeatureSwitches;
import frc.robot.constants.FieldConstants;
import frc.robot.generated.TunerConstants;
import frc.robot.lib.AprilTags;
import frc.robot.lib.AutoCommands;
import frc.robot.lib.CommandTracker;
import frc.robot.subsystems.AdjustableHood;
import frc.robot.subsystems.Climber;
import frc.robot.subsystems.CommandSwerveDrivetrain;
import frc.robot.subsystems.Hopper;
import frc.robot.subsystems.Indexer;
import frc.robot.subsystems.Intake;
import frc.robot.subsystems.MoveMode;
import frc.robot.subsystems.Pickup;
import frc.robot.subsystems.ShootMode;
import frc.robot.subsystems.ShootMode.Mode;
import frc.robot.subsystems.Shooter;
import frc.robot.subsystems.SwerveFeatures;
import frc.robot.subsystems.vision.Vision;
import frc.robot.subsystems.vision.Vision.VisionSample;
import frc.robot.subsystems.vision.VisionConstants;

public class RobotContainer {
        private final SwerveRequest.SwerveDriveBrake brake = new SwerveRequest.SwerveDriveBrake();
        private final SwerveRequest.PointWheelsAt point = new SwerveRequest.PointWheelsAt();

        private final Telemetry logger = new Telemetry(SwerveFeatures.MaxSpeed);

        private final CommandXboxController driverJoystick = new CommandXboxController(0);
        private final CommandXboxController operatorJoystick = new CommandXboxController(1);
        private final CommandXboxController shooterJoystick = new CommandXboxController(2);

        public final CommandSwerveDrivetrain drivetrain = TunerConstants.createDrivetrain();

        // Vision publishers
        StructPublisher<Pose2d> cameraEstimatedPosePublisher1 = NetworkTableInstance.getDefault()
                        .getStructTopic("Camera1_EstimatedPose", Pose2d.struct).publish();
        StructPublisher<Pose2d> cameraEstimatedPosePublisher2 = NetworkTableInstance.getDefault()
                        .getStructTopic("Camera2_EstimatedPose", Pose2d.struct).publish();
        List<StructPublisher<Pose2d>> cameraEstimatedPosesPublisher = Arrays.asList(cameraEstimatedPosePublisher1,
                        cameraEstimatedPosePublisher2);

        public Indexer indexer = new Indexer();
        public final Climber climber = new Climber();
        public final AdjustableHood hood = new AdjustableHood();
        public final Hopper hopper = new Hopper();
        public final Intake intake = new Intake();
        public final Pickup pickup = new Pickup();
        private final Vision vision = new Vision(Vision.camerasFromConfigs(VisionConstants.CONFIGS));
        private final SwerveFeatures swerveFeatures = new SwerveFeatures(drivetrain);
        MoveMode moveMode = new MoveMode();
        public Shooter shooter = new Shooter(operatorJoystick, moveMode.setToStandardMode());
        ShootMode shootMode = new ShootMode(drivetrain, swerveFeatures, intake, indexer, shooter, driverJoystick);
        public final CommandsForAutos commandsForAutos = new CommandsForAutos(drivetrain, climber,
                        intake,
                        pickup,
                        hopper,
                        indexer,
                        shooter,
                        hood);
        public final Full_Autos full_Autos = new Full_Autos(commandsForAutos);

        public RobotContainer() {
                configureBindings();
                // configureBindings_CTReDefault();

                full_Autos.registerAutos(commandsForAutos);
                AutoCommands.setupAutoChooser(drivetrain, climber, intake, hopper, indexer, shooter, hood,
                                swerveFeatures, commandsForAutos);
                AprilTags.publishTags(AprilTags.getAprilTagFieldLayout());
                drivetrain.initOverridePose();
        }

        public Command getAutonomousCommand() {
                return AutoCommands.getAutonomousCommand();
        }

        public void correctOdometry() {
                // if (SIMULATE_VISION_FAILURES){
                // int percentageFramesToDrop = 80;
                // Random rnd = new Random();

                // if(rnd.nextInt(100) < percentageFramesToDrop){
                // return;
                // }
                // }

                List<VisionSample> visionSamples = vision.flushSamples();
                vision.updateSpeeds(drivetrain.getState().Speeds);
                // System.out.println("vision sample count: " + visionSamples.size());
                for (var sample : visionSamples) {

                        double thetaStddev = 99999.0;
                        if (true /* STRICT_VISION_ORIENTATION_WEIGHTING */) {
                                // if sample weight isn't essentially perfect, don't trust orientation, sample
                                // weighting is perfect when disabled
                                thetaStddev = sample.weight() > 0.9 ? 10.0 : 99999.0;
                        } else {
                                // You will need to TUNE this scalar. A higher value (e.g., 5.0) means less
                                // trust.
                                thetaStddev = 1.0 / sample.weight();
                        }

                        drivetrain.addVisionMeasurement(
                                        sample.pose(),
                                        sample.timestamp(),
                                        VecBuilder.fill(0.1 / sample.weight(), 0.1 / sample.weight(), thetaStddev));
                }

                Pose2d visionPose = null;
                Pose2d odomPose = drivetrain.getState().Pose;
                for (int i = 0; i < 2; i++) {
                        if (i + 1 <= visionSamples.size()) {
                                cameraEstimatedPosesPublisher.get(i).set(visionSamples.get(i).pose());
                                visionPose = visionSamples.get(i).pose();
                        }
                }

                // if (visionPose != null) {
                // double yawError = yawDiffDegrees(visionPose, odomPose);
                // yawErrorPub.set(yawError);
                // }
        }

        public static final double JOYSTICK_DEADBAND = 0.10;

        private void configureBindings() {
                // configure operator controls
                Command cmd;

                //
                // Operator Controls
                //
                RumbleJoystick.setPeriodChangeWarningOccasion(operatorJoystick);

                cmd = intake.runIntakeOut();
                // SmartDashboard.putData("Commands/RunIntakeOut", cmd);
                operatorJoystick.povUp().onTrue(cmd);
                cmd = intake.runIntakeIn();
                // SmartDashboard.putData("Commands/RunIntakeIn", cmd);
                operatorJoystick.povDown().onTrue(cmd);

                cmd = intake.runIntakeCenter();
                operatorJoystick.povLeft().onTrue(cmd);

                cmd = new InstantCommand(() -> intake.toggleIntakeMovementDisabledFlag(operatorJoystick));
                operatorJoystick.povRight().onTrue(cmd);

                operatorJoystick.y().onTrue(new SetHoodPosition(hood, HoodAngles.SHORT));
                operatorJoystick.b().onTrue(new SetHoodPosition(hood, HoodAngles.MEDIUM));
                operatorJoystick.a().onTrue(new SetHoodPosition(hood, HoodAngles.LONG));

                // Set Shooter Speeds

                // SHORT
                operatorJoystick.y().onTrue(new SequentialCommandGroup(new InstantCommand(
                                () -> SmartDashboard.putString("Shooter/AutoFireMode",
                                                "Short")),
                                shootMode.setMode(Mode.SHORT)));

                // MEDIUM
                operatorJoystick.b().onTrue(new SequentialCommandGroup(new InstantCommand(
                                () -> SmartDashboard.putString("Shooter/AutoFireMode",
                                                "Medium")),
                                shootMode.setMode(Mode.MEDIUM)));

                // LONG
                operatorJoystick.a().and(operatorJoystick.back()
                                .negate()).onTrue(new SequentialCommandGroup(
                                                new InstantCommand(
                                                                () -> SmartDashboard.putString("Shooter/AutoFireMode",
                                                                                "Long")),
                                                shootMode.setMode(Mode.LONG)));

                // LUDICROUS
                operatorJoystick.a().and(operatorJoystick.back()).onTrue(new SequentialCommandGroup(
                                new InstantCommand(
                                                () -> SmartDashboard.putString("Shooter/AutoFireMode",
                                                                "LUDICROUS")),
                                shootMode.setMode(Mode.LUDICROUS)));

                // DYNAMIC
                operatorJoystick.x().onTrue(new SequentialCommandGroup(new InstantCommand(
                                () -> SmartDashboard.putString("Shooter/AutoFireMode",
                                                "Dynamic")),
                                shootMode.setMode(Mode.DYNAMIC)));

                // Stop Shooter
                Command stopShooterAndDeployIntake = Commands.sequence(shooter.stopShooter(), indexer.runStopIndexer(),
                                intake.runIntakeOut());
                Command stopShooter = Commands.sequence(shooter.stopShooter(), indexer.runStopIndexer());

                if (FeatureSwitches.DEPLOY_INTAKE_WHEN_STOPPING_SHOOTER) {
                        operatorJoystick.rightBumper().onTrue(stopShooterAndDeployIntake);
                } else {
                        operatorJoystick.rightBumper().onTrue(stopShooter);
                }

                operatorJoystick.leftBumper().toggleOnTrue(intake.runIntakeCenter());

                // Bump mode (for crossing the bump)
                operatorJoystick.rightTrigger().onTrue(moveMode.setToBumpMode(drivetrain));

                // Exit Bump Mode
                operatorJoystick.leftTrigger().onTrue(moveMode.setToNormalMode());

                //
                // Driver Controls
                //
                RumbleJoystick.setPeriodChangeOccasion(driverJoystick);
                drivetrain.registerTelemetry(logger::telemeterize);

                // cmd = SwerveFeatures.teleopDriveCommand(drivetrain, moveMode,
                // driverJoystick).withName("Teleop Drive");
                // SmartDashboard.putData("Commands/TeleopDrive", cmd);
                // drivetrain.setDefaultCommand(
                // // Drivetrain will execute this command periodically
                // cmd);

                drivetrain.setDefaultCommand(
                                // Drivetrain will execute this command periodically
                                drivetrain.applyRequest(() -> SwerveFeatures.drive
                                                .withVelocityX(SwerveFeatures.MaxSpeed
                                                                * moveMode.selectSpeedMode(driverJoystick::getLeftY,
                                                                                true)
                                                                                .getAsDouble())
                                                .withVelocityY(SwerveFeatures.MaxSpeed
                                                                * moveMode.selectSpeedMode(
                                                                                driverJoystick::getLeftX, false)
                                                                                .getAsDouble())
                                                .withRotationalRate(
                                                                moveMode.selectRotationMode(driverJoystick, drivetrain,
                                                                                SwerveFeatures.MaxAngularRate)
                                                                                .getAsDouble())));

                // Zeroize/reset the field-centric heading on start and back press.
                driverJoystick.start().and(driverJoystick.back()).onTrue(
                                drivetrain.runOnce(drivetrain::seedFieldCentric));

                // Select speed mode
                driverJoystick.leftTrigger().onTrue(moveMode.setToSlowMode());
                driverJoystick.rightTrigger().onTrue(moveMode.setToFastMode());

                // for the 2 lines below, ex. Left trigger is held, and right trigger is tapped
                // quickly such that left trigger is still being held after right trigger is
                // tapped. MoveMode.currentSpeedMode would be SLOW, then FAST, *then SLOW
                // again*.
                driverJoystick.leftTrigger().and(
                                driverJoystick.rightTrigger().negate()).onTrue(moveMode.setToSlowMode());
                driverJoystick.rightTrigger().and(
                                driverJoystick.leftTrigger().negate()).onTrue(moveMode.setToFastMode());

                driverJoystick.leftTrigger().or(driverJoystick.rightTrigger()).onFalse(moveMode.setToNormalMode());

                // Select rotation mode
                // driverJoystick.y().onTrue(moveMode.setToStandardMode());
                // joystick.x().onTrue(moveMode.setToSnakeMode());
                // joystick.b().onTrue(moveMode.setToCompassMode());

                // Brake mode
                // cmd = drivetrain.applyRequest(() -> brake).withName("Brake Mode");
                // SmartDashboard.putData("Commands/BrakeMode", cmd);
                driverJoystick.b().whileTrue(drivetrain.applyRequest(() -> brake));

                // Auto Align
                // driverJoystick.x()
                // .whileTrue(
                // Commands.either(Commands.defer(() -> drivetrain.driveToPose(
                // () -> Optional.of(
                // FieldConstants.BLUE_HUB_SHOOT_CLOSE),
                // true), Set.of(drivetrain)),
                // Commands.none(),
                // MoveMode.inAllianceZone(drivetrain)));

                // Command driveToHubCommand = new DriveToHubDistance(drivetrain,
                // FieldConstants.ALLIANCE_HUB_POSITION,
                // ShooterPreferences.MEDIUM_DISTANCE);
                Supplier<Command> driveToDistanceCommand = () -> new DriveToHubDistance(drivetrain,
                                FieldConstants.ALLIANCE_HUB_POSITION,
                                shooter.getDistanceFromSpeed());

                driverJoystick.x()
                                .whileTrue(
                                                Commands.either(Commands.defer(driveToDistanceCommand,
                                                                Set.of(drivetrain)),
                                                                Commands.none(),
                                                                MoveMode.inAllianceZone(drivetrain)));

                // Point at hub toggle (STANDARD ↔ POINT or POINT_VELOCITY_COMPENSATED).
                // Which point mode is active is controlled by the
                // "MoveMode/Use Velocity Compensated Point" NT toggle in Elastic Dashboard.
                driverJoystick.y().onTrue(moveMode.togglePointMode());

                Trigger hopperTrigger = new Trigger(() -> {
                        return indexer.isIndexerRunning();
                });
                hopperTrigger.onTrue(hopper.runForwardHopper());
                hopperTrigger.onFalse(hopper.runStopHopper());

                // Idle while the robot is disabled. This ensures the configured
                // neutral mode is applied to the drive motors while disabled.
                final var idle = new SwerveRequest.Idle();
                RobotModeTriggers.disabled().whileTrue(
                                drivetrain.applyRequest(() -> idle).ignoringDisable(true));

                // Run Intake (Pickup)
                // driverJoystick.leftBumper().onFalse(intake.runPickupStop());
                driverJoystick.leftBumper()
                                .whileTrue(new SequentialCommandGroup(new InstantCommand(
                                                () -> SmartDashboard.putBoolean("Pickup/PickupButtonPressed", true)),
                                                pickup.runPickupIn()))
                                .onFalse(new InstantCommand(
                                                () -> SmartDashboard.putBoolean("Pickup/PickupButtonPressed", false)));

                // Shoot — continuous auto-fire while held, with drivetrain brake.
                // Hopper is driven by hopperTrigger (follows indexer state).

                final Command shootCommand = AutoFire.teleop(shooter, indexer,
                                () -> ShooterPreferences.INDEXER_VELOCITY, intake);

                // when you fix the brake mode not allowing driver to manually adjust while
                // shooting bug,
                // uncomment this and add brakeCommand back to the commands.parrallel
                // final Command brakeCommand = drivetrain.applyRequest(() -> brake);

                // TODO allow driver to override brake mode while shooting so they can manually
                // adjust
                driverJoystick.rightBumper().and(
                                shootMode.isNonDynamicShootMode())
                                .whileTrue(shootCommand);

                //
                // Shooter Joystick (DEBUG) Controls
                //
                // A: spin up to whatever value is set in the Shooter/TestTargetRPS dashboard
                // slider
                // shooterJoystick.a().onTrue(shooter.runShooterAtTestRPS());
                // // B: stop shooter
                // shooterJoystick.b().onTrue(shooter.stopShooter());
                // // Preset speeds
                // shooterJoystick.y().onTrue(shooter.runSetRequestedSpeed(() ->
                // ShooterPreferences.SHORT));
                // shooterJoystick.x().onTrue(shooter.runSetRequestedSpeed(() ->
                // ShooterPreferences.MEDIUM));
                // // shooterJoystick.a().onTrue(shooter.runSetRequestedSpeed(() ->
                // // ShooterPreferences.LONG));
                // // Fire + stop
                // shooterJoystick.rightBumper().onTrue(
                // AutoFire.teleop(shooter, indexer, hopper,
                // () -> ShooterPreferences.INDEXER_VELOCITY));
                // shooterJoystick.rightBumper().onFalse(indexer.runStopIndexer());
        }

        public static double applyDeadband(double value) {
                return (Math.abs(value) < JOYSTICK_DEADBAND) ? 0.0 : value;
        }

        /** Update NetworkTables with active commands from CommandTracker */
        public static void updateNT() {
                var inst = NetworkTableInstance.getDefault();
                var table = inst.getTable("CommandTracker");

                // Write active commands
                int i = 0;
                for (Command cmd : CommandTracker.getRunning()) {
                        table.getEntry("cmd_" + i).setString(cmd.getName());
                        i++;
                }

                // Clear leftover slots
                for (int j = i; j < 2; j++) {
                        table.getEntry("cmd_" + j).setString("");
                }

                table.getEntry("count").setNumber(CommandTracker.getRunning().size());
        }

        public static void publishRobotData() {
                SmartDashboard.putNumber("Battery/BatteryVoltage", RobotController.getBatteryVoltage());
                SmartDashboard.putNumber("Battery/BrownoutVoltage", RobotController.getBrownoutVoltage());
        }
}
