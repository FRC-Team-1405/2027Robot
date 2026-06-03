package frc.robot.lib;

import java.util.HashMap;
import java.util.function.Supplier;

import com.pathplanner.lib.auto.NamedCommands;

import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.wpilibj.DriverStation;
import edu.wpi.first.wpilibj.smartdashboard.SendableChooser;
import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.Commands;
import frc.robot.commands.Autos.AutoPoses;
import frc.robot.commands.Autos.CommandsForAutos;
import frc.robot.commands.Autos.Full_Autos;
import frc.robot.commands.PidToPose.PidToPoseCommands;
import frc.robot.subsystems.AdjustableHood;
import frc.robot.subsystems.Climber;
import frc.robot.subsystems.CommandSwerveDrivetrain;
import frc.robot.subsystems.Hopper;
import frc.robot.subsystems.Indexer;
import frc.robot.subsystems.Intake;
import frc.robot.subsystems.Shooter;
import frc.robot.subsystems.SwerveFeatures;

public class AutoCommands {
        private static final SendableChooser<Command> autoChooser = new SendableChooser<>();

        private static final String AUTO_SMARTDASHBOARD_FOLDER = "Auto";

        public static void setupAutoChooser(CommandSwerveDrivetrain drivetrain, Climber climber, Intake intake,
                        Hopper hopper,
                        Indexer indexer,
                        Shooter shooter,
                        AdjustableHood hood,
                        SwerveFeatures swerveFeatures,
                        CommandsForAutos commandsForAutos) {
                SmartDashboard.putBoolean(AUTO_SMARTDASHBOARD_FOLDER + "/Auto Mode Enable", false);
                SmartDashboard.putData(AUTO_SMARTDASHBOARD_FOLDER + "/Auto Mode", autoChooser);

                // this HAS to go after AutoPilotCommands
                AutoCommands.configureAutos(autoChooser, drivetrain);

        }

        public static void configureAutos(SendableChooser<Command> chooser, CommandSwerveDrivetrain drivetrain) {
                HashMap<String, Command> commandsToAddToChooser = new HashMap<>();

                commandsToAddToChooser.put("JUST_SHOOT_FROM_ANYWHERE",
                                NamedCommands.getCommand("JUST_SHOOT_FROM_ANYWHERE"));

                // commandsToAddToChooser.put("blueCenterToDepot",
                // NamedCommands.getCommand("blueCenterToDepot"));
                // // commandsToAddToChooser.put("DepotFaceIn",
                // NamedCommands.getCommand("DepotFaceIn"));

                // commandsToAddToChooser.put("JUSTSHOOT",
                // NamedCommands.getCommand("JUSTSHOOT"));
                // commandsToAddToChooser.put("LeftStart_JUSTSHOOT",
                // NamedCommands.getCommand("LeftStart_JUSTSHOOT"));

                // TODO:BUMP AUTOS
                // commandsToAddToChooser.put("rightBumpToField",
                // NamedCommands.getCommand("rightBumpToField"));
                // commandsToAddToChooser.put("leftBumpToField",
                // NamedCommands.getCommand("leftBumpToField"));
                // commandsToAddToChooser.put("rightBumpToAlliance",
                // NamedCommands.getCommand("rightBumpToAlliance"));
                // commandsToAddToChooser.put("leftBumpToAlliance",
                // NamedCommands.getCommand("leftBumpToAlliance"));

                // commandsToAddToChooser.put("ShootFromDepot",
                // NamedCommands.getCommand("ShootFromDepot"));
                // commandsToAddToChooser.put("TESTCenterHarvest",
                // NamedCommands.getCommand("TESTCenterHarvest"));
                // commandsToAddToChooser.put("LeftStartDepotScore",
                // NamedCommands.getCommand("LeftStartDepotScore"));
                // commandsToAddToChooser.put("RightStartDepotScore",
                // NamedCommands.getCommand("RightStartDepotScore"));
                // commandsToAddToChooser.put("TheShowboater",
                // NamedCommands.getCommand("TheShowboater"));

                // commandsToAddToChooser.put("TEST", NamedCommands.getCommand("TEST"));
                // commandsToAddToChooser.put("fourMeters",
                // NamedCommands.getCommand("fourMeters"));

                // Feeding station
                // commandsToAddToChooser.put("RightStartFeedingStationScore",
                // NamedCommands.getCommand("RightStartFeedingStationScore"));
                // commandsToAddToChooser.put("CenterStartFeedingStationScore",
                // NamedCommands.getCommand("CenterStartFeedingStationScore"));
                // commandsToAddToChooser.put("LeftStartFeedingStationScore",
                // NamedCommands.getCommand("LeftStartFeedingStationScore"));

                // NamedCommands.registerCommand("RightStartFeedingStationScore",
                // RightStartFeedingStationScore);
                // NamedCommands.registerCommand("CenterStartFeedingStationScore",
                // CenterStartFeedingStationScore);
                // NamedCommands.registerCommand("LeftStartFeedingStationScore",
                // LeftStartFeedingStationScore);

                commandsToAddToChooser.put("RightStartCenterHarvestInLeft",
                                NamedCommands.getCommand("RightStartCenterHarvestInLeft"));
                commandsToAddToChooser.put("LeftStartCenterHarvestInRight",
                                NamedCommands.getCommand("LeftStartCenterHarvestInRight"));
                commandsToAddToChooser.put("RightStartCenterHarvest_SecondSweep_TOP_FIRST",
                                NamedCommands.getCommand("RightStartCenterHarvest_SecondSweep_TOP_FIRST"));
                commandsToAddToChooser.put("LeftStartCenterHarvest_SecondSweep_TOP_FIRST",
                                NamedCommands.getCommand("LeftStartCenterHarvest_SecondSweep_TOP_FIRST"));
                commandsToAddToChooser.put("RightStartCenterHarvest_SecondSweep_LOW_FIRST",
                                NamedCommands.getCommand("RightStartCenterHarvest_SecondSweep_LOW_FIRST"));
                commandsToAddToChooser.put("LeftStartCenterHarvest_SecondSweep_LOW_FIRST",
                                NamedCommands.getCommand("LeftStartCenterHarvest_SecondSweep_LOW_FIRST"));

                // commandsToAddToChooser.put("LeftDepotShootCenterHarvestInLeftShoot",
                // NamedCommands.getCommand("LeftDepotShootCenterHarvestInLeftShoot"));
                commandsToAddToChooser.put("RightQuad",
                                NamedCommands.getCommand("RightQuad"));
                commandsToAddToChooser.put("LeftQuad",
                                NamedCommands.getCommand("LeftQuad"));
                commandsToAddToChooser.put("Zac_RightQuad",
                                NamedCommands.getCommand("Zac_RightQuad"));
                commandsToAddToChooser.put("Zac_LeftQuad",
                                NamedCommands.getCommand("Zac_LeftQuad"));
                // commandsToAddToChooser.put("Right_Yum_Middle",
                // NamedCommands.getCommand("Right_Yum_Middle"));

                // Add all commands in Map to chooser
                commandsToAddToChooser.keySet().stream()
                                .forEach(name -> chooser.addOption(name, commandsToAddToChooser.get(name)));

                initShootPositions();

        }

        public static SendableChooser<Supplier<Pose2d>> shootingPositions = new SendableChooser<>();

        public static void initShootPositions() {
                shootingPositions.addOption("FrontHub", AutoPoses.FrontHubShoot);
                shootingPositions.addOption("IntakeIN_FrontHub", AutoPoses.IntakeIN_FrontHubShoot);
                shootingPositions.addOption("IntakeOUT_FrontHub", AutoPoses.IntakeOUT_FrontHubShoot);
                shootingPositions.addOption("RightHub", AutoPoses.RightHubShoot);

                shootingPositions.setDefaultOption("FrontHub", AutoPoses.FrontHubShoot);
                SmartDashboard.putData(AUTO_SMARTDASHBOARD_FOLDER + " Shooting Position", shootingPositions);
        }

        public static Supplier<Pose2d> getShootPosition() {
                return shootingPositions.getSelected();
                // SmartDashboard.getString(AUTO_SMARTDASHBOARD_FOLDER + "shooterPositions",
                // NamedCommands.getCommand("FrontHubShoot"));

        }

        public static Command getAutonomousCommand() {
                /* Run the path selected from the auto chooser */
                if (DriverStation.isFMSAttached()
                                || SmartDashboard.getBoolean(AUTO_SMARTDASHBOARD_FOLDER + "/Auto Mode Enable", false)) {
                        SmartDashboard.putBoolean(AUTO_SMARTDASHBOARD_FOLDER + "/Auto Mode Enable", false);
                        if (Full_Autos.OVERRIDE_AUTO_COMMAND != null) {
                                return Full_Autos.OVERRIDE_AUTO_COMMAND;
                        }
                        return autoChooser.getSelected();
                } else {
                        return Commands.print("Auto Disabled");
                }

        }
}