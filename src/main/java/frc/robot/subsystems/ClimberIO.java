package frc.robot.subsystems;

import org.littletonrobotics.junction.AutoLog;

public interface ClimberIO {
    @AutoLog
    public static class ClimberIOInputs {
        // Climber arm motor
        public double climberPositionRots = 0.0;
        public double climberVelocityRPS = 0.0;
        public double climberStatorCurrentAmps = 0.0;
        public double climberSupplyCurrentAmps = 0.0;
        public double climberOutputVoltage = 0.0;
        public double climberClosedLoopError = 0.0;
        public double climberClosedLoopReference = 0.0;

        // Grabber motor
        public double grabberPositionRots = 0.0;
        public double grabberVelocityRPS = 0.0;
        public double grabberStatorCurrentAmps = 0.0;
        public double grabberSupplyCurrentAmps = 0.0;
        public double grabberOutputVoltage = 0.0;
        public double grabberClosedLoopError = 0.0;
        public double grabberClosedLoopReference = 0.0;
    }

    public default void updateInputs(ClimberIOInputs inputs) {}

    public default void setClimberPosition(double positionRots) {}

    public default void setGrabberPosition(double positionRots) {}

    public default void stopClimber() {}

    public default void stopGrabber() {}
}
