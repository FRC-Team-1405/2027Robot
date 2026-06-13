// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot;

import com.ctre.phoenix6.HootAutoReplay;

import edu.wpi.first.wpilibj.DataLogManager;
import edu.wpi.first.wpilibj.DriverStation;
import edu.wpi.first.wpilibj.RobotBase;
import edu.wpi.first.wpilibj.Timer;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.CommandScheduler;
import frc.robot.util.GamePeriod;

import org.littletonrobotics.junction.LoggedRobot;
import org.littletonrobotics.junction.Logger;
import org.littletonrobotics.junction.networktables.NT4Publisher;
import org.littletonrobotics.junction.wpilog.WPILOGWriter;

public class Robot extends LoggedRobot {
    private Command m_autonomousCommand;

    private final RobotContainer m_robotContainer;

    private HootAutoReplay m_timeAndJoystickReplay;

    // TODO(2027): Verify autonomous duration for 2027 game rules (was 20.0s in 2026).
    private static final double AUTO_DURATION = 20.0;
    private static Timer autoTimer = new Timer();

    public Robot() {
        // ── AdvantageKit setup — must run before any other initialization ──────
        Logger.recordMetadata("ProjectName", "2027Robot");
        Logger.recordMetadata("RuntimeType", getRuntimeType().toString());

        if (isReal()) {
            Logger.addDataReceiver(new WPILOGWriter("/home/lvuser/logs"));
            Logger.addDataReceiver(new NT4Publisher());
        } else {
            // Live sim: always publish to NT so AdvantageScope/Shuffleboard see real-time data.
            // For log replay use ./gradlew replayWatch (or set AKIT_LOG_PATH env var).
            Logger.addDataReceiver(new NT4Publisher());
        }

        Logger.start();

        // CTRE Hoot replay — initialized after Logger.start() per AKit guidance
        m_timeAndJoystickReplay = new HootAutoReplay()
                .withTimestampReplay()
                .withJoystickReplay();

        if (RobotBase.isReal()) {
            DataLogManager.start("/home/lvuser/logs");
            DriverStation.startDataLog(DataLogManager.getLog());
        }

        m_robotContainer = new RobotContainer();

        GamePeriod.elasticInit();
    }

    private void resetSubsystems_init() {
        CommandScheduler.getInstance().schedule(m_robotContainer.indexer.runStopIndexer());
        CommandScheduler.getInstance().schedule(m_robotContainer.hopper.runStopHopper());
    }

    private void resetSubsystems_disable() {
        CommandScheduler.getInstance().schedule(m_robotContainer.shooter.stopShooter());
        CommandScheduler.getInstance().schedule(m_robotContainer.indexer.runStopIndexer());
        CommandScheduler.getInstance().schedule(m_robotContainer.hopper.runStopHopper());
    }

    private static void startAutoTimer() {
        autoTimer.reset();
        autoTimer.start();
    }

    @Override
    public void robotPeriodic() {
        m_timeAndJoystickReplay.update();
        m_robotContainer.correctOdometry();
        CommandScheduler.getInstance().run();
        RobotContainer.updateNT();
        RobotContainer.publishRobotData();
        m_robotContainer.drivetrain.publishDriveOutputVoltage();
        m_robotContainer.drivetrain.publishMotorCurrent();
        m_robotContainer.drivetrain.publishDrivePidErrors();
        m_robotContainer.drivetrain.publishDistanceToHub();
        m_robotContainer.intake.publishMotorCurrents();
    }

    @Override
    public void disabledInit() {
        if (RobotBase.isReal()) {
            DataLogManager.getLog().flush();
        }
        resetSubsystems_disable();
    }

    @Override
    public void disabledPeriodic() {}

    @Override
    public void disabledExit() {}

    @Override
    public void autonomousInit() {
        resetSubsystems_init();
        startAutoTimer();

        m_autonomousCommand = m_robotContainer.getAutonomousCommand();
        if (m_autonomousCommand != null) {
            CommandScheduler.getInstance().schedule(m_autonomousCommand);
        }
    }

    @Override
    public void autonomousPeriodic() {
    }

    @Override
    public void autonomousExit() {}

    @Override
    public void teleopInit() {
        if (m_autonomousCommand != null) {
            CommandScheduler.getInstance().cancel(m_autonomousCommand);
        }
        GamePeriod.elasticTeleopInit();
        resetSubsystems_init();
    }

    @Override
    public void teleopPeriodic() {
        GamePeriod.elasticPeriodic();
    }

    @Override
    public void teleopExit() {}

    @Override
    public void testInit() {
        CommandScheduler.getInstance().cancelAll();
    }

    @Override
    public void testPeriodic() {}

    @Override
    public void testExit() {}

    @Override
    public void simulationPeriodic() {
        // IO sim classes manage their own physics — no global sim runner needed.
    }

    public static double getAutonomousTimeLeft() {
        double fmsTime = Timer.getMatchTime();
        if (fmsTime >= 0) return fmsTime;
        return Math.max(AUTO_DURATION - autoTimer.get(), 0);
    }
}
