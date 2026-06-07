package frc.robot.subsystems;

import org.littletonrobotics.junction.AutoLog;

public interface PickupIO {
    @AutoLog
    public static class PickupIOInputs {
        public double velocityRPS = 0.0;
        public double statorCurrentAmps = 0.0;
        public double supplyCurrentAmps = 0.0;
        public double outputVoltage = 0.0;
        public double closedLoopError = 0.0;
    }

    public default void updateInputs(PickupIOInputs inputs) {}

    public default void setVelocity(double velocityRPS) {}

    public default void stop() {}
}
