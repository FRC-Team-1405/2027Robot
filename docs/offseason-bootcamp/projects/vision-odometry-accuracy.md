# Vision Odometry Accuracy

## Summary

Improve confidence in robot pose estimation by studying calibration quality, update timing, measurement weighting, and the relationship between vision and drivetrain odometry.

## Why This Project Matters

- Good localization affects auto accuracy, driver-assist features, and debugging.
- This project helps students understand how separate subsystems combine into one estimate.
- It exposes where measurements are trustworthy and where they are not.

## Useful References

- `C:\Users\importsjc\robotics\2026Robot\src\main\java\frc\robot\RobotContainer.java`
- `C:\Users\importsjc\robotics\2026Robot\src\main\java\frc\robot\subsystems\vision\Vision.java`
- `C:\Users\importsjc\robotics\2026Robot\Guides\WPICal_Calibration.md`
- `C:\Users\importsjc\robotics\2026Robot\docs\SimulationTroubleshooting.md`

## Proposed Approach

1. Define what "accurate enough" means for this team.
2. Review the current flow of vision samples into odometry correction.
3. Validate calibration quality and camera transforms.
4. Measure single-tag vs multi-tag behavior and moving vs stationary behavior.
5. Review timing, sample delay, weighting, and update frequency assumptions.
6. Produce a recommendation for code changes, calibration changes, or testing changes.

## Deliverables

- A written explanation of the current vision-to-odometry flow.
- A test plan for measuring localization quality.
- A summary of the biggest contributors to inaccuracy.
- A prioritized recommendation list.

## Competency Checklist

- Can trace data across multiple files without losing the overall flow.
- Understands poses, timestamps, and why delayed measurements matter.
- Can follow a test plan and record consistent measurements.
- Can distinguish between calibration errors, timing errors, and logic errors.
- Can write a short technical conclusion that others can act on.

## Good Stretch Goals

- Build a repeatable accuracy test routine.
- Compare stationary and dynamic weighting strategies.
- Create a field-side checklist for validating vision before matches.
