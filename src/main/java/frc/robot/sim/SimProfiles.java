// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot.sim;

import static edu.wpi.first.units.Units.RotationsPerSecond;
import static edu.wpi.first.units.Units.RotationsPerSecondPerSecond;
import static edu.wpi.first.units.Units.Second;
import static edu.wpi.first.units.Units.Volts;

import com.ctre.phoenix6.configs.MotionMagicConfigs;
import com.ctre.phoenix6.configs.TalonFXConfiguration;
import com.ctre.phoenix6.hardware.TalonFX;

import edu.wpi.first.wpilibj.RobotBase;

/** Add your docs here. */
public class SimProfiles {
    private static TalonFXSimProfile simShooter;
    private static TalonFXSimProfile simIndexer;
    @SuppressWarnings("unused")
    private static TalonFXSimProfile simArm;
    @SuppressWarnings("unused")
    private static TalonFXSimProfile simInput;
    @SuppressWarnings("unused")
    private static TalonFXSimProfile simClimber;
    @SuppressWarnings("unused")
    private static TalonFXSimProfile simGrabber;
    @SuppressWarnings("unused")
    private static TalonFXSimProfile simHopper;
    @SuppressWarnings("unused")
    private static TalonFXSimProfile simIntake;
    @SuppressWarnings("unused")
    private static TalonFXSimProfile simPickup;

    public static void initIntake(TalonFX motor) {
        if (!RobotBase.isSimulation())
            return;

        // Sim-only: override with sim-friendly gains. Real config is in Intake.java.
        TalonFXConfiguration configs = new TalonFXConfiguration();

        configs.Slot0.kS = 0.1;
        configs.Slot0.kV = 0.12;
        configs.Slot0.kP = 0.66;
        configs.Slot0.kI = 0;
        configs.Slot0.kD = 0;
        configs.Voltage.withPeakForwardVoltage(Volts.of(8))
                .withPeakReverseVoltage(Volts.of(-8));

        configs.MotionMagic
                .withMotionMagicCruiseVelocity(RotationsPerSecond.of(80))
                .withMotionMagicAcceleration(RotationsPerSecondPerSecond.of(160))
                .withMotionMagicJerk(RotationsPerSecondPerSecond.per(Second).of(1600));

        motor.getConfigurator().apply(configs);

        simIntake = new TalonFXSimProfile(motor).withRotorInertia(0.001).build();
        PhysicsSim.getInstance().addTalonFX(simIntake);
    }

    public static void initPickup(TalonFX motor) {
        if (!RobotBase.isSimulation())
            return;

        // Sim-only: override with sim-friendly gains. Real config is in Intake.java.
        TalonFXConfiguration configs = new TalonFXConfiguration();

        configs.Slot0.kS = 0.1;
        configs.Slot0.kV = 0.12;
        configs.Slot0.kP = 0.66;
        configs.Slot0.kI = 0;
        configs.Slot0.kD = 0;
        configs.Voltage.withPeakForwardVoltage(Volts.of(8))
                .withPeakReverseVoltage(Volts.of(-8));

        configs.MotionMagic
                .withMotionMagicCruiseVelocity(RotationsPerSecond.of(5))
                .withMotionMagicAcceleration(RotationsPerSecondPerSecond.of(10))
                .withMotionMagicJerk(RotationsPerSecondPerSecond.per(Second).of(100));

        motor.getConfigurator().apply(configs);

        simPickup = new TalonFXSimProfile(motor).withRotorInertia(0.001).build();
        PhysicsSim.getInstance().addTalonFX(simPickup);
    }

    public static void initShooter(TalonFX motor) {
        if (!RobotBase.isSimulation())
            return;

        TalonFXConfiguration configs = new TalonFXConfiguration();

        configs.Slot0.kS = 0.1; // To account for friction, add 0.1 V of static feedforward
        configs.Slot0.kV = 0.12; // Kraken X60 is a 500 kV motor, 500 rpm per V = 8.333 rps per V, 1/8.33 = 0.12
                                 // volts / rotation per second
        configs.Slot0.kP = 0.66; // An error of 1 rotation per second results in 0.11 V output
        configs.Slot0.kI = 0; // No output for integrated error
        configs.Slot0.kD = 0; // No output for error derivative
        // Peak output of 8 volts
        configs.Voltage.withPeakForwardVoltage(Volts.of(8))
                .withPeakReverseVoltage(Volts.of(-8));

        motor.getConfigurator().apply(configs);

        simShooter = new TalonFXSimProfile(motor).withRotorInertia(0.1).build();
        PhysicsSim.getInstance().addTalonFX(simShooter);
    }

    public static void initHopper(TalonFX motor) {
        if (!RobotBase.isSimulation())
            return;

        TalonFXConfiguration configs = new TalonFXConfiguration();

        configs.Slot0.kS = 0.1; // To account for friction, add 0.1 V of static feedforward
        configs.Slot0.kV = 0.12; // Kraken X60 is a 500 kV motor, 500 rpm per V = 8.333 rps per V, 1/8.33 = 0.12
                                 // volts / rotation per second
        configs.Slot0.kP = 0.66; // An error of 1 rotation per second results in 0.11 V output
        configs.Slot0.kI = 0; // No output for integrated error
        configs.Slot0.kD = 0; // No output for error derivative
        // Peak output of 8 volts
        configs.Voltage.withPeakForwardVoltage(Volts.of(8))
                .withPeakReverseVoltage(Volts.of(-8));

        configs.MotionMagic
                .withMotionMagicCruiseVelocity(RotationsPerSecond.of(5))
                .withMotionMagicAcceleration(RotationsPerSecondPerSecond.of(10))
                .withMotionMagicJerk(RotationsPerSecondPerSecond.per(Second).of(100));

        motor.getConfigurator().apply(configs);

        simHopper = new TalonFXSimProfile(motor).withRotorInertia(0.001).build();
        PhysicsSim.getInstance().addTalonFX(simHopper);
    }

    public static void initClimber(TalonFX motor) {
        if (!RobotBase.isSimulation())
            return;

        TalonFXConfiguration configs = new TalonFXConfiguration();

        configs.Slot0.kS = 0.1; // To account for friction, add 0.1 V of static feedforward
        configs.Slot0.kV = 0.12; // Kraken X60 is a 500 kV motor, 500 rpm per V = 8.333 rps per V, 1/8.33 = 0.12
                                 // volts / rotation per second
        configs.Slot0.kP = 0.66; // An error of 1 rotation per second results in 0.11 V output
        configs.Slot0.kI = 0; // No output for integrated error
        configs.Slot0.kD = 0; // No output for error derivative
        // Peak output of 8 volts
        configs.Voltage.withPeakForwardVoltage(Volts.of(8))
                .withPeakReverseVoltage(Volts.of(-8));

        configs.MotionMagic
                .withMotionMagicCruiseVelocity(RotationsPerSecond.of(5))
                .withMotionMagicAcceleration(RotationsPerSecondPerSecond.of(10))
                .withMotionMagicJerk(RotationsPerSecondPerSecond.per(Second).of(100));

        motor.getConfigurator().apply(configs);

        simClimber = new TalonFXSimProfile(motor).withRotorInertia(0.001).build();
        PhysicsSim.getInstance().addTalonFX(simClimber);
    }

    public static void initGrabber(TalonFX motor) {
        if (!RobotBase.isSimulation())
            return;

        TalonFXConfiguration configs = new TalonFXConfiguration();

        configs.Slot0.kS = 0.1; // To account for friction, add 0.1 V of static feedforward
        configs.Slot0.kV = 0.12; // Kraken X60 is a 500 kV motor, 500 rpm per V = 8.333 rps per V, 1/8.33 = 0.12
                                 // volts / rotation per second
        configs.Slot0.kP = 0.66; // An error of 1 rotation per second results in 0.11 V output
        configs.Slot0.kI = 0; // No output for integrated error
        configs.Slot0.kD = 0; // No output for error derivative
        // Peak output of 8 volts
        configs.Voltage.withPeakForwardVoltage(Volts.of(8))
                .withPeakReverseVoltage(Volts.of(-8));

        configs.MotionMagic
                .withMotionMagicCruiseVelocity(RotationsPerSecond.of(5))
                .withMotionMagicAcceleration(RotationsPerSecondPerSecond.of(10))
                .withMotionMagicJerk(RotationsPerSecondPerSecond.per(Second).of(100));

        motor.getConfigurator().apply(configs);

        simGrabber = new TalonFXSimProfile(motor).withRotorInertia(0.001).build();
        PhysicsSim.getInstance().addTalonFX(simGrabber);
    }

    public static void initIndexer(TalonFX motor) {
        if (!RobotBase.isSimulation())
            return;

        TalonFXConfiguration configs = new TalonFXConfiguration();

        configs.Slot0.kS = 0.1; // To account for friction, add 0.1 V of static feedforward
        configs.Slot0.kV = 0.12; // Kraken X60 is a 500 kV motor, 500 rpm per V = 8.333 rps per V, 1/8.33 = 0.12
                                 // volts / rotation per second
        configs.Slot0.kP = 0.66; // An error of 1 rotation per second results in 0.11 V output
        configs.Slot0.kI = 0; // No output for integrated error
        configs.Slot0.kD = 0; // No output for error derivative
        // Peak output of 8 volts
        configs.Voltage.withPeakForwardVoltage(Volts.of(8))
                .withPeakReverseVoltage(Volts.of(-8));

        configs.MotionMagic
                .withMotionMagicCruiseVelocity(RotationsPerSecond.of(5))
                .withMotionMagicAcceleration(RotationsPerSecondPerSecond.of(10))
                .withMotionMagicJerk(RotationsPerSecondPerSecond.per(Second).of(100));

        motor.getConfigurator().apply(configs);

        simIndexer = new TalonFXSimProfile(motor) {
            private double lastFire = 0;

            public void run() {
                super.run();

                double fire = _motorSim.getAngularPositionRotations() / 50;
                if (fire > lastFire) {
                    lastFire = fire;
                    SimProfiles.simulateFire();
                }
            }
        }.withRotorInertia(0.001).build();
        PhysicsSim.getInstance().addTalonFX(simIndexer);
    }

    private static void simulateFire() {
        if (simShooter != null)
            simShooter.temporaryLoad(0.5, 20);
        ;
    }

    public static void initArm(TalonFX motor) {
        if (!RobotBase.isSimulation())
            return;

        TalonFXConfiguration configs = new TalonFXConfiguration();

        configs.Slot0.kS = 0.1; // To account for friction, add 0.1 V of static feedforward
        configs.Slot0.kV = 0.12; // Kraken X60 is a 500 kV motor, 500 rpm per V = 8.333 rps per V, 1/8.33 = 0.12
                                 // volts / rotation per second
        configs.Slot0.kP = 0.66; // An error of 1 rotation per second results in 0.11 V output
        configs.Slot0.kI = 0; // No output for integrated error
        configs.Slot0.kD = 0; // No output for error derivative
        // Peak output of 8 volts
        configs.Voltage.withPeakForwardVoltage(Volts.of(8))
                .withPeakReverseVoltage(Volts.of(-8));

        motor.getConfigurator().apply(configs);

        simIndexer = new TalonFXSimProfile(motor).withRotorInertia(0.001).build();
        PhysicsSim.getInstance().addTalonFX(simIndexer);
    }

    public static void initInput(TalonFX motor) {
        if (!RobotBase.isSimulation())
            return;

        TalonFXConfiguration configs = new TalonFXConfiguration();

        configs.Slot0.kS = 0.1; // To account for friction, add 0.1 V of static feedforward
        configs.Slot0.kV = 0.12; // Kraken X60 is a 500 kV motor, 500 rpm per V = 8.333 rps per V, 1/8.33 = 0.12
                                 // volts / rotation per second
        configs.Slot0.kP = 0.66; // An error of 1 rotation per second results in 0.11 V output
        configs.Slot0.kI = 0; // No output for integrated error
        configs.Slot0.kD = 0; // No output for error derivative
        // Peak output of 8 volts
        configs.Voltage.withPeakForwardVoltage(Volts.of(8))
                .withPeakReverseVoltage(Volts.of(-8));

        motor.getConfigurator().apply(configs);

        simIndexer = new TalonFXSimProfile(motor).withRotorInertia(0.001).build();
        PhysicsSim.getInstance().addTalonFX(simIndexer);
    }

}