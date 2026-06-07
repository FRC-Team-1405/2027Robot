package frc.robot.subsystems;

import static edu.wpi.first.units.Units.Volts;

import com.ctre.phoenix6.BaseStatusSignal;
import com.ctre.phoenix6.StatusCode;
import com.ctre.phoenix6.StatusSignal;
import com.ctre.phoenix6.configs.TalonFXConfiguration;
import com.ctre.phoenix6.controls.Follower;
import com.ctre.phoenix6.controls.MotionMagicVelocityVoltage;
import com.ctre.phoenix6.controls.NeutralOut;
import com.ctre.phoenix6.hardware.TalonFX;
import com.ctre.phoenix6.signals.InvertedValue;
import com.ctre.phoenix6.signals.MotorAlignmentValue;
import com.ctre.phoenix6.signals.NeutralModeValue;

import edu.wpi.first.wpilibj.Alert;
import edu.wpi.first.wpilibj.Alert.AlertType;
import frc.robot.Constants;
import frc.robot.Constants.ShooterPIDConfig;

public class ShooterIOTalonFX implements ShooterIO {
    private final TalonFX motor1 = new TalonFX(Constants.CANBus.SHOOTER_MOTOR_1);
    private final TalonFX motor2 = new TalonFX(Constants.CANBus.SHOOTER_MOTOR_2);
    private final TalonFX motor3 = new TalonFX(Constants.CANBus.SHOOTER_MOTOR_3);

    private final MotionMagicVelocityVoltage velocityVoltage = new MotionMagicVelocityVoltage(0).withSlot(0);
    private final NeutralOut brakeRequest = new NeutralOut();

    private final StatusSignal<Double> closedLoopError = motor1.getClosedLoopError();
    private final StatusSignal<Double> closedLoopReference = motor1.getClosedLoopReference();

    private final Alert configAlert = new Alert("Shooter motor configuration failed", AlertType.kError);

    public ShooterIOTalonFX() {
        TalonFXConfiguration mainCfg = new TalonFXConfiguration();
        mainCfg.Slot0.kP = ShooterPIDConfig.KP;
        mainCfg.Slot0.kI = ShooterPIDConfig.KI;
        mainCfg.Slot0.kD = ShooterPIDConfig.KD;
        mainCfg.Slot0.kV = ShooterPIDConfig.KV;
        mainCfg.Slot0.kS = ShooterPIDConfig.KS;
        mainCfg.Voltage.withPeakForwardVoltage(Volts.of(ShooterPIDConfig.PEAK_FORWARD_VOLTAGE))
                .withPeakReverseVoltage(Volts.of(ShooterPIDConfig.PEAK_REVERSE_VOLTAGE));
        mainCfg.MotorOutput.NeutralMode = NeutralModeValue.Coast;
        mainCfg.MotionMagic.MotionMagicAcceleration = ShooterPIDConfig.MOTION_MAGIC_ACCELERATION;
        mainCfg.MotorOutput.Inverted = InvertedValue.Clockwise_Positive;

        applyConfig(motor1, mainCfg, "shooter motor1");

        TalonFXConfiguration followerCfg = new TalonFXConfiguration();
        followerCfg.MotorOutput.NeutralMode = NeutralModeValue.Coast;
        followerCfg.Voltage.withPeakForwardVoltage(Volts.of(ShooterPIDConfig.PEAK_FORWARD_VOLTAGE))
                .withPeakReverseVoltage(Volts.of(ShooterPIDConfig.PEAK_REVERSE_VOLTAGE));
        applyConfig(motor2, followerCfg, "shooter motor2");
        applyConfig(motor3, followerCfg, "shooter motor3");

        motor2.setControl(new Follower(Constants.CANBus.SHOOTER_MOTOR_1, MotorAlignmentValue.Opposed));
        motor3.setControl(new Follower(Constants.CANBus.SHOOTER_MOTOR_1, MotorAlignmentValue.Opposed));

        closedLoopError.setUpdateFrequency(100);
        closedLoopReference.setUpdateFrequency(100);
        motor1.getVelocity().setUpdateFrequency(100);
    }

    private void applyConfig(TalonFX motor, TalonFXConfiguration cfg, String name) {
        StatusCode status = StatusCode.StatusCodeNotInitialized;
        for (int i = 0; i < 5; ++i) {
            status = motor.getConfigurator().apply(cfg);
            if (status.isOK()) break;
        }
        if (!status.isOK()) {
            System.out.println("Could not configure " + name + ". Error: " + status);
            configAlert.set(true);
            motor.setControl(brakeRequest);
        }
    }

    @Override
    public void updateInputs(ShooterIOInputs inputs) {
        BaseStatusSignal.refreshAll(closedLoopError, closedLoopReference);

        inputs.motor1VelocityRPS = motor1.getVelocity().getValueAsDouble();
        inputs.motor2VelocityRPS = motor2.getVelocity().getValueAsDouble();
        inputs.motor3VelocityRPS = motor3.getVelocity().getValueAsDouble();

        inputs.motor1SupplyCurrentAmps = motor1.getSupplyCurrent().getValueAsDouble();
        inputs.motor2SupplyCurrentAmps = motor2.getSupplyCurrent().getValueAsDouble();
        inputs.motor3SupplyCurrentAmps = motor3.getSupplyCurrent().getValueAsDouble();

        inputs.motor1StatorCurrentAmps = motor1.getStatorCurrent().getValueAsDouble();
        inputs.motor2StatorCurrentAmps = motor2.getStatorCurrent().getValueAsDouble();
        inputs.motor3StatorCurrentAmps = motor3.getStatorCurrent().getValueAsDouble();

        inputs.motor1TorqueCurrentAmps = motor1.getTorqueCurrent().getValueAsDouble();
        inputs.motor2TorqueCurrentAmps = motor2.getTorqueCurrent().getValueAsDouble();
        inputs.motor3TorqueCurrentAmps = motor3.getTorqueCurrent().getValueAsDouble();

        inputs.motor1OutputVoltage = motor1.getMotorVoltage().getValueAsDouble();
        inputs.motor2OutputVoltage = motor2.getMotorVoltage().getValueAsDouble();
        inputs.motor3OutputVoltage = motor3.getMotorVoltage().getValueAsDouble();

        inputs.supplyVoltage = motor1.getSupplyVoltage().getValueAsDouble();

        inputs.motor1TempCelsius = motor1.getDeviceTemp().getValueAsDouble();
        inputs.motor2TempCelsius = motor2.getDeviceTemp().getValueAsDouble();
        inputs.motor3TempCelsius = motor3.getDeviceTemp().getValueAsDouble();

        inputs.closedLoopError = closedLoopError.getValueAsDouble();
        inputs.closedLoopReference = closedLoopReference.getValueAsDouble();
    }

    @Override
    public void setVelocity(double velocityRPS) {
        motor1.setControl(velocityVoltage.withVelocity(velocityRPS));
    }

    @Override
    public void stop() {
        motor1.setControl(brakeRequest);
    }
}
