# Orange Pi Compute Analysis

## Summary

Measure CPU and GPU usage under different camera counts and workloads so the team can decide how much vision processing the current coprocessor setup can support.

## Why This Project Matters

- Vision quality depends on more than code; compute saturation can quietly hurt timing and pose quality.
- Students learn to connect software design decisions to system limits.
- This project informs whether more cameras or heavier pipelines are practical.

## Useful References

- `C:\Users\importsjc\robotics\2026Robot\src\main\java\frc\robot\subsystems\vision\Vision.java`
- Existing Orange Pi hardware inventory from the offseason planning notes

## Proposed Approach

1. Define the test matrix, such as camera count, resolution, frame rate, and pipeline mode.
2. Decide what metrics matter, including CPU, GPU, memory, thermals, and effective update rate.
3. Run controlled tests with one camera, then multiple cameras.
4. Record when timing or reliability starts to degrade.
5. Summarize the practical operating envelope for the current hardware.

## Deliverables

- A test matrix and recorded results.
- A summary of safe and unsafe operating ranges.
- A recommendation for camera count and workload limits.

## Competency Checklist

- Understands what resource saturation means at a basic level.
- Can run controlled tests and keep variables consistent.
- Can collect metrics carefully and compare runs fairly.
- Can explain how compute limits affect higher-level robot behavior.
- Can present a recommendation grounded in data.

## Good Stretch Goals

- Compare one shared processor against one processor per camera.
- Add timing observations for end-to-end vision latency.
- Recommend a standard benchmark the team can rerun each season.
