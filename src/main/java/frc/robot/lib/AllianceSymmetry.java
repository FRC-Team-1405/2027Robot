package frc.robot.lib;

import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Rotation2d;
import edu.wpi.first.math.geometry.Translation2d;
import edu.wpi.first.wpilibj.DriverStation;
import edu.wpi.first.wpilibj.DriverStation.Alliance;

import java.util.HashMap;
import java.util.Map;

/**
 * A utility to standardize flipping of coordinate data based on the current
 * alliance across
 * different years.
 *
 * <p>
 * If every vendor used this, the user would be able to specify the year and no
 * matter the year
 * the vendor's code is from, the user would be able to flip as expected.
 */
public final class AllianceSymmetry {
    private AllianceSymmetry() {
        throw new UnsupportedOperationException("This is a utility class!");
    }

    public static boolean isBlue() {
        return DriverStation.getAlliance().orElse(Alliance.Blue) == Alliance.Blue;
    }

    public static boolean isRed() {
        return !isBlue();
    }

    /** The strategy to use for flipping coordinates over axis of symmetry. */
    public enum SymmetryStrategy {
        /**
         * X becomes fieldLength - x, leaves the y coordinate unchanged, and heading
         * becomes PI -
         * heading.
         */
        VERTICAL {
            @Override
            public double flipX(double x) {
                return activeYear.fieldLength - x;
            }

            @Override
            public double flipY(double y) {
                return y;
            }

            @Override
            public double flipHeading(double heading) {
                return Math.PI - heading;
            }
        },
        /**
         * X becomes fieldLength - x, Y becomes fieldWidth - y, and heading becomes PI -
         * heading.
         */
        ROTATIONAL {
            @Override
            public double flipX(double x) {
                return activeYear.fieldLength - x;
            }

            @Override
            public double flipY(double y) {
                return activeYear.fieldWidth - y;
            }

            @Override
            public double flipHeading(double heading) {
                return Math.PI - heading;
            }
        },
        /**
         * Leaves the X coordinate unchanged, Y becomes fieldWidth - y, and heading
         * becomes PI -
         * heading.
         */
        HORIZONTAL {
            @Override
            public double flipX(double x) {
                return x;
            }

            @Override
            public double flipY(double y) {
                return activeYear.fieldWidth - y;
            }

            @Override
            public double flipHeading(double heading) {
                return Math.PI - heading;
            }
        };

        /**
         * Flips the X coordinate.
         *
         * @param x The X coordinate to flip.
         * @return The flipped X coordinate.
         */
        public abstract double flipX(double x);

        /**
         * Flips the Y coordinate.
         *
         * @param y The Y coordinate to flip.
         * @return The flipped Y coordinate.
         */
        public abstract double flipY(double y);

        /**
         * Flips the heading.
         *
         * @param heading The heading to flip.
         * @return The flipped heading.
         */
        public abstract double flipHeading(double heading);
    }

    /**
     * An interface for objects that can be flipped based on the current alliance.
     *
     * @param <Self> The type of the object that is flippable.
     */
    public interface Flippable<Self extends Flippable<Self>> {
        /**
         * Flips the object based on the supplied {@link SymmetryStrategy} .
         *
         * @param strategy The type of symmetry to use for flipping.
         * @return The flipped object.
         */
        Self flip(SymmetryStrategy strategy);

        /**
         * Flips the object based on the active flipper.
         *
         * @return The flipped object.
         */
        default Self flip() {
            return flip(getStrategy());
        }
    }

    private record YearInfo(SymmetryStrategy strategy, double fieldLength, double fieldWidth) {
    }

    private static final HashMap<Integer, YearInfo> flipperMap = new HashMap<Integer, YearInfo>(
            Map.of(
                    2022, new YearInfo(SymmetryStrategy.ROTATIONAL, 16.4592, 8.2296),
                    2023, new YearInfo(SymmetryStrategy.VERTICAL, 16.54175, 8.0137),
                    2024, new YearInfo(SymmetryStrategy.VERTICAL, 16.54175, 8.211),
                    2025, new YearInfo(SymmetryStrategy.ROTATIONAL, 17.548, 8.052),
                    2026, new YearInfo(SymmetryStrategy.ROTATIONAL, 16.540988, 8.069))); // width: 317.69in, length:
                                                                                         // 651.22in

    private static YearInfo activeYear = flipperMap.get(2026);

    /**
     * Get the flipper that is currently active for flipping coordinates. It's
     * reccomended not to
     * store this locally as the flipper may change.
     *
     * @return The active flipper.
     */
    public static SymmetryStrategy getStrategy() {
        return activeYear.strategy;
    }

    /**
     * Set the year to determine the Alliance Coordinate Flipper to use.
     *
     * @param year The year to set the flipper to. [2022 - 2024]
     */
    public static void setYear(int year) {
        if (!flipperMap.containsKey(year)) {
            // Throw an exception instead of just reporting an error
            // because not flipping correctly during an auto routine
            // could cause a robot to damage itself or others.
            throw new IllegalArgumentException("Year " + year + " is not supported.");
        }
        activeYear = flipperMap.get(year);
    }

    /**
     * Flips the X coordinate.
     *
     * @param x        The X coordinate to flip.
     * @param strategy The type of symmetry to use for flipping.
     * @return The flipped X coordinate.
     */
    public static double flipX(double x, SymmetryStrategy strategy) {
        return strategy.flipX(x);
    }

    /**
     * Flips the Y coordinate.
     *
     * @param y        The Y coordinate to flip.
     * @param strategy The type of symmetry to use for flipping.
     * @return The flipped Y coordinate.
     */
    public static double flipY(double y, SymmetryStrategy strategy) {
        return strategy.flipY(y);
    }

    /**
     * Flips the heading.
     *
     * @param heading  The heading in radians to flip.
     * @param strategy The type of symmetry to use for flipping.
     * @return The flipped heading.
     */
    public static double flipHeading(double heading, SymmetryStrategy strategy) {
        return strategy.flipHeading(heading);
    }

    /**
     * Flips the {@link Flippable} object.
     *
     * @param <T>       The type of the object to flip.
     * @param flippable The object to flip.
     * @return The flipped object.
     */
    public static <T extends Flippable<T>> T flip(Flippable<T> flippable) {
        return flippable.flip();
    }

    /**
     * Flips the {@link Flippable} object.
     *
     * @param <T>       The type of the object to flip.
     * @param flippable The object to flip.
     * @param strategy  The type of symmetry to use for flipping.
     * @return The flipped object.
     */
    public static <T extends Flippable<T>> T flip(Flippable<T> flippable, SymmetryStrategy strategy) {
        return flippable.flip(strategy);
    }

    /**
     * Flips a {@link Translation2d}.
     *
     * @param translation The translation to flip.
     * @param strategy    The type of symmetry to use for flipping.
     * @return The flipped translation.
     */
    public static Translation2d flip(Translation2d translation, SymmetryStrategy strategy) {
        return new Translation2d(
                flipX(translation.getX(), strategy), flipY(translation.getY(), strategy));
    }

    /**
     * Flips a {@link Translation2d}.
     *
     * @param translation The translation to flip.
     * @return The flipped translation.
     */
    public static Translation2d flip(Translation2d translation) {
        return flip(translation, getStrategy());
    }

    /**
     * Flips a {@link Rotation2d}.
     *
     * @param rotation The rotation to flip.
     * @param strategy The type of symmetry to use for flipping.
     * @return The flipped rotation.
     */
    public static Rotation2d flip(Rotation2d rotation, SymmetryStrategy strategy) {
        return switch (strategy) {
            case VERTICAL -> new Rotation2d(-rotation.getCos(), rotation.getSin());
            case HORIZONTAL -> new Rotation2d(rotation.getCos(), -rotation.getSin());
            case ROTATIONAL -> new Rotation2d(-rotation.getCos(), -rotation.getSin());
        };
    }

    /**
     * Flips a {@link Rotation2d}.
     *
     * @param rotation The rotation to flip.
     * @return The flipped rotation.
     */
    public static Rotation2d flip(Rotation2d rotation) {
        return flip(rotation, getStrategy());
    }

    /**
     * Flips a {@link Pose2d}.
     *
     * @param pose     The pose to flip.
     * @param strategy The type of symmetry to use for flipping.
     * @return The flipped pose.
     */
    public static Pose2d flip(Pose2d pose, SymmetryStrategy strategy) {
        Pose2d flippedPose = new Pose2d(flip(pose.getTranslation(), strategy), flip(pose.getRotation(), strategy));
        // System.out.println("Flipping Pose (" + pose.toString() + ") to (" +
        // flippedPose.toString() + ")");
        return flippedPose;
    }

    /**
     * Flips a {@link Pose2d}.
     *
     * @param pose The pose to flip.
     * @return The flipped pose.
     */
    public static Pose2d flip(Pose2d pose) {
        return flip(pose, getStrategy());
    }
}
