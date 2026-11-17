# How to Tune a Swerve Drive

> **Scope:** This guide covers tuning the **drive base itself** — the mechanical and control foundation that everything else (auto-aim, path following, auto-pilot) is built on. Get this right first; higher-level features are tuned separately.

---

## Phase 0: Hardware Verification (before writing any code)

Before touching software, confirm the hardware is correct:

1. **Verify CAN bus wiring and device IDs**
   - Use Phoenix Tuner X to confirm every device (4× drive TalonFX, 4× steer TalonFX, 4× CANcoder, 1× Pigeon 2) is visible and on the correct CAN bus.
   - If using a **CANivore** (highly recommended), make sure the CAN bus name in TunerConstants matches. Currently our code has `kCANBus = new CANBus("", ...)` which is the RIO bus — this limits odometry to **100 Hz** instead of **250 Hz** on CAN FD.
   - Confirm no CAN utilization issues (keep below ~70%).

2. **Verify module mechanical constants**
   - **Gear ratios:** Confirm `kDriveGearRatio` and `kSteerGearRatio` match the physical module. Check the module manufacturer's spec sheet (SDS, WCP, etc.).
     - ⚠️ Currently: `kDriveGearRatio = 3.714`, `kSteerGearRatio = 25.9`. Verify these match your actual module configuration.
   - **Wheel radius:** Measure the actual wheel diameter with calipers under load (wheels compressed on carpet with robot weight).
     - ⚠️ Currently: `kWheelRadius = Inches.of(3.5)` → **7-inch diameter wheel**. Most FRC swerve modules use 3–4 inch diameter wheels (radius of 1.5–2.0 inches). **This looks incorrect and will break odometry and speed calculations.** Verify immediately.
   - **Coupling ratio:** `kCoupleRatio` accounts for azimuth-to-drive coupling in the gearbox. Currently set to `0`. Check your module documentation — most swerve modules do have some coupling. Leaving this wrong causes odometry drift when modules rotate.

3. **Verify module positions**
   - Confirm `kFrontLeftXPos/YPos`, etc. are measured correctly from the robot center to each module center, in the WPILib coordinate system (+X = forward, +Y = left).
   - FRC Coordinate System:
https://docs.wpilib.org/en/stable/docs/software/basic-programming/coordinate-system.html
   - Currently all set to ±10 inches. Measure and verify.

4. **Verify motor/encoder inversions**
   - Each module's drive motor, steer motor, and encoder inversion must be correct for your physical wiring. Incorrect inversions will cause modules to fight each other.

---

## Phase 1: CANcoder Offsets & Basic Module Behavior

1. **Run the CTR Electronics Swerve Project Generator / Tuner X**
   - This calibrates the CANcoder magnet offsets so each module's "zero" position is wheels-forward.
   - After calibration, manually spin each module and verify the reported angle in Tuner X matches reality.

2. **Confirm steer direction**
   - Command each module individually. Verify that a positive steer command rotates the module counter-clockwise (when viewed from above), per WPILib convention.
   - If a module goes the wrong way, fix the steer motor or encoder inversion — do NOT band-aid it with negative PID gains.

3. **Confirm drive direction**
   - With all modules pointed forward, command a positive drive voltage. All wheels should spin in the robot-forward direction.
   - Left-side and right-side inversions (`kInvertLeftSide`, `kInvertRightSide`) handle the mirroring.

---

## Phase 2: Steer Motor Tuning

Steer motors need to be tuned **first** because drive tuning and odometry depend on accurate module angles.

1. **Start with closed-loop voltage control** (already configured: `kSteerClosedLoopOutput = Voltage`)
2. **Tune steer kP**
   - Current value: `kP = 64`. This is a reasonable starting point for voltage control.
   - Test by commanding the module to snap between angles (e.g., 0° → 90° → 180°).
   - **Too low:** module is sluggish, overshoots, or oscillates slowly.
   - **Too high:** module buzzes, vibrates, or oscillates rapidly.
   - Add `kD` (start small, e.g., 0.5–2.0) if you see overshoot/oscillation that kP alone can't fix.
3. **Verify all 4 modules behave identically.** If one module is different, it's a hardware or configuration problem.
4. **Consider steer kS (static friction feedforward)**
   - This compensates for friction. Run a slow sweep and note the minimum voltage needed to start moving the module. Set `kS` to approximately that value.
5. **Steer feedback source**
   - Currently using `RemoteCANcoder`. If you have **Phoenix Pro licenses**, switch to `FusedCANcoder` for significantly better steer accuracy (it fuses the internal TalonFX encoder with the CANcoder for high-frequency, low-latency feedback).

---

## Phase 3: Drive Motor Tuning

### 3a. Determine kSpeedAt12Volts (empirically)

This is the **most important constant** for drive behavior. It must be measured, not calculated from motor specs.

1. Set drive to **open-loop** (temporarily set `kDriveClosedLoopOutput = ClosedLoopOutputType.Voltage` and use an open-loop drive request, or just apply 12V directly).
2. On carpet, with the robot at competition weight, drive full speed in a straight line.
3. Log the actual measured velocity (from drive motor encoders or odometry).
4. **That measured speed is your `kSpeedAt12Volts`.**
   - ⚠️ Currently: `kSpeedAt12Volts = MetersPerSecond.of(14.54)` → **14.54 m/s = 32.5 mph**. This is physically impossible for an FRC robot. Typical values are **3.5–5.5 m/s** depending on gearing and wheel size. This is almost certainly wrong because of the incorrect `kWheelRadius`.
   - Getting this wrong means your closed-loop control, odometry scaling, and everything downstream will be broken.

### 3b. Tune drive kV (feedforward)

- `kV` is the **most important drive gain** for closed-loop velocity control. It maps desired velocity to motor voltage.
- Calculate: `kV ≈ 12.0 / kSpeedAt12Volts_in_rotations_per_second` (in mechanism rotations/sec as the motor sees it).
- Or run **SysId** (see Phase 5) to get kV, kS, and kA automatically.
- ⚠️ Currently: `kV = 0`. **This means there is essentially no feedforward.** The robot is relying entirely on the tiny `kP = 0.001` to do all the work. This will perform terribly — the drive will be sluggish and have massive steady-state error.

### 3c. Tune drive kS (static friction feedforward)

- Compensates for the voltage needed to overcome friction and start moving.
- Typical values: 0.1–0.4V. SysId will find this for you.

### 3d. Tune drive kP

- After kV and kS are set, kP handles the remaining error.
- Start small and increase until the robot responds crisply without oscillating.
- ⚠️ Currently: `kP = 0.001`. This is essentially zero. After setting proper kV, you'll want something more like 0.05–0.5 (depends on units and control mode).

---

## Phase 4: Current Limits & Slip Current

### 4a. Drive motor current limits

**This is critical for robot reliability and brownout prevention.**

- ⚠️ Currently: `driveInitialConfigs = new TalonFXConfiguration()` — **no drive motor current limits are configured**. The steer motors have a 60A limit, but the drive motors are unlimited. This WILL cause brownouts under heavy load.
- Add stator current limits to `driveInitialConfigs`:
  ```java
  private static final TalonFXConfiguration driveInitialConfigs = new TalonFXConfiguration()
      .withCurrentLimits(
          new CurrentLimitsConfigs()
              .withStatorCurrentLimit(Amps.of(80))  // start here, tune based on slip testing
              .withStatorCurrentLimitEnable(true));
  ```

### 4b. Determine kSlipCurrent

The slip current is where the tread loses traction. Test using [this CTR guide](https://v6.docs.ctr-electronics.com/en/stable/docs/hardware-reference/talonfx/improving-performance-with-current-limits.html):

1. Place the robot on carpet at competition weight.
2. Drive the robot into an immovable wall (slowly ramp up current).
3. Monitor stator current. Note the current where the wheels start to spin/slip.
4. Set `kSlipCurrent` to that value (or slightly below for margin).
   - ⚠️ Currently: `kSlipCurrent = Amps.of(120)` — this is the generator default. Real slip current depends on your wheel tread, robot weight, and carpet. Typical values: **40–80A** for most FRC setups.
5. Set your `driveInitialConfigs` stator current limit at or below `kSlipCurrent`.

---

## Phase 5: Odometry Validation

**Do this AFTER fixing wheel radius, gear ratio, and kSpeedAt12Volts.** Otherwise you're debugging garbage data.

1. Mark a known distance on the floor (e.g., 3 meters with tape).
2. Slowly drive the robot that exact distance in a straight line.
3. Compare the odometry-reported distance to the real distance.
4. **If odometry is off by a consistent percentage,** the likely causes (in order of likelihood) are:
   - **Wheel radius is wrong** — most common. Remeasure under load.
   - **Drive gear ratio is wrong** — double-check module specs.
   - **Coupling ratio is wrong** — causes drift proportional to how much the modules rotate.
5. Test in multiple directions and at different speeds.
6. Test rotational odometry: rotate the robot exactly 360° and check that the gyro and wheel odometry agree.

---

## Phase 6: System Identification (SysId)

SysId gives you **measured** feedforward values (kS, kV, kA) and helps validate/tune your PID gains. The CTR swerve generator already provides the SysId routines in `CommandSwerveDrivetrain`.

### When to run SysId
- After all mechanical constants (wheel radius, gear ratios, inversions) are verified.
- On carpet, at competition weight.
- With a charged battery (≥12.5V).

### What to run

1. **Translation characterization** (`m_sysIdRoutineTranslation`)
   - Characterizes the drive motors. Gives you kS, kV, kA for the drive.
   - Apply the results to `driveGains` (kS, kV) and adjust kP/kD as needed.

2. **Steer characterization** (`m_sysIdRoutineSteer`)
   - Characterizes the steer motors. Gives you kS, kV, kA for the steer.
   - Apply the results to `steerGains`.

3. **Rotation characterization** (`m_sysIdRoutineRotation`)
   - Characterizes the robot's rotational dynamics. Used for heading controllers (FieldCentricFacingAngle, etc.).
   - This is for higher-level features — run it, but apply the gains to heading PIDs, not TunerConstants.

### SysId docs
- CTR: https://v6.docs.ctr-electronics.com/en/stable/docs/api-reference/wpilib-integration/sysid-integration/index.html
- WPILib: https://docs.wpilib.org/en/stable/docs/software/advanced-controls/system-identification/introduction.html

---

## Summary: TunerConstants Issues to Fix

| Constant | Current Value | Problem | Action |
|---|---|---|---|
| `kWheelRadius` | 3.5 in (7" diameter) | Almost certainly wrong for FRC swerve | Measure actual wheel, likely ~1.5–2.0 in |
| `kSpeedAt12Volts` | 14.54 m/s | Physically impossible, likely caused by wrong wheel radius | Re-derive after fixing wheel radius, then measure empirically |
| `kCoupleRatio` | 0 | Most modules have coupling | Check module documentation |
| `driveGains.kV` | 0 | No feedforward — drive can't track velocity | Calculate or run SysId |
| `driveGains.kP` | 0.001 | Effectively zero | Increase after setting kV |
| `kSlipCurrent` | 120A | Generator default, not tested | Test on carpet at comp weight |
| `driveInitialConfigs` | No current limits | Will brownout under load | Add stator current limit |
| `kCANBus` | `""` (RIO bus) | Limits odometry to 100Hz | Use CANivore name if available |
| `kSteerFeedbackType` | `RemoteCANcoder` | Lower accuracy | Use `FusedCANcoder` if Pro licensed |

---

## Tuning Order Checklist

- [ ] Verify/fix `kWheelRadius` (measure under load)
- [ ] Verify/fix `kDriveGearRatio` and `kSteerGearRatio`
- [ ] Verify/fix `kCoupleRatio`
- [ ] Verify module positions (X/Y from center)
- [ ] Calibrate CANcoder offsets (Tuner X)
- [ ] Verify steer direction and drive direction for all 4 modules
- [ ] Tune steer PID (kP, kD, kS)
- [ ] Upgrade to `FusedCANcoder` if Pro licensed
- [ ] Measure `kSpeedAt12Volts` empirically
- [ ] Run SysId translation (get drive kS, kV, kA)
- [ ] Set drive feedforward gains (kS, kV) from SysId
- [ ] Tune drive kP
- [ ] Test and set `kSlipCurrent`
- [ ] Add drive motor stator current limits
- [ ] Validate odometry (straight-line distance test)
- [ ] Validate rotational odometry (360° spin test)
- [ ] Run SysId steer (refine steer gains)
- [ ] Run SysId rotation (for heading controllers — separate from drive base)

---

## FAQ / Troubleshooting

**Q: Robot drives but odometry is wildly off.**
A: Almost always `kWheelRadius` or `kDriveGearRatio` is wrong. Fix these first.

**Q: Robot is sluggish even at full stick.**
A: Check that `kSpeedAt12Volts` is correct. If it's too high, the robot will request speeds it can never reach, and the controller will always be undersaturated. Also check that `kV` is non-zero.

**Q: Modules jitter or buzz at rest.**
A: Steer `kP` is too high, or `kD` is too high. Reduce gains. Also check for mechanical backlash.

**Q: Robot drifts to one side.**
A: Check that all module positions are correct and symmetric. Verify inversions. Check for one module with different friction or a damaged wheel.

**Q: Is there a way to test/measure gyro drift over time?**
A: Yes. Leave the robot completely still and powered on. Log the Pigeon 2 yaw over 10–30 minutes. The Pigeon 2 has very low drift (~0.5°/min or less when properly calibrated), but temperature changes can affect it. The Pigeon 2 has built-in temperature compensation — make sure it's enabled in config and give the gyro 1–2 minutes to temperature-stabilize after power-on before relying on heading data. You can also compare gyro heading vs. wheel odometry heading over a long drive to detect drift.