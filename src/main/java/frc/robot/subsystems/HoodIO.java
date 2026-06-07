package frc.robot.subsystems;

import org.littletonrobotics.junction.AutoLog;

public interface HoodIO {
    @AutoLog
    public static class HoodIOInputs {
        public double servo1Position = 0.0;
        public double servo2Position = 0.0;
        public double targetPosition = 0.0;
        public boolean enabled = false;
    }

    public default void updateInputs(HoodIOInputs inputs) {}

    /** Set both servos to the given position [0.0, 1.0]. */
    public default void setPosition(double position) {}

    /** Disable (de-energize) both servos. */
    public default void disable() {}
}
