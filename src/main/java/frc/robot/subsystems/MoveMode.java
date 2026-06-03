package frc.robot.subsystems;

import java.util.function.BooleanSupplier;
import java.util.function.DoubleSupplier;

import edu.wpi.first.math.controller.PIDController;
import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Rotation2d;
import edu.wpi.first.networktables.BooleanEntry;
import edu.wpi.first.networktables.BooleanTopic;
import edu.wpi.first.networktables.NetworkTable;
import edu.wpi.first.networktables.NetworkTableInstance;
import edu.wpi.first.networktables.StringPublisher;
import edu.wpi.first.networktables.StringTopic;
import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.Commands;
import edu.wpi.first.wpilibj2.command.InstantCommand;
import edu.wpi.first.wpilibj2.command.button.CommandXboxController;
import frc.robot.constants.FieldConstants;
import frc.robot.lib.AllianceSymmetry;
import frc.robot.lib.AllianceSymmetry.SymmetryStrategy;

import static frc.robot.RobotContainer.applyDeadband;

/*
 * DRIVE TEAM README
 *
 * Left Trigger: slow mode (25% of max speed)
 * Right Trigger: fast mode (100% of max speed)
 * No trigger pressed: normal speed mode (50% of max speed)
 * 
 * Y: standard rotation mode
 * X: snake rotation mode. Robot faces the way it is moving / the left stick is
 * facing.
 * B: compass rotation mode. Robot faces the way the right stick is facing.
 * 
 * Start + Back (simultaneously): Zeroizes the robot
 */

/**
 * Manages how the robot moves at certain speeds and rotates with modes. Modes
 * are changed with button input defined in RobotContainer.java.
 * <p>
 * ***There is a comment for the Drive Team titled 'DRIVE TEAM README' that
 * describes what all of the buttons do***.
 * 
 * @author Dylan Wilson
 */
public class MoveMode {
    /*
     * Two seperate enums for managing the Speed modes and Rotation modes
     * independently.
     */
    /**
     * The speed modes the robot can be in.
     */
    private enum Speed {
        SLOW,
        NORMAL,
        FAST,
        BUMP
    }

    /**
     * The rotation modes the robot can be in.
     */
    public enum Rotation {
        STANDARD,
        SNAKE,
        COMPASS,
        POINT,
        POINT_VELOCITY_COMPENSATED
    }

    /**
     * Sets the currentSpeedMode or currentRotationMode for the robot. Is a private
     * Command class to communicate with the RobotContainer.java's XboxController
     * joystick.
     */
    public class ModeCommand extends InstantCommand {
        private final Speed speedToSet;
        private final Rotation rotationToSet;
        private final CommandSwerveDrivetrain drivetrain;

        private ModeCommand(final Speed speedToSet) {
            this.speedToSet = speedToSet;
            this.rotationToSet = null;
            this.drivetrain = null;
        }

        private ModeCommand(final Rotation rotationToSet) {
            this.speedToSet = null;
            this.rotationToSet = rotationToSet;
            this.drivetrain = null;
        }

        private ModeCommand(final Speed speedToSet, final CommandSwerveDrivetrain drivetrain) {
            this.speedToSet = speedToSet;
            this.rotationToSet = null;
            this.drivetrain = drivetrain;
        }

        @Override
        public void initialize() {
            if (speedToSet != null) {
                currentSpeedMode = speedToSet;
            } else if (rotationToSet != null) {
                currentRotationMode = rotationToSet;
            }

            if (Speed.BUMP.equals(currentSpeedMode) && drivetrain != null) {
                double currentRobotRotationDeg = drivetrain.getState().Pose.getRotation().getDegrees();
                if (Math.abs(currentRobotRotationDeg) >= 90) {
                    bumpTargetRotation = Rotation2d.k180deg;
                } else {
                    bumpTargetRotation = Rotation2d.kZero;
                }

                // if (inAllianceZone(drivetrain).getAsBoolean()) {
                // // Alliance side: face 0 deg (blue) or 180 deg (red) — i.e. always face away
                // // from
                // // the bump toward the alliance wall so the robot crosses backwards.
                // bumpTargetRotation = AllianceSymmetry.isRed()
                // ? Rotation2d.k180deg
                // : Rotation2d.kZero;
                // } else {
                // // Neutral zone side: face 180 deg (blue) or 0 deg (red) — again, backwards
                // into
                // // bump.
                // bumpTargetRotation = AllianceSymmetry.isRed()
                // ? Rotation2d.k180deg
                // : Rotation2d.kZero;
                // }
            }

            elasticUpdate();
        }
    }

    /**
     * The speed mode that the robot is currently in.
     */
    private static Speed currentSpeedMode = Speed.NORMAL;

    /**
     * The rotation mode that the robot is currently in.
     */
    private static Rotation currentRotationMode = Rotation.STANDARD;

    private static Rotation2d bumpTargetRotation = Rotation2d.kZero;

    private static StringPublisher speedModePublisher; // For Eclipse
    private static StringPublisher rotationModePublisher; // For Eclipse

    /**
     * Feature switch: when {@code true} the Y-button point toggle activates
     * velocity-compensated aiming ({@link Rotation#POINT_VELOCITY_COMPENSATED})
     * instead of plain line-of-sight aiming ({@link Rotation#POINT}).
     * <p>
     * The value is exposed as a two-way NetworkTables entry under
     * {@code MoveMode/Use Velocity Compensated Point} so it can be flipped
     * live from an Elastic Dashboard boolean toggle widget without redeploying.
     */
    private static boolean useVelocityCompensatedPoint = false;

    /**
     * NT entry that mirrors {@link #useVelocityCompensatedPoint} (readable +
     * writable).
     */
    private static BooleanEntry velocityCompPointEntry;

    // TODO: Tune rotationController for physical robot
    public static final PIDController rotationController = new PIDController(20, 0, 0.85);

    /** Separate PID controller used exclusively for bump-mode heading hold. */
    // TODO: Tune bumpRotationController for physical robot
    public static final PIDController bumpRotationController = new PIDController(8, 0, 0);

    /**
     * Right-stick magnitude threshold above which the driver can override bump
     * heading hold.
     */
    private static final double BUMP_ROTATION_OVERRIDE_THRESHOLD = 0.15;

    private double goalAngle;
    private double currentAngle;
    private double calculate;

    public MoveMode() {
        elasticInit();
        rotationController.enableContinuousInput(-Math.PI, Math.PI);
        bumpRotationController.enableContinuousInput(-Math.PI, Math.PI);
    }

    /**
     * Selects the speed mode to perform based on which Mode currentSpeedMode is
     * equal to. A parent method for all the other speed modes.
     * 
     * Applies Deadband and flips joystick input
     */
    public DoubleSupplier selectSpeedMode(DoubleSupplier joystickSupplier, boolean isRobotForward) {
        return () -> {
            double input = -applyDeadband(joystickSupplier.getAsDouble());

            return switch (currentSpeedMode) {
                case SLOW -> slowMode() * input;
                case NORMAL -> normalMode() * input;
                case FAST -> fastMode() * input;
                case BUMP -> bumpMode(input, isRobotForward);
            };
        };
    }

    public Rotation getRotationMode() {
        return currentRotationMode;
    }

    /**
     * Selects the rotation mode to perform based on which Mode currentRotationMode
     * is equal to. A parent method for all the other rotation modes.
     * 
     * @param joystick       the connected Xbox Controller (all rotation modes)
     * @param drivetrain     the Swerve Drivetrain (SNAKE, COMPASS)
     * @param maxAngularRate rotational rate cap (STANDARD)
     */
    public DoubleSupplier selectRotationMode(final CommandXboxController joystick,
            final CommandSwerveDrivetrain drivetrain,
            final double maxAngularRate) {
        return new DoubleSupplier() {
            @Override
            public double getAsDouble() {
                // When bump speed mode is active, always use bump rotation hold regardless of
                // the current rotation mode, but still allow the driver to override with the
                // right stick.
                if (currentSpeedMode == Speed.BUMP) {
                    return MoveMode.this.bumpRotationMode(joystick, drivetrain, maxAngularRate);
                }
                return switch (currentRotationMode) {
                    case STANDARD -> standardMode(joystick, maxAngularRate);
                    case SNAKE -> snakeMode(joystick, drivetrain);
                    case COMPASS -> compassMode(joystick, drivetrain);
                    case POINT -> pointMode(drivetrain);
                    case POINT_VELOCITY_COMPENSATED -> pointVelocityCompensatedMode(drivetrain);
                };
            }
        };
    }

    /**
     * Sets currentSpeedMode to Speed.SLOW. Enabled by the left trigger.
     * 
     * @return a Command that sets currentSpeedMode to Speed.SLOW
     */
    public ModeCommand setToSlowMode() {
        return new ModeCommand(Speed.SLOW);
    }

    /**
     * Sets currentSpeedMode to Speed.NORMAL. Enabled by no trigger
     * input(none in left or right).
     * 
     * @return a Command that sets currentSpeedMode to Speed.NORMAL
     */
    public ModeCommand setToNormalMode() {
        return new ModeCommand(Speed.NORMAL);
    }

    /**
     * Sets currentSpeedMode to Speed.FAST. Enabled by the right trigger.
     * 
     * @return a Command that sets currentSpeedMode to Speed.FAST
     */
    public ModeCommand setToFastMode() {
        return new ModeCommand(Speed.FAST);
    }

    public static BooleanSupplier inAllianceZone(CommandSwerveDrivetrain drivetrain) {
        return () -> {
            double robotX = drivetrain.getState().Pose.getX();
            double allianceZoneBoundaryX = FieldConstants.BLUE_HUB.getX();
            if (AllianceSymmetry.isRed()) {
                return robotX < AllianceSymmetry.flipX(allianceZoneBoundaryX,
                        SymmetryStrategy.VERTICAL) ? false
                                : true;
            } else {
                return robotX < allianceZoneBoundaryX ? true : false;
            }
        };
    }

    public ModeCommand setToBumpMode(CommandSwerveDrivetrain drivetrain) {
        return new ModeCommand(Speed.BUMP, drivetrain);
    }

    /**
     * Sets currentRotationMode to Rotation.STANDARD. Enabled by the X button.
     * 
     * @return a Command that sets currentRotationMode to Rotation.STANDARD
     */
    public ModeCommand setToStandardMode() {
        return new ModeCommand(Rotation.STANDARD);
    }

    /**
     * Sets currentRotationMode to Rotation.SNAKE. Enabled by the Y button.
     * 
     * @return a Command that sets currentRotationMode to Rotation.SNAKE
     */
    public ModeCommand setToSnakeMode() {
        return new ModeCommand(Rotation.SNAKE);
    }

    /**
     * Sets currentRotationMode to Rotation.COMPASS. Enabled by the B button.
     * 
     * @return a Command that sets currentRotationMode to Rotation.SNAKE
     */
    public ModeCommand setToCompassMode() {
        return new ModeCommand(Rotation.COMPASS);
    }

    /**
     * Sets currentRotationMode to Rotation.POINT.
     * 
     * @return
     */
    public ModeCommand setToPointMode() {
        return new ModeCommand(Rotation.POINT);
    }

    /**
     * Slow mode is a speed mode where the robot moves at 25% of its speed
     * capacity.
     * 
     * @return a multiplier of the robots max speed
     */
    private double slowMode() {
        return 0.20;
    }

    /**
     * Normal mode is a speed mode where the robot moves at 50% of its speed
     * capacity.
     * 
     * @return a multiplier of the robots max speed
     */
    private double normalMode() {
        return 0.6;
    }

    /**
     * Fast mode is a speed mode where the robot moves at 100% of its speed
     * capacity.
     * 
     * @return a multiplier of the robots max speed
     */
    private double fastMode() {
        return 1.0d;
    }

    private double bumpMode(double joystickInput, boolean applyLimits) {
        double minSpeed = 0.35; // minimum % of max speed to clear bump
        double maxSpeed = 0.6; // cap bump mode so it’s not too fast

        double scaled = joystickInput * maxSpeed;

        if (!applyLimits) {
            // the scaler here represents how fast the robot should move horizontally when
            // crossing the bump
            return joystickInput * 0.3; // TODO TUNE THIS TO THE ROBOT
        }

        // If the joystick is pushed at all, enforce minimum speed
        if (Math.abs(joystickInput) > 0.05) {
            return Math.copySign(
                    Math.max(Math.abs(scaled), minSpeed),
                    joystickInput);
        }

        return 0.0; // no movement if joystick is centered
    }

    /**
     * Bump rotation mode: holds {@code bumpTargetRotation} using a PID controller
     * so the robot always enters the bump backwards. If the driver pushes the right
     * stick beyond {@link #BUMP_ROTATION_OVERRIDE_THRESHOLD}, joystick input takes
     * full priority and the PID hold is suspended for that loop cycle.
     *
     * @param joystick       the connected Xbox Controller
     * @param drivetrain     the Swerve Drivetrain
     * @param maxAngularRate the maximum rotational rate (rad/s)
     * @return rotation rate in rad/s
     */
    private double bumpRotationMode(final CommandXboxController joystick,
            final CommandSwerveDrivetrain drivetrain,
            final double maxAngularRate) {
        double rightX = applyDeadband(joystick.getRightX());

        // Allow driver to override the hold by pushing the right stick
        if (Math.abs(rightX) > BUMP_ROTATION_OVERRIDE_THRESHOLD) {
            return -rightX * maxAngularRate;
        }

        // Otherwise PID-hold bumpTargetRotation
        double targetRad = bumpTargetRotation.getRadians();
        double currentRad = drivetrain.getState().Pose.getRotation().getRadians();
        bumpRotationController.setSetpoint(targetRad);
        return bumpRotationController.calculate(currentRad);
    }

    /**
     * Standard mode is a rotation mode where the robot's angle is determined from
     * the right stick.
     * The angle adds onto or subracts from the value that the right stick is
     * giving, not directly setting the robot's angle to the angle the right stick
     * points--see CompassMode for that.
     * <p>
     * Full right on the right stick means strongest clockwise rotation,
     * while full left on the right stick means strongest counterclockwise rotation.
     * 
     * @param joystick       the connected Xbox Controller
     * @param maxAngularRate the final double that caps the robot's rotation rate,
     *                       defined in RobotContainer.java
     * @return the right stick's value capped by maxAngularRate
     */
    private double standardMode(final CommandXboxController joystick, final double maxAngularRate) {
        return -applyDeadband(joystick.getRightX()) * (maxAngularRate / (1 + joystick.getLeftTriggerAxis()));
    }

    /**
     * Snake mode is a rotation mode where the robot points in the direction that it
     * is driving in /
     * the direction that the left stick is facing.
     * 
     * @param joystick   the connected Xbox Controller
     * @param drivetrain the Swerve Drivetrain
     * @return a difference in goal angle and current angle calculated using a
     *         PIDController
     */
    private double snakeMode(final CommandXboxController joystick, final CommandSwerveDrivetrain drivetrain) {
        final double joystickX = applyDeadband(joystick.getLeftX());
        final double joystickY = applyDeadband(joystick.getLeftY());

        return calculateForJoystick(joystickX, joystickY, drivetrain);
    }

    /**
     * Compass mode is a rotation mode where the robot points in the direction that
     * the right stick
     * is facing.
     * 
     * @param joystick the connected Xbox Controller
     * @return a difference in goal angle and current angle calculated using a
     *         PIDController
     */
    private double compassMode(final CommandXboxController joystick, final CommandSwerveDrivetrain drivetrain) {
        final double joystickY = applyDeadband(joystick.getRightY());
        final double joystickX = applyDeadband(joystick.getRightX());

        return calculateForJoystick(joystickX, joystickY, drivetrain);
    }

    private double pointMode(final CommandSwerveDrivetrain drivetrain) {
        // Setup point target
        Pose2d targetPose = FieldConstants.BLUE_HUB;

        if (AllianceSymmetry.isRed()) {
            targetPose = AllianceSymmetry.flip(targetPose);
        }

        rotationController.setSetpoint(drivetrain.getAngleToTarget(targetPose).getRadians());

        double currentAngle = drivetrain.getState().Pose.getRotation().getRadians();

        double rateToRotate = rotationController.calculate(currentAngle);

        SmartDashboard.putNumber("MoveMode/PointMode_error", rotationController.getError());
        // System.out.printf("PID error: %.3f, target: %.3f, current: %.3f,
        // rateToRotate: %.3f\n",
        // rotationController.getError(),
        // rotationController.getSetpoint(), currentAngle, rateToRotate);

        return rateToRotate;
    }

    /**
     * Cycles rotation between STANDARD and the point mode selected by
     * {@link #useVelocityCompensatedPoint}:
     * <ul>
     * <li>If currently in STANDARD: activates POINT or
     * POINT_VELOCITY_COMPENSATED depending on the feature switch.</li>
     * <li>If currently in any point mode: returns to STANDARD.</li>
     * </ul>
     * The feature switch ({@code MoveMode/Use Velocity Compensated Point}) can be
     * flipped live from Elastic Dashboard and takes effect on the next toggle
     * press.
     *
     * @return a Command that advances the rotation mode
     */
    public Command togglePointMode() {
        return Commands.runOnce(() -> {
            // Read the live NT value each time the button is pressed so a mid-run
            // dashboard change takes effect immediately on the next press.
            useVelocityCompensatedPoint = velocityCompPointEntry.get(useVelocityCompensatedPoint);

            boolean inAnyPointMode = Rotation.POINT.equals(currentRotationMode)
                    || Rotation.POINT_VELOCITY_COMPENSATED.equals(currentRotationMode);

            if (inAnyPointMode) {
                setToStandardMode().initialize();
            } else if (useVelocityCompensatedPoint) {
                new ModeCommand(Rotation.POINT_VELOCITY_COMPENSATED).initialize();
            } else {
                setToPointMode().initialize();
            }
        });
    }

    /**
     * Point velocity-compensated mode: behaves like {@link #pointMode} but uses
     * {@link CommandSwerveDrivetrain#getAngleToTargetWithVelocityCompensation} so
     * the robot leads the target by the projectile flight time, compensating for
     * the robot's own translational velocity.
     *
     * @param drivetrain the Swerve Drivetrain
     * @return rotation rate in rad/s
     */
    private double pointVelocityCompensatedMode(final CommandSwerveDrivetrain drivetrain) {
        Pose2d targetPose = FieldConstants.BLUE_HUB;

        if (AllianceSymmetry.isRed()) {
            targetPose = AllianceSymmetry.flip(targetPose);
        }

        Rotation2d compensatedAngle = drivetrain.getAngleToTargetWithVelocityCompensation(targetPose);
        rotationController.setSetpoint(compensatedAngle.getRadians());

        double currentRad = drivetrain.getState().Pose.getRotation().getRadians();
        double rateToRotate = rotationController.calculate(currentRad);

        // System.out.printf("[VelComp] PID error: %.3f, target: %.3f, current: %.3f,
        // rate: %.3f\n",
        // rotationController.getError(),
        // rotationController.getSetpoint(), currentRad, rateToRotate);

        SmartDashboard.putNumber("MoveMode/VelComp_error", rotationController.getError());

        return rateToRotate;
    }

    /**
     * Helper method for snakeMode() and compassMode() that calculates a difference
     * in a goal angle(given by joystick direction) and a current angle(given by
     * robot / drivetrain direction) from a PIDController. The only difference in
     * snakeMode() and compassMode() is that snakeMode() uses the left stick while
     * compassMode() uses the right.
     * 
     * @param joystickX  X-value from joystick
     * @param joystickY  Y-value form joystick
     * @param drivetrain the Swerve Drivetrain
     * @return a difference in goal angle and current angle calculated using a
     *         PIDController
     */
    private double calculateForJoystick(final double joystickX, final double joystickY,
            final CommandSwerveDrivetrain drivetrain) {
        // If no input from joystick, don't change angle
        if (joystickX == 0f && joystickY == 0f) {
            return 0;
        }

        goalAngle = -Math.atan2(joystickY, joystickX) - Math.PI / 2; // radians
        currentAngle = drivetrain.getState().Pose.getRotation().getRadians();

        rotationController.setSetpoint(goalAngle);
        calculate = rotationController.calculate(currentAngle);

        return calculate;
    }

    /**
     * Manages Elastic display initialization for the currentMode.
     */
    private void elasticInit() {
        final NetworkTable table = NetworkTableInstance.getDefault().getTable("DataTable");

        final StringTopic speedModeTopic = table.getStringTopic("Speed Mode");
        speedModePublisher = speedModeTopic.publish();

        final StringTopic rotationModeTopic = table.getStringTopic("Rotation Mode");
        rotationModePublisher = rotationModeTopic.publish();

        // Two-way boolean entry so Elastic toggle widget can read and write the flag
        final NetworkTable moveModeTable = NetworkTableInstance.getDefault().getTable("SmartDashboard")
                .getSubTable("MoveMode");
        final BooleanTopic velocityCompTopic = moveModeTable.getBooleanTopic("Use Velocity Compensated Point");
        velocityCompPointEntry = velocityCompTopic.getEntry(useVelocityCompensatedPoint);
        velocityCompPointEntry.set(useVelocityCompensatedPoint); // publish initial value

        elasticUpdate();
    }

    /**
     * Manages Elastic display whenever the currentSpeedMode or currentRotationMode
     * is changed.
     */
    private void elasticUpdate() {
        final String strSpeedMode = currentSpeedMode.toString();
        speedModePublisher.set(strSpeedMode);
        SmartDashboard.putString("MoveMode/Speed Mode", strSpeedMode);

        final String strRotationMode = currentRotationMode.toString();
        rotationModePublisher.set(strRotationMode);
        SmartDashboard.putString("MoveMode/Rotation Mode", strRotationMode);
    }
}