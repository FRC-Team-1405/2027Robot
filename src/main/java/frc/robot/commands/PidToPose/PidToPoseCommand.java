package frc.robot.commands.PidToPose;

import java.util.List;
import java.util.function.Supplier;

import com.ctre.phoenix6.swerve.SwerveModule.DriveRequestType;
import com.ctre.phoenix6.swerve.SwerveRequest;
import com.therekrab.autopilot.APConstraints;

import edu.wpi.first.math.controller.ProfiledPIDController;
import edu.wpi.first.math.filter.LinearFilter;
import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Rotation2d;
import edu.wpi.first.math.geometry.Translation2d;
import edu.wpi.first.math.kinematics.ChassisSpeeds;
import edu.wpi.first.math.trajectory.TrapezoidProfile;
import edu.wpi.first.math.util.Units;
import edu.wpi.first.networktables.NetworkTableInstance;
import edu.wpi.first.networktables.StructPublisher;
import edu.wpi.first.util.datalog.DataLog;
import edu.wpi.first.util.datalog.StringLogEntry;
import edu.wpi.first.wpilibj.DataLogManager;
import edu.wpi.first.wpilibj.DriverStation;
import edu.wpi.first.wpilibj.DriverStation.Alliance;
import edu.wpi.first.wpilibj.smartdashboard.Mechanism2d;
import edu.wpi.first.wpilibj.smartdashboard.MechanismLigament2d;
import edu.wpi.first.wpilibj.smartdashboard.MechanismRoot2d;
import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import edu.wpi.first.wpilibj.util.Color;
import edu.wpi.first.wpilibj.util.Color8Bit;
import frc.robot.lib.AllianceSymmetry;
import frc.robot.lib.FinneyCommand;
import frc.robot.lib.FinneyLogger;
import frc.robot.subsystems.CommandSwerveDrivetrain;

/**
 * Command that uses PID control to navigate the robot to a target pose.
 * 
 * <p>
 * Use the Builder pattern to create instances:
 * 
 * <pre>
 * // Simple usage - default constraints, no name
 * new PidToPoseCommand.Builder(drivetrain, targetPoseSupplier, toleranceInches)
 *                 .build();
 * 
 * // With field symmetry (flip for red alliance)
 * new PidToPoseCommand.Builder(drivetrain, targetPoseSupplier, toleranceInches)
 *                 .withFieldSymmetry(true)
 *                 .withName("ScoreReef")
 *                 .build();
 * 
 * // With velocities for path chaining
 * new PidToPoseCommand.Builder(drivetrain, targetPoseSupplier, toleranceInches)
 *                 .withInitialVelocity(2.0)
 *                 .withEndVelocity(1.5)
 *                 .withName("ApproachTarget")
 *                 .build();
 * 
 * // With REEF constraints (faster)
 * new PidToPoseCommand.Builder(drivetrain, targetPoseSupplier, toleranceInches)
 *                 .withReefConstraints()
 *                 .withName("ReefScore")
 *                 .build();
 * 
 * // With custom constraints
 * new PidToPoseCommand.Builder(drivetrain, targetPoseSupplier, toleranceInches)
 *                 .withConstraints(new TrapezoidProfile.Constraints(6, 8))
 *                 .withName("FastMove")
 *                 .build();
 * </pre>
 */
public class PidToPoseCommand extends FinneyCommand {
        private final FinneyLogger fLogger = new FinneyLogger(this.getClass().getSimpleName());

        private static final TrapezoidProfile.Constraints DEFAULT_CONSTRAINTS = new TrapezoidProfile.Constraints(4, 5);
        private static final TrapezoidProfile.Constraints REEF_DEFAULT_CONSTRAINTS = new TrapezoidProfile.Constraints(5,
                        6);

        private final boolean DEBUG_LOGGING_ENABLED = false;
        DataLog log = DataLogManager.getLog();
        StringLogEntry commandLog = new StringLogEntry(log, "/Commands/P2P");

        private final CommandSwerveDrivetrain drive;
        private final Supplier<Pose2d> targetPose;
        private final double toleranceInches;
        private final double toleranceDegrees;

        // a wait timer to run the auto for at least that many seconds. used for
        // rotating in place currently very hacky
        private double waitSeconds = 0;
        private final boolean applyFieldSymmetryToPose;
        private final double initialStateVelocity;
        private Translation2d initialVelocityVector;
        private final double endStateVelocity;
        private final String commandName; // used to improve logging, if not provided targetPose is used
        private final TrapezoidProfile.Constraints drivingContraints;

        private final ProfiledPIDController xController;
        private final ProfiledPIDController yController;
        private final ProfiledPIDController thetaController;

        private Pose2d poseToMoveTo;
        private StructPublisher<Pose2d> pidToPosePublisher = NetworkTableInstance.getDefault()
                        .getStructTopic("SmartDashboard/Auto/AUTOPILOT/PID_TO_POSE/TargetPose", Pose2d.struct)
                        .publish();

        // initial velocity mechanism
        Mechanism2d initialMechanism;
        MechanismRoot2d initialOrigin;

        MechanismLigament2d initialDeltaLigament;
        MechanismLigament2d initialDirectionLigament;
        MechanismLigament2d initialVelocityLigament;

        // execution velocity mechanism
        Mechanism2d loopMechanism;
        MechanismRoot2d loopOrigin;

        MechanismLigament2d loopDeltaLigament;
        MechanismLigament2d loopDirectionLigament;
        MechanismLigament2d loopVelocityLigament;

        double previousLoopBiggestError = 0;
        double currentLoopBiggestError = 0;
        boolean errorIncreasing = true;

        LinearFilter errorAverage = LinearFilter.movingAverage(10); // 10-sample window
        double previousSmoothedError;
        double smoothedError;

        public static final SwerveRequest.ApplyFieldSpeeds pidToPose_FieldSpeeds = new SwerveRequest.ApplyFieldSpeeds()
                        .withDriveRequestType(DriveRequestType.Velocity);

        /**
         * Private constructor - use Builder to create instances
         */
        private PidToPoseCommand(Builder builder) {
                this.drive = builder.drive;
                this.targetPose = builder.targetPose;
                this.toleranceInches = builder.toleranceInches;
                this.toleranceDegrees = builder.toleranceDegrees;
                this.applyFieldSymmetryToPose = builder.applyFieldSymmetryToPose;
                this.initialStateVelocity = builder.initialStateVelocity;
                this.endStateVelocity = builder.endStateVelocity;
                this.commandName = builder.commandName;
                this.drivingContraints = builder.drivingContraints;
                this.waitSeconds = builder.waitSeconds;

                xController = new ProfiledPIDController(2.5, 0, 0, drivingContraints);
                yController = new ProfiledPIDController(2.5, 0, 0, drivingContraints);
                thetaController = new ProfiledPIDController(5, 0, 0, DEFAULT_CONSTRAINTS);
                thetaController.enableContinuousInput(-Math.PI, Math.PI); // Enable angle wrapping

                initialMechanism = new Mechanism2d(2, 2); // 2x2 unit canvas
                initialOrigin = initialMechanism.getRoot("initialOrigin", 1, 1); // center of canvas

                initialDeltaLigament = initialOrigin
                                .append(new MechanismLigament2d("initialdelta", 0, 0, 1, new Color8Bit(Color.kBlue)));
                initialDirectionLigament = initialOrigin
                                .append(new MechanismLigament2d("initialdirection", 0, 0, 1,
                                                new Color8Bit(Color.kGreen)));
                initialVelocityLigament = initialOrigin
                                .append(new MechanismLigament2d("initialvelocity", 0, 0, 1, new Color8Bit(Color.kRed)));

                loopMechanism = new Mechanism2d(2, 2); // 2x2 unit canvas
                loopOrigin = loopMechanism.getRoot("loopOrigin", 1, 1); // center of canvas

                loopDeltaLigament = loopOrigin
                                .append(new MechanismLigament2d("loopdelta", 0, 0, 1, new Color8Bit(Color.kBlue)));
                loopDirectionLigament = loopOrigin
                                .append(new MechanismLigament2d("loopdirection", 0, 0, 1, new Color8Bit(Color.kGreen)));
                loopVelocityLigament = loopOrigin
                                .append(new MechanismLigament2d("loopvelocity", 0, 0, 1, new Color8Bit(Color.kRed)));

                // SmartDashboard.putData("P2P_InitialVectorMechanism", initialMechanism);
                // SmartDashboard.putData("P2P_LoopVectorMechanism", loopMechanism);

                addRequirements(drive);

                this.setName("PidToPose");
        }

        /**
         * Builder class for PidToPoseCommand
         */
        public static class Builder {
                // Required parameters
                private final CommandSwerveDrivetrain drive;
                private final Supplier<Pose2d> targetPose;
                private final String commandName;

                // Optional parameters with default values
                private boolean applyFieldSymmetryToPose = false;
                private double initialStateVelocity = 0;
                private double endStateVelocity = 0;
                private double toleranceInches = 3.0;
                private double toleranceDegrees = 3.0;
                private double waitSeconds = 0;
                private TrapezoidProfile.Constraints drivingContraints = DEFAULT_CONSTRAINTS;

                public Builder(Supplier<Pose2d> targetPose, CommandSwerveDrivetrain drive, String commandName) {
                        this.drive = drive;
                        this.targetPose = targetPose;
                        this.commandName = commandName;
                }

                public Builder withFlipPoseForAlliance(boolean applyFieldSymmetryToPose) {
                        this.applyFieldSymmetryToPose = applyFieldSymmetryToPose;
                        return this;
                }

                public Builder withInitialVelocity(double initialStateVelocity) {
                        this.initialStateVelocity = initialStateVelocity;
                        return this;
                }

                public Builder withEndVelocity(double endStateVelocity) {
                        this.endStateVelocity = endStateVelocity;
                        return this;
                }

                public Builder withTolerance(double toleranceInches) {
                        this.toleranceInches = toleranceInches;
                        return this;
                }

                public Builder withThetaTolerance(double toleranceDegrees) {
                        this.toleranceDegrees = toleranceDegrees;
                        return this;
                }

                // public Builder withConstraints(APConstraints fullfieldconstraints) {
                // this.drivingContraints = fullfieldconstraints;
                // return this;
                // }

                public Builder withWaitSeconds(double waitSeconds) {
                        this.waitSeconds = waitSeconds;
                        return this;
                }

                public PidToPoseCommand build() {
                        return new PidToPoseCommand(this);
                }
        }

        @Override
        public void initialize() {
                super.initialize();
                Pose2d symmetricPose = AllianceSymmetry.isBlue()
                                ? targetPose.get()
                                : AllianceSymmetry.flip(targetPose.get());
                poseToMoveTo = applyFieldSymmetryToPose ? symmetricPose : targetPose.get();
                pidToPosePublisher.set(poseToMoveTo);

                log("Target pose: " + targetPose);
                log("Pose to move to (after symmetry): " + poseToMoveTo);
                log("Current pose: " + drive.getState().Pose);

                // Without resetting when we chain commands together the robot will drive full
                // speed in a weird direction. unclear why but this fixes it.
                Pose2d currentPose = drive.getState().Pose;

                Translation2d delta = poseToMoveTo.getTranslation().minus(currentPose.getTranslation());
                Translation2d direction = delta.div(delta.getNorm()); // get a unit vector
                initialVelocityVector = direction.times(initialStateVelocity);

                // // MECHANISM

                // double deltaLength = delta.getNorm();
                // double deltaAngle = delta.getAngle().getDegrees(); // blue

                // double directionLength = 1.0; // unit vector
                // double directionAngle = direction.getAngle().getDegrees(); // green

                // double velocityLength = initialVelocityVector.getNorm();
                // double velocityAngle;
                // if (initialVelocityVector.getNorm() < 1e-6) {
                // velocityAngle = 0.0; // protect against error: x and y components of
                // Rotation2d are zero
                // } else {
                // velocityAngle = initialVelocityVector.getAngle().getDegrees(); // red
                // }

                // initialDeltaLigament.setLength(deltaLength);
                // initialDeltaLigament.setAngle(deltaAngle);

                // initialDirectionLigament.setLength(directionLength);
                // initialDirectionLigament.setAngle(directionAngle);

                // initialVelocityLigament.setLength(velocityLength);
                // initialVelocityLigament.setAngle(velocityAngle);

                // // MECHANISM

                xController.reset(new TrapezoidProfile.State(currentPose.getX(), initialVelocityVector.getX()));
                yController.reset(new TrapezoidProfile.State(currentPose.getY(), initialVelocityVector.getY()));
                thetaController.reset(new TrapezoidProfile.State(currentPose.getRotation().getRadians(), 0)); // TODO:
                                                                                                              // provide
                                                                                                              // a
                                                                                                              // value?

                // preload controllers
                if (Math.abs(initialStateVelocity) > 0) {
                        for (int i = 0; i < 5; i++) {
                                // arbitrary 5 times preloaded, but it works
                                double xOutput = xController.calculate(currentPose.getX(),
                                                new TrapezoidProfile.State(poseToMoveTo.getX(), 0));
                                double yOutput = yController.calculate(currentPose.getY(),
                                                new TrapezoidProfile.State(poseToMoveTo.getY(), 0));
                                drive.setControl(pidToPose_FieldSpeeds
                                                .withSpeeds(new ChassisSpeeds(xOutput, yOutput, 0)));
                        }
                }

                commandLog.append("Initialized: " + getName());

                fLogger.log("Initializing %s to target Pose (x: %.1f, y: %.1f, rot: %.1f deg)",
                                getName(),
                                poseToMoveTo.getX(), poseToMoveTo.getY(), poseToMoveTo.getRotation().getDegrees());
        }

        @Override
        public void execute() {
                Pose2d currentPose = drive.getState().Pose;

                Translation2d delta = poseToMoveTo.getTranslation().minus(currentPose.getTranslation());
                Translation2d direction = delta.div(delta.getNorm()); // get a unit vector
                Translation2d endVelocityVector = direction.times(endStateVelocity);

                // // MECHANISM

                // double deltaLength = delta.getNorm();
                // double deltaAngle = delta.getAngle().getDegrees(); // blue

                // double directionLength = 1.0; // unit vector
                // double directionAngle = direction.getAngle().getDegrees(); // green

                // double velocityLength = endVelocityVector.getNorm();
                // double velocityAngle;
                // if (initialVelocityVector.getNorm() < 1e-6) {
                // velocityAngle = 0.0; // protect against error: x and y components of
                // Rotation2d are zero
                // } else {
                // velocityAngle = initialVelocityVector.getAngle().getDegrees(); // red
                // }

                // loopDeltaLigament.setLength(deltaLength);
                // loopDeltaLigament.setAngle(deltaAngle);

                // loopDirectionLigament.setLength(directionLength);
                // loopDirectionLigament.setAngle(directionAngle);

                // loopVelocityLigament.setLength(velocityLength);
                // loopVelocityLigament.setAngle(velocityAngle);

                // // MECHANISM

                double xOutput = xController.calculate(currentPose.getX(),
                                new TrapezoidProfile.State(poseToMoveTo.getX(), endVelocityVector.getX()));
                double yOutput = yController.calculate(currentPose.getY(),
                                new TrapezoidProfile.State(poseToMoveTo.getY(), endVelocityVector.getY()));
                double thetaOutput = thetaController.calculate(currentPose.getRotation().getRadians(),
                                poseToMoveTo.getRotation().getRadians());

                if (errorIncreasing && Math.abs(initialStateVelocity) > 0) {
                        xOutput = xOutput < initialVelocityVector.getX()
                                        ? average(initialVelocityVector.getX(), xOutput)
                                        : xOutput;
                        yOutput = yOutput < initialVelocityVector.getY()
                                        ? average(initialVelocityVector.getY(), yOutput)
                                        : yOutput;
                }

                SmartDashboard.putNumber("PID_TO_POSE/xError", xController.getPositionError());
                SmartDashboard.putNumber("PID_TO_POSE/yError", yController.getPositionError());
                SmartDashboard.putNumber("PID_TO_POSE/xOutput", xOutput);
                SmartDashboard.putNumber("PID_TO_POSE/yOutput", yOutput);
                SmartDashboard.putNumber("PID_TO_POSE/thetaOutput", thetaOutput);

                drive.setControl(pidToPose_FieldSpeeds.withSpeeds(new ChassisSpeeds(xOutput, yOutput, thetaOutput)));

                previousLoopBiggestError = currentLoopBiggestError;
                currentLoopBiggestError = xController.getPositionError() > yController.getPositionError()
                                ? xController.getPositionError()
                                : yController.getPositionError();

                previousSmoothedError = smoothedError;
                double maxError = Math.max(
                                Math.abs(xController.getPositionError()),
                                Math.abs(yController.getPositionError()));
                smoothedError = errorAverage.calculate(maxError);

                if (smoothedError < previousSmoothedError) {
                        // error is decreasing, you are halfway through your command.
                        // no longer apply feedforward constant based on initial velocity
                        errorIncreasing = false;
                }
        }

        @Override
        public boolean isFinished() {
                double distance = drive.getState().Pose.getTranslation().getDistance(poseToMoveTo.getTranslation());
                boolean distanceThreshold = Units.metersToInches(distance) < toleranceInches;
                Rotation2d thetaDiff = drive.getState().Pose.getRotation().minus(poseToMoveTo.getRotation());
                boolean thetaThreshold = Math.abs(thetaDiff.getDegrees()) <= toleranceDegrees;
                return distanceThreshold && thetaThreshold;
        }

        @Override
        public void end(boolean interrupted) {
                super.end(interrupted);
                // TODO modify command to optionally apply "brakes" where it not only cuts
                // velocity to wheels but moves the wheels into brake formation making the robot
                // harder to move
                if (endStateVelocity == 0) {
                        log("KILLING DRIVE VELOCITY");
                        drive.setControl(pidToPose_FieldSpeeds.withSpeeds(new ChassisSpeeds(0, 0, 0)));

                        SmartDashboard.putNumber("PID_TO_POSE/xError", xController.getPositionError());
                        SmartDashboard.putNumber("PID_TO_POSE/yError", yController.getPositionError());
                }

                double finalDistance = Units
                                .metersToInches(drive.getState().Pose.getTranslation()
                                                .getDistance(poseToMoveTo.getTranslation()));
                log("PidToPose " + (interrupted ? "interrupted" : "completed") +
                                ". Final pose: " + drive.getState().Pose +
                                ", Target: " + poseToMoveTo +
                                ", Distance to target (in): " + finalDistance +
                                ", End state velocity: ( x: " + drive.getState().Speeds.vxMetersPerSecond + ", y: "
                                + drive.getState().Speeds.vyMetersPerSecond + " )");

                commandLog.append("Finished (interrupt: " + (interrupted ? "Y" : "N") + "): " + getName());

                fLogger.log(
                                "%s ended, final Pose (x: %.1f, y: %.1f, rot: %.1f deg), target Pose (x: %.1f, y: %.1f, rot: %.1f deg), interrupted: %s",
                                getName(),
                                drive.getState().Pose.getX(), drive.getState().Pose.getY(),
                                drive.getState().Pose.getRotation().getDegrees(),
                                poseToMoveTo.getX(), poseToMoveTo.getY(), poseToMoveTo.getRotation().getDegrees(),
                                interrupted);
        }

        public static double average(Double... values) {
                return List.of(values).stream().mapToDouble(Double::doubleValue).average().orElse(0.0);
        }

        private void log(String logMessage) {
                if (DEBUG_LOGGING_ENABLED) {
                        DataLogManager.log("[PidToPoseCommand] " + logMessage);
                        System.out.println("[PidToPoseCommand] " + logMessage);
                }
        }

        @Override
        public String getName() {
                String instanceSpecificValue = commandName == null ? formatPose(targetPose.get()) : commandName;
                return "PidToPose(" + instanceSpecificValue + ")";
        }

        private String formatPose(Pose2d pose) {
                return String.format("(%.2f, %.2f, %.1f°)",
                                pose.getX(), pose.getY(), pose.getRotation().getDegrees());
        }

}