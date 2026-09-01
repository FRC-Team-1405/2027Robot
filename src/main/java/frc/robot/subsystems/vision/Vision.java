package frc.robot.subsystems.vision;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Deque;
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
import frc.robot.subsystems.vision.VisionConstants.Health;
import org.littletonrobotics.junction.Logger;

public class Vision extends SubsystemBase {
    private final VisionIO[] ios;
    private final VisionIOInputsAutoLogged[] inputs;

    // Per-camera state for velocity rejection — maintained across loops.
    // Stored here (not in IO) so it is recomputed during replay along with
    // the rest of the filter logic.
    private final Pose2d[] lastAcceptedPose;
    private final double[] lastAcceptedTimestamp;

    // Rolling window of accepted poses per camera, used to compute a pose
    // stability metric — mirrors PhotonVision's dashboard "multi-tag pose
    // standard deviation over the last 100 samples" panel.
    private static final int POSE_STDDEV_WINDOW = 100;
    private final List<Deque<Pose2d>> recentAcceptedPoses;

    // Second window, time-bounded instead of count-bounded — reacts faster to
    // motion transitions than the 100-sample window above and is kept side by
    // side with it so the two can be sanity-checked against each other.
    private static final double POSE_STDDEV_TIME_WINDOW_SEC = 1.0;
    private final List<Deque<TimestampedPose>> recentAcceptedPosesTimed;

    private record TimestampedPose(double timestamp, Pose2d pose) {}

    // Rolling window of "was this accepted result multi-tag" flags, used by VisionHealth as a
    // mount-positioning signal (how often does this camera achieve a well-constrained solve).
    private static final int MULTI_TAG_RATIO_WINDOW = 50;
    private final List<Deque<Boolean>> recentMultiTagFlags;

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
        this.recentAcceptedPoses = new ArrayList<>(ios.length);
        this.recentAcceptedPosesTimed = new ArrayList<>(ios.length);
        this.recentMultiTagFlags = new ArrayList<>(ios.length);
        for (int i = 0; i < ios.length; i++) {
            inputs[i] = new VisionIOInputsAutoLogged();
            lastAcceptedPose[i] = Pose2d.kZero;
            lastAcceptedTimestamp[i] = 0.0;
            recentAcceptedPoses.add(new ArrayDeque<>(POSE_STDDEV_WINDOW));
            recentAcceptedPosesTimed.add(new ArrayDeque<>());
            recentMultiTagFlags.add(new ArrayDeque<>(MULTI_TAG_RATIO_WINDOW));
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

    /**
     * Translation stddev (meters) and circular rotation stddev (degrees) over the given
     * pose window. Rotation uses circular statistics (mean resultant length) so it
     * doesn't break down near the 0/360 wrap boundary. Returns zeros if fewer than 2 samples.
     */
    private static double[] computePoseStdDev(Collection<Pose2d> poses) {
        int n = poses.size();
        if (n < 2) return new double[] {0.0, 0.0, 0.0};

        double sumX = 0.0, sumY = 0.0;
        double sumCos = 0.0, sumSin = 0.0;
        for (Pose2d p : poses) {
            sumX += p.getX();
            sumY += p.getY();
            sumCos += p.getRotation().getCos();
            sumSin += p.getRotation().getSin();
        }
        double meanX = sumX / n;
        double meanY = sumY / n;

        double varX = 0.0, varY = 0.0;
        for (Pose2d p : poses) {
            varX += Math.pow(p.getX() - meanX, 2);
            varY += Math.pow(p.getY() - meanY, 2);
        }
        varX /= n;
        varY /= n;

        double resultantLength = Math.hypot(sumCos, sumSin) / n;
        double thetaStdDevDeg = resultantLength > 0.0
                ? Math.toDegrees(Math.sqrt(-2.0 * Math.log(resultantLength)))
                : 0.0;

        return new double[] {Math.sqrt(varX), Math.sqrt(varY), thetaStdDevDeg};
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
            ArrayList<Double> acceptedTimestamps = new ArrayList<>();
            ArrayList<Pose2d> rejectedBoundaryPoses = new ArrayList<>();
            ArrayList<Pose2d> rejectedVelocityPoses = new ArrayList<>();
            ArrayList<Pose2d> rejectedAmbiguityPoses = new ArrayList<>();

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
                        && tagCount == 1 && ambiguity >= Filtering.AMBIGUITY_REJECT_AT) {
                    rejAmbiguity++;
                    rejectedAmbiguityPoses.add(pose3d.toPose2d());
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
                        rejectedBoundaryPoses.add(pose3d.toPose2d());
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
                        rejectedVelocityPoses.add(pose2d);
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

                Deque<Boolean> multiTagWindow = recentMultiTagFlags.get(i);
                multiTagWindow.addLast(tagCount >= 2);
                if (multiTagWindow.size() > MULTI_TAG_RATIO_WINDOW) {
                    multiTagWindow.pollFirst();
                }

                gaugeWeight(pose2d, ts, trust, avgDist).ifPresent(sample -> {
                    timerSinceLastSample.restart();
                    samples.add(sample);
                    acceptedPoses.add(sample.pose());
                    acceptedTimestamps.add(ts);
                    GlobalField.setObject(name + "Camera", sample.pose());
                });
            }

            Logger.recordOutput("Vision/" + name + "/AcceptedPoses",
                    acceptedPoses.toArray(new Pose2d[0]));
            Logger.recordOutput("Vision/" + name + "/RejectedBoundary", rejBoundary);
            Logger.recordOutput("Vision/" + name + "/RejectedVelocity", rejVelocity);
            Logger.recordOutput("Vision/" + name + "/RejectedAmbiguity", rejAmbiguity);
            Logger.recordOutput("Vision/" + name + "/RejectedBoundaryPoses",
                    rejectedBoundaryPoses.toArray(new Pose2d[0]));
            Logger.recordOutput("Vision/" + name + "/RejectedVelocityPoses",
                    rejectedVelocityPoses.toArray(new Pose2d[0]));
            Logger.recordOutput("Vision/" + name + "/RejectedAmbiguityPoses",
                    rejectedAmbiguityPoses.toArray(new Pose2d[0]));

            // Pose stability — rolling stddev of the last N accepted poses.
            Deque<Pose2d> window = recentAcceptedPoses.get(i);
            for (Pose2d p : acceptedPoses) {
                window.addLast(p);
                if (window.size() > POSE_STDDEV_WINDOW) {
                    window.pollFirst();
                }
            }
            double[] poseStdDev = computePoseStdDev(window);
            Logger.recordOutput("Vision/" + name + "/PoseStdDevXMeters", poseStdDev[0]);
            Logger.recordOutput("Vision/" + name + "/PoseStdDevYMeters", poseStdDev[1]);
            Logger.recordOutput("Vision/" + name + "/PoseStdDevThetaDegrees", poseStdDev[2]);
            Logger.recordOutput("Vision/" + name + "/PoseStdDevSampleCount", window.size());

            // Pose stability — same idea, but bounded by time (last 1s) instead of sample
            // count, so it reacts to motion transitions independent of FPS. Kept alongside
            // the 100-sample window above for sanity-checking against PhotonVision's panel.
            Deque<TimestampedPose> timedWindow = recentAcceptedPosesTimed.get(i);
            for (int k = 0; k < acceptedPoses.size(); k++) {
                timedWindow.addLast(new TimestampedPose(acceptedTimestamps.get(k), acceptedPoses.get(k)));
            }
            if (!timedWindow.isEmpty()) {
                double latestTs = timedWindow.peekLast().timestamp();
                while (timedWindow.peekFirst().timestamp() < latestTs - POSE_STDDEV_TIME_WINDOW_SEC) {
                    timedWindow.pollFirst();
                }
            }
            List<Pose2d> timedPoses = new ArrayList<>(timedWindow.size());
            for (TimestampedPose tp : timedWindow) timedPoses.add(tp.pose());
            double[] poseStdDev1s = computePoseStdDev(timedPoses);
            Logger.recordOutput("Vision/" + name + "/PoseStdDevXMeters1s", poseStdDev1s[0]);
            Logger.recordOutput("Vision/" + name + "/PoseStdDevYMeters1s", poseStdDev1s[1]);
            Logger.recordOutput("Vision/" + name + "/PoseStdDevThetaDegrees1s", poseStdDev1s[2]);
            Logger.recordOutput("Vision/" + name + "/PoseStdDevSampleCount1s", timedWindow.size());

            // Derived metrics — viewable natively in AdvantageScope Line Graph / Statistics
            int rawCount = inputs[i].rawEstimatedPoses.length;
            Logger.recordOutput("Vision/" + name + "/ResultsPerLoop", (double) rawCount);
            double acceptanceRatePercent = rawCount > 0 ? 100.0 * acceptedPoses.size() / rawCount : 0.0;
            Logger.recordOutput("Vision/" + name + "/AcceptanceRatePercent", acceptanceRatePercent);
            double latencyMs = inputs[i].rawTimestampsSec.length > 0
                    ? (Timer.getFPGATimestamp()
                       - inputs[i].rawTimestampsSec[inputs[i].rawTimestampsSec.length - 1]) * 1000.0
                    : 0.0;
            Logger.recordOutput("Vision/" + name + "/LatencyMsLatest", latencyMs);

            // Live camera-health score (calibration tool Tab 5) — see VisionHealth.java. A pit
            // tuning aid, computed from data already published above; not used by the filter
            // pipeline or match-time trust weighting.
            double multiTagRatio = recentMultiTagFlags.get(i).isEmpty() ? 0.0
                    : recentMultiTagFlags.get(i).stream().mapToInt(b -> b ? 1 : 0).average().orElse(0.0);
            VisionHealth.CameraHealth health = VisionHealth.computeCameraHealth(
                    inputs[i].connected, inputs[i].visibleTagIds.length > 0,
                    Math.hypot(speeds.vxMetersPerSecond, speeds.vyMetersPerSecond),
                    speeds.omegaRadiansPerSecond,
                    rawCount > 0 ? inputs[i].rawSumTagAreas[rawCount - 1] : 0.0,
                    rawCount > 0 ? inputs[i].rawAmbiguities[rawCount - 1] : -1.0,
                    inputs[i].currentFps, Health.TARGET_FPS,
                    Math.hypot(poseStdDev1s[0], poseStdDev1s[1]), poseStdDev1s[2],
                    acceptanceRatePercent, latencyMs, multiTagRatio);

            Logger.recordOutput("Vision/" + name + "/Health/ScorePercent", health.score());
            Logger.recordOutput("Vision/" + name + "/Health/Reason", health.reason());
            Logger.recordOutput("Vision/" + name + "/Health/StillnessPercent", health.stillnessPct());
            Logger.recordOutput("Vision/" + name + "/Health/AreaPercent", health.areaPct());
            Logger.recordOutput("Vision/" + name + "/Health/AmbiguityPercent", health.ambiguityPct());
            Logger.recordOutput("Vision/" + name + "/Health/FpsPercent", health.fpsPct());
            Logger.recordOutput("Vision/" + name + "/Health/JitterPercent", health.jitterPct());
            Logger.recordOutput("Vision/" + name + "/Health/AcceptanceRateFactorPercent", health.acceptanceRatePct());
            Logger.recordOutput("Vision/" + name + "/Health/LatencyPercent", health.latencyPct());
            Logger.recordOutput("Vision/" + name + "/Health/MultiTagRatioPercent", health.multiTagRatioPct());
            Logger.recordOutput("Vision/" + name + "/Health/MultiTagRatio", multiTagRatio);

            // Log visible tag positions on the field for AdvantageScope odometry view
            for (int tagId : inputs[i].visibleTagIds) {
                AprilTags.getAprilTagFieldLayout().getTagPose(tagId)
                        .map(Pose3d::toPose2d)
                        .ifPresent(p -> GlobalField.setObject("SeenTag_" + tagId, p));
            }

            Tracer.endTrace();
        }

        // Cross-camera agreement — the one health check above that can catch a systematically
        // mis-calibrated camera (wrong mount transform), which can otherwise look perfectly
        // clean on every single-camera self-consistency metric. Only meaningful with exactly the
        // two-camera Left/Right layout this robot has (see VisionConstants.CONFIGS).
        if (ios.length == 2) {
            double now = Timer.getFPGATimestamp();
            VisionHealth.PairAgreement agreement = VisionHealth.computePairAgreement(
                    lastAcceptedPose[0], lastAcceptedTimestamp[0],
                    lastAcceptedPose[1], lastAcceptedTimestamp[1], now);
            Logger.recordOutput("Vision/CrossCameraAgreement/ScorePercent", agreement.score());
            Logger.recordOutput("Vision/CrossCameraAgreement/Reason", agreement.reason());
            Logger.recordOutput("Vision/CrossCameraAgreement/TranslationDeltaMeters",
                    agreement.translationDeltaMeters());
            Logger.recordOutput("Vision/CrossCameraAgreement/RotationDeltaDegrees",
                    agreement.rotationDeltaDegrees());
        }

        Tracer.endTrace();
    }
}
