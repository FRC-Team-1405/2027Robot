package frc.robot.subsystems.vision;

import edu.wpi.first.math.MatBuilder;
import edu.wpi.first.math.Matrix;
import edu.wpi.first.math.Nat;
import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Rotation2d;
import edu.wpi.first.math.geometry.Transform3d;
import edu.wpi.first.math.numbers.N1;
import edu.wpi.first.math.numbers.N3;
import edu.wpi.first.math.numbers.N8;
import edu.wpi.first.wpilibj.DriverStation;
import edu.wpi.first.wpilibj.Timer;
import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import frc.robot.Robot;
import frc.robot.lib.AprilTags;
import frc.robot.subsystems.vision.Vision.VisionUpdate;
import frc.robot.subsystems.vision.VisionConstants.Filtering;
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

/** An abstraction for a photon camera. */
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
      return MatBuilder.fill(Nat.N3(), Nat.N3(), new double[] { fx, 0, cx, 0, fy, cy, 0, 0, 1 });
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

  protected final PhotonCamera camera;
  protected final Transform3d robotToCamera, cameraToRobot;
  private final PhotonPoseEstimator poseEstimator;
  private final double trustScalar;

  private final CameraIntrinsics intrinsics;
  private final Optional<Matrix<N8, N1>> cachedDistortionMatrix;
  private final Optional<Matrix<N3, N3>> cachedCameraMatrix;

  private Optional<VisionUpdate> previousUpdate = Optional.empty();
  private ArrayList<Integer> seenTags = new ArrayList<>();
  private ArrayList<VisionUpdate> updates = new ArrayList<>();

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

  private Optional<VisionUpdate> update(EstimatedRobotPose estRoboPose) {
    for (PhotonTrackedTarget target : estRoboPose.targetsUsed) {
      seenTags.add(target.fiducialId);
    }

    double trust = trustScalar;

    Pose2d pose = estRoboPose.estimatedPose.toPose2d();

    double sumArea = estRoboPose.targetsUsed.stream()
        .map(PhotonTrackedTarget::getArea)
        .mapToDouble(Double::doubleValue)
        .sum();

    double avgNormalizedPixelsFromCenter = estRoboPose.targetsUsed.stream()
        .map(this::normalizedDistanceFromCenter)
        .mapToDouble(Double::doubleValue)
        .average()
        .orElseGet(() -> 0.0);

    double avgDimensionProportion = estRoboPose.targetsUsed.stream()
        .map(this::dimensionProportionDifference)
        .mapToDouble(Double::doubleValue)
        .average()
        .orElseGet(() -> 0.0);

    if (previousUpdate.isPresent()) {
      double timeSinceLastUpdate = estRoboPose.timestampSeconds - previousUpdate.get().timestamp();
      double distanceFromLastUpdate = pose.getTranslation().getDistance(previousUpdate.get().pose().getTranslation());
      if (distanceFromLastUpdate > timeSinceLastUpdate * 5.0) {
        return Optional.empty();
      }
    }

    // for (int tagId : seenTags) {
    // trust *= Filtering.TAG_RANKINGS.getOrDefault(tagId, 0.0);
    // }

    trust *= Filtering.AREA_WEIGHT_COEFFICIENT.lerp(sumArea);
    trust *= Filtering.PIXEL_OFFSET_WEIGHT_COEFFICIENT.lerp(avgNormalizedPixelsFromCenter);
    trust *= Filtering.HEIGHT_WIDTH_PROPORTION_WEIGHT_COEFFICIENT.lerp(avgDimensionProportion);

    if (DriverStation.isDisabled()) {
      trust = 1.0;
    }

    var u = new VisionUpdate(pose, estRoboPose.timestampSeconds, trust);
    previousUpdate = Optional.of(u);

    return previousUpdate;
  }

  public String getName() {
    return camera.getName();
  }

  public List<VisionUpdate> flushUpdates() {
    var u = updates;
    updates = new ArrayList<>();
    return u;
  }

  public List<Integer> getSeenTags() {
    return seenTags;
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
      // poseEstimator.addHeadingData(Timer.getFPGATimestamp(), Rotation2d.kZero);
      // TODO determine if this had any effect on vision. i think it might only be
      // used in PNP_DISTANCE_TRIG_SOLVE PoseStrategy
      seenTags.clear();
      final var results = camera.getAllUnreadResults();
      for (var result : results) {
        if (result.hasTargets()) {
          result = pruneTags(result);
          Optional<EstimatedRobotPose> estRoboPose = poseEstimator.update(result, cachedCameraMatrix,
              cachedDistortionMatrix, Optional.empty());
          if (estRoboPose.isPresent()) {
            Optional<VisionUpdate> u = update(estRoboPose.get());
            if (u.isPresent()) {
              updates.add(u.get());
            }
          }
        }
      }

      SmartDashboard.putBoolean("/Vision/" + getName() + "/isConnected", camera.isConnected());
    }
  }
}
