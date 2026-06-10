package frc.robot.subsystems.vision;

import edu.wpi.first.math.geometry.Pose3d;

public class VisionIOSim implements VisionIO {
    private final String name;

    public VisionIOSim(String name) {
        this.name = name;
    }

    @Override
    public String getName() {
        return name;
    }

    @Override
    public void updateInputs(VisionIOInputs inputs) {
        inputs.connected = false;
        inputs.currentFps = 0.0;
        inputs.visibleTagIds = new int[0];
        inputs.rawEstimatedPoses = new Pose3d[0];
        inputs.rawTimestampsSec = new double[0];
        inputs.rawAmbiguities = new double[0];
        inputs.rawAvgDistancesMeters = new double[0];
        inputs.rawSumTagAreas = new double[0];
        inputs.rawAvgNormalizedPixelOffsets = new double[0];
        inputs.rawAvgAspectRatioDevs = new double[0];
        inputs.rawTagCountsPerResult = new int[0];
        inputs.rawTagIdsFlat = new int[0];
    }
}
