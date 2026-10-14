// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot.commands.Autos;

import java.util.function.Supplier;

import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Rotation2d;
import frc.robot.constants.FieldConstants;

/** Add your docs here. */
public class AutoPoses {

        // Rotations
        // Positive rotations are CCW:
        // https://frcdocs.wpi.edu/en/latest/docs/software/advanced-controls/geometry/pose.html#rotation
        public static final Rotation2d CW_30deg = Rotation2d.fromDegrees(-30);
        public static final Rotation2d CCW_30deg = Rotation2d.fromDegrees(30);
        private static double BUMP_X_FIELD_SIDE = 6.0;
        private static double BUMP_X_ALLIANCE_SIDE = 3.0; 
        // Poses
        // off blue center only used for Right Start Depot Score

        public static Supplier<Pose2d> feedingStation = () -> FieldConstants.BLUE_FEED_ROBOT_POSITION;
        public static Supplier<Pose2d> rightLoadInZone = () -> new Pose2d(0, 0, Rotation2d.fromDegrees(90)); // was
                                                                                                             // 5.75,
                                                                                                             // 2.5,
                                                                                                             // Rotation2d.fromDegrees(180)
        public static Supplier<Pose2d> leftLoadInZone = () -> new Pose2d(0, 0, Rotation2d.fromDegrees(180)); // 5.75,
                                                                                                             // 5.5,
                                                                                                             // Rotation2d.fromDegrees(180)

        // region Test Poses

        // Define your adjustable distance in meters (7 feet = 2.1336 meters)
        public static final double CIRCLE_DIST = 1.5;

        public static Supplier<Pose2d> circleBottom = () -> new Pose2d(4.546 - CIRCLE_DIST, 4.035,
                        Rotation2d.fromDegrees(0));
        public static Supplier<Pose2d> circleRight = () -> new Pose2d(4.546, 4.035 - CIRCLE_DIST,
                        Rotation2d.fromDegrees(90));
        public static Supplier<Pose2d> circleTop = () -> new Pose2d(4.546 + CIRCLE_DIST, 4.035,
                        Rotation2d.fromDegrees(180));
        public static Supplier<Pose2d> circleLeft = () -> new Pose2d(4.546, 4.035 + CIRCLE_DIST,
                        Rotation2d.fromDegrees(270));

        // endregion Test Poses

        // #region START Poses
        public static Supplier<Pose2d> startRightFaceIn = () -> new Pose2d(BUMP_X_ALLIANCE_SIDE, 5,
                        Rotation2d.fromDegrees(0)); // was 3.55,
        // 0.37,
        // Rotation2d.fromDegrees(90)
        public static Supplier<Pose2d> startLeftFaceIn = () -> new Pose2d(3.55, 7.65, Rotation2d.fromDegrees(270));
        public static Supplier<Pose2d> startRightFaceFront = () -> new Pose2d(3.55, 0.37, Rotation2d.fromDegrees(0));
        // #endregion

        // #region BUMP Poses
        // Left Bump

        // Values for our test field at home, TODO update to the real field values
        // Move across the bump while rotating to always face the hub
        // TODO:Add left bump
        private static double RIGHT_BUMP_ALLIANCE_ANGLE = 45;
        private static double RIGHT_BUMP_FIELD_ANGLE = 125;

        public static Supplier<Pose2d> leftBump_AllianceToFieldStart = () -> new Pose2d(
                        BUMP_X_ALLIANCE_SIDE, 5.85,
                        Rotation2d.fromDegrees(315)); // was 0
        public static Supplier<Pose2d> leftBump_AllianceToFieldStart_LOOK_HUB = () -> new Pose2d(
                        BUMP_X_ALLIANCE_SIDE, 5.5,
                        Rotation2d.fromDegrees(270)); // TODO:Test
        public static Supplier<Pose2d> leftBump_AllianceToFieldEnd = () -> new Pose2d(
                        BUMP_X_FIELD_SIDE, 5.85,
                        Rotation2d.fromDegrees(225)); // was 0

        public static Supplier<Pose2d> leftBump_FieldToAllianceStart = () -> new Pose2d(
                        BUMP_X_FIELD_SIDE, 5.65,
                        Rotation2d.fromDegrees(225)); // was 180
        public static Supplier<Pose2d> leftBump_FieldToAllianceEnd = () -> new Pose2d(
                        BUMP_X_ALLIANCE_SIDE, 5.7,
                        Rotation2d.fromDegrees(315)); // was 180
        // Right Bump
        public static Supplier<Pose2d> rightBump_AllianceToFieldStart = () -> new Pose2d(
                        BUMP_X_ALLIANCE_SIDE, 2.25, // was 2.5
                        Rotation2d.fromDegrees(RIGHT_BUMP_ALLIANCE_ANGLE)); // rotation was 0

        public static Supplier<Pose2d> rightBump_AllianceToFieldStart_LOOK_HUB = () -> new Pose2d(
                        BUMP_X_FIELD_SIDE, 2.5, // was 2.5
                        Rotation2d.fromDegrees(90)); // rotation was 0
        public static Supplier<Pose2d> rightBump_AllianceToFieldEnd = () -> new Pose2d(
                        BUMP_X_FIELD_SIDE, 2.25, // was 2.5
                        Rotation2d.fromDegrees(RIGHT_BUMP_FIELD_ANGLE)); // rotation was 0

        public static Supplier<Pose2d> rightBump_FieldToAllianceStart = () -> new Pose2d(
                        BUMP_X_FIELD_SIDE, 2.25,
                        Rotation2d.fromDegrees(RIGHT_BUMP_FIELD_ANGLE)); // was 180
        public static Supplier<Pose2d> rightBump_FieldToAllianceEnd = () -> new Pose2d(
                        BUMP_X_ALLIANCE_SIDE, 2.25,
                        Rotation2d.fromDegrees(RIGHT_BUMP_ALLIANCE_ANGLE)); // was 180
        public static Supplier<Pose2d> rightBump_FieldToAllianceEndDos = () -> new Pose2d(
                        BUMP_X_ALLIANCE_SIDE, 2.5,
                        Rotation2d.fromDegrees(90)); // was 180
        // #endregion

        // #region SHOOTER Poses
        public static Supplier<Pose2d> FrontHubShoot = () -> new Pose2d(3.069361, 4.034638, Rotation2d.fromDegrees(0));
        public static Supplier<Pose2d> IntakeIN_FrontHubShoot = () -> new Pose2d(3.569361, 4.034638,
                        Rotation2d.fromDegrees(0));
        public static Supplier<Pose2d> IntakeOUT_FrontHubShoot = () -> new Pose2d(3.469361, 4.034638,
                        Rotation2d.fromDegrees(0));
        public static Supplier<Pose2d> RightHubShoot = () -> new Pose2d(3.069361, 3.034638, Rotation2d.fromDegrees(0));
        // #endregion

        // #region Center Harvest Poses
        // y position to start center harvesting on the right side
        // TODO: Change for actual field
        private static double RIGHT_START_HARVEST_HORIZONTAL_POINT = 3; // was 1
        private static double RIGHT_END_HARVEST_HORIZONTAL_POINT = 5; // was 6
        private static double LEFT_START_HARVEST_HORIZONTAL_POINT = 6; // was 7 //was 6 at Finney
        private static double LEFT_END_HARVEST_HORIZONTAL_POINT = 2.5; // was 2
        private static double LEFT_QUAD_HARVEST_END_POINT = 3; // was 7
        private static double RIGHT_QUAD_HARVEST_END_POINT = 4.75; // was 7
        private static double RIGHT_START_SECOND_SWEEP_HORIZONTAL_POINT = 1;
        private static double RIGHT_END_SECOND_SWEEP_HORIZONTAL_POINT = 3.5;
        private static double LEFT_START_SECOND_SWEEP_HORIZONTAL_POINT = 7;
        private static double LEFT_END_SECOND_SWEEP_HORIZONTAL_POINT = 4.5;

        // centerRightIntakeStart was (7.75, 1, 90)
        public static Supplier<Pose2d> centerRightIntakeStart = () -> new Pose2d(7.95,
                        RIGHT_START_HARVEST_HORIZONTAL_POINT, Rotation2d.fromDegrees(90));
        // centerRightIntakeEnd was (7.75, 6, 90)
        public static Supplier<Pose2d> centerRightIntakeEnd = () -> new Pose2d(7.95,
                        RIGHT_END_HARVEST_HORIZONTAL_POINT, Rotation2d.fromDegrees(90));
        // centerRightIntakeStart was (7.75, 7, 270)
        public static Supplier<Pose2d> centerLeftIntakeStart = () -> new Pose2d(6.5,
                        LEFT_START_HARVEST_HORIZONTAL_POINT, Rotation2d.fromDegrees(270));
        // centerLeftIntakeEnd was (7.75, 2, 270)
        public static Supplier<Pose2d> centerLeftIntakeEnd = () -> new Pose2d(7.75,
                        LEFT_END_HARVEST_HORIZONTAL_POINT, Rotation2d.fromDegrees(270));
        // rotation was 180
        public static Supplier<Pose2d> centerRightIntakeEndLookHub = () -> new Pose2d(7.75,
                        RIGHT_END_HARVEST_HORIZONTAL_POINT, Rotation2d.fromDegrees(200));

        public static Supplier<Pose2d> centerLeftIntakeEndLookHub = () -> new Pose2d(7.75,
                        LEFT_END_HARVEST_HORIZONTAL_POINT, Rotation2d.fromDegrees(160));
        // Center Harvest Second Sweep
        public static Supplier<Pose2d> centerRightIntake_SecondSweep = () -> new Pose2d(6,
                        LEFT_END_HARVEST_HORIZONTAL_POINT, Rotation2d.fromDegrees(270));
        public static Supplier<Pose2d> centerLeftIntake_SecondSweep = () -> new Pose2d(6.5,
                        RIGHT_END_HARVEST_HORIZONTAL_POINT, Rotation2d.fromDegrees(90));

        public static Supplier<Pose2d> centerLine_RightIntakeStart = () -> new Pose2d(8.5,
                        RIGHT_START_HARVEST_HORIZONTAL_POINT, Rotation2d.fromDegrees(90));

        public static Supplier<Pose2d> centerLine_RightIntakeEnd = () -> new Pose2d(8.5,
                        RIGHT_END_HARVEST_HORIZONTAL_POINT, Rotation2d.fromDegrees(90));

        public static Supplier<Pose2d> centerLine_LeftIntakeStart = () -> new Pose2d(8.5,
                        LEFT_START_HARVEST_HORIZONTAL_POINT, Rotation2d.fromDegrees(270));

        public static Supplier<Pose2d> centerLine_LeftIntakeEnd = () -> new Pose2d(8.5,
                        LEFT_END_HARVEST_HORIZONTAL_POINT, Rotation2d.fromDegrees(270));
        // #endregion
        // #region Quads

        // centerRightIntakeStart was (7.75, 7, 270)
        public static Supplier<Pose2d> quadRightIntakeStart = () -> new Pose2d(7.95,
                        RIGHT_START_HARVEST_HORIZONTAL_POINT, Rotation2d.fromDegrees(90));
        public static Supplier<Pose2d> quadLeftIntakeStart = () -> new Pose2d(7.95,
                        LEFT_START_HARVEST_HORIZONTAL_POINT, Rotation2d.fromDegrees(270));

        public static Supplier<Pose2d> quadRight = () -> new Pose2d(8, 3.25, Rotation2d.fromDegrees(120)); // was 7.5,
                                                                                                           // 3.5
        public static Supplier<Pose2d> quadLeft = () -> new Pose2d(8, 4.5, Rotation2d.fromDegrees(230)); // was 4.5,
                                                                                                         // 6.5
        // Second Sweeps
        public static Supplier<Pose2d> rightQuadSecondSweep_Start = () -> new Pose2d(6.95,
                        RIGHT_START_SECOND_SWEEP_HORIZONTAL_POINT, Rotation2d.fromDegrees(270));

        public static Supplier<Pose2d> rightQuadSecondSweep_End = () -> new Pose2d(6.55,
                        RIGHT_END_SECOND_SWEEP_HORIZONTAL_POINT, Rotation2d.fromDegrees(90));

        public static Supplier<Pose2d> leftQuadSecondSweep_Start = () -> new Pose2d(6.95,
                        LEFT_START_SECOND_SWEEP_HORIZONTAL_POINT, Rotation2d.fromDegrees(90));

        public static Supplier<Pose2d> leftQuadSecondSweep_End = () -> new Pose2d(6.55,
                        LEFT_END_SECOND_SWEEP_HORIZONTAL_POINT, Rotation2d.fromDegrees(270));

        // #endregion

        // #region DEPOT Poses
        // wall pose is 0.40
        public static Supplier<Pose2d> leftOfDepot_Out = () -> new Pose2d(0.50, 7, Rotation2d.fromDegrees(270));
        public static Supplier<Pose2d> leftOfDepot_In = () -> new Pose2d(0.50, 6.6, Rotation2d.fromDegrees(270));
        public static Supplier<Pose2d> rightOfDepot_Out = () -> new Pose2d(0.50, 5, Rotation2d.fromDegrees(90));
        public static Supplier<Pose2d> rightOfDepot_In = () -> new Pose2d(0.50, 5.4, Rotation2d.fromDegrees(90));

        public static Supplier<Pose2d> depot_BackFace_Out = () -> new Pose2d(1.5, 5.5, Rotation2d.fromDegrees(180));
        public static Supplier<Pose2d> depot_BackFace_In = () -> new Pose2d(0.75, 5.5, Rotation2d.fromDegrees(180));
        public static Supplier<Pose2d> depot_BackFace_End_Dos = () -> new Pose2d(0.50, 5.5,
                        Rotation2d.fromDegrees(180));
        public static Supplier<Pose2d> midOfDepotFaceOut = () -> new Pose2d(0.50, 5.75, Rotation2d.fromDegrees(180));
        public static Supplier<Pose2d> left_midOfDepot_In = () -> new Pose2d(0.75, 6.35, Rotation2d.fromDegrees(180));
        public static Supplier<Pose2d> left_midOfDepot_Out = () -> new Pose2d(1.5, 6.35, Rotation2d.fromDegrees(180));
        public static Supplier<Pose2d> midOfDepot_In = () -> new Pose2d(0.75, 5.75, Rotation2d.fromDegrees(180));
        public static Supplier<Pose2d> midOfDepot_Out = () -> new Pose2d(1.5, 5.75, Rotation2d.fromDegrees(180));

        public static Supplier<Pose2d> towerDodge_Start = () -> new Pose2d(2, 4.85, Rotation2d.fromDegrees(90));
        public static Supplier<Pose2d> towerDodge_End = () -> new Pose2d(0.40, 4.85, Rotation2d.fromDegrees(90));
        public static Supplier<Pose2d> towerDodge_DUCK = () -> new Pose2d(0.40, 4.85, Rotation2d.fromDegrees(90));
        // #endregion

        public static Supplier<Pose2d> LeftMidAlliance = () -> new Pose2d(2, 6, Rotation2d.kZero);

        public static Supplier<Pose2d> behindHub = () -> new Pose2d(10, 4, Rotation2d.fromDegrees(0));
        // #region FIELD CONSTANT Poses
        // Center Pose is 8,4, Blue Center Pose is 2,4,90
        public static Supplier<Pose2d> centerOfField = () -> new Pose2d(8, 4, Rotation2d.fromDegrees(0));
        // #endregion

        public static Supplier<Pose2d> fourMeters = () -> new Pose2d(3.5, 4, Rotation2d.fromDegrees(0));
        public static Supplier<Pose2d> testOffHub = () -> new Pose2d(2, 4, Rotation2d.fromDegrees(0));
}
