package frc.robot.subsystems.vision;

import edu.wpi.first.math.geometry.Pose2d;
import frc.robot.subsystems.vision.VisionConstants.Filtering;
import frc.robot.subsystems.vision.VisionConstants.Health;

/**
 * Composite live camera-health scoring for the calibration tool's Tab 5. Pure math only (no NT
 * or hardware access) so it's independently testable and — because it's called from
 * Vision.periodic() after Logger.processInputs() — replayable, like the match-time filter
 * pipeline in Vision.java.
 *
 * This is a *tuning aid* for pit/practice camera setup, not a match-accuracy signal: it answers
 * "does this camera look healthy right now, with a tag in view and the robot held still," not
 * "how did vision perform last match." A camera at a worse mount angle than another will always
 * read lower; the useful signal is one camera's score moving as its configuration changes.
 */
public class VisionHealth {
    private VisionHealth() {}

    public record CameraHealth(
            double score, // 0-100; 0.0 if unmeasurable right now (see reason)
            String reason, // why score is 0.0 and unmeasurable, else ""
            double stillnessPct,
            double areaPct,
            double ambiguityPct,
            double fpsPct,
            double jitterPct,
            double acceptanceRatePct,
            double latencyPct,
            double multiTagRatioPct) {}

    public record PairAgreement(
            double score, // 0-100; 0.0 if unmeasurable right now (see reason)
            String reason,
            double translationDeltaMeters,
            double rotationDeltaDegrees) {}

    public static double stillnessFactor(double linSpeedMps, double angSpeedRadps) {
        return Health.LIN_STILL_CURVE.lerp(Math.abs(linSpeedMps))
                * Health.ANG_STILL_CURVE.lerp(Math.abs(angSpeedRadps));
    }

    public static double areaFactor(double sumTagAreaPct) {
        return Filtering.AREA_WEIGHT_COEFFICIENT.lerp(Math.max(0.0, sumTagAreaPct));
    }

    public static double ambiguityFactor(double ambiguity) {
        // -1.0 is the multi-tag sentinel (see VisionIO.java) -- PnP is well-constrained with
        // 2+ tags regardless of the single-tag ambiguity score, so it never hurts.
        if (ambiguity < 0) return 1.0;
        double rejectAt = Filtering.AMBIGUITY_REJECT_AT;
        if (ambiguity >= rejectAt) return 0.0;
        return 1.0 - ambiguity / rejectAt;
    }

    public static double fpsFactor(double currentFps, double targetFps) {
        if (targetFps <= 0) return 0.0;
        return Math.max(0.0, Math.min(1.0, currentFps / targetFps));
    }

    public static double jitterFactor(double jitterXyMeters, double jitterThetaDeg) {
        return Health.JITTER_XY_CURVE.lerp(Math.abs(jitterXyMeters))
                * Health.JITTER_THETA_CURVE.lerp(Math.abs(jitterThetaDeg));
    }

    public static double acceptanceRateFactor(double acceptanceRatePct) {
        return Health.ACCEPTANCE_RATE_CURVE.lerp(acceptanceRatePct);
    }

    public static double latencyFactor(double latencyMs) {
        return Health.LATENCY_CURVE.lerp(latencyMs);
    }

    public static double multiTagRatioFactor(double multiTagRatio) {
        return Health.MULTI_TAG_RATIO_CURVE.lerp(multiTagRatio);
    }

    /**
     * @param jitterXyMeters trailing-1s pose stddev radius (hypot of X/Y stddev), meters
     * @param jitterThetaDeg trailing-1s pose heading stddev, degrees
     * @param multiTagRatio  fraction (0-1) of recent accepted results that used 2+ tags
     */
    public static CameraHealth computeCameraHealth(
            boolean connected, boolean hasTag,
            double linSpeedMps, double angSpeedRadps,
            double sumTagAreaPct, double ambiguity,
            double currentFps, double targetFps,
            double jitterXyMeters, double jitterThetaDeg,
            double acceptanceRatePct, double latencyMs,
            double multiTagRatio) {

        return computeCameraHealthFromFactors(connected, hasTag,
                stillnessFactor(linSpeedMps, angSpeedRadps), areaFactor(sumTagAreaPct),
                ambiguityFactor(ambiguity), fpsFactor(currentFps, targetFps),
                jitterFactor(jitterXyMeters, jitterThetaDeg),
                acceptanceRateFactor(acceptanceRatePct), latencyFactor(latencyMs),
                multiTagRatioFactor(multiTagRatio));
    }

    /** Uses precomputed factors so callers can smooth noisy camera measurements first. */
    public static CameraHealth computeCameraHealthFromFactors(
            boolean connected, boolean hasTag,
            double stillnessFactor, double areaFactor, double ambiguityFactor,
            double fpsFactor, double jitterFactor, double acceptanceRateFactor,
            double latencyFactor, double multiTagRatioFactor) {
        if (!connected) return unmeasurableCamera("Camera not connected");
        if (!hasTag) return unmeasurableCamera("No tag in view");

        // Multiplicative, mirroring Vision.java's own `trust *= ...` composition -- one bad
        // factor (e.g. the robot rolling during the check) craters the whole reading instead of
        // being averaged away by several good ones.
        double score = 100.0 * stillnessFactor * areaFactor * ambiguityFactor * fpsFactor
                * jitterFactor * acceptanceRateFactor * latencyFactor * multiTagRatioFactor;
        return new CameraHealth(score, "", stillnessFactor * 100, areaFactor * 100,
                ambiguityFactor * 100, fpsFactor * 100, jitterFactor * 100,
                acceptanceRateFactor * 100, latencyFactor * 100, multiTagRatioFactor * 100);
    }

    private static CameraHealth unmeasurableCamera(String reason) {
        return new CameraHealth(0.0, reason, 0, 0, 0, 0, 0, 0, 0, 0);
    }

    /**
     * Disagreement between two cameras' most recent accepted pose estimates. The one check here
     * that can catch a systematically mis-calibrated camera (wrong mount transform): a camera
     * with bad extrinsics can still look perfectly clean on every single-camera metric above,
     * because those only measure self-consistency, not correctness.
     */
    public static PairAgreement computePairAgreement(
            Pose2d poseA, double timestampA, Pose2d poseB, double timestampB, double nowSec) {
        if (timestampA <= 0.0 || timestampB <= 0.0) {
            return unmeasurablePair("No accepted sample yet from one or both cameras");
        }
        if (nowSec - timestampA > Health.CROSS_CAMERA_MAX_SAMPLE_AGE_SEC
                || nowSec - timestampB > Health.CROSS_CAMERA_MAX_SAMPLE_AGE_SEC) {
            return unmeasurablePair("Stale sample (>"
                    + (int) (Health.CROSS_CAMERA_MAX_SAMPLE_AGE_SEC * 1000) + "ms) from one or both cameras");
        }

        double translationDeltaMeters = poseA.getTranslation().getDistance(poseB.getTranslation());
        double rotationDeltaDegrees = Math.abs(poseA.getRotation().minus(poseB.getRotation()).getDegrees());

        double tf = Health.CROSS_CAMERA_TRANSLATION_CURVE.lerp(translationDeltaMeters);
        double rf = Health.CROSS_CAMERA_ROTATION_CURVE.lerp(rotationDeltaDegrees);
        return new PairAgreement(100.0 * tf * rf, "", translationDeltaMeters, rotationDeltaDegrees);
    }

    private static PairAgreement unmeasurablePair(String reason) {
        return new PairAgreement(0.0, reason, 0, 0);
    }
}
