package frc.robot.subsystems;

import org.littletonrobotics.junction.AutoLog;

public interface ShooterIO {
    @AutoLog
    public static class ShooterIOInputs {
        public double motor1VelocityRPS = 0.0;
        public double motor2VelocityRPS = 0.0;
        public double motor3VelocityRPS = 0.0;

        public double motor1SupplyCurrentAmps = 0.0;
        public double motor2SupplyCurrentAmps = 0.0;
        public double motor3SupplyCurrentAmps = 0.0;

        public double motor1StatorCurrentAmps = 0.0;
        public double motor2StatorCurrentAmps = 0.0;
        public double motor3StatorCurrentAmps = 0.0;

        public double motor1TorqueCurrentAmps = 0.0;
        public double motor2TorqueCurrentAmps = 0.0;
        public double motor3TorqueCurrentAmps = 0.0;

        public double motor1OutputVoltage = 0.0;
        public double motor2OutputVoltage = 0.0;
        public double motor3OutputVoltage = 0.0;

        public double supplyVoltage = 0.0;

        public double motor1TempCelsius = 0.0;
        public double motor2TempCelsius = 0.0;
        public double motor3TempCelsius = 0.0;

        public double closedLoopError = 0.0;
        public double closedLoopReference = 0.0;
    }

    public default void updateInputs(ShooterIOInputs inputs) {}

    /** Spin the flywheel to the given velocity in rotations per second. */
    public default void setVelocity(double velocityRPS) {}

    /** Brake / coast to stop. */
    public default void stop() {}
}
