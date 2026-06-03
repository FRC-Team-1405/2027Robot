package frc.robot.lib;

import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.wpilibj.smartdashboard.Field2d;
import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;

import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

public class GlobalField {
    private static final AtomicBoolean initialized = new AtomicBoolean(false);
    private static final Field2d field = new Field2d();

    private static void publish() {
        if (initialized.getAndSet(true)) {
            return;
        }
        SmartDashboard.putData("/Field", field);
    }

    public static synchronized void setObject(String name, Pose2d pose) {
        publish();
        field.getObject(name).setPose(pose);
    }

    public static synchronized void setObject(String name, Pose2d... pose) {
        publish();
        field.getObject(name).setPoses(pose);
    }

    public static synchronized void setObject(String name, List<Pose2d> pose) {
        publish();
        field.getObject(name).setPoses(pose);
    }
}
