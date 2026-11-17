# AdvantageKit: Adding it to a Subsystem

This guide walks through the exact pattern used in this codebase. Follow it
whenever you add a new subsystem or retrofit an existing one.

---

## The Three-File Rule

Every hardware subsystem gets three files:

```
subsystems/
├── FooIO.java          ← interface + @AutoLog inputs struct
├── FooIOTalonFX.java   ← real hardware (runs on the robot)
├── FooIOSim.java       ← simulated hardware (runs in Gradle sim)
└── Foo.java            ← subsystem logic (unchanged by which IO is used)
```

The subsystem (`Foo.java`) never imports CTRE, PhotonVision, or WPILib
hardware classes directly. All hardware lives in the IO implementations.

---

## Step 1 — Define the IO Interface

Create `FooIO.java` in `src/main/java/frc/robot/subsystems/`:

```java
package frc.robot.subsystems;

import org.littletonrobotics.junction.AutoLog;

public interface FooIO {

    // The @AutoLog annotation triggers the annotation processor to generate
    // FooIOInputsAutoLogged, which implements AutoLoggedInputs so AKit can
    // serialize/deserialize every field for logging and replay.
    @AutoLog
    public static class FooIOInputs {
        // List every sensor reading the subsystem needs.
        // Use primitive types or arrays of primitives/structs — no Optional.
        public double motorVelocityRPS    = 0.0;
        public double statorCurrentAmps   = 0.0;
        public double supplyCurrentAmps   = 0.0;
        public double outputVoltage       = 0.0;
        public double closedLoopError     = 0.0;
        public double closedLoopReference = 0.0;
    }

    // updateInputs is called every loop by the subsystem.
    // The real impl reads hardware; the sim impl steps physics and returns results.
    public default void updateInputs(FooIOInputs inputs) {}

    // One method per hardware action the subsystem needs to perform.
    public default void setVelocity(double velocityRPS) {}
    public default void stop() {}
}
```

**Rules for the Inputs struct:**
- Public fields only — no getters. The annotation processor reflects on them.
- Initialize every field to a safe default (0.0 / false / empty array).
- For arrays (e.g. pose estimates), initialize to `new Pose2d[0]` not `null`.
- Supported types: `boolean`, `int`, `long`, `float`, `double`, `String`,
  `boolean[]`, `int[]`, `long[]`, `float[]`, `double[]`, `String[]`, and
  any type implementing `StructSerializable` (e.g. `Pose2d`, `Rotation2d`).

---

## Step 2 — Implement Real Hardware

Create `FooIOTalonFX.java` (or `FooIONeo.java`, `FooIOServo.java`, etc.):

```java
package frc.robot.subsystems;

import com.ctre.phoenix6.hardware.TalonFX;
// ... other CTRE/WPILib hardware imports

public class FooIOTalonFX implements FooIO {
    private final TalonFX motor = new TalonFX(Constants.CANBus.FOO_MOTOR);
    private final MotionMagicVelocityVoltage velocityRequest =
            new MotionMagicVelocityVoltage(0);
    private final NeutralOut brakeRequest = new NeutralOut();

    public FooIOTalonFX() {
        // Configure motor here — gains, current limits, soft limits, etc.
        TalonFXConfiguration cfg = new TalonFXConfiguration();
        cfg.Slot0.kP = Constants.FooPreferences.KP;
        // ...
        motor.getConfigurator().apply(cfg);
    }

    @Override
    public void updateInputs(FooIOInputs inputs) {
        // Read every signal needed by the subsystem and write into inputs.
        inputs.motorVelocityRPS    = motor.getVelocity().getValueAsDouble();
        inputs.statorCurrentAmps   = motor.getStatorCurrent().getValueAsDouble();
        inputs.supplyCurrentAmps   = motor.getSupplyCurrent().getValueAsDouble();
        inputs.outputVoltage       = motor.getMotorVoltage().getValueAsDouble();
        inputs.closedLoopError     = motor.getClosedLoopError().getValueAsDouble();
        inputs.closedLoopReference = motor.getClosedLoopReference().getValueAsDouble();
    }

    @Override
    public void setVelocity(double velocityRPS) {
        motor.setControl(velocityRequest.withVelocity(velocityRPS));
    }

    @Override
    public void stop() {
        motor.setControl(brakeRequest);
    }
}
```

**Rules:**
- No business logic here — only hardware configuration and reading/writing.
- CTRE signals: call `.getValueAsDouble()` directly; don't cache them across
  loops (AKit already timestamps everything).
- If signals need higher frequency, call `.setUpdateFrequency(100)` in the
  constructor, not in `updateInputs`.

---

## Step 3 — Implement Simulation

Create `FooIOSim.java`:

```java
package frc.robot.subsystems;

import edu.wpi.first.math.MathUtil;
import edu.wpi.first.math.system.plant.DCMotor;
import edu.wpi.first.math.system.plant.LinearSystemId;
import edu.wpi.first.wpilibj.simulation.DCMotorSim;

public class FooIOSim implements FooIO {
    // DCMotorSim takes: linear system model, motor type.
    // createDCMotorSystem(motor, momentOfInertia_kgm2, gearRatio)
    private final DCMotorSim motorSim = new DCMotorSim(
            LinearSystemId.createDCMotorSystem(DCMotor.getKrakenX60(1), 0.001, 1.0),
            DCMotor.getKrakenX60(1));

    private double targetRPS = 0.0;
    private boolean running  = false;

    @Override
    public void updateInputs(FooIOInputs inputs) {
        // 1. Compute voltage to apply based on target
        double currentRPS = motorSim.getAngularVelocityRPM() / 60.0;
        double voltage = 0.0;
        if (running) {
            // Simple kV feedforward + proportional feedback — good enough for sim
            double ff = 0.12 * targetRPS;  // kV ≈ 0.12 V·s/rot for Kraken
            double fb = 0.66 * (targetRPS - currentRPS);
            voltage = MathUtil.clamp(ff + fb, -12.0, 12.0);
        }

        // 2. Step the physics simulation one 20 ms loop
        motorSim.setInputVoltage(voltage);
        motorSim.update(0.02);   // seconds per loop

        // 3. Write results into inputs — same fields as the real impl
        inputs.motorVelocityRPS    = motorSim.getAngularVelocityRPM() / 60.0;
        inputs.statorCurrentAmps   = motorSim.getCurrentDrawAmps();
        inputs.supplyCurrentAmps   = motorSim.getCurrentDrawAmps();
        inputs.outputVoltage       = voltage;
        inputs.closedLoopError     = targetRPS - inputs.motorVelocityRPS;
        inputs.closedLoopReference = targetRPS;
    }

    @Override
    public void setVelocity(double velocityRPS) {
        targetRPS = velocityRPS;
        running   = true;
    }

    @Override
    public void stop() {
        targetRPS = 0.0;
        running   = false;
    }
}
```

**Choosing a motor model:**
| Motor | DCMotor factory method |
|-------|------------------------|
| Kraken X60 | `DCMotor.getKrakenX60(n)` |
| Falcon 500 | `DCMotor.getFalcon500(n)` |
| NEO | `DCMotor.getNEO(n)` |
| NEO 550 | `DCMotor.getNeo550(n)` |

`n` = number of motors acting on the same mechanism.

**For position-controlled mechanisms** (arm, elevator, intake deploy):

```java
private final PIDController pid = new PIDController(kP, kI, kD);
private double targetPositionRots = 0.0;

// In updateInputs():
double posError   = targetPositionRots - motorSim.getAngularPositionRotations();
double voltage    = MathUtil.clamp(pid.calculate(posError), -12.0, 12.0);
motorSim.setInputVoltage(voltage);
motorSim.update(0.02);
inputs.positionRots = motorSim.getAngularPositionRotations();
```

---

## Step 4 — Refactor the Subsystem

Rewrite `Foo.java` to accept an IO and use it:

```java
package frc.robot.subsystems;

import edu.wpi.first.wpilibj2.command.SubsystemBase;
import org.littletonrobotics.junction.AutoLogOutput;
import org.littletonrobotics.junction.Logger;

public class Foo extends SubsystemBase {

    // 1. Hold an IO reference and a live inputs snapshot
    private final FooIO io;
    private final FooIOInputsAutoLogged inputs = new FooIOInputsAutoLogged();
    //            ^^^^^^^^^^^^^^^^^^^^^^^^^^^
    //            Generated by the @AutoLog annotation processor.
    //            Never instantiate FooIOInputs directly — always use the
    //            AutoLogged subclass so AKit can serialize it.

    // 2. Computed outputs — logged via @AutoLogOutput (not through IO)
    @AutoLogOutput(key = "Foo/IsRunning")
    private boolean isRunning = false;

    @AutoLogOutput(key = "Foo/TargetRPS")
    private double targetRPS = 0.0;

    // 3. Accept the IO in the constructor
    public Foo(FooIO io) {
        this.io = io;
    }

    @Override
    public void periodic() {
        // 4a. Poll hardware (or simulation) and store into inputs
        io.updateInputs(inputs);

        // 4b. Log the entire inputs struct under the "Foo" namespace.
        //     On replay this line feeds the logged values BACK into inputs
        //     instead of reading from hardware.
        Logger.processInputs("Foo", inputs);

        // 5. Business logic uses inputs.fieldName — never calls motor.getX() here
        if (inputs.closedLoopError > THRESHOLD) {
            // ... react
        }
    }

    // 6. Commands call io.action() — never touch hardware objects directly
    public void runAt(double rps) {
        targetRPS = rps;
        isRunning = true;
        io.setVelocity(rps);
    }

    public void stopMechanism() {
        isRunning = false;
        io.stop();
    }
}
```

**Key rules:**
- `io.updateInputs(inputs)` then `Logger.processInputs(...)` — always in
  that order, always first in `periodic()`.
- Read sensor data from `inputs.fieldName` everywhere else in the subsystem.
  Never call `motor.getVelocity()` directly in the subsystem class.
- `@AutoLogOutput` on fields/methods logs values that the subsystem
  *computes* (not raw sensor data). These are NOT replayable — they will be
  recomputed from the replayed inputs.
- Never put `@AutoLogOutput` on an enum field directly; return `.name()` from
  a method instead (AKit doesn't know how to serialize arbitrary enums).

---

## Step 5 — Wire it in RobotContainer

```java
// RobotContainer.java
import edu.wpi.first.wpilibj.RobotBase;

public class RobotContainer {

    public final Foo foo = new Foo(
            RobotBase.isReal() ? new FooIOTalonFX() : new FooIOSim());

    // ...
}
```

That single ternary is the only place in the entire codebase that knows
which implementation is running. Everything else is interface-typed.

---

## Naming Conventions

| Item | Convention | Example |
|------|-----------|---------|
| Interface | `SubsystemIO` | `ShooterIO` |
| Inputs struct | `SubsystemIOInputs` | `ShooterIOInputs` |
| Generated class | `SubsystemIOInputsAutoLogged` | `ShooterIOInputsAutoLogged` |
| Real impl | `SubsystemIOTalonFX` / `SubsystemIONeo` | `ShooterIOTalonFX` |
| Sim impl | `SubsystemIOSim` | `ShooterIOSim` |
| Logger key | Subsystem name, PascalCase | `"Shooter"` |
| AutoLogOutput key | `"Subsystem/FieldName"` | `"Shooter/Locked"` |

---

## Checklist for a New Subsystem

- [ ] `FooIO.java` with `@AutoLog` Inputs class and `default` action methods
- [ ] `FooIOTalonFX.java` (or equivalent) — hardware only, no logic
- [ ] `FooIOSim.java` — `DCMotorSim` stepped in `updateInputs()`
- [ ] `Foo.java` — constructor takes `FooIO`, periodic calls `updateInputs` + `processInputs`
- [ ] No direct hardware imports in `Foo.java`
- [ ] `@AutoLogOutput` on all computed outputs (booleans, setpoints, state machines)
- [ ] RobotContainer injects via `RobotBase.isReal()` ternary
- [ ] Every sensor reading consumed from `inputs.field`, never from motor getters
