package frc.robot.subsystems.vision;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Pose3d;
import edu.wpi.first.math.kinematics.ChassisSpeeds;
import edu.wpi.first.util.struct.Struct;
import edu.wpi.first.util.struct.StructSerializable;
import edu.wpi.first.wpilibj.DriverStation;
import edu.wpi.first.wpilibj.Timer;
import edu.wpi.first.wpilibj2.command.SubsystemBase;
import frc.robot.lib.AprilTags;
import frc.robot.lib.GlobalField;
import frc.robot.lib.ProceduralStructGenerator;
import frc.robot.lib.Tracer;
import frc.robot.subsystems.vision.VisionConstants.Filtering;
import org.littletonrobotics.junction.Logger;

public class Vision extends SubsystemBase {
    private final VisionIO[] ios;
    private final VisionIOInputsAutoLogged[] inputs;

    private final Timer timerSinceLastSample = new Timer();
    private final ChassisSpeeds speeds = new ChassisSpeeds();
    private final ArrayList<VisionSample> samples = new ArrayList<>();

    public record VisionUpdate(Pose2d pose, double timestamp, double weightScalar, double avgDistanceMeters)
            implements StructSerializable {
        private static final VisionUpdate kEmpty = new VisionUpdate(Pose2d.kZero, 0.0, 1.0, 0.0);

        public static VisionUpdate empty() { return kEmpty; }

        public static final Struct<VisionUpdate> struct = ProceduralStructGenerator.genRecord(VisionUpdate.class);
    }

    public record VisionSample(Pose2d pose, double timestamp, double weight, double avgDistanceMeters)
            implements StructSerializable {
        public static final Struct<VisionSample> struct = ProceduralStructGenerator.genRecord(VisionSample.class);
    }

    public Vision(VisionIO... ios) {
        this.ios = ios;
        this.inputs = new VisionIOInputsAutoLogged[ios.length];
        for (int i = 0; i < ios.length; i++) {
            inputs[i] = new VisionIOInputsAutoLogged();
        }
    }

    public void updateSpeeds(ChassisSpeeds speeds) {
        this.speeds.vxMetersPerSecond = speeds.vxMetersPerSecond;
        this.speeds.vyMetersPerSecond = speeds.vyMetersPerSecond;
        this.speeds.omegaRadiansPerSecond = speeds.omegaRadiansPerSecond;
    }

    private Optional<VisionSample> gaugeWeight(String cameraName, Pose2d pose, double timestamp,
            double weightScalar, double avgDistMeters) {
        double weight = weightScalar;
        weight *= Filtering.LINEAR_VELOCITY_WEIGHT_COEFFICIENT
                .lerp(Math.hypot(speeds.vxMetersPerSecond, speeds.vyMetersPerSecond));
        weight *= Filtering.ANGULAR_VELOCITY_WEIGHT_COEFFICIENT.lerp(speeds.omegaRadiansPerSecond);
        if (DriverStation.isDisabled()) weight = 1.0;
        return Optional.of(new VisionSample(pose, timestamp, weight, avgDistMeters));
    }

    public double timeSinceLastSample() {
        return timerSinceLastSample.get();
    }

    public List<VisionSample> flushSamples() {
        List<VisionSample> out = new ArrayList<>(samples);
        samples.clear();
        return out;
    }

    @Override
    public void periodic() {
        Tracer.startTrace("VisionPeriodic");

        for (int i = 0; i < ios.length; i++) {
            String name = ios[i].getName();
            Tracer.startTrace(name + "Periodic");

            try {
                ios[i].updateInputs(inputs[i]);
            } catch (Exception e) {
                DriverStation.reportError("Error in VisionIO " + name, e.getStackTrace());
            }
            Logger.processInputs("Vision/" + name, inputs[i]);

            // Process logged pose estimates into vision samples
            for (int j = 0; j < inputs[i].estimatedPoses.length; j++) {
                Pose2d pose = inputs[i].estimatedPoses[j];
                double ts = inputs[i].estimateTimestampsSec[j];
                double w = inputs[i].estimateWeightScalars[j];
                double d = inputs[i].estimateAvgDistancesMeters[j];

                gaugeWeight(name, pose, ts, w, d).ifPresent(sample -> {
                    timerSinceLastSample.restart();
                    samples.add(sample);
                    GlobalField.setObject(name + "Camera", sample.pose());
                });
            }

            // Log visible tag locations on the field
            for (int tagId : inputs[i].visibleTagIds) {
                AprilTags.getAprilTagFieldLayout().getTagPose(tagId)
                        .map(Pose3d::toPose2d)
                        .ifPresent(p -> GlobalField.setObject("SeenTag_" + tagId, p));
            }

            Tracer.endTrace();
        }

        Tracer.endTrace();
    }
}
