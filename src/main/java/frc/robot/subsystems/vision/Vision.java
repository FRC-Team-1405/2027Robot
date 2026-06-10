package frc.robot.subsystems.vision;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;

import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Pose3d;
import edu.wpi.first.math.kinematics.ChassisSpeeds;
import edu.wpi.first.util.struct.Struct;
import edu.wpi.first.util.struct.StructSerializable;
import edu.wpi.first.wpilibj.DriverStation;
import edu.wpi.first.wpilibj.Timer;
import edu.wpi.first.wpilibj2.command.SubsystemBase;
import frc.robot.constants.FeatureSwitches;
import frc.robot.lib.AprilTags;
import frc.robot.lib.GlobalField;
import frc.robot.lib.ProceduralStructGenerator;
import frc.robot.lib.Tracer;
import frc.robot.subsystems.vision.VisionConstants.Filtering;
import org.littletonrobotics.junction.Logger;

public class Vision extends SubsystemBase {
    private final VisionIO[] ios;
    private final VisionIOInputsAutoLogged[] inputs;

    // Per-camera state for velocity rejection — maintained across loops.
    // Stored here (not in IO) so it is recomputed during replay along with
    // the rest of the filter logic.
    private final Pose2d[] lastAcceptedPose;
    private final double[] lastAcceptedTimestamp;

    private final Timer timerSinceLastSample = new Timer();
    private final ChassisSpeeds speeds = new ChassisSpeeds();
    private final ArrayList<VisionSample> samples = new ArrayList<>();

    public record VisionUpdate(Pose2d pose, double timestamp, double weightScalar, double avgDistanceMeters)
            implements StructSerializable {
        private static final VisionUpdate kEmpty = new VisionUpdate(Pose2d.kZero, 0.0, 1.0, 0.0);

        public static VisionUpdate empty() { return kEmpty; }

        public static final Struct<VisionUpdate> struct = ProceduralStructGenerator.genRecord(VisionUpdate.class);
    }

    public record VisionSample(Pose2d pose, double timestamp, double weight, double avgDistanceMeters)
            implements StructSerializable {
        public static final Struct<VisionSample> struct = ProceduralStructGenerator.genRecord(VisionSample.class);
    }

    public Vision(VisionIO... ios) {
        this.ios = ios;
        this.inputs = new VisionIOInputsAutoLogged[ios.length];
        this.lastAcceptedPose = new Pose2d[ios.length];
        this.lastAcceptedTimestamp = new double[ios.length];
        for (int i = 0; i < ios.length; i++) {
            inputs[i] = new VisionIOInputsAutoLogged();
            lastAcceptedPose[i] = Pose2d.kZero;
            lastAcceptedTimestamp[i] = 0.0;
        }
    }

    public void updateSpeeds(ChassisSpeeds speeds) {
        this.speeds.vxMetersPerSecond = speeds.vxMetersPerSecond;
        this.speeds.vyMetersPerSecond = speeds.vyMetersPerSecond;
        this.speeds.omegaRadiansPerSecond = speeds.omegaRadiansPerSecond;
    }

    private Optional<VisionSample> gaugeWeight(Pose2d pose, double timestamp,
            double weightScalar, double avgDistMeters) {
        double weight = weightScalar;
        weight *= Filtering.LINEAR_VELOCITY_WEIGHT_COEFFICIENT
                .lerp(Math.hypot(speeds.vxMetersPerSecond, speeds.vyMetersPerSecond));
        weight *= Filtering.ANGULAR_VELOCITY_WEIGHT_COEFFICIENT.lerp(speeds.omegaRadiansPerSecond);
        if (DriverStation.isDisabled()) weight = 1.0;
        return Optional.of(new VisionSample(pose, timestamp, weight, avgDistMeters));
    }

    public double timeSinceLastSample() {
        return timerSinceLastSample.get();
    }

    public List<VisionSample> flushSamples() {
        List<VisionSample> out = new ArrayList<>(samples);
        samples.clear();
        return out;
    }

    @Override
    public void periodic() {
        Tracer.startTrace("VisionPeriodic");

        for (int i = 0; i < ios.length; i++) {
            String name = ios[i].getName();
            Tracer.startTrace(name + "Periodic");

            try {
                ios[i].updateInputs(inputs[i]);
            } catch (Exception e) {
                DriverStation.reportError("Error in VisionIO " + name, e.getStackTrace());
            }
            Logger.processInputs("Vision/" + name, inputs[i]);

            // -------------------------------------------------------------------
            // All filter logic below runs AFTER processInputs() — this is the
            // replay boundary. Changing any threshold, margin, or LerpTable and
            // running simulateJava against an old .wpilog will show the new
            // filter behaviour against real match data.
            // -------------------------------------------------------------------

            int rejBoundary = 0;
            int rejVelocity = 0;
            int rejAmbiguity = 0;
            int tagIdOffset = 0;
            ArrayList<Pose2d> acceptedPoses = new ArrayList<>();

            for (int j = 0; j < inputs[i].rawEstimatedPoses.length; j++) {
                Pose3d pose3d = inputs[i].rawEstimatedPoses[j];
                double ts = inputs[i].rawTimestampsSec[j];
                double ambiguity = inputs[i].rawAmbiguities[j];
                int tagCount = inputs[i].rawTagCountsPerResult[j];
                double sumArea = inputs[i].rawSumTagAreas[j];
                double avgDist = inputs[i].rawAvgDistancesMeters[j];
                double pixelOffset = inputs[i].rawAvgNormalizedPixelOffsets[j];
                double aspectRatio = inputs[i].rawAvgAspectRatioDevs[j];

                int[] resultTagIds = Arrays.copyOfRange(
                        inputs[i].rawTagIdsFlat, tagIdOffset, tagIdOffset + tagCount);
                tagIdOffset += tagCount;

                // P3: Ambiguity filter — skip single-tag estimates the PnP solver can't
                // distinguish. Multi-tag results report ambiguity = -1 and always pass.
                if (FeatureSwitches.VISION_AMBIGUITY_THRESHOLD
                        && tagCount == 1 && ambiguity >= 0.2) {
                    rejAmbiguity++;
                    continue;
                }

                // P1: Field boundary rejection
                // TODO(2027): Update FIELD_LENGTH and FIELD_WIDTH once 2027 field layout is published.
                if (FeatureSwitches.VISION_FIELD_BOUNDARY_REJECTION) {
                    final double MARGIN = 0.5;
                    final double FIELD_LENGTH = 17.548;
                    final double FIELD_WIDTH = 8.052;
                    final double MAX_Z = 0.75;
                    if (pose3d.getX() < -MARGIN || pose3d.getX() > FIELD_LENGTH + MARGIN
                            || pose3d.getY() < -MARGIN || pose3d.getY() > FIELD_WIDTH + MARGIN
                            || Math.abs(pose3d.getZ()) > MAX_Z) {
                        rejBoundary++;
                        continue;
                    }
                }

                Pose2d pose2d = pose3d.toPose2d();

                // Velocity rejection — discard jumps implying motion > 5 m/s between estimates.
                if (lastAcceptedTimestamp[i] > 0.0) {
                    double dt = ts - lastAcceptedTimestamp[i];
                    double dist = pose2d.getTranslation().getDistance(lastAcceptedPose[i].getTranslation());
                    if (dist > dt * 5.0) {
                        rejVelocity++;
                        continue;
                    }
                }

                // Trust scalar computation
                double trust = ios[i].getTrustScalar();

                // P2: Tag-rankings filter — zero-weight non-scoring tags.
                // TODO(2027): Update TAG_RANKINGS values for 2027 game structure.
                if (FeatureSwitches.VISION_TAG_RANKINGS_FILTER) {
                    for (int tagId : resultTagIds) {
                        trust *= Filtering.TAG_RANKINGS.getOrDefault(tagId, 0.0);
                    }
                }

                trust *= Filtering.AREA_WEIGHT_COEFFICIENT.lerp(sumArea);
                trust *= Filtering.PIXEL_OFFSET_WEIGHT_COEFFICIENT.lerp(pixelOffset);
                trust *= Filtering.HEIGHT_WIDTH_PROPORTION_WEIGHT_COEFFICIENT.lerp(aspectRatio);

                if (DriverStation.isDisabled()) trust = 1.0;

                lastAcceptedPose[i] = pose2d;
                lastAcceptedTimestamp[i] = ts;

                gaugeWeight(pose2d, ts, trust, avgDist).ifPresent(sample -> {
                    timerSinceLastSample.restart();
                    samples.add(sample);
                    acceptedPoses.add(sample.pose());
                    GlobalField.setObject(name + "Camera", sample.pose());
                });
            }

            Logger.recordOutput("Vision/" + name + "/AcceptedPoses",
                    acceptedPoses.toArray(new Pose2d[0]));
            Logger.recordOutput("Vision/" + name + "/RejectedBoundary", rejBoundary);
            Logger.recordOutput("Vision/" + name + "/RejectedVelocity", rejVelocity);
            Logger.recordOutput("Vision/" + name + "/RejectedAmbiguity", rejAmbiguity);

            // Log visible tag positions on the field for AdvantageScope odometry view
            for (int tagId : inputs[i].visibleTagIds) {
                AprilTags.getAprilTagFieldLayout().getTagPose(tagId)
                        .map(Pose3d::toPose2d)
                        .ifPresent(p -> GlobalField.setObject("SeenTag_" + tagId, p));
            }

            Tracer.endTrace();
        }

        Tracer.endTrace();
    }
}
