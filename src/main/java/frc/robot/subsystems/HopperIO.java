package frc.robot.subsystems;

import org.littletonrobotics.junction.AutoLog;

public interface HopperIO {
    @AutoLog
    public static class HopperIOInputs {
        public double velocityRPS = 0.0;
        public double statorCurrentAmps = 0.0;
        public double supplyCurrentAmps = 0.0;
        public double outputVoltage = 0.0;
        public double closedLoopError = 0.0;
        public double closedLoopReference = 0.0;
    }

    public default void updateInputs(HopperIOInputs inputs) {}

    public default void setVelocity(double velocityRPS) {}

    public default void stop() {}
}
