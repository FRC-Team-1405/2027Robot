package frc.robot.subsystems.vision;

import java.util.List;

import edu.wpi.first.cscore.OpenCvLoader;
import edu.wpi.first.math.geometry.Pose3d;
import edu.wpi.first.math.geometry.Transform3d;
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
    public double getTrustScalar() {
        return camera.getTrustScalar();
    }

    @Override
    public void updateInputs(VisionIOInputs inputs) {
        camera.periodic();

        inputs.connected = camera.isConnected();
        inputs.currentFps = camera.getCurrentFps();
        inputs.visibleTagIds = camera.getSeenTagIds();

        List<Camera.RawVisionData> raw = camera.flushRawData();
        int n = raw.size();

        inputs.rawEstimatedPoses = new Pose3d[n];
        inputs.rawTimestampsSec = new double[n];
        inputs.rawAmbiguities = new double[n];
        inputs.rawAvgDistancesMeters = new double[n];
        inputs.rawSumTagAreas = new double[n];
        inputs.rawAvgNormalizedPixelOffsets = new double[n];
        inputs.rawAvgAspectRatioDevs = new double[n];
        inputs.rawTagCountsPerResult = new int[n];

        int totalTagIds = 0;
        for (Camera.RawVisionData d : raw) totalTagIds += d.tagIds().length;
        inputs.rawTagIdsFlat = new int[totalTagIds];

        int tagIdOffset = 0;
        for (int i = 0; i < n; i++) {
            Camera.RawVisionData d = raw.get(i);
            inputs.rawEstimatedPoses[i] = d.pose3d();
            inputs.rawTimestampsSec[i] = d.timestampSec();
            inputs.rawAmbiguities[i] = d.ambiguity();
            inputs.rawAvgDistancesMeters[i] = d.avgDistanceMeters();
            inputs.rawSumTagAreas[i] = d.sumTagArea();
            inputs.rawAvgNormalizedPixelOffsets[i] = d.avgNormalizedPixelOffset();
            inputs.rawAvgAspectRatioDevs[i] = d.avgAspectRatioDev();
            inputs.rawTagCountsPerResult[i] = d.tagIds().length;
            System.arraycopy(d.tagIds(), 0, inputs.rawTagIdsFlat, tagIdOffset, d.tagIds().length);
            tagIdOffset += d.tagIds().length;
        }

        if (n > 0) {
            inputs.latestResultTimestampSec = raw.get(n - 1).timestampSec();
        }
    }
}
