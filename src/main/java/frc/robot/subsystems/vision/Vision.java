package frc.robot.subsystems.vision;

import edu.wpi.first.apriltag.AprilTag;
import edu.wpi.first.cscore.OpenCvLoader;
import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Pose3d;
import edu.wpi.first.math.kinematics.ChassisSpeeds;
import edu.wpi.first.util.struct.Struct;
import edu.wpi.first.util.struct.StructSerializable;
import edu.wpi.first.wpilibj.DriverStation;
import edu.wpi.first.wpilibj.Timer;
import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import edu.wpi.first.wpilibj2.command.SubsystemBase;
import frc.robot.RobotContainer;
import frc.robot.lib.AprilTags;
import frc.robot.lib.GlobalField;
import frc.robot.lib.ProceduralStructGenerator;
import frc.robot.lib.Tracer;
import frc.robot.subsystems.vision.VisionConstants.CameraConfig;
import frc.robot.subsystems.vision.VisionConstants.Filtering;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Optional;

public class Vision extends SubsystemBase {
  static {
    OpenCvLoader.forceStaticLoad();
  }

  private final Camera[] cameras;

  private final Timer timerSinceLastSample = new Timer();
  private final HashSet<Integer> seenTags = new HashSet<>();
  private final ChassisSpeeds speeds = new ChassisSpeeds();
  private final ArrayList<VisionSample> samples = new ArrayList<>();

  public record VisionUpdate(Pose2d pose, double timestamp, double weightScalar)
      implements StructSerializable {

    private static final VisionUpdate kEmpty = new VisionUpdate(Pose2d.kZero, 0.0, 1.0);

    public static VisionUpdate empty() {
      return kEmpty;
    }

    public static final Struct<VisionUpdate> struct = ProceduralStructGenerator.genRecord(VisionUpdate.class);
  }

  public record VisionSample(Pose2d pose, double timestamp, double weight) implements StructSerializable {
    public static final Struct<VisionSample> struct = ProceduralStructGenerator.genRecord(VisionSample.class);
  }

  public static Camera[] camerasFromConfigs(CameraConfig... configs) {
    Camera[] cameras = new Camera[configs.length];
    for (int i = 0; i < configs.length; i++) {
      CameraConfig config = configs[i];
      cameras[i] = new Camera(
          config.name(),
          config.trustScalar(),
          config.transform(),
          config.intrinsics());
    }
    return cameras;
  }

  public Vision(Camera... cameras) {
    this.cameras = cameras;
  }

  public void updateSpeeds(ChassisSpeeds speeds) {
    this.speeds.vxMetersPerSecond = speeds.vxMetersPerSecond;
    this.speeds.vyMetersPerSecond = speeds.vyMetersPerSecond;
    this.speeds.omegaRadiansPerSecond = speeds.omegaRadiansPerSecond;
  }

  private Optional<VisionSample> gaugeWeight(final VisionUpdate update) {
    // if (!RobotContainer.REDUCE_VISION_WEIGHT_WHEN_MOVING) {
    // return Optional.of(new VisionSample(update.pose(), update.timestamp(), 1.0));
    // }

    double weight = update.weightScalar();

    // Completely arbitrary values for the velocity thresholds.
    // When the robot is moving fast there can be paralaxing and motion blur
    // that can cause the vision system to be less accurate, reduce the weight due
    // to this
    weight *= Filtering.LINEAR_VELOCITY_WEIGHT_COEFFICIENT
        .lerp(Math.hypot(speeds.vxMetersPerSecond, speeds.vyMetersPerSecond));
    weight *= Filtering.ANGULAR_VELOCITY_WEIGHT_COEFFICIENT.lerp(speeds.omegaRadiansPerSecond);

    if (DriverStation.isDisabled()) {
      weight = 1.0;
    }

    return Optional.of(new VisionSample(update.pose(), update.timestamp(), weight));
  }

  public double timeSinceLastSample() {
    return timerSinceLastSample.get();
  }

  public List<VisionSample> flushSamples() {
    List<VisionSample> outList = new ArrayList<>();
    outList.addAll(samples);
    samples.clear();
    return outList;
  }

  @Override
  public void periodic() {
    Tracer.startTrace("VisionPeriodic");
    for (final Camera camera : cameras) {
      Tracer.startTrace(camera.getName() + "Periodic");

      try {
        camera.periodic();
      } catch (Exception e) {
        DriverStation.reportError("Error in camera " + camera.getName(), e.getStackTrace());
      }

      camera.flushUpdates().stream()
          .map(this::gaugeWeight)
          .filter(Optional::isPresent)
          .map(Optional::get)
          .forEach(
              sample -> {
                timerSinceLastSample.restart();
                samples.add(sample);
                GlobalField.setObject(camera.getName() + "Camera", sample.pose());
                SmartDashboard.putNumber("VisionWeight", sample.weight());
              });

      seenTags.addAll(camera.getSeenTags());

      Tracer.endTrace();
    }

    Pose2d[] tagLoc = seenTags.stream()
        .map(i -> AprilTags.getAprilTagFieldLayout().getTagPose(i))
        .filter(Optional::isPresent)
        .map(Optional::get)
        .map(Pose3d::toPose2d)
        .toArray(Pose2d[]::new);
    GlobalField.setObject("SeenTags", tagLoc);

    seenTags.clear();

    Tracer.endTrace();
  }
}
