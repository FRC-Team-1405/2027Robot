package frc.robot.subsystems.vision;

import edu.wpi.first.math.geometry.Pose3d;
import org.littletonrobotics.junction.AutoLog;

public interface VisionIO {
    @AutoLog
    public static class VisionIOInputs {
        // Camera health
        public boolean connected = false;
        public double currentFps = 0.0;
        public int[] visibleTagIds = new int[0];
        public double latestResultTimestampSec = 0.0;

        // Raw pose estimates — one entry per pipeline result this cycle, BEFORE any filtering.
        // Vision.periodic() applies all rejection logic after Logger.processInputs() so that
        // changes to ambiguity threshold, boundary margins, velocity limit, and trust LerpTables
        // are visible in replay without re-running the robot.
        public Pose3d[] rawEstimatedPoses = new Pose3d[0];
        public double[] rawTimestampsSec = new double[0];
        // -1.0 for multi-tag results (no meaningful single ambiguity score)
        public double[] rawAmbiguities = new double[0];
        public double[] rawAvgDistancesMeters = new double[0];
        public double[] rawSumTagAreas = new double[0];
        public double[] rawAvgNormalizedPixelOffsets = new double[0];
        public double[] rawAvgAspectRatioDevs = new double[0];

        // Tag IDs per result — parallel to rawEstimatedPoses.
        // rawTagCountsPerResult[j] gives how many IDs result j used;
        // rawTagIdsFlat is all those IDs concatenated in order.
        public int[] rawTagCountsPerResult = new int[0];
        public int[] rawTagIdsFlat = new int[0];
    }

    /** Human-readable name used as the Logger key suffix. */
    public default String getName() { return "UnknownCamera"; }

    /** Base trust scalar for this camera, applied before LerpTable multipliers. */
    public default double getTrustScalar() { return 1.0; }

    public default void updateInputs(VisionIOInputs inputs) {}
}
