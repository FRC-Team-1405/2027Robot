package frc.robot.lib;

import java.io.File;
import java.io.IOException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import edu.wpi.first.apriltag.AprilTag;
import edu.wpi.first.apriltag.AprilTagFieldLayout;
import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Pose3d;
import edu.wpi.first.math.geometry.Quaternion;
import edu.wpi.first.math.geometry.Rotation3d;
import edu.wpi.first.math.geometry.Translation3d;
import edu.wpi.first.networktables.NetworkTableInstance;
import edu.wpi.first.networktables.StructPublisher;
import edu.wpi.first.wpilibj.Filesystem;

public class AprilTags {
        // AprilTag Fields:
        // https://github.com/wpilibsuite/allwpilib/blob/main/apriltag/src/main/native/resources/edu/wpi/first/apriltag/

        /**
         * Returns a new array of AprilTags, replacing any tags in APRIL_TAG_FIELD with
         * overrides in TAGS_OVERRIDES if they match by ID.
         * 
         * @return AprilTag[] with overrides applied
         */
        public static AprilTag[] getTagsWithOverrides() {
                List<AprilTag> tags = getAprilTagFieldLayout().getTags();

                Map<Integer, AprilTag> overrideMap = new HashMap<>();
                for (AprilTag tag : TAGS_OVERRIDES) {
                        overrideMap.put(tag.ID, tag);
                }

                AprilTag[] result = new AprilTag[tags.size()];
                for (int i = 0; i < tags.size(); i++) {
                        int id = tags.get(i).ID;
                        result[i] = overrideMap.getOrDefault(id, tags.get(i));
                }

                return result;
        }

        public static boolean observableTag(int id) {
                // TODO(2027): Update alliance-visibility logic based on 2027 game rules.
                        // For now: all tags observable from both alliances (same as 2026).
                        return true;

                // AprilTagFieldLayout fieldLayout = FieldConstants.getAprilTagFieldLayout();

                // // Convert the list of AprilTags to an array
                // AprilTag[] aprilTagsArray = fieldLayout.getTags().toArray(new AprilTag[0]);

                // for (AprilTag tag : aprilTagsArray) {
                // if (tag.ID == id) {
                // if (AllianceSymmetry.isBlue()) {
                // return tag.pose.getX() < FieldConstants.FIELD_LENGTH / 2.0;
                // } else {
                // return tag.pose.getX() > FieldConstants.FIELD_LENGTH / 2.0;
                // }
                // }
                // }
                // return false;
        }

        // region tag overrides

        public static final AprilTag[] NONE = new AprilTag[] {};

        // used for testing robot odometry, put the tag on the left wall and drive the
        // robot forward.
        public static final AprilTag[] ROBOT_ODOMETRY_TAG = new AprilTag[] {
                        new AprilTag(
                                        22,
                                        new Pose3d(
                                                        new Translation3d(2, 8.05561, 0.308102),
                                                        new Rotation3d(new Quaternion(0.7071067811865476, 0.0, 0.0,
                                                                        0.7071067811865476))
                                                                        .plus(new Rotation3d(0, 0, Math.PI)) // rotate
                                                                                                             // by 180
                                                                                                             // deg
                                        ))
        };

        // endregion tag overrides

        public static final AprilTag[] TAGS_OVERRIDES = NONE;

        public static void publishTagsFromJson(String pathToJson) {
                try {
                        AprilTagFieldLayout aprilTagFieldLayout = new AprilTagFieldLayout(pathToJson);
                        publishTags(aprilTagFieldLayout);
                } catch (IOException e) {
                        // TODO Auto-generated catch block
                        e.printStackTrace();
                }
        }

        public static void publishTags(AprilTagFieldLayout aprilTagFieldLayout) {
                List<AprilTag> aprilTags = aprilTagFieldLayout.getTags();
                for (int i = 0; i < aprilTags.size(); i++) {
                        StructPublisher<Pose2d> aprilTagPublisher = NetworkTableInstance.getDefault()
                                        .getStructTopic("TagMap/AprilTags_" + (i + 1), Pose2d.struct).publish();
                        aprilTagPublisher.set(aprilTags.get(i).pose.toPose2d());
                }
        }

        // TODO(2027): Replace with the official 2027 AprilTag field layout JSON once available.
        // Download from: https://github.com/wpilibsuite/allwpilib/tree/main/apriltag/src/main/native/resources/edu/wpi/first/apriltag/
        private static String APRIL_TAG_LAYOUT_NAME = "2026-rebuilt-welded.json";
        private static AprilTagFieldLayout APRIL_TAG_FIELD = null;

        public static AprilTagFieldLayout getAprilTagFieldLayout() {
                if (APRIL_TAG_FIELD != null) {
                        return APRIL_TAG_FIELD;
                }

                try {
                        APRIL_TAG_FIELD = new AprilTagFieldLayout(
                                        new File(Filesystem.getDeployDirectory(),
                                                        APRIL_TAG_LAYOUT_NAME)
                                                        .getAbsolutePath());
                        return APRIL_TAG_FIELD;
                } catch (IOException e) {
                        System.err.println("ERROR: " + APRIL_TAG_LAYOUT_NAME + " not found in deploy directory");
                        e.printStackTrace();
                        return null;
                }
        }

        /**
         * Throws error if april tag id doesn't exist!
         * 
         * @param aprilTagId
         * @return
         * @throws Exception
         */
        public static Pose2d getAprilTagPose(int aprilTagId) {
                if (APRIL_TAG_FIELD == null || !APRIL_TAG_FIELD.getTagPose(aprilTagId).isPresent()) {
                        // april tag isn't present, robot is likely booting up
                        return new Pose2d();
                }
                return APRIL_TAG_FIELD.getTagPose(aprilTagId).get().toPose2d();
        }
}