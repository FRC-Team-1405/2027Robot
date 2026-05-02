# Multi-Side Camera Drive Base

## Summary

Prototype a drive base with cameras on multiple sides to explore broader field coverage, better tag visibility, and improved localization options.

## Why This Project Matters

- Multi-camera layouts may improve pose updates when one camera loses targets.
- This project forces students to think about hardware, transforms, calibration, compute limits, and validation together.
- It creates a direct bridge between mechanical layout and software architecture.

## Useful References

- `C:\Users\importsjc\robotics\2026Robot\src\main\java\frc\robot\subsystems\vision\Vision.java`
- `C:\Users\importsjc\robotics\2026Robot\src\main\java\frc\robot\subsystems\vision\Camera.java`
- `C:\Users\importsjc\robotics\2026Robot\src\main\java\frc\robot\subsystems\vision\VisionConstants.java`
- `C:\Users\importsjc\robotics\2026Robot\Guides\WPICal_Calibration.md`

## Proposed Approach

1. Inventory available cameras, coprocessors, and mounts.
2. Define candidate camera layouts and what problem each layout is trying to solve.
3. Build or simulate a test chassis layout.
4. Calibrate each camera and document transforms carefully.
5. Measure tag visibility, update quality, and integration behavior under different orientations.
6. Compare benefits against added complexity and compute cost.

## Deliverables

- A documented candidate layout with rationale.
- Calibration and transform notes for each camera.
- A simple comparison of one-camera vs multi-camera behavior.
- A recommendation on whether the team should invest more in this direction.

## Competency Checklist

- Understands coordinate frames at a basic level.
- Can explain why camera transform accuracy matters.
- Can follow a calibration process carefully and record results.
- Can read the team vision architecture at a high level.
- Can compare tradeoffs instead of only chasing more hardware.

## Good Stretch Goals

- Explore 360-degree coverage strategies.
- Compare one coprocessor per camera vs shared compute.
- Propose a standard mounting and calibration checklist for future robots.
