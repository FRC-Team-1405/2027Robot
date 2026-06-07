package frc.robot.subsystems;

public class HoodIOSim implements HoodIO {
    private double currentTarget = 0.0;
    private double currentPosition = 0.0;
    private boolean enabled = false;

    // Simulate servo slew rate: full range in SERVO_FULL_RANGE_SECONDS seconds
    private static final double SLEW_RATE_PER_SEC = 1.0 / 5.0;

    @Override
    public void updateInputs(HoodIOInputs inputs) {
        if (enabled) {
            double error = currentTarget - currentPosition;
            double maxStep = SLEW_RATE_PER_SEC * 0.02;
            if (Math.abs(error) <= maxStep) {
                currentPosition = currentTarget;
            } else {
                currentPosition += Math.signum(error) * maxStep;
            }
        }
        inputs.servo1Position = currentPosition;
        inputs.servo2Position = currentPosition;
        inputs.targetPosition = currentTarget;
        inputs.enabled = enabled;
    }

    @Override
    public void setPosition(double position) {
        currentTarget = position;
        enabled = true;
    }

    @Override
    public void disable() {
        enabled = false;
    }
}
