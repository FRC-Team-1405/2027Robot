package frc.robot.subsystems;

import org.littletonrobotics.junction.AutoLog;

public interface IntakeIO {
    @AutoLog
    public static class IntakeIOInputs {
        // Deploy arm motor
        public double deployPositionRots = 0.0;
        public double deployVelocityRPS = 0.0;
        public double deployStatorCurrentAmps = 0.0;
        public double deploySupplyCurrentAmps = 0.0;
        public double deployOutputVoltage = 0.0;
        public double deployClosedLoopError = 0.0;
        public double deployClosedLoopReference = 0.0;

        // Pickup roller motor (embedded in intake)
        public double pickupVelocityRPS = 0.0;
        public double pickupStatorCurrentAmps = 0.0;
        public double pickupSupplyCurrentAmps = 0.0;
        public double pickupOutputVoltage = 0.0;
        public double pickupClosedLoopError = 0.0;
    }

    public default void updateInputs(IntakeIOInputs inputs) {}

    /** Drive the deploy arm to the given position (rotations). */
    public default void setDeployPosition(double positionRots) {}

    /** Drive the pickup roller at the given velocity (RPS). */
    public default void setPickupVelocity(double velocityRPS) {}

    /** Neutral output on deploy motor. */
    public default void stopDeploy() {}

    /** Neutral output on pickup roller. */
    public default void stopPickup() {}

    /** Zero the deploy encoder (call when at a known hard stop). */
    public default void zeroDeployEncoder() {}
}
