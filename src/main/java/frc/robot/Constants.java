// Copyright (c) FIRST and other WPILib contributors.
// Open Source Software; you can modify and/or share it under the terms of
// the WPILib BSD license file in the root directory of this project.

package frc.robot;

import static edu.wpi.first.units.Units.Feet;
import static edu.wpi.first.units.Units.Inches;
import static edu.wpi.first.units.Units.Kilograms;
import static edu.wpi.first.units.Units.Meters;
import static edu.wpi.first.units.Units.Pounds;
import static edu.wpi.first.units.Units.RotationsPerSecond;

import java.util.HashMap;
import java.util.function.Supplier;

import edu.wpi.first.units.measure.AngularVelocity;
import edu.wpi.first.units.measure.Distance;
import edu.wpi.first.wpilibj.Preferences;

/** Add your docs here. */
public class Constants {
    public static class CANBus {
        public static final int CLIMBER_MOTOR = 45;
        public static final int CLIMBER_GRABBER = 37;
        public static final int HOPPER_MOTOR = 25;
        public static final int INTAKE_MOTOR = 28;
        public static final int PICKUP_MOTOR = 29;

        public static final int INDEXER_MOTOR = 40;
        public static final int SHOOTER_MOTOR_1 = 41;
        public static final int SHOOTER_MOTOR_2 = 42;
        public static final int SHOOTER_MOTOR_3 = 43;

        public static final int ADJUSTABLE_SHOOTER_MOTOR = 24;

    }

    public static class ShooterPIDConfig {
        public static final double KP = 0.3;
        public static final double KI = 0.0;
        public static final double KD = 0.0;
        public static final double KV = 0.12;
        public static final double KS = 0.15;
        public static final double PEAK_FORWARD_VOLTAGE = 10.0;
        public static final double PEAK_REVERSE_VOLTAGE = -10.0;
        public static final double SUPPLY_CURRENT_LIMIT = 40;
        public static final double STATOR_CURRENT_LIMIT = 60;
        public static final double MOTION_MAGIC_ACCELERATION = 60.0;
        public static final int FILTER_WINDOW = 50;
        public static final double TARGET_MATCH_TOLERANCE = 1.0;
    }

    public static class ShooterPhysicalProperties {
        // Flywheel physical properties
        public static final double FLYWHEEL_DIAMETER_INCHES = 2.25;
        public static final double FLYWHEEL_WEIGHT_LBS = 6.0;

        // Gear ratio: wheel spins 1.8x faster than motor output (9:5 ratio, 36:20)
        public static final double MOTOR_TO_WHEEL_GEAR_RATIO = 1.8;

        // Moment of inertia calculation for simulation
        // Approximating flywheel as solid cylinder: I = (1/2) * m * r^2
        // Using WPILib Units for conversion:
        // mass = 6.0 lbs, radius = 1.125 inches
        // I = 0.5 * mass_kg * radius_m^2
        private static final double FLYWHEEL_MASS_KG = Pounds.of(FLYWHEEL_WEIGHT_LBS).in(Kilograms);
        private static final double FLYWHEEL_RADIUS_M = Inches.of(FLYWHEEL_DIAMETER_INCHES / 2.0).in(Meters);
        public static final double FLYWHEEL_MOMENT_OF_INERTIA = 0.5 * FLYWHEEL_MASS_KG * FLYWHEEL_RADIUS_M
                * FLYWHEEL_RADIUS_M; // kg*m^2

        public static final double FUEL_WEIGHT_LBS = 0.5; // Approximate weight of a fuel (ball)
    }

    public static class ShooterPreferences {
        // Shooter speeds
        public static final AngularVelocity SHORT = RotationsPerSecond.of(38);
        public static final AngularVelocity MEDIUM = RotationsPerSecond.of(42);
        public static final AngularVelocity LONG = RotationsPerSecond.of(50);
        public static final AngularVelocity LONGER = RotationsPerSecond.of(85);
        public static final AngularVelocity LUDICROUS_SPEED = RotationsPerSecond.of(90);
        public static final AngularVelocity DYNAMIC = RotationsPerSecond.of(20);
        public static final AngularVelocity MAX = RotationsPerSecond.of(90);

        // Shooting distances
        // desired robot distances for each shooting speed
        public static Supplier<Double> SHORT_DISTANCE = () -> 1.4;
        public static Supplier<Double> MEDIUM_DISTANCE = () -> 1.9542;
        public static Supplier<Double> LONG_DISTANCE = () -> 2.5;
        public static Supplier<Double> LONGER_DISTANCE = () -> 3.0;

        public static final HashMap<AngularVelocity, Supplier<Double>> SHOOTER_SPEED_TO_DISTANCE = new HashMap<>();
        static {
            SHOOTER_SPEED_TO_DISTANCE.put(SHORT, SHORT_DISTANCE);
            SHOOTER_SPEED_TO_DISTANCE.put(MEDIUM, MEDIUM_DISTANCE);
            SHOOTER_SPEED_TO_DISTANCE.put(LONG, LONG_DISTANCE);
            SHOOTER_SPEED_TO_DISTANCE.put(LONGER, LONGER_DISTANCE);

        };

        public static final AngularVelocity INDEXER_VELOCITY;

        public static final double TIGHT;
        public static final double WIDE;
        public static final int STABLE_COUNT;

        public static AngularVelocity distanceToVelocity(Distance distance) {
            double temp = distance.in(Feet);
            return RotationsPerSecond.of(temp * 5);
        }

        static {
            // Indexer Velocities
            Preferences.initDouble("IndexerVelocities/IndexerVelocity", 35);
            INDEXER_VELOCITY = RotationsPerSecond.of(50);

            TIGHT = 3;
            WIDE = 5;
            STABLE_COUNT = 5;
        }
    }

    public static class IndexerPreferences {

        // PID gains for indexer roller motor (MotionMagic velocity control)
        public static final double KS = 0.1;
        public static final double KV = 0.12;
        public static final double KP = 0.8;
        public static final double KI = 0.0;
        public static final double KD = 0.0;

        // Voltage limits
        public static final double PEAK_FORWARD_VOLTAGE = 10.0;
        public static final double PEAK_REVERSE_VOLTAGE = -10.0;

        // MotionMagic profile for indexer roller
        public static final double CRUISE_VELOCITY = 40.0; // rotations per second
        public static final double ACCELERATION = 100.0; // rotations per second^2

        public static final double STATOR_CURRENT_LIMIT = 60;
        public static final double SUPPLY_CURRENT_LIMIT = 50;
    }

    public static class ClimberPreferences {
        public static final double CLIMBER_EXTEND_POSITION;
        public static final double CLIMBER_RETRACT_POSITION;
        public static final double GRABBER_OPEN_POSITION;
        public static final double GRABBER_CLOSED_POSITION;
        public static final double POSITION_TOLERANCE;
        public static final double SETTLE_MAX;

        static {
            Preferences.initDouble("Climber/Arm/Extended", 100.0);
            CLIMBER_EXTEND_POSITION = Preferences.getDouble("Climber/Arm/Extended", 100.0);

            Preferences.initDouble("Climber/Arm/Retracted", 0.0);
            CLIMBER_RETRACT_POSITION = Preferences.getDouble("Climber/Arm/Retracted", 0.0);

            Preferences.initDouble("Climber/Grabber/Open", 50.0);
            GRABBER_OPEN_POSITION = Preferences.getDouble("Climber/Grabber/Open", 50.0);

            Preferences.initDouble("Climber/Grabber/Closed", 0.0);
            GRABBER_CLOSED_POSITION = Preferences.getDouble("Climber/Grabber/Closed", 0.0);

            Preferences.initDouble("Climber/PositionTolerance", 1.0);
            POSITION_TOLERANCE = Preferences.getDouble("Climber/PositionTolerance", 1.0);

            Preferences.initDouble("Climber/SettleMax", 3);
            SETTLE_MAX = Preferences.getDouble("Climber/SettleMax", 3);
        }
    }

    public static class HoodPreferences {

        public static final double SERVO_FULL_RANGE_SECONDS = 5.0;
        public static final double SERVO_SHORT_PERCENTAGE = 0.25;
        public static final double SERVO_MEDIUM_PERCENTAGE = 0.3;
        public static final double SERVO_LONG_PERCENTAGE = 0.3;

        // static {
        // Preferences.initDouble("Hood/Servo Full Range Seconds", 5.0);
        // SERVO_FULL_RANGE_SECONDS = Preferences.getDouble("Hood/Servo Full Range
        // Seconds", 5.0);

        // // Positions are a percentage of a full range of motion
        // Preferences.initDouble("Hood/Servo Short Position", 0.1);
        // SERVO_SHORT_PERCENTAGE = Preferences.getDouble("Hood/Servo Short Position",
        // 0.1);

        // Preferences.initDouble("Hood/Servo Medium Position", 0.2);
        // SERVO_MEDIUM_PERCENTAGE = Preferences.getDouble("Hood/Servo Medium Position",
        // 0.2);

        // Preferences.initDouble("Hood/Servo Long Position", 0.5);
        // SERVO_LONG_PERCENTAGE = Preferences.getDouble("Hood/Servo Long Position",
        // 0.5);
        // }

        public enum HoodAngles {
            ZERO(0),
            SHORT(SERVO_SHORT_PERCENTAGE),
            MEDIUM(SERVO_MEDIUM_PERCENTAGE),
            LONG(SERVO_LONG_PERCENTAGE),
            ONE(1);

            double positionPercentage;

            HoodAngles(double positionPercentage) {
                this.positionPercentage = positionPercentage;
            }

            public double getPositionPercentage() {
                return positionPercentage;
            }
        }

    }

    public static class AutonomousPreferences {

        public static final double WAIT_TIME;
        public static final double WAIT_FEEDER_TIME = 4.0;

        static {
            Preferences.initDouble("Auto Wait Time (Seconds)", 3.0);
            WAIT_TIME = Preferences.getDouble("Auto Wait Time (Seconds)", 3.0);

        }

    }

    public static class HopperPreferences {

        public static final AngularVelocity HOPPER_FORWARD_SPEED;
        public static final AngularVelocity HOPPER_REVERSE_SPEED;

        // PID gains for hopper roller motor (MotionMagic velocity control)
        public static final double KS = 0.1;
        public static final double KV = 0.12;
        public static final double KP = 0.3;
        public static final double KI = 0.0;
        public static final double KD = 0.0;

        // Voltage limits
        public static final double PEAK_FORWARD_VOLTAGE = 10.0;
        public static final double PEAK_REVERSE_VOLTAGE = -10.0;

        // MotionMagic profile for hopper roller
        public static final double CRUISE_VELOCITY = 40.0; // rotations per second
        public static final double ACCELERATION = 40.0; // rotations per second^2

        public static final double STATOR_CURRENT_LIMIT = 60;
        public static final double SUPPLY_CURRENT_LIMIT = 50;

        static {
            Preferences.initDouble("Hopper/Forward", 5.0);
            HOPPER_FORWARD_SPEED = RotationsPerSecond.of(50); // TODO add a hopper forward speed for picking up and for
                                                              // shooting. shooting=50 picking up=30
            Preferences.initDouble("Hopper/Reverse", -1.0);
            HOPPER_REVERSE_SPEED = RotationsPerSecond.of(Preferences.getDouble("Hopper/Reverse", -1.0));

        }
    }

    public static class IntakePreferences {
        public static final double INTAKE_MOTOR_OUT;
        public static final double INTAKE_MOTOR_IN;
        public static final double INTAKE_MOTOR_CENTER;
        public static final double PICKUP_MOTOR_OUT;
        public static final double PICKUP_MOTOR_IN;
        public static final int SETTLE_COUNT;
        public static final double POSITION_TOLERANCE;

        // PID gains for intake deploy motor (MotionMagic position control)
        public static final double DEPLOY_KP = 4.8;
        public static final double DEPLOY_KI = 0.0;
        public static final double DEPLOY_KD = 0.1;
        public static final double DEPLOY_KS = 0.25;
        public static final double DEPLOY_KV = 0.12;
        public static final double DEPLOY_KG = 0.0;

        // MotionMagic profile for intake deploy (faster deployment)
        public static final double DEPLOY_CRUISE_VELOCITY = 40.0; // rotations per second
        public static final double DEPLOY_ACCELERATION = 80.0; // rotations per second^2
        public static final double DEPLOY_JERK = 200.0; // rotations per second^3

        // PID gains for pickup roller motor (velocity control)
        public static final double PICKUP_KP = 0.5;
        public static final double PICKUP_KI = 0.0;
        public static final double PICKUP_KD = 0.0;
        public static final double PICKUP_KS = 0.25;
        public static final double PICKUP_KV = 0.105;

        // MotionMagic profile for pickup roller (velocity mode)
        // public static final double PICKUP_CRUISE_VELOCITY = 10.0; // rotations per
        // second
        public static final double PICKUP_ACCELERATION = 200.0; // rotations per second^2, flr acceleration = 50
        public static final double PICKUP_JERK = 0.0; // rotations per second^3

        // Current limits to protect the chain and detect hard stops
        public static final double DEPLOY_STATOR_LIMIT = 40.0; // amps
        public static final double DEPLOY_SUPPLY_LIMIT = 30.0; // amps
        public static final double PICKUP_STATOR_LIMIT = 60.0; // amps flr limit = 60, testing 80
        public static final double PICKUP_SUPPLY_LIMIT = 40.0; // amps flr limit = 40, testing 60
        public static final double STALL_CURRENT_THRESHOLD = 30.0; // amps — above this = likely stalled
        public static final int STALL_CYCLES_THRESHOLD = 10; // consecutive cycles before stall shutdown

        // Soft limit margin beyond IN/OUT positions (rotations)
        public static final double SOFT_LIMIT_MARGIN = 2.0;

        // Voltage limits
        public static final double PEAK_FORWARD_VOLTAGE = 15.0;
        public static final double PEAK_REVERSE_VOLTAGE = -15.0;

        static {
            Preferences.initDouble("Intake/Out", 70.0);
            INTAKE_MOTOR_OUT = 70;
            Preferences.initDouble("Intake/In", 3.0);
            INTAKE_MOTOR_IN = 3;
            Preferences.initDouble("Intake/Center", 57.0);
            INTAKE_MOTOR_CENTER = 30;
            Preferences.initDouble("Pickup/Out", -25.0);
            PICKUP_MOTOR_OUT = Preferences.getDouble("Pickup/Out", -25.0);
            Preferences.initDouble("Pickup/In", 80.0);

            // target pickup velocity (rps)
            PICKUP_MOTOR_IN = 100;

            Preferences.initDouble("Intake/SettleCount", 5);
            SETTLE_COUNT = (int) Preferences.getDouble("Intake/SettleCount", 5);
            Preferences.initDouble("Intake/PositionTolerance", 1.0);
            POSITION_TOLERANCE = Preferences.getDouble("Intake/PositionTolerance", 1.0);
        }
    }
}
