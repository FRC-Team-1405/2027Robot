package frc.robot.subsystems;

import static edu.wpi.first.units.Units.Inches;
import static edu.wpi.first.units.Units.Kilograms;
import static edu.wpi.first.units.Units.Meters;
import static edu.wpi.first.units.Units.Pounds;
import static edu.wpi.first.units.Units.RotationsPerSecond;
import static edu.wpi.first.units.Units.Volts;

import java.util.function.DoubleSupplier;
import java.util.function.Supplier;

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

import edu.wpi.first.math.MathUtil;
import edu.wpi.first.math.filter.LinearFilter;
import edu.wpi.first.units.measure.AngularVelocity;
import edu.wpi.first.wpilibj.Alert;
import edu.wpi.first.wpilibj.Alert.AlertType;
import edu.wpi.first.wpilibj.GenericHID.RumbleType;
import edu.wpi.first.wpilibj.RobotBase;
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
import frc.robot.constants.FeatureSwitches;
import frc.robot.lib.FinneyLogger;
import frc.robot.lib.MotorSim.MotorSim_Mech;

public class Shooter extends SubsystemBase {
  private final FinneyLogger fLogger = new FinneyLogger(this.getClass().getSimpleName(),
      FeatureSwitches.ENABLE_SUBSYSTEM_NT_LOGGING);

  private final TalonFX shooterMotor1 = new TalonFX(Constants.CANBus.SHOOTER_MOTOR_1);
  private final TalonFX shooterMotor2 = new TalonFX(Constants.CANBus.SHOOTER_MOTOR_2);
  private final TalonFX shooterMotor3 = new TalonFX(Constants.CANBus.SHOOTER_MOTOR_3);

  private final MotionMagicVelocityVoltage velocityVoltage = new MotionMagicVelocityVoltage(0).withSlot(0);
  private final NeutralOut brake = new NeutralOut();

  // Cached status signals — refreshed atomically each periodic() tick.
  // Declared here so we can set update frequencies once during setup and avoid
  // repeated CAN getter overhead (and duplicate reads) in the hot path.
  private final StatusSignal<Double> m_closedLoopError = shooterMotor1.getClosedLoopError();
  private final StatusSignal<Double> m_closedLoopReference = shooterMotor1.getClosedLoopReference();

  private final MotorSim_Mech shooterMotorSimMech = new MotorSim_Mech("Shooter/Mech2d");

  private final Alert configAlert = new Alert("Shooter motor configuration failed", AlertType.kError);

  private LinearFilter filter = LinearFilter.movingAverage(ShooterPIDConfig.FILTER_WINDOW);

  // Rolling std dev via E[x^2] - E[x]^2
  private LinearFilter velocityMeanFilter = LinearFilter.movingAverage(ShooterPIDConfig.FILTER_WINDOW);
  private LinearFilter velocityMeanSqFilter = LinearFilter.movingAverage(ShooterPIDConfig.FILTER_WINDOW);

  private double highError = 0.0;
  private double lowError = 0.0;

  private int settleCount = 0;
  private int shotCount = 0;

  private double shooterTarget = 0.0;
  private double shooterStartTimestamp = 0.0;
  private double timeToLockSeconds = 0.0;

  private boolean locked = false;
  private boolean wasLocked = false;

  private CommandXboxController operatorJoystick;
  private Command setToStandardPointMode;

  private Supplier<AngularVelocity> requestedSpeed = () -> Constants.ShooterPreferences.LONG;

  public boolean isReadyToFire() {
    return locked;
  }

  public boolean isShooterSpinning() {
    return shooterMotor1.getVelocity().getValueAsDouble() >= 0.5;
  }

  private void setupMotors() {
    // Leader Motor
    TalonFXConfiguration mainMotorCfg = new TalonFXConfiguration();
    if (!RobotBase.isSimulation()) {
      // real robot
      mainMotorCfg.Slot0.kP = ShooterPIDConfig.KP;
      mainMotorCfg.Slot0.kI = ShooterPIDConfig.KI;
      mainMotorCfg.Slot0.kD = ShooterPIDConfig.KD;
      mainMotorCfg.Slot0.kV = ShooterPIDConfig.KV;
      mainMotorCfg.Slot0.kS = ShooterPIDConfig.KS;
    } else {
      if (FeatureSwitches.CUSTOM_SIMULATION_SHOOTER_PIDS) {
        // simulation
        mainMotorCfg.Slot0.kP = 0.2;
        mainMotorCfg.Slot0.kI = 0.0;
        mainMotorCfg.Slot0.kD = 0.0;
        mainMotorCfg.Slot0.kV = 0.1;
        mainMotorCfg.Slot0.kS = 0.15;
      } else {
        mainMotorCfg.Slot0.kP = ShooterPIDConfig.KP;
        mainMotorCfg.Slot0.kI = ShooterPIDConfig.KI;
        mainMotorCfg.Slot0.kD = ShooterPIDConfig.KD;
        mainMotorCfg.Slot0.kV = ShooterPIDConfig.KV;
        mainMotorCfg.Slot0.kS = ShooterPIDConfig.KS;
      }
    }
    mainMotorCfg.Voltage.withPeakForwardVoltage(Volts.of(ShooterPIDConfig.PEAK_FORWARD_VOLTAGE))
        .withPeakReverseVoltage(Volts.of(ShooterPIDConfig.PEAK_REVERSE_VOLTAGE));

    mainMotorCfg.MotorOutput.NeutralMode = NeutralModeValue.Coast;
    mainMotorCfg.MotionMagic.MotionMagicAcceleration = ShooterPIDConfig.MOTION_MAGIC_ACCELERATION;
    mainMotorCfg.MotorOutput.Inverted = InvertedValue.Clockwise_Positive;

    StatusCode status1 = StatusCode.StatusCodeNotInitialized;
    for (int i = 0; i < 5; ++i) {
      status1 = shooterMotor1.getConfigurator().apply(mainMotorCfg);
      if (status1.isOK())
        break;
    }
    if (!status1.isOK()) {
      System.out.println("Could not configure shooter motor1. Error: " + status1.toString());
      configAlert.set(true);
      shooterMotor1.setControl(brake);
    }

    // Follower Motors
    TalonFXConfiguration followerMotorsCfg = new TalonFXConfiguration();
    followerMotorsCfg.MotorOutput.NeutralMode = NeutralModeValue.Coast;
    followerMotorsCfg.Voltage.withPeakForwardVoltage(Volts.of(ShooterPIDConfig.PEAK_FORWARD_VOLTAGE))
        .withPeakReverseVoltage(Volts.of(ShooterPIDConfig.PEAK_REVERSE_VOLTAGE));

    StatusCode status2 = StatusCode.StatusCodeNotInitialized;
    for (int i = 0; i < 5; ++i) {
      status2 = shooterMotor2.getConfigurator().apply(followerMotorsCfg);
      if (status2.isOK())
        break;
    }
    if (!status2.isOK()) {
      System.out.println("Could not configure shooter motor2. Error: " + status2.toString());
      configAlert.set(true);
      shooterMotor2.setControl(brake);
    }

    StatusCode status3 = StatusCode.StatusCodeNotInitialized;
    for (int i = 0; i < 5; ++i) {
      status3 = shooterMotor3.getConfigurator().apply(followerMotorsCfg);
      if (status3.isOK())
        break;
    }
    if (!status3.isOK()) {
      System.out.println("Could not configure shooter motor3. Error: " + status3.toString());
      configAlert.set(true);
      shooterMotor3.setControl(brake);
    }

    // Increase update frequency on the signals used by the lock check so the
    // periodic() poll sees data that is at most ~10 ms old (vs the default 20 ms).
    m_closedLoopError.setUpdateFrequency(100);
    m_closedLoopReference.setUpdateFrequency(100);
    shooterMotor1.getVelocity().setUpdateFrequency(100);
  }

  /** Creates a new Shooter. */
  public Shooter(CommandXboxController operatorJoystick, Command setToStandardPointMode) {
    this.operatorJoystick = operatorJoystick;
    this.setToStandardPointMode = setToStandardPointMode;
    setupMotors();
    simulationInit();
    shooterMotor2.setControl(new Follower(Constants.CANBus.SHOOTER_MOTOR_1, MotorAlignmentValue.Opposed));
    shooterMotor3.setControl(new Follower(Constants.CANBus.SHOOTER_MOTOR_1, MotorAlignmentValue.Opposed));
    SmartDashboard.putNumber("Shooter/TestTargetRPS", 10.0);
    shooterStop();
  }

  private void setShooterSpeed(Supplier<AngularVelocity> speed) {
    if (operatorJoystick != null) {
      CommandScheduler.getInstance().schedule(RumbleJoystick.continousRumble(operatorJoystick));
    }

    AngularVelocity target = speed.get();
    shooterMotor1.setControl(velocityVoltage.withVelocity(target));
    shooterTarget = target.in(RotationsPerSecond);
    shooterStartTimestamp = Timer.getFPGATimestamp();
    timeToLockSeconds = 0.0;
    fLogger.log("setShooterSpeed called: target=%.2f RPS", shooterTarget);
  }

  private void shooterStop() {
    if (operatorJoystick != null) {
      CommandScheduler.getInstance().schedule(RumbleJoystick.stopRumble(operatorJoystick));
    }

    if (setToStandardPointMode != null) {
      CommandScheduler.getInstance().schedule(setToStandardPointMode);
    }

    shooterTarget = 0.0;
    shooterMotor1.setControl(brake);
    fLogger.log("shooterStop called");
  }

  /** Spin up the flywheel to the currently requested speed. */
  public void spinUp() {
    setShooterSpeed(requestedSpeed);
  }

  /**
   * Update the motor control to the current requested speed without resetting
   * settle tracking state. Use this for continuous speed updates (e.g. dynamic
   * distance-based shooting) to avoid disrupting the lock/settle logic.
   */
  public void updateSpeed() {
    AngularVelocity target = requestedSpeed.get();
    shooterMotor1.setControl(velocityVoltage.withVelocity(target));
    shooterTarget = target.in(RotationsPerSecond);
  }

  /** Stop the flywheel motors. */
  public void spinDown() {
    shooterStop();
  }

  /**
   * set requested speed and spin up shooter to that speed
   */
  private void setRequestedSpeed(Supplier<AngularVelocity> speed) {
    requestedSpeed = speed;
    setShooterSpeed(requestedSpeed);
  }

  /**
   * set requested speed and DON'T spin up shooter
   * 
   * @param speed
   */
  public void setRequestedSpeedWithoutShooting(Supplier<AngularVelocity> speed) {
    requestedSpeed = speed;
  }

  /**
   * get the desired robot distance to the center of the hub for the set shooter
   * speed.
   * 
   * @return
   */
  public Supplier<Supplier<Double>> getDistanceFromSpeed() {
    // TODO fix the bug where this doesn't update due to callers getting the value
    // once instead of using the supplier properly
    Supplier<Supplier<Double>> distanceFromSpeed = () -> ShooterPreferences.SHOOTER_SPEED_TO_DISTANCE
        .get(requestedSpeed.get()) == null
            ? ShooterPreferences.MEDIUM_DISTANCE
            : ShooterPreferences.SHOOTER_SPEED_TO_DISTANCE
                .get(requestedSpeed.get());

    // System.out.println("getDistanceFromSpeed: " +
    // distanceFromSpeed.get().doubleValue());
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
    double floorDistance;
    double ceilingDistance;
    AngularVelocity floorSpeed;
    AngularVelocity ceilingSpeed;
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
    setRequestedSpeedWithoutShooting(() -> {
      return AngularVelocity.ofBaseUnits(
          dynamicShooterRPS(floorDistance, ceilingDistance, floorSpeed, ceilingSpeed, distanceToHub),
          RotationsPerSecond);
    });
  }

  public double dynamicShooterRPS(Double floorDistance, Double ceilingDistance, AngularVelocity floorSpeed,
      AngularVelocity ceilingSpeed, DoubleSupplier distanceToHub) {
    double dynamicRPS;
    dynamicRPS = (floorSpeed.baseUnitMagnitude() * (ceilingDistance - distanceToHub.getAsDouble())
        + (ceilingSpeed.baseUnitMagnitude() * (distanceToHub.getAsDouble() - floorDistance)))
        / (ceilingDistance - floorDistance);
    if (dynamicRPS >= ShooterPreferences.MAX.baseUnitMagnitude()) {
      dynamicRPS = ShooterPreferences.MAX.baseUnitMagnitude();
    }
    return dynamicRPS;
  }

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

  /**
   * Reads Shooter/TestTargetRPS from SmartDashboard and spins up to that speed.
   */
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

  @Override
  public void periodic() {

    // --- Velocities (cache to avoid redundant CAN calls) ---
    double motor1RPS = shooterMotor1.getVelocity().getValueAsDouble();
    double motor2RPS = shooterMotor2.getVelocity().getValueAsDouble();
    double motor3RPS = shooterMotor3.getVelocity().getValueAsDouble();

    // --- Current draw ---
    double motor1SupplyCurrent = shooterMotor1.getSupplyCurrent().getValueAsDouble();
    double motor2SupplyCurrent = shooterMotor2.getSupplyCurrent().getValueAsDouble();
    double motor3SupplyCurrent = shooterMotor3.getSupplyCurrent().getValueAsDouble();
    double cumulativeMotorSupplyCurrent = motor1SupplyCurrent + motor2SupplyCurrent + motor3SupplyCurrent;

    double motor1TorqueCurrent = shooterMotor1.getTorqueCurrent().getValueAsDouble();
    double motor2TorqueCurrent = shooterMotor2.getTorqueCurrent().getValueAsDouble();
    double motor3TorqueCurrent = shooterMotor3.getTorqueCurrent().getValueAsDouble();

    double cumulativeMotorStatorCurrent = shooterMotor1.getStatorCurrent().getValueAsDouble()
        + shooterMotor2.getStatorCurrent().getValueAsDouble() + shooterMotor3.getStatorCurrent().getValueAsDouble();

    // --- Output & supply voltage ---
    double motor1OutputVoltage = shooterMotor1.getMotorVoltage().getValueAsDouble();
    double motor2OutputVoltage = shooterMotor2.getMotorVoltage().getValueAsDouble();
    double motor3OutputVoltage = shooterMotor3.getMotorVoltage().getValueAsDouble();
    double supplyVoltage = shooterMotor1.getSupplyVoltage().getValueAsDouble();

    // --- Temperatures ---
    double motor1Temp = shooterMotor1.getDeviceTemp().getValueAsDouble();
    double motor2Temp = shooterMotor2.getDeviceTemp().getValueAsDouble();
    double motor3Temp = shooterMotor3.getDeviceTemp().getValueAsDouble();

    // --- Closed loop diagnostics ---
    // Atomically refresh the lock-critical signals (100 Hz on CAN) so both reads
    // share the same timestamp and we avoid a duplicate CAN getter call.
    BaseStatusSignal.refreshAll(m_closedLoopError, m_closedLoopReference);
    double error = m_closedLoopError.getValueAsDouble();
    double averageError = filter.calculate(error);
    double target = m_closedLoopReference.getValueAsDouble();
    double range = locked ? ShooterPreferences.WIDE : ShooterPreferences.TIGHT;

    // --- Rolling std dev: sqrt(E[x^2] - E[x]^2) ---
    double mean = velocityMeanFilter.calculate(motor1RPS);
    double meanSq = velocityMeanSqFilter.calculate(motor1RPS * motor1RPS);
    double stdDev = Math.sqrt(Math.max(0.0, meanSq - mean * mean));

    // --- Ball exit velocity estimation ---
    // wheel RPS = motor RPS * gear ratio; exit vel = wheel RPS * wheel
    // circumference
    double exitVelocityFPS = motor1RPS
        * ShooterPhysicalProperties.MOTOR_TO_WHEEL_GEAR_RATIO
        * Math.PI * (ShooterPhysicalProperties.FLYWHEEL_DIAMETER_INCHES / 12.0);

    // --- Follower sync check ---
    double motor2RPSDelta = motor1RPS - motor2RPS;
    double motor3RPSDelta = motor1RPS - motor3RPS;
    double differentialCurrentDraw = Math.abs(motor1SupplyCurrent - motor2SupplyCurrent);

    // --- High/low error envelope ---
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

    // --- Settle / lock logic ---
    if (MathUtil.isNear(shooterTarget, target, ShooterPIDConfig.TARGET_MATCH_TOLERANCE) && Math.abs(error) < range) {
      if (settleCount < ShooterPreferences.STABLE_COUNT) {
        settleCount += 1;
      }
    } else {
      settleCount = 0;
    }

    locked = settleCount >= ShooterPreferences.STABLE_COUNT && shooterTarget > 0.0;

    // --- Time to lock ---
    if (locked && !wasLocked) {
      timeToLockSeconds = Timer.getFPGATimestamp() - shooterStartTimestamp;
      fLogger.log("Shooter locked: timeToLock=%.2fs, target=%.2f RPS", timeToLockSeconds, shooterTarget);
    }

    // --- Shot counter: locked -> unlocked while target is still set ---
    if (!locked && wasLocked && shooterTarget > 0.0) {
      shotCount++;
      fLogger.log("Shot detected: count=%d", shotCount);
    }

    wasLocked = locked;

    // --- Mechanism2d update ---
    shooterMotorSimMech.update(shooterMotor1.getPosition(), shooterMotor1.getVelocity());

    // --- SmartDashboard ---
    if (FeatureSwitches.ENABLE_SUBSYSTEM_NT_LOGGING) {
      // Velocity
      SmartDashboard.putNumber("Shooter/Motor1RPS", motor1RPS);
      SmartDashboard.putNumber("Shooter/Motor2RPS", motor2RPS);
      SmartDashboard.putNumber("Shooter/Motor3RPS", motor3RPS);
      SmartDashboard.putNumber("Shooter/TargetRPS", shooterTarget);
      // SmartDashboard.putNumber("Shooter/Motor1StdDev", stdDev);
      // SmartDashboard.putNumber("Shooter/BallExitVelocityFPS", exitVelocityFPS);

      // Dynamice Shooter
      // SmartDashboard.putNumber("Shooter/DynamicRPS", ); //TODO ben needs to finish
      // writing this

      // Follower sync
      SmartDashboard.putNumber("Shooter/Motor2RPSDelta", motor2RPSDelta);
      SmartDashboard.putNumber("Shooter/Motor3RPSDelta", motor3RPSDelta);

      // Supply & output voltage
      // SmartDashboard.putNumber("Shooter/SupplyVoltage", supplyVoltage);
      // SmartDashboard.putNumber("Shooter/Motor1OutputVoltage", motor1OutputVoltage);
      // SmartDashboard.putNumber("Shooter/Motor2OutputVoltage", motor2OutputVoltage);
      // SmartDashboard.putNumber("Shooter/Motor3OutputVoltage", motor3OutputVoltage);

      // Current
      // SmartDashboard.putNumber("Shooter/Motor1SupplyCurrent", motor1SupplyCurrent);
      // SmartDashboard.putNumber("Shooter/Motor2SupplyCurrent", motor2SupplyCurrent);
      // SmartDashboard.putNumber("Shooter/Motor3SupplyCurrent", motor3SupplyCurrent);
      SmartDashboard.putNumber("Shooter/DifferentialCurrent", differentialCurrentDraw);
      SmartDashboard.putNumber("Shooter/CumulativeSupplyCurrent", cumulativeMotorSupplyCurrent);

      SmartDashboard.putNumber("Shooter/Motor1TorqueCurrent", motor1TorqueCurrent);
      SmartDashboard.putNumber("Shooter/Motor2TorqueCurrent", motor2TorqueCurrent);
      SmartDashboard.putNumber("Shooter/Motor3TorqueCurrent", motor3TorqueCurrent);

      // Temperature
      // SmartDashboard.putNumber("Shooter/Motor1Temp", motor1Temp);
      // SmartDashboard.putNumber("Shooter/Motor2Temp", motor2Temp);
      // SmartDashboard.putNumber("Shooter/Motor3Temp", motor3Temp);

      // PID diagnostics
      SmartDashboard.putNumber("Shooter/Error", error);
      SmartDashboard.putNumber("Shooter/AverageError", averageError);
      // SmartDashboard.putNumber("Shooter/HighError", highError);
      // SmartDashboard.putNumber("Shooter/LowError", lowError);
      SmartDashboard.putNumber("Shooter/SettleCount", settleCount);

      // Lock & shot
      SmartDashboard.putBoolean("Shooter/Locked", locked);
      SmartDashboard.putNumber("Shooter/TimeToLockSeconds", timeToLockSeconds);
      SmartDashboard.putNumber("Shooter/ShotCount", shotCount);

      // Speed preset indicators
      SmartDashboard.putBoolean("Shooter/Long Speed", requestedSpeed.get() == Constants.ShooterPreferences.LONG);
      SmartDashboard.putBoolean("Shooter/Medium Speed", requestedSpeed.get() == Constants.ShooterPreferences.MEDIUM);
      SmartDashboard.putBoolean("Shooter/Short Speed", requestedSpeed.get() == Constants.ShooterPreferences.SHORT);

      // Shooter Distance
      SmartDashboard.putNumber("Shooter/Requested Speed", requestedSpeed.get().in(RotationsPerSecond));
      SmartDashboard.putNumber("Shooter/Desired Distance", getDistanceFromSpeed().get().get());
    }
  }

  public void simulationInit() {
    // Use physical properties from Constants to create a more realistic sim
    // profile.
    // The moment of inertia in Constants is for the flywheel (wheel side). Reflect
    // it to the motor/rotor side: I_rotor = I_wheel / (gearRatio^2)
    final double gearRatio = Constants.ShooterPhysicalProperties.MOTOR_TO_WHEEL_GEAR_RATIO;
    final double flywheelInertia = Constants.ShooterPhysicalProperties.FLYWHEEL_MOMENT_OF_INERTIA;
    final double rotorInertia = flywheelInertia / (gearRatio * gearRatio);

    // Convert the (approximate) projectile mass (lbs) to kg for gravity load
    final double loadMassKg = Pounds.of(Constants.ShooterPhysicalProperties.FUEL_WEIGHT_LBS).in(Kilograms);

    // Use flywheel radius as the arm for gravity torque (meters)
    final double armMeters = Inches.of(Constants.ShooterPhysicalProperties.FLYWHEEL_DIAMETER_INCHES / 2.0)
        .in(Meters);

    // Small viscous friction estimate (N*m per rad/s). Tweak if needed.
    final double viscousCoeff = 0.01;

    // There are three motors on the shooter (one leader + two followers)
    final int numMotors = 3;

    frc.robot.sim.sjc.PhysicsSim_SJC.getInstance().addTalonFX(shooterMotor1, rotorInertia, loadMassKg,
        armMeters, viscousCoeff, numMotors, gearRatio);
  }

  @Override
  public void simulationPeriodic() {
    frc.robot.sim.sjc.PhysicsSim_SJC.getInstance().run();
  }
}