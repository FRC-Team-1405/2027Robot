package frc.robot.subsystems;

import edu.wpi.first.wpilibj.Servo;

public class HoodIOServo implements HoodIO {
    private final Servo servo1 = new Servo(4);
    private final Servo servo2 = new Servo(5);

    private double currentTarget = 0.0;
    private boolean enabled = false;

    public HoodIOServo() {
        servo1.setBoundsMicroseconds(2000, 1000, 1500, 1200, 1000);
        servo2.setBoundsMicroseconds(2000, 1000, 1500, 1200, 1000);
    }

    @Override
    public void updateInputs(HoodIOInputs inputs) {
        inputs.servo1Position = servo1.get();
        inputs.servo2Position = servo2.get();
        inputs.targetPosition = currentTarget;
        inputs.enabled = enabled;
    }

    @Override
    public void setPosition(double position) {
        currentTarget = position;
        enabled = true;
        servo1.set(position);
        servo2.set(position);
    }

    @Override
    public void disable() {
        enabled = false;
        servo1.setDisabled();
        servo2.setDisabled();
    }
}
