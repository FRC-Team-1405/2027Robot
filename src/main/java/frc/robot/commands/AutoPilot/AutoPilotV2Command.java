package frc.robot.commands.AutoPilot;

import static edu.wpi.first.units.Units.Centimeters;
import static edu.wpi.first.units.Units.Degrees;

import java.util.Optional;
import java.util.function.Supplier;

import com.ctre.phoenix6.hardware.CANcoder;
import com.ctre.phoenix6.hardware.TalonFX;
import com.ctre.phoenix6.swerve.SwerveModule;
import com.ctre.phoenix6.swerve.SwerveModule.DriveRequestType;
import com.ctre.phoenix6.swerve.SwerveRequest;
import com.ctre.phoenix6.swerve.SwerveRequest.ForwardPerspectiveValue;
import com.therekrab.autopilot.APConstraints;
import com.therekrab.autopilot.APProfile;
import com.therekrab.autopilot.APTarget;
import com.therekrab.autopilot.Autopilot;
import com.therekrab.autopilot.Autopilot.APResult;

import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Rotation2d;
import edu.wpi.first.math.geometry.Translation2d;
import edu.wpi.first.math.kinematics.ChassisSpeeds;
import edu.wpi.first.networktables.NetworkTableInstance;
import edu.wpi.first.networktables.StructPublisher;
import edu.wpi.first.wpilibj.DriverStation;
import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import frc.robot.constants.FeatureSwitches;
import frc.robot.lib.AllianceSymmetry;
import frc.robot.lib.FinneyCommand;
import frc.robot.lib.FinneyLogger;
import frc.robot.subsystems.CommandSwerveDrivetrain;
import frc.robot.subsystems.SwerveFeatures;

/**
 * Simplified AutoPilot command — single control path, no theta controller
 * switching.
 *
 * <p>
 * Key differences from {@link AutoPilotCommand}:
 * <ul>
 * <li>Uses {@code FieldCentricFacingAngle} exclusively — no
 * {@code ApplyRobotSpeeds}, no manual frame conversion.</li>
 * <li>No distance-to-target code-path switching; every cycle takes the same
 * path.</li>
 * <li>Logs both robot-relative and field-relative speeds so AutoPilot frame
 * assumptions are easy to validate during tuning.</li>
 * <li>Comprehensive per-module drive motor logging for oscillation
 * debugging.</li>
 * </ul>
 *
 * <pre>
 * // Basic usage
 * new AutoPilotV2Command.Builder(targetSupplier, drivetrain, "name").build();
 *
 * // With alliance flipping and custom heading PID
 * new AutoPilotV2Command.Builder(targetSupplier, drivetrain, "name")
 *         .withFlipPoseForAlliance(true)
 *         .withHeadingPID(1.5, 0.05)
 *         .build();
 * </pre>
 */
public class AutoPilotV2Command extends FinneyCommand {
    private final FinneyLogger fLogger = new FinneyLogger(this.getClass().getSimpleName());

    public static final double DEFAULT_XY_THRESHOLD = 4.0;
    public static final double DEFAULT_THETA_THRESHOLD = 6.0;
    public static final double DEFAULT_BEELINE_THRESHOLD = 16.0;

    private static final String NT = "APv2/";

    private final StructPublisher<Pose2d> targetPublisher = NetworkTableInstance.getDefault()
            .getStructTopic("SmartDashboard/Auto/APv2/TargetPose", Pose2d.struct).publish();

    // --- AutoPilot components ---
    private static final APConstraints kDefaultConstraints = new APConstraints()
            .withAcceleration(8.0)
            .withVelocity(4.0)
            .withJerk(67.0);

    private final APConstraints kConstraints;
    private final APProfile kProfile;
    private Autopilot kAutopilot;

    // --- Instance state ---
    private APTarget m_target;
    private final Supplier<Pose2d> m_targetSupplier;
    private final CommandSwerveDrivetrain m_drivetrain;
    private final Optional<Rotation2d> m_entryAngle;
    private final boolean m_flipPoseForAlliance;
    private final String commandName;
    private final double m_beelineRadiusMeters;
    private final double m_headingDeadbandDegrees;
    private boolean m_nearTargetVisionSuppressed = false;
    private boolean m_previousVisionOdometryUpdatesEnabled = true;

    private boolean isVelocityThresholdActive = false;
    private double velocityThreshold = 0.5;

    private Supplier<Double> maxVelocity = null;

    // Single swerve request for every cycle
    private final SwerveRequest.FieldCentricFacingAngle m_request;

    // Logging helpers
    private int m_cycleCount = 0;
    private static final int MODULE_LOG_INTERVAL = 5;

    // -----------------------------------------------------------------------
    // Builder
    // -----------------------------------------------------------------------

    public static class Builder {
        private final Supplier<Pose2d> targetSupplier;
        private final CommandSwerveDrivetrain drivetrain;
        private final String commandName;

        private Optional<Rotation2d> entryAngle = Optional.empty();
        private boolean flipPoseForAlliance = false;
        private APConstraints constraints = kDefaultConstraints;
        private double errorXYCentimeters = DEFAULT_XY_THRESHOLD;
        private double errorThetaDegrees = DEFAULT_THETA_THRESHOLD;
        private double beelineRadiusCentimeters = DEFAULT_BEELINE_THRESHOLD;
        private double headingKP = 8.0; // was 2
        private double headingKD = 0.0;
        private double headingDeadbandDegrees = 1.0;
        private boolean isVelocityThresholdActive = false;
        private double velocityThreshold = 0.5;

        private Supplier<Double> maxVelocity = null;

        public Builder(Supplier<Pose2d> targetSupplier, CommandSwerveDrivetrain drivetrain, String commandName) {
            this.targetSupplier = targetSupplier;
            this.drivetrain = drivetrain;
            this.commandName = commandName;
        }

        public Builder withEntryAngle(Rotation2d entryAngle) {
            this.entryAngle = Optional.of(entryAngle);
            return this;
        }

        public Builder withFlipPoseForAlliance(boolean flip) {
            this.flipPoseForAlliance = flip;
            return this;
        }

        public Builder withConstraints(APConstraints constraints) {
            this.constraints = constraints;
            return this;
        }

        public Builder withVelocityThreshold(double velocityThreshold) {
            this.isVelocityThresholdActive = true;
            this.velocityThreshold = velocityThreshold;
            return this;
        }

        public Builder withMaxVelocity(Supplier<Double> maxVelocity) {
            this.maxVelocity = maxVelocity;
            return this;
        }

        /**
         * @param errorXYCm       XY error threshold in centimeters
         * @param errorThetaDeg   theta error threshold in degrees
         * @param beelineRadiusCm beeline radius in centimeters
         */
        public Builder withProfileThresholds(double errorXYCm, double errorThetaDeg, double beelineRadiusCm) {
            this.errorXYCentimeters = errorXYCm;
            this.errorThetaDegrees = errorThetaDeg;
            this.beelineRadiusCentimeters = beelineRadiusCm;
            return this;
        }

        /**
         * Tune the heading PID used by {@code FieldCentricFacingAngle}.
         * Default is kP=2.0, kD=0.0.
         */
        public Builder withHeadingPID(double kP, double kD) {
            this.headingKP = kP;
            this.headingKD = kD;
            return this;
        }

        public Builder withHeadingDeadband(double deadbandDegrees) {
            this.headingDeadbandDegrees = deadbandDegrees;
            return this;
        }

        public AutoPilotV2Command build() {
            return new AutoPilotV2Command(this);
        }
    }

    // -----------------------------------------------------------------------
    // Construction
    // -----------------------------------------------------------------------

    private AutoPilotV2Command(Builder b) {
        m_targetSupplier = b.targetSupplier;
        m_drivetrain = b.drivetrain;
        m_entryAngle = b.entryAngle;
        m_flipPoseForAlliance = b.flipPoseForAlliance;
        commandName = b.commandName;

        this.isVelocityThresholdActive = b.isVelocityThresholdActive;
        this.velocityThreshold = b.velocityThreshold;
        this.maxVelocity = b.maxVelocity;

        kConstraints = b.constraints;
        kProfile = new APProfile(kConstraints)
                .withErrorXY(Centimeters.of(b.errorXYCentimeters))
                .withErrorTheta(Degrees.of(b.errorThetaDegrees))
                .withBeelineRadius(Centimeters.of(b.beelineRadiusCentimeters));
        kAutopilot = new Autopilot(kProfile);
        m_beelineRadiusMeters = b.beelineRadiusCentimeters / 100.0;
        m_headingDeadbandDegrees = b.headingDeadbandDegrees;

        m_request = new SwerveRequest.FieldCentricFacingAngle()
                .withForwardPerspective(ForwardPerspectiveValue.BlueAlliance)
                .withDriveRequestType(DriveRequestType.Velocity)
                .withHeadingPID(b.headingKP, 0, b.headingKD);

        addRequirements(m_drivetrain);
    }

    // -----------------------------------------------------------------------
    // Command lifecycle
    // -----------------------------------------------------------------------

    @Override
    public void initialize() {
        super.initialize();
        m_cycleCount = 0;
        m_nearTargetVisionSuppressed = false;
        m_previousVisionOdometryUpdatesEnabled = m_drivetrain.areVisionOdometryUpdatesEnabled();

        if (m_flipPoseForAlliance
                && DriverStation.Alliance.Red.equals(DriverStation.getAlliance().orElse(null))) {
            m_target = new APTarget(AllianceSymmetry.flip(m_targetSupplier.get()));
        } else {
            m_target = new APTarget(m_targetSupplier.get());
        }

        targetPublisher.set(m_target.getReference());

        Pose2d currentPose = m_drivetrain.getState().Pose;
        double dist = currentPose.getTranslation().getDistance(m_target.getReference().getTranslation());

        fLogger.log(
                "INIT %s | target(%.2f,%.2f,%.1fdeg) current(%.2f,%.2f,%.1fdeg) dist=%.2fm, activeVelThresh: %s, velThresh: %s",
                getName(),
                m_target.getReference().getX(), m_target.getReference().getY(),
                m_target.getReference().getRotation().getDegrees(),
                currentPose.getX(), currentPose.getY(),
                currentPose.getRotation().getDegrees(),
                dist, isVelocityThresholdActive, velocityThreshold);
    }

    @Override
    public void execute() {
        m_cycleCount++;

        // --- 1. Read current state ---
        Pose2d pose = m_drivetrain.getState().Pose;
        ChassisSpeeds robotSpeeds = m_drivetrain.getState().Speeds;

        // --- 2. Convert robot-relative speeds → field-relative for diagnostics ---
        ChassisSpeeds fieldSpeeds = toFieldRelative(robotSpeeds, pose.getRotation());
        double distToTarget = pose.getTranslation().getDistance(m_target.getReference().getTranslation());
        updateVisionSuppression(distToTarget);

        // --- 3. Compute AutoPilot result ---
        Optional<Rotation2d> fieldEntryAngle = m_entryAngle
                .map(a -> a.plus(m_target.getReference().getRotation()));

        if (maxVelocity != null) {
            SmartDashboard.putNumber(NT + "maxVelocity", maxVelocity.get());
            APConstraints newConstraints = kConstraints.withVelocity(maxVelocity.get());
            APProfile newProfile = kProfile.withConstraints(newConstraints);
            kAutopilot = new Autopilot(newProfile);
        }

        APResult out;
        if (fieldEntryAngle.isPresent()) {
            out = kAutopilot.calculate(pose,
                    robotSpeeds,
                    m_target.withEntryAngle(fieldEntryAngle.get()));
        } else {
            out = kAutopilot.calculate(pose,
                    robotSpeeds,
                    m_target.withoutEntryAngle());
        }

        // --- 4. Apply single control request ---
        // FieldCentricFacingAngle handles field→module kinematics and heading PID
        // internally. No frame conversion, no code-path branching.
        Rotation2d commandedTargetDirection = applyHeadingDeadband(out.targetAngle(), pose.getRotation());
        m_drivetrain.setControl(m_request
                .withVelocityX(out.vx())
                .withVelocityY(out.vy())
                .withTargetDirection(commandedTargetDirection));

        // --- 5. Diagnostic logging ---
        logAPOutputs(out, pose, robotSpeeds, fieldSpeeds, commandedTargetDirection);

        if (m_cycleCount % MODULE_LOG_INTERVAL == 0) {
            logModuleDiagnostics();
        }
    }

    @Override
    public boolean isFinished() {
        if (isVelocityThresholdActive) {
            double velocity = SwerveFeatures.getRobotVelocity(m_drivetrain);
            fLogger.log("VELTHRESH RobotVelocity: " + velocity);
            return velocity <= velocityThreshold
                    && kAutopilot.atTarget(m_drivetrain.getState().Pose, m_target);
        } else {
            double velocity = SwerveFeatures.getRobotVelocity(m_drivetrain);
            fLogger.log("NO VELTHRESH RobotVelocity: " + velocity);
            return kAutopilot.atTarget(m_drivetrain.getState().Pose, m_target);
        }
    }

    @Override
    public void end(boolean interrupted) {
        super.end(interrupted);
        m_nearTargetVisionSuppressed = false;
        m_drivetrain.setVisionOdometryUpdatesEnabled(m_previousVisionOdometryUpdatesEnabled);

        m_drivetrain.setControl(m_request
                .withVelocityX(0)
                .withVelocityY(0)
                .withTargetDirection(m_drivetrain.getState().Pose.getRotation()));

        Pose2d finalPose = m_drivetrain.getState().Pose;
        double finalDist = finalPose.getTranslation()
                .getDistance(m_target.getReference().getTranslation());
        double finalHdgErr = m_target.getReference().getRotation()
                .minus(finalPose.getRotation()).getDegrees();

        fLogger.log(
                "END %s | interrupted=%s dist=%.3fm hdgErr=%.1fdeg final(%.2f,%.2f,%.1fdeg) target(%.2f,%.2f,%.1fdeg)",
                getName(), interrupted,
                finalDist, finalHdgErr,
                finalPose.getX(), finalPose.getY(), finalPose.getRotation().getDegrees(),
                m_target.getReference().getX(), m_target.getReference().getY(),
                m_target.getReference().getRotation().getDegrees());
    }

    @Override
    public String getName() {
        return "APv2(" + commandName + ")";
    }

    // -----------------------------------------------------------------------
    // Logging
    // -----------------------------------------------------------------------

    /**
     * Logs AutoPilot inputs/outputs every cycle.
     *
     * <p>
     * <b>How to read these in AdvantageScope / SmartDashboard:</b>
     * <ul>
     * <li>{@code APv2/AP_vx_mps}, {@code AP_vy_mps} — field-relative velocity
     * AutoPilot is commanding. If THESE oscillate, the problem is upstream
     * of driveGains (AutoPilot itself or the speed input).</li>
     * <li>{@code APv2/fieldSpeed_*} vs {@code robotSpeed_*} — compare the
     * speed conversion. If {@code fieldSpeed} looks wrong when the robot
     * is rotated, the conversion is broken.</li>
     * <li>{@code APv2/headingError_deg} — heading error fed to
     * FieldCentricFacingAngle's internal PID. Large/oscillating values
     * inject rotational velocity into module drive motors.</li>
     * </ul>
     */
    private void logAPOutputs(APResult out, Pose2d pose,
            ChassisSpeeds robotSpeeds, ChassisSpeeds fieldSpeeds, Rotation2d commandedTargetDirection) {
        double apVx = out.vx().baseUnitMagnitude();
        double apVy = out.vy().baseUnitMagnitude();
        double apSpeed = Math.hypot(apVx, apVy);
        double headingErr = out.targetAngle().minus(pose.getRotation()).getDegrees();
        double headingCmdErr = commandedTargetDirection.minus(pose.getRotation()).getDegrees();
        double dist = pose.getTranslation().getDistance(m_target.getReference().getTranslation());

        // AP command outputs
        SmartDashboard.putNumber(NT + "AP_vx_mps", apVx);
        SmartDashboard.putNumber(NT + "AP_vy_mps", apVy);
        SmartDashboard.putNumber(NT + "AP_speed_mps", apSpeed);
        SmartDashboard.putNumber(NT + "AP_targetAngle_deg", out.targetAngle().getDegrees());
        SmartDashboard.putNumber(NT + "commandedTargetAngle_deg", commandedTargetDirection.getDegrees());

        // State
        SmartDashboard.putNumber(NT + "headingError_deg", headingErr);
        SmartDashboard.putNumber(NT + "headingCommandError_deg", headingCmdErr);
        SmartDashboard.putBoolean(NT + "headingDeadbandActive", Math.abs(headingErr) <= m_headingDeadbandDegrees);
        SmartDashboard.putNumber(NT + "distToTarget_m", dist);
        SmartDashboard.putBoolean(NT + "visionSuppressedNearTarget", m_nearTargetVisionSuppressed);

        // Speed comparison: robot-relative vs field-relative
        SmartDashboard.putNumber(NT + "robotSpeed_vx", robotSpeeds.vxMetersPerSecond);
        SmartDashboard.putNumber(NT + "robotSpeed_vy", robotSpeeds.vyMetersPerSecond);
        SmartDashboard.putNumber(NT + "robotSpeed_omega", robotSpeeds.omegaRadiansPerSecond);
        SmartDashboard.putNumber(NT + "fieldSpeed_vx", fieldSpeeds.vxMetersPerSecond);
        SmartDashboard.putNumber(NT + "fieldSpeed_vy", fieldSpeeds.vyMetersPerSecond);

        fLogger.log("vx:%.3f vy:%.3f spd:%.3f hdg:%.1fdeg dist:%.3fm | rVx:%.3f rVy:%.3f fVx:%.3f fVy:%.3f",
                apVx, apVy, apSpeed, headingErr, dist,
                robotSpeeds.vxMetersPerSecond, robotSpeeds.vyMetersPerSecond,
                fieldSpeeds.vxMetersPerSecond, fieldSpeeds.vyMetersPerSecond);
    }

    /**
     * Logs per-module drive motor closed-loop data (throttled).
     *
     * <p>
     * <b>How to interpret:</b>
     * <ul>
     * <li>{@code clRef} (closedLoopReference) — velocity the motor is TOLD to
     * achieve. If this oscillates, the swerve kinematics or heading PID is
     * the source, not driveGains.</li>
     * <li>{@code clErr} (closedLoopError) — gap between reference and actual.
     * Sign-flipping every few cycles = oscillation.</li>
     * <li>{@code clOut} (closedLoopOutput) — PID output voltage. If this
     * alternates ±, the motor is hunting. Reduce kP or increase kD.</li>
     * <li>{@code vel} — actual motor velocity (rot/s). Compare to
     * {@code clRef}.</li>
     * <li>{@code volts} — actual voltage applied to the motor.</li>
     * </ul>
     */
    private void logModuleDiagnostics() {
        @SuppressWarnings("unchecked")
        SwerveModule<TalonFX, TalonFX, CANcoder>[] modules = m_drivetrain.getModules();

        for (int i = 0; i < modules.length; i++) {
            TalonFX driveMotor = modules[i].getDriveMotor();
            String p = NT + "M" + i + "/";

            SmartDashboard.putNumber(p + "clRef", driveMotor.getClosedLoopReference().getValueAsDouble());
            SmartDashboard.putNumber(p + "clErr", driveMotor.getClosedLoopError().getValueAsDouble());
            SmartDashboard.putNumber(p + "clOut", driveMotor.getClosedLoopOutput().getValueAsDouble());
            SmartDashboard.putNumber(p + "vel", driveMotor.getVelocity().getValueAsDouble());
            SmartDashboard.putNumber(p + "volts", driveMotor.getMotorVoltage().getValueAsDouble());
        }
    }

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    /**
     * Converts robot-relative ChassisSpeeds to field-relative by rotating the
     * translational component by the robot's heading.
     */
    private static ChassisSpeeds toFieldRelative(ChassisSpeeds robotSpeeds, Rotation2d robotAngle) {
        Translation2d vel = new Translation2d(
                robotSpeeds.vxMetersPerSecond,
                robotSpeeds.vyMetersPerSecond);
        Translation2d fieldVel = vel.rotateBy(robotAngle);
        return new ChassisSpeeds(
                fieldVel.getX(),
                fieldVel.getY(),
                robotSpeeds.omegaRadiansPerSecond);
    }

    private Rotation2d applyHeadingDeadband(Rotation2d targetAngle, Rotation2d currentAngle) {
        double headingErrorDegrees = targetAngle.minus(currentAngle).getDegrees();
        if (Math.abs(headingErrorDegrees) <= m_headingDeadbandDegrees) {
            return currentAngle;
        }
        return targetAngle;
    }

    private void updateVisionSuppression(double distToTargetMeters) {
        boolean shouldSuppressVision = FeatureSwitches.DISABLE_VISION_ODOM_NEAR_AUTOPILOT_TARGET
                && distToTargetMeters <= m_beelineRadiusMeters;
        if (shouldSuppressVision != m_nearTargetVisionSuppressed) {
            m_nearTargetVisionSuppressed = shouldSuppressVision;
            m_drivetrain.setVisionOdometryUpdatesEnabled(!shouldSuppressVision);
        }
    }
}
