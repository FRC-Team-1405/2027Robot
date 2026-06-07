package frc.robot.subsystems.vision;

import edu.wpi.first.math.geometry.Pose2d;

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
        inputs.rejectionCountVelocity = 0;
        inputs.rejectionCountBoundary = 0;
        inputs.estimatedPoses = new Pose2d[0];
        inputs.estimateTimestampsSec = new double[0];
        inputs.estimateWeightScalars = new double[0];
        inputs.estimateAvgDistancesMeters = new double[0];
        inputs.visibleTagIds = new int[0];
    }
}
