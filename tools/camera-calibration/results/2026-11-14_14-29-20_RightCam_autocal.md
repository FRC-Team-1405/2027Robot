# Camera auto-calibration: RightCam

- Saved: 2026-11-14T14:29:20  (repo 40fa1f04ab92)
- Log: `akit_26-11-14_19-11-27.wpilog`, calibration window (112.982194, 129.990503)
- Tags used: [9, 10]
- Vision samples used: 1065 of 1073

## Mount (inches / degrees)

| Parameter | Current | Calibrated | Change | +-1 sigma | Unit |
|---|---|---|---|---|---|
| x | 2.190 | 2.393 | +0.203 | 0.382 in | in |
| y | -10.910 | -9.759 | +1.151 | 0.401 in | in |
| z | 28.700 | 23.579 | -5.121 | 0.034 in | in |
| roll | -0.000 | -2.773 | -2.773 | 0.06 deg | deg |
| pitch | -25.000 | -28.248 | -3.248 | 0.05 deg | deg |
| yaw | 10.000 | 19.405 | +9.405 | 0.22 deg | deg |

- Position residual (RMS): 51.9 mm; rotation residual (RMS): 1.25 deg
- Vision-vs-odometry clock offset: -28 ms; wheel-odometry distance scale: 0.899
- Repeatability (two halves solved separately differ by): -38.3 / -21.7 / +8.1 mm and 0.35 deg

## Warnings

- x_mm uncertainty is 9.71 mm (limit 8): more data or a better tag view would help.
- y_mm uncertainty is 10.19 mm (limit 8): more data or a better tag view would help.
- The two halves of the run disagree by 38/22 mm and 0.35 deg: the result is not repeatable. Re-run, or check for odometry slip.
- Wheel odometry distance is off by 10.1% (fitted scale 0.899): check the wheel radius in the swerve constants, and for wheel slip.

## By phase of the routine

| Phase | Seconds | Samples | Samples/s | Position err (mm, RMS) | Rotation err (deg, RMS) |
|---|---|---|---|---|---|
| Hold | 2.0 | 126 | 63 | 28.6 | 0.41 |
| SweepCCW | 1.2 | 78 | 63 | 30.4 | 0.69 |
| SweepCW | 2.5 | 157 | 63 | 24.4 | 0.78 |
| SweepBack | 1.3 | 82 | 65 | 22.6 | 0.79 |
| DriveForward | 1.5 | 92 | 62 | 44.3 | 0.47 |
| DriveBack | 1.5 | 95 | 63 | 57.4 | 0.65 |
| StrafeLeft | 1.5 | 94 | 63 | 61.3 | 1.69 |
| StrafeRight | 3.0 | 188 | 63 | 71.8 | 2.04 |
| StrafeCenter | 1.5 | 94 | 62 | 86.9 | 2.07 |
| HoldEnd | 1.0 | 65 | 65 | 45.2 | 0.43 |

## Straight drives: wheels vs camera

| Drive | Wheels say (mm) | Camera saw (mm) | Ratio camera/wheels | Direction vs typical drive (deg) |
|---|---|---|---|---|
| DriveForward | 483 | 459 | 0.950 | 2.7 |
| DriveBack | 518 | 504 | 0.973 | 2.6 |
| StrafeLeft | 485 | 373 | 0.769 | 0.0 |
| StrafeRight | 1294 | 1092 | 0.844 | -1.7 |
| StrafeCenter | 504 | 495 | 0.983 | -0.7 |

## Java

```java
// RightCam — calibrated 2026-11-14
new Transform3d(
    new Translation3d(
        Units.inchesToMeters(2.393),
        Units.inchesToMeters(-9.759),
        Units.inchesToMeters(23.579)),
    new Rotation3d(
        Math.toRadians(-2.773),
        Math.toRadians(-28.248),
        Math.toRadians(19.405)))
```
