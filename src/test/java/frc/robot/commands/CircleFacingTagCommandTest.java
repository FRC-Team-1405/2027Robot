package frc.robot.commands;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Rotation2d;

/**
 * The fixed start spot for the CircleFacingTag vision test. It is a pure function of the tag's
 * pose, so it can be checked without a robot: what matters is that it sits the same distance from
 * the tag on the tag's visible side, facing it, however the tag is oriented.
 */
class CircleFacingTagCommandTest {
    private static final double EPS = 1e-9;
    private static final double START_DISTANCE_METERS = 1.75;

    @Test
    void startsInFrontOfTag10FacingIt() {
        // Tag 10 in 2026-rebuilt-welded.json: x=12.519177, y=4.034638, facing +x (rotation 0).
        Pose2d start = CircleFacingTagCommand.startPoseFor(new Pose2d(12.5191774, 4.0346376, Rotation2d.kZero));

        // The 9/5 baseline log this reproduces started at x=14.271, y=4.050, heading about 180.
        assertEquals(12.5191774 + START_DISTANCE_METERS, start.getX(), EPS);
        assertEquals(4.0346376, start.getY(), EPS);
        assertEquals(180.0, Math.abs(start.getRotation().getDegrees()), 1e-9);
    }

    @Test
    void isTheSameDistanceFromTheTagWhicheverWayItFaces() {
        for (double tagDegrees : new double[] { 0, 45, 90, 180, -90, 137.5 }) {
            Pose2d tag = new Pose2d(3.0, 5.0, Rotation2d.fromDegrees(tagDegrees));
            Pose2d start = CircleFacingTagCommand.startPoseFor(tag);

            assertEquals(START_DISTANCE_METERS, start.getTranslation().getDistance(tag.getTranslation()), EPS,
                    "distance from tag at tag rotation " + tagDegrees);
            // Pointed straight back at the tag.
            Rotation2d towardTag = tag.getTranslation().minus(start.getTranslation()).getAngle();
            assertEquals(0.0, start.getRotation().minus(towardTag).getRadians(), 1e-9,
                    "heading at tag rotation " + tagDegrees);
        }
    }
}
