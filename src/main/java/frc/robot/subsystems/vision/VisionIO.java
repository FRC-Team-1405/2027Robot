package frc.robot.subsystems.vision;

import edu.wpi.first.math.geometry.Pose2d;
import org.littletonrobotics.junction.AutoLog;

public interface VisionIO {
    @AutoLog
    public static class VisionIOInputs {
        public boolean connected = false;
        public double latestResultTimestampSec = 0.0;
        public double currentFps = 0.0;
        public int rejectionCountVelocity = 0;
        public int rejectionCountBoundary = 0;

        // Parallel arrays — one entry per accepted pose estimate this cycle
        public Pose2d[] estimatedPoses = new Pose2d[0];
        public double[] estimateTimestampsSec = new double[0];
        public double[] estimateWeightScalars = new double[0];
        public double[] estimateAvgDistancesMeters = new double[0];
        public int[] visibleTagIds = new int[0];
    }

    /** Human-readable name used as the Logger key suffix. */
    public default String getName() { return "UnknownCamera"; }

    public default void updateInputs(VisionIOInputs inputs) {}
}
