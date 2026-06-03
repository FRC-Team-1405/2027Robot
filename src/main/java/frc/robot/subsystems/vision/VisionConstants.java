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
}
