package frc.robot.subsystems.vision;

import frc.robot.lib.LerpTable;
import frc.robot.subsystems.vision.Camera.CameraIntrinsics;

import java.util.HashMap;

import edu.wpi.first.math.geometry.Rotation3d;
import edu.wpi.first.math.geometry.Transform3d;
import edu.wpi.first.math.geometry.Translation3d;
import edu.wpi.first.math.util.Units;

public class VisionConstants {
        public record CameraConfig(String name, double trustScalar, Transform3d transform,
                        CameraIntrinsics intrinsics) {
        }

        // TODO(2027): Re-run PhotonVision camera calibration for 2027 robot mounts.
        // TODO(2027): Update camera positions/angles to match 2027 physical layout.
        // TODO(2027): Recalibrate intrinsics (fx, fy, cx, cy, distortion) per camera after mounting.
        public static final CameraConfig[] CONFIGS = {
                        new CameraConfig(
                                        "Left",
                                        1.0,
                                        new Transform3d(
                                                        new Translation3d(
                                                                        Units.inchesToMeters(2.19),
                                                                        Units.inchesToMeters(10.91),
                                                                        Units.inchesToMeters(28.7)),
                                                        new Rotation3d(0, Math.toRadians(-25), Math.toRadians(-10))),
                                        new CameraIntrinsics(
                                                        1280.0,
                                                        800.0,
                                                        910.28,
                                                        909.75,
                                                        654.27,
                                                        386.21,
                                                        new double[] { 0.055, -0.093, 0, 0, 0.03, -0.001, 0.003,
                                                                        -0.003 })),
                        new CameraConfig(
                                        "Right",
                                        1.0,
                                        new Transform3d(
                                                        new Translation3d(Units.inchesToMeters(2.19),
                                                                        Units.inchesToMeters(-10.91),
                                                                        Units.inchesToMeters(28.7)),
                                                        new Rotation3d(0, Math.toRadians(-25), Math.toRadians(10))),
                                        new CameraIntrinsics(
                                                        1280.0,
                                                        800.0,
                                                        912.02,
                                                        911.39,
                                                        635.5,
                                                        430.50,
                                                        new double[] { 0.049, -0.078, 0, 0, 0.018, -0.002, 0.004, 0 }))
        };

        public static final class Filtering {
                public static final LerpTable HEIGHT_WIDTH_PROPORTION_WEIGHT_COEFFICIENT = new LerpTable(
                                new LerpTable.LerpTableEntry(0.25, 0.0),
                                new LerpTable.LerpTableEntry(0.7, 0.9),
                                new LerpTable.LerpTableEntry(1.0, 1.0));

                public static final LerpTable AREA_WEIGHT_COEFFICIENT = new LerpTable(
                                new LerpTable.LerpTableEntry(0.0, 0.0),
                                new LerpTable.LerpTableEntry(0.2, 0.35),
                                new LerpTable.LerpTableEntry(1.0, 0.45),
                                new LerpTable.LerpTableEntry(4.0, 0.70),
                                new LerpTable.LerpTableEntry(7.5, 1.0));

                public static final LerpTable PIXEL_OFFSET_WEIGHT_COEFFICIENT = new LerpTable(
                                new LerpTable.LerpTableEntry(0.0, 1.0),
                                new LerpTable.LerpTableEntry(0.2, 1.0),
                                new LerpTable.LerpTableEntry(0.65, 0.75),
                                new LerpTable.LerpTableEntry(1.0, 0.35));

                public static final LerpTable LINEAR_VELOCITY_WEIGHT_COEFFICIENT = new LerpTable(
                                new LerpTable.LerpTableEntry(0.0, 1.0),
                                new LerpTable.LerpTableEntry(2.5, 0.8),
                                new LerpTable.LerpTableEntry(5.0, 0.1));

                public static final LerpTable ANGULAR_VELOCITY_WEIGHT_COEFFICIENT = new LerpTable(
                                new LerpTable.LerpTableEntry(0.0, 1.0),
                                new LerpTable.LerpTableEntry(7.0, 0.65),
                                new LerpTable.LerpTableEntry(12.0, 0.0));

                // Single-tag PnP ambiguity cutoff: results at/above this are rejected by the
                // P3 filter below AND scored as fully unhealthy by VisionHealth. Named so both
                // call sites derive from one number instead of two copies of "0.2" drifting apart.
                public static final double AMBIGUITY_REJECT_AT = 0.2;

                /**
                 * P2: Distance-based XY stddev - a more principled alternative to area-proxy weighting.
                 * Maps estimated distance from camera to tag (meters) -> XY stddev multiplier.
                 * Farther tags = less accurate pose = higher stddev.
                 *
                 * This table produces a stddev that is used directly as:
                 *   stddev = DISTANCE_XY_STDDEV.lerp(avgDistanceMeters)
                 * replacing the 0.1 / weight formula when VISION_DISTANCE_BASED_STDDEV is enabled.
                 *
                 * TODO: Tune breakpoints on the 2027 robot. Good starting point from Team 6328 data:
                 * single-tag at 1m ~0.1m stddev, at 4m ~0.5m stddev, at 7m+ reject.
                 */
                public static final LerpTable DISTANCE_XY_STDDEV = new LerpTable(
                                new LerpTable.LerpTableEntry(0.5, 0.05),
                                new LerpTable.LerpTableEntry(2.0, 0.15),
                                new LerpTable.LerpTableEntry(4.0, 0.45),
                                new LerpTable.LerpTableEntry(6.0, 1.50),
                                new LerpTable.LerpTableEntry(7.5, 9999.0));

                /**
                 * P1: Smooth theta (heading) stddev as a function of vision weight.
                 * Replaces the 2026 binary threshold (weight > 0.9 -> 10.0 rad, else 99999.0).
                 *
                 * Maps weight [0..1] -> theta stddev (radians).
                 * High weight (close, centered tag) -> lower stddev (more trust in heading).
                 * Low weight (far, edge-of-frame) -> high stddev (essentially ignore heading).
                 *
                 * TODO: Tune these breakpoints on the 2027 robot during pre-season testing.
                 * See docs/vision-testing-protocol.md Experiment 2.
                 */
                public static final LerpTable THETA_STDDEV_WEIGHT_COEFFICIENT = new LerpTable(
                                new LerpTable.LerpTableEntry(0.0, 99999.0),
                                new LerpTable.LerpTableEntry(0.5,   200.0),
                                new LerpTable.LerpTableEntry(0.75,   20.0),
                                new LerpTable.LerpTableEntry(0.9,    10.0),
                                new LerpTable.LerpTableEntry(1.0,     5.0));

                // TODO(2027): Update TAG_RANKINGS for 2027 game structure.
                // 2026 values: reef tags (6-11, 17-22) = 1.0 (trust), all others = 0.0 (reject).
                // This map is used by the TAG_RANKINGS feature switch (disabled by default).
                public static final HashMap<Integer, Double> TAG_RANKINGS = new HashMap<>() {
                        {
                                put(1, 0.0); // CORAL STATION
                                put(2, 0.0); // CORAL STATION
                                put(3, 0.0); // PROCESSOR
                                put(4, 0.0); // BARGE
                                put(5, 0.0); // BARGE
                                put(6, 1.0); // REEF
                                put(7, 1.0); // REEF
                                put(8, 1.0); // REEF
                                put(9, 1.0); // REEF
                                put(10, 1.0); // REEF
                                put(11, 1.0); // REEF
                                put(12, 0.0); // CORAL STATION
                                put(13, 0.0); // CORAL STATION
                                put(14, 0.0); // BARGE
                                put(15, 0.0); // BARGE
                                put(16, 0.0); // PROCESSOR
                                put(17, 1.0); // REEF
                                put(18, 1.0); // REEF
                                put(19, 1.0); // REEF
                                put(20, 1.0); // REEF
                                put(21, 1.0); // REEF
                                put(22, 1.0); // REEF
                        }
                };
        }

        /**
         * Curves for VisionHealth's live camera-health score (calibration tool Tab 5) — a
         * pit/practice tuning aid, not part of the match-time filter pipeline above. Kept as
         * separate LerpTables from Filtering because the two answer different questions: Filtering
         * must tolerate the robot actually driving during a match, while these gate a deliberate
         * "hold the robot still and look at one camera" check, so the stillness/jitter curves are
         * intentionally much stricter than LINEAR_VELOCITY_WEIGHT_COEFFICIENT etc.
         *
         * First-pass breakpoints — not yet validated against real mount/calibration data. Tune
         * after collecting a few sessions' worth of Vision/*\/Health/* logs.
         */
        public static final class Health {
                public static final double TARGET_FPS = 100.0;

                public static final LerpTable LIN_STILL_CURVE = new LerpTable(
                                new LerpTable.LerpTableEntry(0.0, 1.0),
                                new LerpTable.LerpTableEntry(0.06, 0.95),
                                new LerpTable.LerpTableEntry(0.3, 0.25),
                                new LerpTable.LerpTableEntry(0.6, 0.0));

                public static final LerpTable ANG_STILL_CURVE = new LerpTable(
                                new LerpTable.LerpTableEntry(0.0, 1.0),
                                new LerpTable.LerpTableEntry(0.06, 0.95),
                                new LerpTable.LerpTableEntry(1.0, 0.25),
                                new LerpTable.LerpTableEntry(2.0, 0.0));

                // Trailing-1s pose stddev (Vision/*/PoseStdDevXMeters1s etc.) while the robot is
                // stationary — a direct, physical-units measurement of PnP solve noise, independent
                // of what the solver itself claims via ambiguity. 1cm negligible, 3cm concerning,
                // 6cm+ treated as unusable.
                public static final LerpTable JITTER_XY_CURVE = new LerpTable(
                                new LerpTable.LerpTableEntry(0.0, 1.0),
                                new LerpTable.LerpTableEntry(0.01, 0.9),
                                new LerpTable.LerpTableEntry(0.03, 0.5),
                                new LerpTable.LerpTableEntry(0.06, 0.0));

                public static final LerpTable JITTER_THETA_CURVE = new LerpTable(
                                new LerpTable.LerpTableEntry(0.0, 1.0),
                                new LerpTable.LerpTableEntry(0.5, 0.9),
                                new LerpTable.LerpTableEntry(1.5, 0.5),
                                new LerpTable.LerpTableEntry(3.0, 0.0));

                // Vision/*/LatencyMsLatest -- catches a camera that's clean in every other respect
                // but consistently stale, which none of the per-sample quality factors can see.
                public static final LerpTable LATENCY_CURVE = new LerpTable(
                                new LerpTable.LerpTableEntry(0.0, 1.0),
                                new LerpTable.LerpTableEntry(50.0, 1.0),
                                new LerpTable.LerpTableEntry(150.0, 0.5),
                                new LerpTable.LerpTableEntry(300.0, 0.0));

                // Vision/*/AcceptanceRatePercent -- catches a camera delivering frames at target FPS
                // that are mostly getting thrown out by the boundary/velocity/ambiguity filters,
                // which fps_factor alone can't see.
                public static final LerpTable ACCEPTANCE_RATE_CURVE = new LerpTable(
                                new LerpTable.LerpTableEntry(0.0, 0.0),
                                new LerpTable.LerpTableEntry(50.0, 0.4),
                                new LerpTable.LerpTableEntry(80.0, 0.85),
                                new LerpTable.LerpTableEntry(100.0, 1.0));

                // Fraction of recent accepted results that used 2+ tags -- a mount-positioning
                // signal (how often does this camera achieve a well-constrained solve), orthogonal
                // to per-sample quality. Never zeroes out: a mostly-single-tag camera isn't broken,
                // just less ideally positioned.
                public static final LerpTable MULTI_TAG_RATIO_CURVE = new LerpTable(
                                new LerpTable.LerpTableEntry(0.0, 0.5),
                                new LerpTable.LerpTableEntry(0.3, 0.8),
                                new LerpTable.LerpTableEntry(1.0, 1.0));

                // Disagreement between Left's and Right's simultaneous pose estimates -- the one
                // check here that can catch a systematically mis-calibrated camera (wrong mount
                // transform), which can otherwise look perfectly clean on every self-consistency
                // metric above.
                public static final LerpTable CROSS_CAMERA_TRANSLATION_CURVE = new LerpTable(
                                new LerpTable.LerpTableEntry(0.0, 1.0),
                                new LerpTable.LerpTableEntry(0.05, 0.9),
                                new LerpTable.LerpTableEntry(0.15, 0.4),
                                new LerpTable.LerpTableEntry(0.3, 0.0));

                public static final LerpTable CROSS_CAMERA_ROTATION_CURVE = new LerpTable(
                                new LerpTable.LerpTableEntry(0.0, 1.0),
                                new LerpTable.LerpTableEntry(1.0, 0.9),
                                new LerpTable.LerpTableEntry(3.0, 0.4),
                                new LerpTable.LerpTableEntry(6.0, 0.0));

                // Older than this, a camera's last accepted sample is too stale for the cross-camera
                // check to mean anything -- "they disagree" is meaningless if one side just hasn't
                // seen a tag recently.
                public static final double CROSS_CAMERA_MAX_SAMPLE_AGE_SEC = 0.5;
        }
}
