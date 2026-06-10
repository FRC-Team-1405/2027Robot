package frc.robot.subsystems.vision;

import edu.wpi.first.math.MatBuilder;
import edu.wpi.first.math.Matrix;
import edu.wpi.first.math.Nat;
import edu.wpi.first.math.geometry.Pose3d;
import edu.wpi.first.math.geometry.Transform3d;
import edu.wpi.first.math.numbers.N1;
import edu.wpi.first.math.numbers.N3;
import edu.wpi.first.math.numbers.N8;
import edu.wpi.first.wpilibj.Timer;
import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import frc.robot.Robot;
import frc.robot.lib.AprilTags;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import org.photonvision.EstimatedRobotPose;
import org.photonvision.PhotonCamera;
import org.photonvision.PhotonPoseEstimator;
import org.photonvision.PhotonPoseEstimator.PoseStrategy;
import org.photonvision.estimation.TargetModel;
import org.photonvision.targeting.PhotonPipelineResult;
import org.photonvision.targeting.PhotonTrackedTarget;

/**
 * Thin wrapper around PhotonCamera + PhotonPoseEstimator. Extracts raw pose estimates and
 * per-target geometry data without applying any rejection filters. All filtering (ambiguity
 * threshold, boundary rejection, velocity rejection, trust LerpTables) is performed in
 * Vision.periodic() after Logger.processInputs() so it is replayable.
 */
public class Camera {
    public record CameraIntrinsics(
            double width,
            double height,
            double fx,
            double fy,
            double cx,
            double cy,
            double[] distortion) {

        public Matrix<N8, N1> distortionMatrix() {
            return MatBuilder.fill(Nat.N8(), Nat.N1(), distortion);
        }

        public Matrix<N3, N3> cameraMatrix() {
            return MatBuilder.fill(Nat.N3(), Nat.N3(), new double[]{ fx, 0, cx, 0, fy, cy, 0, 0, 1 });
        }

        public double horizontalFOV() {
            return 2.0 * Math.atan2(width, 2.0 * fx);
        }

        public double verticalFOV() {
            return 2.0 * Math.atan2(height, 2.0 * fy);
        }

        public double diagonalFOV() {
            return 2.0 * Math.atan2(Math.hypot(width, height) / 2.0, fx);
        }
    }

    /**
     * Raw data extracted from one PhotonPipelineResult, before any robot-side filtering.
     * Vision.periodic() reads these fields from VisionIOInputs and applies all rejection logic.
     */
    public record RawVisionData(
            edu.wpi.first.math.geometry.Pose3d pose3d,
            double timestampSec,
            // -1.0 for multi-tag results; [0,1] for single-tag (ambiguity score from PnP)
            double ambiguity,
            int[] tagIds,
            double avgDistanceMeters,
            double sumTagArea,
            double avgNormalizedPixelOffset,
            double avgAspectRatioDev) {}

    protected final PhotonCamera camera;
    protected final Transform3d robotToCamera, cameraToRobot;
    private final PhotonPoseEstimator poseEstimator;
    private final double trustScalar;

    private final CameraIntrinsics intrinsics;
    private final Optional<Matrix<N8, N1>> cachedDistortionMatrix;
    private final Optional<Matrix<N3, N3>> cachedCameraMatrix;

    private ArrayList<Integer> seenTags = new ArrayList<>();
    private ArrayList<RawVisionData> rawData = new ArrayList<>();

    private int fpsResultCount = 0;
    private double fpsWindowStart = 0.0;
    private double currentFps = 0.0;

    public Camera(String name, double trustScalar, Transform3d cameraTransform, CameraIntrinsics intrinsics) {
        this.camera = new PhotonCamera(name);
        this.robotToCamera = cameraTransform;
        this.cameraToRobot = robotToCamera.inverse();
        this.trustScalar = trustScalar;
        this.intrinsics = intrinsics;
        this.cachedDistortionMatrix = Optional.of(intrinsics.distortionMatrix());
        this.cachedCameraMatrix = Optional.of(intrinsics.cameraMatrix());

        poseEstimator = new PhotonPoseEstimator(
                AprilTags.getAprilTagFieldLayout(), PoseStrategy.MULTI_TAG_PNP_ON_COPROCESSOR, this.robotToCamera);
        poseEstimator.setTagModel(TargetModel.kAprilTag36h11);
        poseEstimator.setMultiTagFallbackStrategy(PoseStrategy.LOWEST_AMBIGUITY);
    }

    private double normalizedDistanceFromCenter(PhotonTrackedTarget target) {
        final double HEIGHT = intrinsics.height;
        final double WIDTH = intrinsics.width;
        double sumX = 0.0;
        double sumY = 0.0;
        for (var corner : target.minAreaRectCorners) {
            sumX += corner.x - WIDTH / 2.0;
            sumY += corner.y - HEIGHT / 2.0;
        }
        double avgX = sumX / target.minAreaRectCorners.size();
        double avgY = sumY / target.minAreaRectCorners.size();
        return Math.hypot(avgX, avgY) / Math.hypot(WIDTH / 2.0, HEIGHT / 2.0);
    }

    private double dimensionProportionDifference(PhotonTrackedTarget target) {
        final var corners = target.getDetectedCorners();
        double height = Math.abs(corners.get(0).y - corners.get(3).y);
        double width = Math.abs(corners.get(1).x - corners.get(0).x);
        return Math.min(height, width) / Math.max(height, width);
    }

    private RawVisionData extractRawData(EstimatedRobotPose estRoboPose, PhotonPipelineResult result) {
        int[] tagIds = estRoboPose.targetsUsed.stream()
                .mapToInt(t -> t.fiducialId)
                .toArray();
        for (int id : tagIds) seenTags.add(id);

        double ambiguity = result.targets.size() == 1
                ? result.targets.get(0).getPoseAmbiguity()
                : -1.0;

        double sumArea = estRoboPose.targetsUsed.stream()
                .mapToDouble(PhotonTrackedTarget::getArea)
                .sum();

        double avgDistanceMeters = estRoboPose.targetsUsed.stream()
                .mapToDouble(t -> t.getBestCameraToTarget().getTranslation().getNorm())
                .average()
                .orElse(0.0);

        double avgNormalizedPixelOffset = estRoboPose.targetsUsed.stream()
                .mapToDouble(this::normalizedDistanceFromCenter)
                .average()
                .orElse(0.0);

        double avgAspectRatioDev = estRoboPose.targetsUsed.stream()
                .mapToDouble(this::dimensionProportionDifference)
                .average()
                .orElse(0.0);

        return new RawVisionData(
                estRoboPose.estimatedPose,
                estRoboPose.timestampSeconds,
                ambiguity,
                tagIds,
                avgDistanceMeters,
                sumArea,
                avgNormalizedPixelOffset,
                avgAspectRatioDev);
    }

    public String getName() {
        return camera.getName();
    }

    public double getTrustScalar() {
        return trustScalar;
    }

    /** Returns and clears the raw data accumulated since the last call. */
    public List<RawVisionData> flushRawData() {
        var out = rawData;
        rawData = new ArrayList<>();
        seenTags.clear();
        return out;
    }

    public int[] getSeenTagIds() {
        return seenTags.stream().mapToInt(Integer::intValue).toArray();
    }

    public boolean isConnected() {
        return camera.isConnected();
    }

    public double getCurrentFps() {
        return currentFps;
    }

    private PhotonPipelineResult pruneTags(PhotonPipelineResult result) {
        ArrayList<PhotonTrackedTarget> newTargets = new ArrayList<>();
        for (var target : result.targets) {
            if (AprilTags.observableTag(target.fiducialId)) {
                newTargets.add(target);
            }
        }
        result.targets = newTargets;
        return result;
    }

    public void periodic() {
        if (Robot.isReal()) {
            seenTags.clear();
            final var results = camera.getAllUnreadResults();
            for (var result : results) {
                if (result.hasTargets()) {
                    result = pruneTags(result);
                    Optional<EstimatedRobotPose> estRoboPose = poseEstimator.update(
                            result, cachedCameraMatrix, cachedDistortionMatrix, Optional.empty());
                    if (estRoboPose.isPresent()) {
                        rawData.add(extractRawData(estRoboPose.get(), result));
                    }
                }
            }

            SmartDashboard.putBoolean("/Vision/" + getName() + "/isConnected", camera.isConnected());

            fpsResultCount += results.size();
            double now = Timer.getFPGATimestamp();
            if (fpsWindowStart == 0.0) fpsWindowStart = now;
            double elapsed = now - fpsWindowStart;
            if (elapsed >= 1.0) {
                currentFps = fpsResultCount / elapsed;
                fpsResultCount = 0;
                fpsWindowStart = now;
                SmartDashboard.putNumber("/Vision/" + getName() + "/FPS", currentFps);
            }
        }
    }
}
