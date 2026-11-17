# Camera auto-calibration: RightCam

- Saved: 2026-11-14T14:17:11  (repo ba2197f381a8)
- Log: `akit_26-11-14_19-11-27.wpilog`, calibration window (112.982194, 129.990503)
- Tags used: [9, 10]
- Vision samples used: 1066 of 1073

## Mount (inches / degrees)

| Parameter | Current | Calibrated | Change | +-1 sigma | Unit |
|---|---|---|---|---|---|
| x | 2.190 | 2.404 | +0.214 | 0.383 in | in |
| y | -10.910 | -9.742 | +1.168 | 0.402 in | in |
| z | 28.700 | 23.579 | -5.121 | 0.034 in | in |
| roll | -0.000 | -2.773 | -2.773 | 0.06 deg | deg |
| pitch | -25.000 | -28.248 | -3.248 | 0.05 deg | deg |
| yaw | 10.000 | 19.413 | +9.413 | 0.22 deg | deg |

- Position residual (RMS): 52.0 mm; rotation residual (RMS): 1.25 deg
- Vision-vs-odometry clock offset: -28 ms; wheel-odometry distance scale: 0.900
- Repeatability (two halves solved separately differ by): -28.2 / -9.1 / +8.1 mm and 0.24 deg

## Warnings

- x_mm uncertainty is 9.72 mm (limit 8): more data or a better tag view would help.
- y_mm uncertainty is 10.21 mm (limit 8): more data or a better tag view would help.
- The two halves of the run disagree by 28/9 mm and 0.24 deg: the result is not repeatable. Re-run, or check for odometry slip.
- Wheel odometry distance is off by 10.0% (fitted scale 0.900): check the wheel radius in the swerve constants, and for wheel slip.

## By phase of the routine

| Phase | Seconds | Samples | Samples/s | Position err (mm, RMS) | Rotation err (deg, RMS) |
|---|---|---|---|---|---|
| Hold | 2.0 | 126 | 63 | 28.7 | 0.41 |
| SweepCCW | 1.2 | 78 | 63 | 30.5 | 0.69 |
| SweepCW | 2.5 | 157 | 63 | 24.4 | 0.78 |
| SweepBack | 1.3 | 82 | 65 | 22.6 | 0.79 |
| DriveForward | 1.5 | 92 | 62 | 44.1 | 0.47 |
| DriveBack | 1.5 | 95 | 63 | 57.2 | 0.65 |
| StrafeLeft | 1.5 | 94 | 63 | 61.6 | 1.69 |
| StrafeRight | 3.0 | 188 | 63 | 71.9 | 2.04 |
| StrafeCenter | 1.5 | 94 | 62 | 86.8 | 2.07 |
| HoldEnd | 1.0 | 65 | 65 | 45.1 | 0.43 |

## Java

```java
// RightCam — calibrated 2026-11-14
new Transform3d(
    new Translation3d(
        Units.inchesToMeters(2.404),
        Units.inchesToMeters(-9.742),
        Units.inchesToMeters(23.579)),
    new Rotation3d(
        Math.toRadians(-2.773),
        Math.toRadians(-28.248),
        Math.toRadians(19.413)))
```
