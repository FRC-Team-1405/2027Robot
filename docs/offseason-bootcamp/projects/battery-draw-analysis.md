# Battery Draw Analysis

## Summary

Study match logs to understand current spikes, brownouts, battery sag, and how drivetrain behavior or mechanism usage contributes to power issues.

## Why This Project Matters

- It can explain why the robot feels inconsistent across a match.
- It can guide current limits, drive tuning, and driver feedback.
- It can reveal whether logging coverage is good enough for deeper diagnosis.

## Useful References

- `C:\Users\importsjc\robotics\2026Robot\docs\BatteryStatus.md`
- `C:\Users\importsjc\robotics\2026Robot\Guides\DownloadMatchLogsForReplay.md`
- `C:\Users\importsjc\robotics\2026Robot\src\main\java\frc\robot\Robot.java`
- `C:\Users\importsjc\robotics\2026Robot\src\main\java\frc\robot\subsystems\CommandSwerveDrivetrain.java`

## Proposed Approach

1. Gather logs from a representative set of matches and practices.
2. Identify the key signals to track, such as battery voltage, drive current, subsystem current, and robot acceleration.
3. Mark notable events like brownouts, heavy pushing, fast acceleration, collisions, or major mechanism movement.
4. Compare current draw to robot actions and driver behavior.
5. Summarize patterns and propose changes to logging, current limiting, or drive tuning.

## Deliverables

- A small report showing the major battery draw patterns found.
- At least one graph or dashboard view that demonstrates a useful trend.
- A recommendation list for logging additions or control changes.

## Competency Checklist

- Can open and inspect robot logs without help.
- Understands basic electrical concepts such as voltage sag and current spikes.
- Can read drivetrain and subsystem-related code well enough to locate where values come from.
- Can explain the difference between observation, hypothesis, and recommendation.
- Can document findings clearly.

## Good Stretch Goals

- Create a repeatable process for comparing one match to another.
- Correlate acceleration estimates with current draw.
- Propose driver-visible alerts or post-match review metrics.
