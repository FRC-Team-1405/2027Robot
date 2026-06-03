// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot;

import com.ctre.phoenix6.HootAutoReplay;

import edu.wpi.first.wpilibj.DataLogManager;
import edu.wpi.first.wpilibj.DriverStation;
import edu.wpi.first.wpilibj.RobotController;
import edu.wpi.first.wpilibj.TimedRobot;
import edu.wpi.first.wpilibj.Timer;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.CommandScheduler;
import frc.robot.constants.FieldConstants;
import frc.robot.lib.MotorSim.PhysicsSim;
import frc.robot.sim.sjc.PhysicsSim_SJC;
import frc.robot.util.GamePeriod;

public class Robot extends TimedRobot {
    private Command m_autonomousCommand;

    private final RobotContainer m_robotContainer;

    /* log and replay timestamp and joystick data */
    private final HootAutoReplay m_timeAndJoystickReplay = new HootAutoReplay()
            .withTimestampReplay()
            .withJoystickReplay();

    // TODO(2027): Verify autonomous duration for 2027 game rules (was 20.0s in 2026).
    private static final double AUTO_DURATION = 20.0; // seconds
    private static Timer autoTimer = new Timer();

    public Robot() {
        // Start WPILib data logging to /home/lvuser/logs so .wpilog files are created
        // for every match. Also mirror NetworkTables entries into the log file.
        DataLogManager.start("/home/lvuser/logs");
        DriverStation.startDataLog(DataLogManager.getLog());

        m_robotContainer = new RobotContainer();

        GamePeriod.elasticInit();
    }

    private void resetSubsystems_init() {
        // Reset subsystems — schedule stop commands so their initialize() logic runs
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
    }

    @Override
    public void disabledInit() {
        // Flush the data log so all buffered entries are written to disk at end of match
        DataLogManager.getLog().flush();
        // Resetting subsystems here doesn't work
        resetSubsystems_disable();
    }

    @Override
    public void disabledPeriodic() {

    }

    @Override
    public void disabledExit() {

    }

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
        PhysicsSim.getInstance().run();
        m_robotContainer.drivetrain.publishDrivePidErrors();
        m_robotContainer.drivetrain.publishDistanceToHub();
    }

    @Override
    public void autonomousExit() {

    }

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
        m_robotContainer.drivetrain.publishDriveOutputVoltage();
        m_robotContainer.drivetrain.publishMotorCurrent();
        m_robotContainer.intake.publishMotorCurrents();
        m_robotContainer.drivetrain.publishDistanceToHub();
    }

    @Override
    public void teleopExit() {

    }

    @Override
    public void testInit() {
        CommandScheduler.getInstance().cancelAll();
    }

    @Override
    public void testPeriodic() {
    }

    @Override
    public void testExit() {
    }

    @Override
    public void simulationPeriodic() {
        PhysicsSim.getInstance().run();
        PhysicsSim_SJC.getInstance().run();
    }

    public static double getAutonomousTimeLeft() {
        double fmsTime = Timer.getMatchTime();

        // If FMS is giving real match time, use it
        if (fmsTime >= 0) {
            return fmsTime;
        }

        // Otherwise fall back to our own timer
        double elapsed = autoTimer.get();
        double remaining = AUTO_DURATION - elapsed;

        return Math.max(remaining, 0); // never go negative
    }

}
