package frc.robot.constants;

import static edu.wpi.first.units.Units.Rotation;

import java.util.function.Supplier;

import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Rotation2d;
import edu.wpi.first.math.geometry.Transform2d;
import edu.wpi.first.math.util.Units;
import frc.robot.lib.AllianceSymmetry;

public class FieldConstants {
    // TODO(2027): All positions below are from the 2026 Reefscape game.
    // Update BLUE_HUB, BLUE_FEEDER_WALL, and all derived positions once 2027 field layout is known.
    public static Pose2d BLUE_HUB = new Pose2d(4.546, 4.035, Rotation2d.kZero);

    public static Pose2d BLUE_FEEDER_WALL = new Pose2d(0.0077469999999999995, 0.6659626, Rotation2d.kZero);

    public static Supplier<Pose2d> ALLIANCE_HUB_POSITION = () -> {
        return AllianceSymmetry.isBlue() ? BLUE_HUB : AllianceSymmetry.flip(BLUE_HUB);
    };

    // location of middle april tag on the blue hub
    public static Pose2d BLUE_HUB_EDGE = new Pose2d(4.0218614, 4.0346376, Rotation2d.kZero);

    // teams prefered shooting location close to hub, back a foot from the edge of
    // the hub from the front of the intake
    public static Pose2d BLUE_HUB_SHOOT_CLOSE = BLUE_HUB_EDGE.transformBy(new Transform2d(
            -RobotConstants.HALF_ROBOT_WIDTH - RobotConstants.INTAKE_EXTENSION_LENGTH - Units.inchesToMeters(12), 0,
            Rotation2d.kZero));

    public static Pose2d BLUE_FEED_ROBOT_POSITION = BLUE_FEEDER_WALL.transformBy(new Transform2d(
            RobotConstants.HALF_ROBOT_WIDTH + RobotConstants.INTAKE_EXTENSION_LENGTH + Units.inchesToMeters(1), 0.0,
            Rotation2d.k180deg));

    // Start Positions
    public static Pose2d CENTER_START = BLUE_HUB_EDGE.transformBy(new Transform2d(
            -RobotConstants.HALF_ROBOT_WIDTH, 0,
            Rotation2d.kZero));

    public static Pose2d LEFT_START = BLUE_HUB_EDGE.transformBy(new Transform2d(
            -RobotConstants.HALF_ROBOT_WIDTH, RobotConstants.ROBOT_WIDTH
                    * 2,
            Rotation2d.kZero));

    public static Pose2d RIGHT_START = BLUE_HUB_EDGE.transformBy(new Transform2d(
            -RobotConstants.HALF_ROBOT_WIDTH, -(RobotConstants.ROBOT_WIDTH * 2),
            Rotation2d.kZero));
}