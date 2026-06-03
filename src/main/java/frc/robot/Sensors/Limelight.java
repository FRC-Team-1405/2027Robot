/* I really just took this file and started
   hacking away because I don't know if the
   Limelight stuff should be in another file */

package frc.robot.Sensors;

//import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import edu.wpi.first.networktables.NetworkTable;
import edu.wpi.first.networktables.NetworkTableEntry;
import edu.wpi.first.networktables.NetworkTableInstance;

public class Limelight {
    private NetworkTable table;
    private NetworkTableEntry tv;
    private NetworkTableEntry tx;
    private NetworkTableEntry ty;
    private NetworkTableEntry ta;
    private NetworkTableEntry ts;
    private NetworkTableEntry tl;
    private NetworkTableEntry tshort;
    private NetworkTableEntry tlong;
    private NetworkTableEntry thoriz;
    private NetworkTableEntry tvert;
    private NetworkTableEntry getpipe;
    private NetworkTableEntry getCamMode;
    private NetworkTableEntry tcornxy;

    public static class Position {
        private final double height;
        private final double angle;

        public Position(double height, double angle) {
            this.height = height;
            this.angle = angle;
        }

        public double getHeight() {
            return height;
        }

        public double getAngle() {
            return angle;
        }
    }

    private Position cameraPosition;

    // public byte pipeline;
    /*
     * public enum pipe {
     * PIPE1, PIPE2, PIPE3, PIPE4, PIPE5,
     * PIPE6, PIPE7, PIPE8, PIPE9, PIPE10
     * }
     * We only need ints for this (I'm using chars for the
     * byte's memory savings)
     */
    public Limelight() {
        this("", null);
    }

    public Limelight(Position cameraPosition) {
        this("", cameraPosition);
    }

    public Limelight(String name) {
        this(name, null);
    }

    public Limelight(String name, Position cameraPosition) {
        this.cameraPosition = cameraPosition;
        if (name.isBlank()) {
            table = NetworkTableInstance.getDefault().getTable("limelight");
        } else {
            table = NetworkTableInstance.getDefault().getTable("limelight-" + name);

        }
        tv = table.getEntry("tv");
        tx = table.getEntry("tx");
        ty = table.getEntry("ty");
        ta = table.getEntry("ta");
        ts = table.getEntry("ts");
        tl = table.getEntry("tl");
        tshort = table.getEntry("tshort");
        tlong = table.getEntry("tlong");
        thoriz = table.getEntry("thoriz");
        tvert = table.getEntry("tvert");
        tcornxy = table.getEntry("tcornxy");
        getpipe = table.getEntry("getpipe");
        getCamMode = table.getEntry("camMode");
    }

    byte currentPipeline = 0;

    public void setPipeline(byte id) {
        currentPipeline = id;
        // pipeline = id;
        table.getEntry("pipeline").setNumber(id);
    }

    public enum LED {
        Default, Off, Blink, On
    };

    public void setLED(LED mode) {
        switch (mode) {
            case Default:
                table.getEntry("ledMode").setNumber(0);
                break;
            case Off:
                table.getEntry("ledMode").setNumber(1);
                break;
            case Blink:
                table.getEntry("ledMode").setNumber(2);
                break;
            case On:
                table.getEntry("ledMode").setNumber(3);
                break;
        }
    }

    public LED getLED() {
        switch ((int) table.getEntry("ledMode").getDouble(0.0)) {
            case 0:
                return LED.Default;
            case 1:
                return LED.Off;
            case 2:
                return LED.Blink;
            case 3:
                return LED.On;
            default:
                return LED.Default;
        }
    }

    public void setCameraMode(boolean turnOn) {
        getCamMode.setNumber(turnOn ? 1 : 0);
    }

    public boolean getCameraMode() {
        // camMode should be 0 or 1
        return (getCamMode.getDouble(0) > 0.9);
    }

    public void setStream(byte mode) {
        /*
         * 0: Standard - Side-by-side streams if a webcam is attached to Limelight
         * 1: The secondary camera stream is placed in the lower-right corner of the
         * primary camera stream
         * 2: The primary camera stream is placed in the lower-right corner of the
         * secondary camera stream
         */
        table.getEntry("stream").setNumber(mode);
    } /*
       * At the time of writing this every other site
       * I visit had either had its domain expire,
       * had some sort of DB error or just said OOPS
       * AN ERROR OCCURED
       * Including FIRST's docs.
       * REEEEEEEEEEEEEEEEEEEEEE
       */

    public byte getPipeline() {
        return (byte) (getpipe.getDouble(0));
    }

    public boolean hasTarget() {
        return (tv.getDouble(0.0) == 1);
    }

    public double getTX() {
        return tx.getDouble(0.0);
    }

    public double getTY() {
        return ty.getDouble(0.0);
    }

    public double getTA() {
        return ta.getDouble(0.0);
    }

    public double getTS() {
        return ts.getDouble(0.0);
    }

    public double getTL() {
        return tl.getDouble(0.0); // At the time of writing
    }

    public double getTSHORT() {
        return tshort.getDouble(0.0);
    }

    public double getTLONG() {
        return tlong.getDouble(0.0);
    } /*
       * Monks used to write their thoughts and
       * feelings in the margins of books they copied
       * As you can see I've adopted that practise.
       */

    public double getTHORIZ() {
        return thoriz.getDouble(0.0);
    }

    public double getTVERT() {
        return tvert.getDouble(0.0);
    }

    public double[] getTCORNXY() {
        return tcornxy.getDoubleArray(new double[] { 0.0 });
    }

    public double getTXPos() {
        double points[] = getTCORNXY();
        if (points.length < 4)
            return getTX();
        return (points[0] + (points[2] - points[0]) / 2.0);
    }

    public double getTYPos() {
        double points[] = getTCORNXY();
        if (points.length < 4)
            return getTX();
        return (points[1] + (points[3] - points[1]) / 2.0);
    }

    public double fixedAngleDist(double targetHeight) {
        if (cameraPosition == null) {
            return Integer.MIN_VALUE;
        }

        if (!this.hasTarget()) {
            return Integer.MIN_VALUE;
        }

        return (targetHeight - cameraPosition.getHeight())
                / Math.tan(Math.toRadians(this.getTY() + cameraPosition.getAngle()));
    }
}