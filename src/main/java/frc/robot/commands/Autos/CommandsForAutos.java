package frc.robot.commands.Autos;

import java.util.function.Supplier;

import com.therekrab.autopilot.APConstraints;

import edu.wpi.first.math.geometry.Rotation2d;
import edu.wpi.first.math.trajectory.TrapezoidProfile;
import edu.wpi.first.units.Units;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.Commands;
import edu.wpi.first.wpilibj2.command.InstantCommand;
import frc.robot.Constants.ShooterPreferences;
import frc.robot.commands.CircleFacingTagCommand;
import frc.robot.commands.DriveToHubDistance;
import frc.robot.commands.AutoPilot.AutoPilotV2Command;
import frc.robot.commands.Shooter.AutoFire;
import frc.robot.constants.FieldConstants;
import frc.robot.subsystems.AdjustableHood;
import frc.robot.subsystems.Climber;
import frc.robot.subsystems.CommandSwerveDrivetrain;
import frc.robot.subsystems.Hopper;
import frc.robot.subsystems.Indexer;
import frc.robot.subsystems.Intake;
import frc.robot.subsystems.Pickup;
import frc.robot.subsystems.Shooter;
import static frc.robot.commands.AutoPilot.AutoPilotV2Command.DEFAULT_XY_THRESHOLD;
import static frc.robot.commands.AutoPilot.AutoPilotV2Command.DEFAULT_THETA_THRESHOLD;
import static frc.robot.commands.AutoPilot.AutoPilotV2Command.DEFAULT_BEELINE_THRESHOLD;
import static frc.robot.commands.Autos.AutoPoses.*;

public class CommandsForAutos {
        // TODO: integrate shooting positions dropdown into all autos, include the shoot
        // from distance in the dropdown
        // TODO: add a start position dropdown, integrate into all autos
        // TODO: integrate shooting positions dropdown into all autos, include the shoot
        // from distance in the dropdown
        // TODO: add a start position dropdown, integrate into all autos

        // Velocity is max speed overall/ in a sec, how much can position change
        // Acceleration in a second, how much can velocity change
        // Jerk is how fast it starts and stops

        // #region CONSTRAINTS
        private static final APConstraints bumpConstraints = new APConstraints()
                        .withAcceleration(30) // TUNE THIS TO YOUR ROBOT!
                        .withVelocity(6)
                        .withJerk(600);

        private static final double BUMP_NARROW_XY_THRESHOLD_CM = 12;
        private static final double BUMP_WIDE_XY_THRESHOLD_CM = 30;
        private static final double BUMP_THETA_THRESHOLD_DEG = 12;
        private static final double BUMP_headingKp = 2;
        private static final double FAST_BUMP_headingKp = 16;

        // TODO: Adjust
        private static final APConstraints fullFieldConstraints = new APConstraints()
                        .withAcceleration(4.0) // TUNE THIS TO YOUR ROBOT!
                        .withVelocity(1.5)
                        .withJerk(67);

        private static final TrapezoidProfile.Constraints centerHarvestConstraint = new TrapezoidProfile.Constraints(
                        0.5, 0.5);

        // .withJerk(67.0);
        // #endregion
        CommandSwerveDrivetrain drivetrain;
        Climber climber;
        Intake intake;
        Pickup pickup;
        Hopper hopper;
        Indexer indexer;
        Shooter shooter;
        AdjustableHood hood;

        public CommandsForAutos(CommandSwerveDrivetrain drivetrain, Climber climber,
                        Intake intake,
                        Pickup pickup,
                        Hopper hopper,
                        Indexer indexer,
                        Shooter shooter,
                        AdjustableHood hood) {

                this.drivetrain = drivetrain;
                this.climber = climber;
                this.intake = intake;
                this.pickup = pickup;
                this.hopper = hopper;
                this.indexer = indexer;
                this.shooter = shooter;
                this.hood = hood;

        }

        // region Test Commands

        //
        // Circle
        //
        private static final APConstraints circleDrivingConstraints = new APConstraints()
                        .withAcceleration(6.0) // TUNE THIS TO YOUR ROBOT!
                        .withVelocity(2.0)
                        .withJerk(5); // jerk=5 -> 25s; jerk=50 -> 24s 
        
        private static final double circle_headingKp = 0.8;
        Supplier<Command> MoveTo_circleBottom = () -> new AutoPilotV2Command.Builder(
                        circleBottom, drivetrain, "MoveTo_circleBottom")
                        .withFlipPoseForAlliance(true)
                        .withConstraints(circleDrivingConstraints)
                        .withHeadingPID(circle_headingKp, 0)
                        .withEntryAngle(Rotation2d.fromDegrees(-45))
                        .build();

        Supplier<Command> MoveTo_circleRight = () -> new AutoPilotV2Command.Builder(
                        circleRight, drivetrain, "MoveTo_circleRight")
                        .withFlipPoseForAlliance(true)
                        .withConstraints(circleDrivingConstraints)
                        .withHeadingPID(circle_headingKp, 0)
                        .withEntryAngle(Rotation2d.fromDegrees(-45))
                        .build();

        Supplier<Command> MoveTo_circleTop = () -> new AutoPilotV2Command.Builder(
                        circleTop, drivetrain, "MoveTo_circleTop")
                        .withFlipPoseForAlliance(true)
                        .withConstraints(circleDrivingConstraints)
                        .withHeadingPID(circle_headingKp, 0)
                        .withEntryAngle(Rotation2d.fromDegrees(-45))
                        .build();

        Supplier<Command> MoveTo_circleLeft = () -> new AutoPilotV2Command.Builder(
                        circleLeft, drivetrain, "MoveTo_circleLeft")
                        .withFlipPoseForAlliance(true)
                        .withConstraints(circleDrivingConstraints)
                        .withHeadingPID(circle_headingKp, 0)
                        .withEntryAngle(Rotation2d.fromDegrees(-45))
                        .build();

        //
        // Vision test: orbit the starting point while facing a fixed AprilTag,
        // ramping speed up to exercise vision under acceleration + rotation.
        //
        private static final int VISION_CIRCLE_TEST_TAG_ID = 10;
        Supplier<Command> CircleFacingTag = () -> new CircleFacingTagCommand(drivetrain,
                        VISION_CIRCLE_TEST_TAG_ID);

        // endregion Test Commands

        /* Commands */
        // Uses command suppliers instead of commands so that we can reuse the same
        // command in an autonomous
        Supplier<Command> MoveTo_allianceCenter = () -> new AutoPilotV2Command.Builder(
                        () -> FieldConstants.BLUE_HUB_SHOOT_CLOSE, drivetrain, "MoveTo_allianceCenter")
                        .withFlipPoseForAlliance(true)
                        .build();

        Supplier<Command> MoveTo_LeftMidAlliance = () -> new AutoPilotV2Command.Builder(
                        () -> LeftMidAlliance.get(), drivetrain, "MoveTo_LeftMidAlliance")
                        .withFlipPoseForAlliance(true)
                        .build();

        Supplier<Command> MoveTo_centerOfField = () -> new AutoPilotV2Command.Builder(
                        () -> centerOfField.get(), drivetrain, "MoveTo_centerOfField")
                        .withFlipPoseForAlliance(true)
                        .build();

        // #region Feeding station Movements
        Supplier<Command> MoveTo_feedingStation = () -> new AutoPilotV2Command.Builder(
                        () -> feedingStation.get(), drivetrain, "MoveTo_feedingStation")
                        .withFlipPoseForAlliance(true)
                        .build();
        Supplier<Command> MoveTo_feedingStation_leftStart = () -> Commands.parallel(intake.runIntakeOut(),
                        Commands.sequence(MoveTo_allianceCenter.get(),
                                        MoveTo_feedingStation.get()));
        Supplier<Command> MoveTo_feedingStation_centerStart = () -> Commands.parallel(intake.runIntakeOut(),
                        Commands.sequence(
                                        MoveTo_allianceCenter.get(),
                                        MoveTo_feedingStation.get()));

        Supplier<Command> MoveTo_fourMeters = () -> new AutoPilotV2Command.Builder(
                        () -> fourMeters.get(), drivetrain, "MoveTo_fourMeters")
                        .withFlipPoseForAlliance(true)
                        // .withConstraints(fullFieldConstraints)
                       // .withMaxVelocity(() -> Math.min(Math.min((1 - (pickup.getPidError() / 20)) * 5, 20), 1.5))
                        .build();
        Supplier<Command> MoveTo_testOffHub = () -> new AutoPilotV2Command.Builder(
                        () -> testOffHub.get(), drivetrain, "MoveTo_testOffHub")
                        .withFlipPoseForAlliance(true)
                        // .withConstraints(fullFieldConstraints)
                        .build();
        // #endregion
        Supplier<Command> MoveTo_behindHub = () -> new AutoPilotV2Command.Builder(
                        () -> behindHub.get(), drivetrain, "MoveTo_behindHub")
                        .withFlipPoseForAlliance(true)
                        .build();
        // Shooter
        Supplier<Command> MoveTo_FrontHubShoot = () -> new DriveToHubDistance(drivetrain,
                        FieldConstants.ALLIANCE_HUB_POSITION,
                        shooter.getDistanceFromSpeed());
        Supplier<Command> MoveTo_New_FrontHubShoot = () -> new AutoPilotV2Command.Builder(
                        () -> FrontHubShoot.get(), drivetrain, "MoveTo_New_FrontHubShoot")
                        .withFlipPoseForAlliance(true)
                        .build();
        Supplier<Command> MoveTo_requestedSpeedDistanceToHub = () -> new DriveToHubDistance(drivetrain,
                        FieldConstants.ALLIANCE_HUB_POSITION,
                        shooter.getDistanceFromSpeed());
        // #region Move To Shooting Positions
        Supplier<Command> MoveTo_ClosestShootingPosition_SHORT = () -> Commands.sequence(
                        new InstantCommand(() -> shooter
                                        .setRequestedSpeedWithoutShooting(() -> ShooterPreferences.SHORT)),
                        MoveTo_requestedSpeedDistanceToHub.get());
        Supplier<Command> MoveTo_ClosestShootingPosition_MEDIUM = () -> Commands.sequence(
                        new InstantCommand(() -> shooter
                                        .setRequestedSpeedWithoutShooting(() -> ShooterPreferences.MEDIUM)),
                        MoveTo_requestedSpeedDistanceToHub.get());
        Supplier<Command> MoveTo_ClosestShootingPosition_LONG = () -> Commands.sequence(
                        new InstantCommand(() -> shooter
                                        .setRequestedSpeedWithoutShooting(() -> ShooterPreferences.LONG)),
                        MoveTo_requestedSpeedDistanceToHub.get());
        // #endregion
        Supplier<Command> MoveTo_IntakeIN_FrontHubShoot = () -> new AutoPilotV2Command.Builder(
                        () -> IntakeIN_FrontHubShoot.get(), drivetrain, "MoveTo_IntakeIN_FrontHubShoot")
                        .withFlipPoseForAlliance(true)
                        .build();
        Supplier<Command> MoveTo_IntakeOUT_FrontHubShoot = () -> new AutoPilotV2Command.Builder(
                        () -> IntakeOUT_FrontHubShoot.get(), drivetrain, "MoveTo_IntakeOUT_FrontHubShoot")
                        .withFlipPoseForAlliance(true)
                        .build();
        Supplier<Command> MoveTo_RightHubShoot = () -> new AutoPilotV2Command.Builder(
                        () -> RightHubShoot.get(), drivetrain, "MoveTo_RightHubShoot")
                        .withFlipPoseForAlliance(true)
                        .build();
        // Center Harvest(s)
        Supplier<Command> MoveTo_centerRightIntakeStart = () -> new AutoPilotV2Command.Builder(
                        () -> centerRightIntakeStart.get(), drivetrain, "MoveTo_centerRightIntakeStart")
                        .withFlipPoseForAlliance(true)
                        .build();

        Supplier<Command> MoveTo_centerRightIntakeEnd = () -> new AutoPilotV2Command.Builder(
                        () -> centerRightIntakeEnd.get(), drivetrain, "MoveTo_centerRightIntakeEnd")
                        .withFlipPoseForAlliance(true)
                        .withMaxVelocity(() -> Math.min(Math.min((1 - (pickup.getPidError() / 20)) * 5, 20), 1.5))
                        // TODO: .withConstraints(fullFieldConstraints)
                        .build();

        Supplier<Command> MoveTo_centerLeftIntakeStart = () -> new AutoPilotV2Command.Builder(
                        () -> centerLeftIntakeStart.get(), drivetrain, "MoveTo_centerLeftIntakeStart")
                        .withFlipPoseForAlliance(true)
                        .build();

        Supplier<Command> MoveTo_centerLeftIntakeEnd = () -> new AutoPilotV2Command.Builder(
                        () -> centerLeftIntakeEnd.get(), drivetrain, "MoveTo_centerRightIntakeEnd")
                        .withFlipPoseForAlliance(true)
                        // .withConstraints(centerHarvestConstraint)
                        .withMaxVelocity(() -> Math.min(Math.min((1 - (pickup.getPidError() / 20)) * 5, 20), 1.5))
                        .build();
        Supplier<Command> MoveTo_centerRightIntake_SecondSweep = () -> new AutoPilotV2Command.Builder(
                        () -> centerRightIntake_SecondSweep.get(), drivetrain, "MoveTo_centerRightIntake_SecondSweep")
                        .withFlipPoseForAlliance(true)
                        .build();
        Supplier<Command> MoveTo_centerLeftIntake_SecondSweep = () -> new AutoPilotV2Command.Builder(
                        () -> centerLeftIntake_SecondSweep.get(), drivetrain, "MoveTo_centerRightIntake_SecondSweep")
                        .withFlipPoseForAlliance(true)
                        .build();
        // #region Quads
        Supplier<Command> MoveTo_quadRightIntakeStart = () -> new AutoPilotV2Command.Builder(
                        () -> quadRightIntakeStart.get(), drivetrain, "MoveTo_quadRightIntakeStart")
                        .withFlipPoseForAlliance(true)
                        .build();
        Supplier<Command> MoveTo_quadLeftIntakeStart = () -> new AutoPilotV2Command.Builder(
                        () -> quadLeftIntakeStart.get(), drivetrain, "MoveTo_quadLeftIntakeStart")
                        .withFlipPoseForAlliance(true)
                        .build();
        Supplier<Command> MoveTo_rightQuadSecondSweep_Start = () -> new AutoPilotV2Command.Builder(
                        () -> rightQuadSecondSweep_Start.get(), drivetrain, "MoveTo_rightQuadSecondSweep_Start")
                        .withFlipPoseForAlliance(true)
                        .build();

        Supplier<Command> MoveTo_rightQuadSecondSweep_End = () -> new AutoPilotV2Command.Builder(
                        () -> rightQuadSecondSweep_End.get(), drivetrain, "MoveTo_rightQuadSecondSweep_End")
                        .withFlipPoseForAlliance(true)
                        // TODO: .withConstraints(fullFieldConstraints)
                        .build();

        Supplier<Command> MoveTo_leftQuadSecondSweep_Start = () -> new AutoPilotV2Command.Builder(
                        () -> leftQuadSecondSweep_Start.get(), drivetrain, "MoveTo_leftQuadSecondSweep_Start")
                        .withFlipPoseForAlliance(true)
                        .build();

        Supplier<Command> MoveTo_leftQuadSecondSweep_End = () -> new AutoPilotV2Command.Builder(
                        () -> leftQuadSecondSweep_End.get(), drivetrain, "MoveTo_leftQuadSecondSweep_End")
                        .withFlipPoseForAlliance(true)
                        // .withConstraints(centerHarvestConstraint)
                        .build();

        Supplier<Command> MoveTo_centerLine_RightIntakeStart = () -> new AutoPilotV2Command.Builder(
                        () -> centerLine_RightIntakeStart.get(), drivetrain, "MoveTo_centerLine_RightIntakeStart")
                        .withFlipPoseForAlliance(true)
                        .build();

        Supplier<Command> MoveTo_centerLine_RightIntakeEnd = () -> new AutoPilotV2Command.Builder(
                        () -> centerLine_RightIntakeEnd.get(), drivetrain, "MoveTo_centerLine_RightIntakeEnd")
                        .withFlipPoseForAlliance(true)
                        .withMaxVelocity(() -> Math.min(Math.min((1 - (pickup.getPidError() / 20)) * 5, 20), 1.5))
                        // TODO: .withConstraints(fullFieldConstraints)
                        .build();

        Supplier<Command> MoveTo_centerLine_LeftIntakeStart = () -> new AutoPilotV2Command.Builder(
                        () -> centerLine_LeftIntakeStart.get(), drivetrain, "MoveTo_centerLine_LeftIntakeStart")
                        .withFlipPoseForAlliance(true)
                        .build();

        Supplier<Command> MoveTo_centerLine_LeftIntakeEnd = () -> new AutoPilotV2Command.Builder(
                        () -> centerLine_LeftIntakeEnd.get(), drivetrain, "MoveTo_centerLine_RightIntakeEnd")
                        .withFlipPoseForAlliance(true)
                        // .withConstraints(centerHarvestConstraint)
                        .build();
        // deadline runs in
        // parrallel until the
        // first command
        // finishes
        Supplier<Command> MoveTo_quadRight = () -> new AutoPilotV2Command.Builder(
                        () -> quadRight.get(), drivetrain, "MoveTo_quadRight")
                        .withFlipPoseForAlliance(true)
                        .withProfileThresholds(8, DEFAULT_THETA_THRESHOLD, DEFAULT_BEELINE_THRESHOLD)
                        .build();
        Supplier<Command> MoveTo_quadLeft = () -> new AutoPilotV2Command.Builder(
                        () -> quadLeft.get(), drivetrain, "MoveTo_quadLeft")
                        .withFlipPoseForAlliance(true)
                        .withProfileThresholds(8, DEFAULT_THETA_THRESHOLD, DEFAULT_BEELINE_THRESHOLD)
                        // .withMaxVelocity(() -> Math.min(Math.min((1 - (pickup.getPidError() / 20)) *
                        // 5, 20), 1.5))
                        .build();
        // #endregion
        Supplier<Command> MoveTo_centerRightIntakeEndLookHub = () -> new AutoPilotV2Command.Builder(
                        () -> centerRightIntakeEndLookHub.get(), drivetrain, "centerRightIntakeEndLookHub")
                        .withFlipPoseForAlliance(true)
                        .withProfileThresholds(
                                        16.0, 5.0, DEFAULT_BEELINE_THRESHOLD)
                        // .withWaitSeconds(1)
                        .build();

        Supplier<Command> MoveTo_centerLeftIntakeEndLookHub = () -> new AutoPilotV2Command.Builder(
                        () -> centerLeftIntakeEndLookHub.get(), drivetrain, "centerRightIntakeEndLookHub")
                        .withFlipPoseForAlliance(true)
                        // .withWaitSeconds(1)
                        .build();

        Supplier<Command> MoveTo_rightLoadInZone = () -> new AutoPilotV2Command.Builder(
                        () -> rightLoadInZone.get(), drivetrain, "MoveTo_rightLoadInZone")
                        .withFlipPoseForAlliance(true)
                        .build();
        Supplier<Command> MoveTo_leftLoadInZone = () -> new AutoPilotV2Command.Builder(
                        () -> leftLoadInZone.get(), drivetrain, "MoveTo_leftLoadInZone")
                        .withFlipPoseForAlliance(true)
                        .build();
        // Depot
        Supplier<Command> MoveTo_rightOfDepot_In = () -> new AutoPilotV2Command.Builder(
                        () -> rightOfDepot_In.get(), drivetrain, "MoveTo_rightOfDepot_In")
                        .withFlipPoseForAlliance(true)
                        .build();
        Supplier<Command> MoveTo_rightOfDepot_Out = () -> new AutoPilotV2Command.Builder(
                        () -> rightOfDepot_Out.get(), drivetrain, "MoveTo_rightOfDepot_Out")
                        .withFlipPoseForAlliance(true)
                        .build();
        Supplier<Command> MoveTo_leftOfDepot_In = () -> new AutoPilotV2Command.Builder(
                        () -> leftOfDepot_In.get(), drivetrain, "MoveTo_leftOfDepot_In")
                        .withFlipPoseForAlliance(true)
                        .build();
        Supplier<Command> MoveTo_leftOfDepot_Out = () -> new AutoPilotV2Command.Builder(
                        () -> leftOfDepot_Out.get(), drivetrain, "MoveTo_leftOfDepot_Out")
                        .withFlipPoseForAlliance(true)
                        .build();
        Supplier<Command> MoveTo_midOfDepotFaceOut = () -> new AutoPilotV2Command.Builder(
                        () -> midOfDepotFaceOut.get(), drivetrain, "MoveTo_midOfDepotFaceOut")
                        .withFlipPoseForAlliance(true)
                        .build();
        Supplier<Command> MoveTo_left_midOfDepot_In = () -> new AutoPilotV2Command.Builder(
                        () -> left_midOfDepot_In.get(), drivetrain, "MoveTo_left_midOfDepot_In")
                        .withFlipPoseForAlliance(true)
                        .build();
        Supplier<Command> MoveTo_left_midOfDepot_Out = () -> new AutoPilotV2Command.Builder(
                        () -> left_midOfDepot_Out.get(), drivetrain, "MoveTo_left_midOfDepot_Out")
                        .withFlipPoseForAlliance(true)
                        .build();

        Supplier<Command> MoveTo_depot_BackFace_Out = () -> new AutoPilotV2Command.Builder(
                        () -> depot_BackFace_Out.get(), drivetrain, "MoveTo_depot_BackFace_Out")
                        .withFlipPoseForAlliance(true)
                        .build();
        Supplier<Command> MoveTo_depot_BackFace_In = () -> new AutoPilotV2Command.Builder(
                        () -> depot_BackFace_In.get(), drivetrain, "MoveTo_depot_BackFace_In")
                        .withFlipPoseForAlliance(true)
                        .build();
        Supplier<Command> MoveTo_depot_BackFace_End_Dos = () -> new AutoPilotV2Command.Builder(
                        () -> depot_BackFace_End_Dos.get(), drivetrain, "MoveTo_depot_BackFace_End_Dos")
                        .withFlipPoseForAlliance(true)
                        .build();
        Supplier<Command> MoveTo_towerDodge_Start = () -> new AutoPilotV2Command.Builder(
                        () -> towerDodge_Start.get(), drivetrain, "MoveTo_towerDodge_Start")
                        .withFlipPoseForAlliance(true)
                        .build();
        Supplier<Command> MoveTo_towerDodge_End = () -> new AutoPilotV2Command.Builder(
                        () -> towerDodge_End.get(), drivetrain, "MoveTo_towerDodge_End")
                        .withFlipPoseForAlliance(true)
                        .build();
        Supplier<Command> MoveTo_selectedShootPosition = () -> new AutoPilotV2Command.Builder(
                        AutoCommands.getShootPosition(), drivetrain, "MoveTo_selectedShootPosition")
                        .withFlipPoseForAlliance(true)
                        .build();
        // right from the driver station view
        // Bump Stuff

        Supplier<Command> MoveTo_leftBump_AllianceToFieldStart = () -> new AutoPilotV2Command.Builder(
                        () -> leftBump_AllianceToFieldStart.get(), drivetrain,
                        "MoveTo_leftBump_AllianceToFieldStart")
                        .withFlipPoseForAlliance(true)
                        // .withConstraints(bumpConstraints)
                        .withProfileThresholds(32, DEFAULT_THETA_THRESHOLD, DEFAULT_BEELINE_THRESHOLD)
                        // .withHeadingPID(BUMP_headingKp, 0)
                        .build();
        Supplier<Command> MoveTo_leftBump_AllianceToFieldStart_LOOK_HUB = () -> new AutoPilotV2Command.Builder(
                        () -> leftBump_AllianceToFieldStart_LOOK_HUB.get(), drivetrain,
                        "MoveTo_leftBump_AllianceToFieldStart_LOOK_HUB")
                        .withFlipPoseForAlliance(true)
                        // .withConstraints(bumpConstraints)
                        .build();
        Supplier<Command> MoveTo_leftBump_AllianceToFieldEnd = () -> new AutoPilotV2Command.Builder(
                        () -> leftBump_AllianceToFieldEnd.get(), drivetrain,
                        "MoveTo_leftBump_AllianceToFieldEnd")
                        .withFlipPoseForAlliance(true)
                        .withConstraints(bumpConstraints)
                        .withHeadingPID(BUMP_headingKp, 0)
                        .build();

        Supplier<Command> MoveTo_rightBump_AllianceToFieldStart = () -> new AutoPilotV2Command.Builder(
                        () -> rightBump_AllianceToFieldStart.get(), drivetrain,
                        "MoveTo_rightBump_AllianceToFieldStart")
                        .withFlipPoseForAlliance(true)
                        .withProfileThresholds(BUMP_NARROW_XY_THRESHOLD_CM, BUMP_THETA_THRESHOLD_DEG,
                                        DEFAULT_BEELINE_THRESHOLD)
                        .withHeadingPID(BUMP_headingKp, 0)
                        // .withConstraints(bumpConstraints)
                        .build();
        Supplier<Command> MoveTo_rightBump_AllianceToFieldStart_LOOK_HUB = () -> new AutoPilotV2Command.Builder(
                        () -> rightBump_AllianceToFieldStart_LOOK_HUB.get(), drivetrain,
                        "MoveTo_rightBump_AllianceToFieldStart_LOOK_HUB")
                        .withFlipPoseForAlliance(true)
                        // .withConstraints(bumpConstraints)
                        .build();

        Supplier<Command> MoveTo_rightBump_AllianceToFieldEnd = () -> new AutoPilotV2Command.Builder(
                        () -> rightBump_AllianceToFieldEnd.get(), drivetrain,
                        "MoveTo_rightBump_AllianceToFieldEnd")
                        .withFlipPoseForAlliance(true)
                        .withConstraints(bumpConstraints)
                        .withProfileThresholds(
                                        BUMP_WIDE_XY_THRESHOLD_CM, BUMP_THETA_THRESHOLD_DEG,
                                        DEFAULT_BEELINE_THRESHOLD)
                        .withHeadingPID(BUMP_headingKp, 0)
                        .build();

        Supplier<Command> MoveTo_leftBump_FieldToAllianceStart = () -> new AutoPilotV2Command.Builder(
                        () -> leftBump_FieldToAllianceStart.get(), drivetrain,
                        "MoveTo_leftBump_FieldToAllianceStart")
                        .withFlipPoseForAlliance(true)
                        // .withConstraints(bumpConstraints)
                        .withHeadingPID(FAST_BUMP_headingKp, 0)
                        .withProfileThresholds(40, DEFAULT_THETA_THRESHOLD, DEFAULT_BEELINE_THRESHOLD)
                        .build();

        Supplier<Command> MoveTo_leftBump_FieldToAllianceEnd = () -> new AutoPilotV2Command.Builder(
                        () -> leftBump_FieldToAllianceEnd.get(), drivetrain,
                        "MoveTo_leftBump_FieldToAllianceEnd")
                        .withFlipPoseForAlliance(true)
                        .withProfileThresholds(6, 12, DEFAULT_BEELINE_THRESHOLD)
                        .withConstraints(bumpConstraints)
                        .withHeadingPID(BUMP_headingKp, 0)
                        .build();
        Supplier<Command> MoveTo_rightBump_FieldToAllianceStart = () -> new AutoPilotV2Command.Builder(
                        () -> rightBump_FieldToAllianceStart.get(), drivetrain,
                        "MoveTo_rightBump_FieldToAllianceStart")
                        .withFlipPoseForAlliance(true)
                        .withProfileThresholds(BUMP_NARROW_XY_THRESHOLD_CM, BUMP_THETA_THRESHOLD_DEG,
                                        DEFAULT_BEELINE_THRESHOLD)
                        // .withHeadingPID(BUMP_headingKp, 0)
                        .build();
        Supplier<Command> MoveTo_rightBump_FieldToAllianceEnd = () -> new AutoPilotV2Command.Builder(
                        () -> rightBump_FieldToAllianceEnd.get(), drivetrain,
                        "MoveTo_rightBump_FieldToAllianceEnd")
                        .withFlipPoseForAlliance(true)
                        .withHeadingPID(BUMP_headingKp, 0)
                        .build();
        Supplier<Command> MoveTo_rightBump_FieldToAllianceEndDos = () -> new AutoPilotV2Command.Builder(
                        () -> rightBump_FieldToAllianceEndDos.get(), drivetrain,
                        "MoveTo_rightBump_FieldToAllianceEndDos")
                        .withFlipPoseForAlliance(true)
                        // TODO:This may not be necessary
                        .withHeadingPID(BUMP_headingKp, 0)
                        .build();
        Supplier<Command> MoveTo_startRightFaceIn = () -> new AutoPilotV2Command.Builder(
                        () -> startRightFaceIn.get(), drivetrain,
                        "MoveTo_startRightFaceIn")
                        .withFlipPoseForAlliance(true)
                        .build();
        // Supplier<Command> quickShoot = () -> Commands.sequence(
        // shooter.runSetRequestedSpeed(() -> ShooterPreferences.LONG),
        // new AutoFire(shooter, indexer, hopper, () ->
        // ShooterPreferences.INDEXER_VELOCITY)
        // .repeatedly())
        // .withTimeout(3)
        // .andThen(Commands.sequence(
        // indexer.runStopIndexer(),
        // shooter.stopShooter(),
        // indexer.runStopIndexer()));

        Supplier<Command> mediumShoot = () -> Commands.sequence(
                        shooter.runSetRequestedSpeed(() -> ShooterPreferences.MEDIUM),
                        AutoFire.autonomous(shooter, indexer,
                                        () -> ShooterPreferences.INDEXER_VELOCITY))
                        .withTimeout(10)
                        .andThen(Commands.sequence(
                                        indexer.runStopIndexer(),
                                        shooter.stopShooter(),
                                        indexer.runStopIndexer()));

        Supplier<Command> longShoot = () -> Commands.sequence(
                        shooter.runSetRequestedSpeed(() -> ShooterPreferences.LONG),
                        AutoFire.autonomous(shooter, indexer,
                                        () -> ShooterPreferences.INDEXER_VELOCITY))
                        .withTimeout(10)
                        .andThen(Commands.sequence(
                                        indexer.runStopIndexer(),
                                        shooter.stopShooter(),
                                        indexer.runStopIndexer()));

        Supplier<Command> shortShoot = () -> Commands.sequence(
                        shooter.runSetRequestedSpeed(() -> ShooterPreferences.SHORT),
                        AutoFire.autonomous(shooter, indexer,
                                        () -> ShooterPreferences.INDEXER_VELOCITY))
                        .withTimeout(10)
                        .andThen(Commands.sequence(
                                        indexer.runStopIndexer(),
                                        shooter.stopShooter(),
                                        indexer.runStopIndexer()));
        // Supplier<Command> fullShoot = () -> Commands.sequence(
        // shooter.runSetRequestedSpeed(() -> ShooterPreferences.LONG),
        // new AutoFire(shooter, indexer, hopper, () ->
        // ShooterPreferences.INDEXER_VELOCITY)
        // .repeatedly())
        // .withTimeout(7)
        // .andThen(Commands.sequence(
        // indexer.runStopIndexer(),
        // shooter.stopShooter(),
        // indexer.runStopIndexer()));

}
