# AutoPilot Drive Gains Tuning & Debugging Guide

> **Context:** This guide covers debugging the oscillation issue seen when increasing `driveGains.kP` above 0.5 while using `AutoPilotCommand`, and why `PidToPoseCommand` doesn't exhibit the same behavior.
>
> **Update:** `AutoPilotV2Command` was created to address the issues below. It uses a single code path (no distance-based switching), converts speeds to field-relative before passing to AutoPilot, and includes per-module diagnostic logging. Try V2 first — if oscillation persists, use the logging output to identify the source.

---

## Symptom Summary

| Condition | Behavior |
|---|---|
| `driveGains.kP ≤ 0.5`, all other gains zeroed | `closedLoopOutput` = 0, modules do nothing |
| `driveGains.kP > 0.5`, all other gains zeroed | Modules oscillate (small forward/backward vectors) |
| `driveGains.kP=0.5, kS=0.3, kV=0.5, kA=0.8` | Still oscillates with AutoPilot |
| PidToPose with current gains (`kP=0.25, kV=0.12, kD=0.01`) | Works fine |

---

## Root Cause Analysis

### 1. Likely Bug: Robot-Relative Speeds Passed to AutoPilot

**This is the most likely root cause, and why feedforward alone didn't fix it.**

The original `AutoPilotCommand` passes `getState().Speeds` (robot-relative) directly to `kAutopilot.calculate()`:
```java
ChassisSpeeds robotRelativeSpeeds = m_drivetrain.getState().Speeds;
out = kAutopilot.calculate(pose, robotRelativeSpeeds, m_target);
```

AutoPilot plans in field coordinates and outputs field-relative velocities (`vx`, `vy`). It almost certainly expects **field-relative** speed input to compute its deceleration profile. When you pass robot-relative speeds:

- **Robot facing 0° (forward):** Robot-relative ≈ field-relative → works OK
- **Robot rotated 90°:** Robot-relative vx becomes field-relative vy → AutoPilot sees velocity **perpendicular** to actual field motion → computes wrong deceleration → oscillation

This explains:
- **Why feedforward didn't fix it:** The motor-level PID is working correctly, but it's being given bad velocity *references* from AutoPilot's miscalculated profile
- **Why PidToPose works:** It uses `ProfiledPIDController` on X/Y position directly — no AutoPilot library, no speed-frame issue
- **Why oscillation gets worse with higher kP:** The motors more aggressively track the *wrong* velocity commands

`AutoPilotV2Command` fixes this by converting to field-relative before calling AutoPilot:
```java
ChassisSpeeds fieldSpeeds = toFieldRelative(robotSpeeds, pose.getRotation());
out = kAutopilot.calculate(pose, fieldSpeeds, m_target);
```

### 2. Missing Feedforward Compounds the Problem

When you zero out all gains except `kP`, you remove `kV` (velocity feedforward) and `kS` (static friction feedforward). **This fundamentally changes how the motor controller operates.**

With the production gains (`kP=0.25, kV=0.12`):
```
Motor Output = kS + kV × desiredVelocity + kP × velocityError
```

With your test gains (`kP=0.5, kV=0, kS=0`):
```
Motor Output = kP × velocityError
```

Without `kV`, the motor **must** accumulate a velocity error before it produces any output. This creates a feedback loop:
1. Velocity setpoint arrives (e.g., 0.5 m/s) → motor is at 0 m/s → error = 0.5
2. `kP × 0.5` applies voltage → motor accelerates
3. Motor overshoots the setpoint → error flips sign → motor brakes
4. Motor undershoots → error flips again → **oscillation**

**Why `kP ≤ 0.5` shows zero output:** The velocity commands from AutoPilot are small enough that `kP × error` can't overcome the motor's static friction. The motor doesn't move, error stays constant, and you see a steady (near-zero) `closedLoopOutput`.

**Why `kP > 0.5` oscillates:** Now `kP × error` is enough to overcome friction, but without feedforward damping the response, the motor overshoots and enters a limit cycle.

### 2. Key Architectural Differences: AutoPilot vs PidToPose

This is **why PidToPose works with the same production gains** but AutoPilot is more sensitive:

#### Swerve Request Types

| | AutoPilotCommand | PidToPoseCommand |
|---|---|---|
| **Request type** | `ApplyRobotSpeeds` + `FieldCentricFacingAngle` | `ApplyFieldSpeeds` |
| **Heading control** | External theta PID OR `FieldCentricFacingAngle.withHeadingPID(2,0,0)` | Theta PID baked into ChassisSpeeds omega |
| **Speed reference frame** | Mixed: robot-relative (end motion) + field-relative (mid motion) | Always field-relative |

#### How Each Command Applies Speeds

**PidToPoseCommand** (line 381):
```java
// Simple: field-relative speeds, one consistent path
drive.setControl(pidToPose_FieldSpeeds
    .withSpeeds(new ChassisSpeeds(xOutput, yOutput, thetaOutput)));
```
- `xOutput` and `yOutput` come from `ProfiledPIDController` — these produce **smooth, trapezoidally-profiled** velocity commands
- The velocity profile ramps up and down smoothly, so the module-level velocity setpoints are always changing gradually
- No frame-of-reference conversion artifacts

**AutoPilotCommand** has **three different code paths** depending on distance-to-target:

| Distance % | Code Path | Request Type | Heading Control |
|---|---|---|---|
| 0–10% | Lines 399–413 | `FieldCentricFacingAngle` | Hold starting rotation |
| 10–90% | Lines 355–395 | `FieldCentricFacingAngle` OR `ApplyRobotSpeeds` | AP angle or custom theta PID |
| 90–100% | Lines 333–354 | `ApplyRobotSpeeds` | End-motion theta PID |

**Problem areas:**

1. **`FieldCentricFacingAngle` adds heading PID jitter** (lines 382–385):
   ```java
   m_drivetrain.setControl(m_request
       .withVelocityX(out.vx())
       .withVelocityY(out.vy())
       .withTargetDirection(rotationToUse));
   ```
   The internal `headingPID(2, 0, 0)` generates a rotational velocity (omega). CTRE's swerve kinematics decomposes `vx + vy + omega` into per-module speeds. Even tiny omega corrections cause opposite-side modules to get **opposite velocity deltas**. This means module FL might get `+0.05 m/s` while FR gets `-0.05 m/s`. With an aggressive kP and no feedforward, these tiny velocity commands cause oscillation.

2. **`ApplyRobotSpeeds` with frame conversion** (lines 339–345):
   ```java
   ChassisSpeeds outRobotRelativeSpeeds = ChassisSpeeds.fromFieldRelativeSpeeds(
       out.vx(), out.vy(),
       AngularVelocity.ofBaseUnits(thetaOutput, RadiansPerSecond),
       m_drivetrain.getState().Pose.getRotation());
   m_drivetrain.setControl(applyRobotSpeeds.withSpeeds(outRobotRelativeSpeeds));
   ```
   The `fromFieldRelativeSpeeds()` conversion uses the current pose rotation, which may be **one control loop stale**. Any latency in the rotation estimate introduces a phase error in the vx/vy decomposition. At higher kP, the motor reacts aggressively to this error, amplifying the oscillation.

3. **AutoPilot velocity profile characteristics:** The third-party `Autopilot` library generates its own motion profile via `APResult.vx()` and `APResult.vy()`. These may have different smoothness characteristics than WPILib's `ProfiledPIDController`. If the AutoPilot library produces velocity commands that change more abruptly (step-like), this demands more from the motor-level PID, making oscillation more likely without feedforward.

#### Summary Table

| Factor | AutoPilotCommand | PidToPoseCommand | Impact |
|---|---|---|---|
| Velocity source | `Autopilot.calculate()` library | `ProfiledPIDController` (WPILib) | Different smoothness profiles |
| Field-to-robot conversion | Manual `fromFieldRelativeSpeeds()` | Handled internally by `ApplyFieldSpeeds` | AP has potential phase lag |
| Heading control | `FieldCentricFacingAngle` heading PID | Omega in ChassisSpeeds | AP heading PID adds module-level velocity noise |
| Code path complexity | 3 branches with different request types | 1 consistent path | AP has more edge cases |
| Module velocity noise floor | Higher (heading PID + conversion) | Lower (direct field speeds) | AP needs more feedforward to stabilize |

---

## Tuning Procedure

### Step 0: Don't Zero Out Feedforward

**The most important advice: never tune `kP` in isolation without feedforward.**

The `driveGains` control the **motor-level velocity PID** on each TalonFX. These are not translational position gains — they are velocity-tracking gains. Velocity control requires feedforward (`kV`) to function correctly. Without it, the PID must generate 100% of the output from error alone, which is inherently oscillation-prone.

Think of it this way:
- `kV` says "to go 1 m/s, apply approximately X volts" (open-loop estimate)
- `kP` says "for every unit of velocity error, add Y volts of correction"
- Without `kV`, the controller has no idea what voltage corresponds to the desired speed

### Step 1: Establish Feedforward First (kS, kV)

If you haven't already run SysId for the drive motors, do so now. This gives you measured `kS` and `kV` values. See `HowToTuneASwerveDrive.md` Phase 6.

If you can't run SysId, estimate:
```
kV ≈ 12.0 / (kSpeedAt12Volts in motor rotations per second)
```

Your current production values (`kS=0.0, kV=0.12`) are a starting point. Consider running SysId to verify `kS` — a non-zero `kS` helps overcome static friction cleanly.

### Step 2: Tune Drive kP with Feedforward Present

1. Start with your SysId/estimated `kV` and `kS`
2. Set `kP = 0` and verify the robot drives roughly correctly (feedforward only)
3. Increase `kP` in small increments (0.05 → 0.1 → 0.25 → 0.5)
4. Test with **both** PidToPose and AutoPilot at each increment
5. Look for:
   - **Sluggish response** → increase kP
   - **Oscillation** → decrease kP (or add kD)
   - **Steady-state error** → kV might be slightly off, adjust it

### Step 3: Add kD If Needed

If you see overshoot oscillation even with correct feedforward:
- Start with `kD = 0.005` and increase to `0.01–0.05`
- kD dampens rapid velocity changes, reducing oscillation
- Your current production value (`kD = 0.01`) is reasonable

### Step 4: Validate with AutoPilot Specifically

AutoPilot is more sensitive to drive gains due to the architectural differences above. After tuning with teleop/PidToPose:

1. Run a simple AutoPilot move (1–2 meters, straight line, no rotation)
2. Log `closedLoopReference`, `closedLoopError`, and `closedLoopOutput` for all 4 modules
3. Check for:
   - **Reference oscillation:** The velocity setpoint itself is oscillating → issue is in AutoPilot/heading PID, not drive gains
   - **Output oscillation with steady reference:** The motor is oscillating around the setpoint → kP too high or kV too low
   - **Asymmetric module behavior:** Some modules oscillate while others don't → heading PID is injecting rotational velocity

### Step 5: Tune AutoPilot's Heading PID

The `FieldCentricFacingAngle` heading PID is set at line 130:
```java
.withHeadingPID(2, 0, 0)
```

If modules on opposite sides show opposite oscillation patterns, this heading PID is the culprit:
- Reduce heading kP (try 1.0 or 1.5)
- Add heading kD (try 0.05–0.1) to dampen heading corrections

### Step 6: Consider Switching AutoPilot to ApplyFieldSpeeds

The cleanest fix for the frame-conversion issue is to change `AutoPilotCommand` to use `ApplyFieldSpeeds` instead of `ApplyRobotSpeeds` for the end-motion phase. This eliminates the `fromFieldRelativeSpeeds()` conversion and matches what PidToPose does:

```java
// Instead of converting to robot-relative:
// ChassisSpeeds outRobotRelativeSpeeds = ChassisSpeeds.fromFieldRelativeSpeeds(...);
// m_drivetrain.setControl(applyRobotSpeeds.withSpeeds(outRobotRelativeSpeeds));

// Use field-relative directly:
private final SwerveRequest.ApplyFieldSpeeds applyFieldSpeeds = new SwerveRequest.ApplyFieldSpeeds()
    .withDriveRequestType(DriveRequestType.Velocity);

// In execute():
m_drivetrain.setControl(applyFieldSpeeds
    .withSpeeds(new ChassisSpeeds(out.vx(), out.vy(), thetaOutput)));
```

This removes the stale-rotation-estimate issue and matches the approach that works in PidToPose.

---

## Diagnostic Logging Checklist

When debugging, log these values every cycle (publish to SmartDashboard/NetworkTables):

| Value | What It Tells You |
|---|---|
| `APResult.vx()`, `APResult.vy()` | What AutoPilot is commanding (field-relative) |
| Per-module `closedLoopReference` | What velocity the motor is being told to achieve |
| Per-module `closedLoopError` | Gap between reference and actual velocity |
| Per-module `closedLoopOutput` | What voltage/effort the PID is applying |
| Per-module `velocity` | Actual motor velocity |
| `getPercentageOfDistanceToTarget()` | Which code path is active (0-10%, 10-90%, 90-100%) |
| Heading PID output | Whether theta corrections are injecting module velocity noise |

### What to Look For in Logs

**Healthy behavior:**
- `closedLoopReference` changes smoothly (no sudden jumps)
- `closedLoopError` is small and converges to zero
- `closedLoopOutput` is primarily from feedforward, with small PID corrections
- All 4 modules show similar patterns

**Oscillation pattern (your current issue):**
- `closedLoopReference` may be steady, but `closedLoopOutput` alternates +/-
- `closedLoopError` sign-flips every few cycles
- Opposite-side modules show mirrored oscillation (heading PID issue)

---

## Quick Reference: Current Gain Values

### TunerConstants driveGains (motor-level velocity PID)
```java
kP = 0.25, kI = 0, kD = 0.01, kS = 0.0, kV = 0.12, kA = 0
ClosedLoopOutputType = Voltage
```

### AutoPilotCommand theta PIDs (robot-level heading control)
```java
// Mid-motion theta PID
kP = 8, kI = 0, kD = 0
Constraints: maxVel = 20 rad/s, maxAccel = 25 rad/s²

// End-motion theta PID
kP = 10, kI = 0, kD = 0.1
Constraints: maxVel = 10 rad/s, maxAccel = 15 rad/s²

// FieldCentricFacingAngle heading PID
kP = 2, kI = 0, kD = 0
```

### PidToPoseCommand PIDs (robot-level position control)
```java
// X/Y controllers (position → velocity)
kP = 2.5, kI = 0, kD = 0
Constraints: maxVel = 4 m/s, maxAccel = 5 m/s²

// Theta controller
kP = 5, kI = 0, kD = 0
```

### AutoPilot constraints
```java
Acceleration = 2.0 m/s², Velocity = 2.0 m/s, Jerk = 10.0 m/s³
```

---

## TL;DR

1. **Don't zero feedforward when tuning kP.** The oscillation is caused by removing kV/kS, not by kP being too high. Keep `kV=0.12` (or run SysId) and tune kP on top of that.
2. **AutoPilot is more oscillation-prone than PidToPose** because of its `FieldCentricFacingAngle` heading PID injecting rotational velocity into modules, and its `ApplyRobotSpeeds` frame conversion introducing phase lag.
3. **To make AutoPilot more robust:** Consider switching its end-motion path to `ApplyFieldSpeeds` (matching PidToPose), and reducing the `FieldCentricFacingAngle` heading kP from 2 to ~1.0.
4. **Proper tuning order:** SysId → set kV/kS → tune kP small → add kD if needed → validate with AutoPilot.
