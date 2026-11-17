# Subsystem Writing Guide

This guide outlines the standards for writing subsystems for our FRC team based on our established patterns. 

## Required Components

### 1. FinneyLogger Integration
```java
private final FinneyLogger fLogger = new FinneyLogger(this.getClass().getSimpleName());
```
- Creates subsystem-separated NetworkTables (NT) logs
- Use `fLogger.log()` for debugging and state tracking
- Constructor option to utilize feature-switching for a reduction in NT resource usage

### 2. Motor Configuration (`setupMotors()` method)
```java
private void setupMotors() {
    TalonFXConfiguration cfg = new TalonFXConfiguration();
    
    // Configure relevant motor parameters
    FeedbackConfigs fdb = cfg.Feedback;
    MotionMagicConfigs mm = cfg.MotionMagic;
    Slot0Configs slot0 = cfg.Slot0;
    CurrentLimitsConfigs limits = cfg.CurrentLimits;
    SoftwareLimitSwitchConfigs soft = cfg.SoftwareLimitSwitch;
    
    // Retry configuration up to 5 times (CTRE recommendation)
    StatusCode status = StatusCode.StatusCodeNotInitialized;
    for (int i = 0; i < 5; ++i) {
        status = motor.getConfigurator().apply(cfg);
        if (status.isOK()) break;
    }
    if (!status.isOK()) {
        System.out.println("Could not configure motor. Error: " + status.toString());
    }
}
```

**Common configurations:**
- Gear ratios (SensorToMechanismRatio)
- Current limits (Supply and Stator)
- Software limit switches (if applicable)
- PID gains (kP, kI, kD, kS, kV, kA, kG)
- Motion Magic parameters (velocity, acceleration, jerk)
- Neutral mode (Brake/Coast)

### 3. Motor Visualization (`MotorSim_Mech`)
```java
private MotorSim_Mech motorSimMech = new MotorSim_Mech("MotorName");

@Override
public void periodic() {
    motorSimMech.update(motor.getPosition(), motor.getVelocity());
}
```
- Simple Mechanism2d display showing position and velocity
- Update in `periodic()` method

### 4. Custom Mechanism2d (when applicable)
```java
private void initMechanism() {
    // Create Mechanism2d with appropriate size
    // Add roots, ligaments, indicators
    SmartDashboard.putData("Subsystem/Mech2d", mechanism);
}

private void updateMechanism() {
    // Update ligament positions/angles/colors based on real-time data
}
```
- Initialize in constructor with `initMechanism()`
- Update in `periodic()` with `updateMechanism()`
- Visualize mechanism state intuitively (positions, targets, game pieces)

### 5. Motor Simulation
```java
private MotorSim_Mech motorSimMech = new MotorSim_Mech("MotorName");

public void simulationInit() {
    PhysicsSim.getInstance().addTalonFX(motor, loadInertia);
}

@Override
public void simulationPeriodic() {
    PhysicsSim.getInstance().run();
}
```
- Configure simulated load and inertia
- Enables accurate PID tuning in simulation
- Required methods: `simulationInit()` and `simulationPeriodic()`

### 6. Logging
```java
// Competition-safe logging
// Publish motor info
if (FeatureSwitches.ENABLE_SUBSYSTEM_LOGGING) {
    SmartDashboard.putNumber("Subsystem/Position", motor.getPosition().getValue());
    SmartDashboard.putNumber("Subsystem/Velocity", motor.getVelocity().getValue());
}

// Debug logging (feature-switchable)
fLogger.log("setLevel called with level: %s (%. 1f)", level.name(), level.getposition());
```
- Consider: would logging this variable help me debug this subsystem if there was an issue?
- Numbers that we might want to graph (position, velocity, etc.) push to SmartDashboard with feature switch to disable
- Use FinneyLogger for detailed debug information
- Consider if a log will happen once in a while or every robot cycle. No need to feature switch logging that occurs occasionally.

## Best Practices

### Constants Usage
- **NO magic numbers** - use constants!
```java
// Good
if (current > CURRENT_LIMIT)

// Bad
if (current > 40)
```

### Naming Conventions
- **Fields**: camelCase with descriptive names
  - `private TalonFX mainMotor`
  - `private MotorSim_Mech elevator_motorSimMech`
- **Methods**: camelCase, verb-based
  - `setupMotors()`, `moveTo()`, `isAtPosition()`
- **Enums**: PascalCase with descriptive values
  - `ElevationLevel.Level_2`, `ElevationControl.Moving`
- **Constants**:  UPPER_SNAKE_CASE
  - `CURRENT_LIMIT`, `POSITION_ACCURACY`

### Safety Features
- Implement current limiting checks
- Use Alerts for operator warnings
- Soft/hard position limit switches for mechanical protection
- Neutral mode configuration (Brake/Coast)

### State Management
- Use enums for states and positions
- Validate state transitions
- Provide query methods:  `isAtPosition()`, `isAtLevel()`

## Constructor Pattern
```java
public SubsystemName() {
    setupMotors();
    simulationInit();
    initMechanism(); // if applicable
}
```

## Required Overrides
```java
@Override
public void periodic() {
    updateMechanism(); // if applicable
    motorSimMech.update(motor. getPosition(), motor.getVelocity());
    SmartDashboard.putNumber(... );
}

@Override
public void simulationPeriodic() {
    PhysicsSim.getInstance().run();
}
```

---

**Reference Implementation**:  See [Elevator.java](https://github.com/FRC-Team-1405/2025Robot/blob/feature/refactoring_elevator/src/main/java/frc/robot/subsystems/Elevator.java) from 2025 for a complete example following all these patterns.