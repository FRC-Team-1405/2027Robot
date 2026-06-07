package frc.robot.subsystems;

import static edu.wpi.first.units.Units.RotationsPerSecond;

import java.util.function.DoubleSupplier;
import java.util.function.Supplier;

import edu.wpi.first.math.MathUtil;
import edu.wpi.first.math.filter.LinearFilter;
import edu.wpi.first.units.measure.AngularVelocity;
import edu.wpi.first.wpilibj.Timer;
import edu.wpi.first.wpilibj.smartdashboard.SmartDashboard;
import edu.wpi.first.wpilibj2.command.Command;
import edu.wpi.first.wpilibj2.command.CommandScheduler;
import edu.wpi.first.wpilibj2.command.Commands;
import edu.wpi.first.wpilibj2.command.SubsystemBase;
import edu.wpi.first.wpilibj2.command.button.CommandXboxController;
import frc.robot.Constants;
import frc.robot.Constants.ShooterPIDConfig;
import frc.robot.Constants.ShooterPhysicalProperties;
import frc.robot.Constants.ShooterPreferences;
import frc.robot.commands.RumbleJoystick;
import org.littletonrobotics.junction.AutoLogOutput;
import org.littletonrobotics.junction.Logger;

public class Shooter extends SubsystemBase {
    private final ShooterIO io;
    private final ShooterIOInputsAutoLogged inputs = new ShooterIOInputsAutoLogged();

    private final LinearFilter filter = LinearFilter.movingAverage(ShooterPIDConfig.FILTER_WINDOW);
    private final LinearFilter velocityMeanFilter = LinearFilter.movingAverage(ShooterPIDConfig.FILTER_WINDOW);
    private final LinearFilter velocityMeanSqFilter = LinearFilter.movingAverage(ShooterPIDConfig.FILTER_WINDOW);

    private double highError = 0.0;
    private double lowError = 0.0;
    private int settleCount = 0;

    @AutoLogOutput(key = "Shooter/ShotCount")
    private int shotCount = 0;

    @AutoLogOutput(key = "Shooter/TargetRPS")
    private double shooterTarget = 0.0;

    private double shooterStartTimestamp = 0.0;

    @AutoLogOutput(key = "Shooter/TimeToLockSeconds")
    private double timeToLockSeconds = 0.0;

    @AutoLogOutput(key = "Shooter/Locked")
    private boolean locked = false;

    @AutoLogOutput(key = "Shooter/WasLocked")
    private boolean wasLocked = false;

    @AutoLogOutput(key = "Shooter/SettleCount")
    private int settleCountLog = 0;

    @AutoLogOutput(key = "Shooter/AverageError")
    private double averageError = 0.0;

    @AutoLogOutput(key = "Shooter/StdDev")
    private double stdDev = 0.0;

    @AutoLogOutput(key = "Shooter/ExitVelocityFPS")
    private double exitVelocityFPS = 0.0;

    @AutoLogOutput(key = "Shooter/Motor2RPSDelta")
    private double motor2RPSDelta = 0.0;

    @AutoLogOutput(key = "Shooter/Motor3RPSDelta")
    private double motor3RPSDelta = 0.0;

    private CommandXboxController operatorJoystick;
    private Command setToStandardPointMode;

    private Supplier<AngularVelocity> requestedSpeed = () -> Constants.ShooterPreferences.LONG;

    public Shooter(ShooterIO io, CommandXboxController operatorJoystick, Command setToStandardPointMode) {
        this.io = io;
        this.operatorJoystick = operatorJoystick;
        this.setToStandardPointMode = setToStandardPointMode;
        SmartDashboard.putNumber("Shooter/TestTargetRPS", 10.0);
        shooterStop();
    }

    public boolean isReadyToFire() {
        return locked;
    }

    public boolean isShooterSpinning() {
        return inputs.motor1VelocityRPS >= 0.5;
    }

    private void setShooterSpeed(Supplier<AngularVelocity> speed) {
        if (operatorJoystick != null) {
            CommandScheduler.getInstance().schedule(RumbleJoystick.continousRumble(operatorJoystick));
        }
        AngularVelocity target = speed.get();
        io.setVelocity(target.in(RotationsPerSecond));
        shooterTarget = target.in(RotationsPerSecond);
        shooterStartTimestamp = Timer.getFPGATimestamp();
        timeToLockSeconds = 0.0;
    }

    private void shooterStop() {
        if (operatorJoystick != null) {
            CommandScheduler.getInstance().schedule(RumbleJoystick.stopRumble(operatorJoystick));
        }
        if (setToStandardPointMode != null) {
            CommandScheduler.getInstance().schedule(setToStandardPointMode);
        }
        shooterTarget = 0.0;
        io.stop();
    }

    public void spinUp() {
        setShooterSpeed(requestedSpeed);
    }

    public void updateSpeed() {
        AngularVelocity target = requestedSpeed.get();
        io.setVelocity(target.in(RotationsPerSecond));
        shooterTarget = target.in(RotationsPerSecond);
    }

    public void spinDown() {
        shooterStop();
    }

    private void setRequestedSpeed(Supplier<AngularVelocity> speed) {
        requestedSpeed = speed;
        setShooterSpeed(requestedSpeed);
    }

    public void setRequestedSpeedWithoutShooting(Supplier<AngularVelocity> speed) {
        requestedSpeed = speed;
    }

    public Supplier<Supplier<Double>> getDistanceFromSpeed() {
        Supplier<Supplier<Double>> distanceFromSpeed = () -> ShooterPreferences.SHOOTER_SPEED_TO_DISTANCE
                .get(requestedSpeed.get()) == null
                        ? ShooterPreferences.MEDIUM_DISTANCE
                        : ShooterPreferences.SHOOTER_SPEED_TO_DISTANCE.get(requestedSpeed.get());
        return distanceFromSpeed;
    }

    public void increaseDistanceForSpeed() {
        Double value = ShooterPreferences.SHOOTER_SPEED_TO_DISTANCE.get(requestedSpeed.get()).get();
        ShooterPreferences.SHOOTER_SPEED_TO_DISTANCE.put(requestedSpeed.get(), () -> value + 0.1);
    }

    public void descreaseDistanceForSpeed() {
        Double value = ShooterPreferences.SHOOTER_SPEED_TO_DISTANCE.get(requestedSpeed.get()).get();
        ShooterPreferences.SHOOTER_SPEED_TO_DISTANCE.put(requestedSpeed.get(), () -> value - 0.1);
    }

    public void setDynamicShooterSpeed(DoubleSupplier distanceToHub) {
        double floorDistance, ceilingDistance;
        AngularVelocity floorSpeed, ceilingSpeed;
        if (distanceToHub.getAsDouble() <= ShooterPreferences.SHORT_DISTANCE.get()) {
            floorDistance = 0.0;
            ceilingDistance = ShooterPreferences.SHORT_DISTANCE.get();
            floorSpeed = RotationsPerSecond.of(0);
            ceilingSpeed = ShooterPreferences.SHORT;
        } else if (distanceToHub.getAsDouble() <= ShooterPreferences.MEDIUM_DISTANCE.get()) {
            floorDistance = ShooterPreferences.SHORT_DISTANCE.get();
            ceilingDistance = ShooterPreferences.MEDIUM_DISTANCE.get();
            floorSpeed = ShooterPreferences.SHORT;
            ceilingSpeed = ShooterPreferences.MEDIUM;
        } else if (distanceToHub.getAsDouble() <= ShooterPreferences.LONG_DISTANCE.get()) {
            floorDistance = ShooterPreferences.MEDIUM_DISTANCE.get();
            ceilingDistance = ShooterPreferences.LONG_DISTANCE.get();
            floorSpeed = ShooterPreferences.MEDIUM;
            ceilingSpeed = ShooterPreferences.LONG;
        } else if (distanceToHub.getAsDouble() <= ShooterPreferences.LONGER_DISTANCE.get()) {
            floorDistance = ShooterPreferences.LONG_DISTANCE.get();
            ceilingDistance = ShooterPreferences.LONGER_DISTANCE.get();
            floorSpeed = ShooterPreferences.LONG;
            ceilingSpeed = ShooterPreferences.LONGER;
        } else {
            floorDistance = ShooterPreferences.LONGER_DISTANCE.get();
            ceilingDistance = 4.02844;
            floorSpeed = ShooterPreferences.LONGER;
            ceilingSpeed = ShooterPreferences.LUDICROUS_SPEED;
        }
        setRequestedSpeedWithoutShooting(() -> AngularVelocity.ofBaseUnits(
                dynamicShooterRPS(floorDistance, ceilingDistance, floorSpeed, ceilingSpeed, distanceToHub),
                RotationsPerSecond));
    }

    public double dynamicShooterRPS(Double floorDistance, Double ceilingDistance, AngularVelocity floorSpeed,
            AngularVelocity ceilingSpeed, DoubleSupplier distanceToHub) {
        double rps = (floorSpeed.baseUnitMagnitude() * (ceilingDistance - distanceToHub.getAsDouble())
                + (ceilingSpeed.baseUnitMagnitude() * (distanceToHub.getAsDouble() - floorDistance)))
                / (ceilingDistance - floorDistance);
        if (rps >= ShooterPreferences.MAX.baseUnitMagnitude()) {
            rps = ShooterPreferences.MAX.baseUnitMagnitude();
        }
        return rps;
    }

    @Override
    public void periodic() {
        io.updateInputs(inputs);
        Logger.processInputs("Shooter", inputs);

        double motor1RPS = inputs.motor1VelocityRPS;
        double motor2RPS = inputs.motor2VelocityRPS;
        double motor3RPS = inputs.motor3VelocityRPS;
        double error = inputs.closedLoopError;
        double target = inputs.closedLoopReference;

        averageError = filter.calculate(error);
        double mean = velocityMeanFilter.calculate(motor1RPS);
        double meanSq = velocityMeanSqFilter.calculate(motor1RPS * motor1RPS);
        stdDev = Math.sqrt(Math.max(0.0, meanSq - mean * mean));

        exitVelocityFPS = motor1RPS
                * ShooterPhysicalProperties.MOTOR_TO_WHEEL_GEAR_RATIO
                * Math.PI * (ShooterPhysicalProperties.FLYWHEEL_DIAMETER_INCHES / 12.0);

        motor2RPSDelta = motor1RPS - motor2RPS;
        motor3RPSDelta = motor1RPS - motor3RPS;

        if (error >= highError) {
            highError = error;
        } else {
            highError -= 1;
        }
        if (error <= lowError) {
            lowError = error;
        } else {
            lowError += 1;
        }

        double range = locked ? ShooterPreferences.WIDE : ShooterPreferences.TIGHT;
        if (MathUtil.isNear(shooterTarget, target, ShooterPIDConfig.TARGET_MATCH_TOLERANCE)
                && Math.abs(error) < range) {
            if (settleCount < ShooterPreferences.STABLE_COUNT) settleCount++;
        } else {
            settleCount = 0;
        }
        settleCountLog = settleCount;

        locked = settleCount >= ShooterPreferences.STABLE_COUNT && shooterTarget > 0.0;

        if (locked && !wasLocked) {
            timeToLockSeconds = Timer.getFPGATimestamp() - shooterStartTimestamp;
        }

        if (!locked && wasLocked && shooterTarget > 0.0) {
            shotCount++;
        }

        wasLocked = locked;
    }

    // ── Public Commands ──────────────────────────────────────────────────────

    public Command runShooter(Supplier<AngularVelocity> speed) {
        return Commands.runOnce(() -> setShooterSpeed(speed), this);
    }

    public Command runShooterAuto(Supplier<AngularVelocity> requestedSpeed) {
        return Commands.startEnd(
                () -> setShooterSpeed(requestedSpeed),
                () -> shooterStop(),
                this);
    }

    public Command runShooter() {
        return Commands.runOnce(() -> setShooterSpeed(requestedSpeed), this);
    }

    public Command runShooterAtTestRPS() {
        return Commands.runOnce(
                () -> setShooterSpeed(
                        () -> RotationsPerSecond.of(SmartDashboard.getNumber("Shooter/TestTargetRPS", 10.0))),
                this);
    }

    public Command runSetRequestedSpeed(Supplier<AngularVelocity> speed) {
        return Commands.runOnce(() -> setRequestedSpeed(speed));
    }

    public Command stopShooter() {
        return Commands.runOnce(() -> shooterStop(), this);
    }

    @AutoLogOutput(key = "Shooter/RequestedSpeedRPS")
    public double getRequestedSpeedRPS() {
        return requestedSpeed.get().in(RotationsPerSecond);
    }
}
