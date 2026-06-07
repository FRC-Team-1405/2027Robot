package frc.robot.subsystems.vision;

import java.util.List;

import edu.wpi.first.cscore.OpenCvLoader;
import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Transform3d;
import frc.robot.subsystems.vision.Vision.VisionUpdate;
import frc.robot.subsystems.vision.VisionConstants.CameraConfig;

public class VisionIOPhotonVision implements VisionIO {
    static {
        OpenCvLoader.forceStaticLoad();
    }

    private final Camera camera;

    public VisionIOPhotonVision(String name, double trustScalar,
            Transform3d cameraTransform, Camera.CameraIntrinsics intrinsics) {
        this.camera = new Camera(name, trustScalar, cameraTransform, intrinsics);
    }

    public VisionIOPhotonVision(CameraConfig config) {
        this(config.name(), config.trustScalar(), config.transform(), config.intrinsics());
    }

    @Override
    public String getName() {
        return camera.getName();
    }

    @Override
    public void updateInputs(VisionIOInputs inputs) {
        camera.periodic();

        inputs.connected = camera.isConnected();
        inputs.currentFps = camera.getCurrentFps();
        inputs.rejectionCountVelocity = camera.getRejectionCountVelocity();
        inputs.rejectionCountBoundary = camera.getRejectionCountBoundary();
        inputs.visibleTagIds = camera.getSeenTagIds();

        List<VisionUpdate> updates = camera.flushUpdates();
        int n = updates.size();
        inputs.estimatedPoses = new Pose2d[n];
        inputs.estimateTimestampsSec = new double[n];
        inputs.estimateWeightScalars = new double[n];
        inputs.estimateAvgDistancesMeters = new double[n];

        for (int i = 0; i < n; i++) {
            VisionUpdate u = updates.get(i);
            inputs.estimatedPoses[i] = u.pose();
            inputs.estimateTimestampsSec[i] = u.timestamp();
            inputs.estimateWeightScalars[i] = u.weightScalar();
            inputs.estimateAvgDistancesMeters[i] = u.avgDistanceMeters();
        }
        inputs.latestResultTimestampSec = n > 0 ? updates.get(n - 1).timestamp() : inputs.latestResultTimestampSec;
    }
}
