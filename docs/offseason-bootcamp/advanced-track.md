# Advanced Track

This track is for returning or more advanced students. The target outcome is a guided rebuild of the existing robot code architecture from scratch using the previous season's code as the reference point.

## Track Goal

Rebuild a full command-based robot project that includes drivetrain integration, subsystem patterns, logging, operator controls, and vision-related architecture.

## Reference Architecture

The rebuild should use the previous season code as a reference for overall structure:

- `src/main/java/frc/robot/Robot.java`
- `src/main/java/frc/robot/RobotContainer.java`
- `src/main/java/frc/robot/subsystems/CommandSwerveDrivetrain.java`
- `src/main/java/frc/robot/subsystems/vision/Vision.java`
- `src/main/java/frc/robot/lib/FinneyLogger.java`
- `Guides/SubsystemWritingGuide.md`

## Major Learning Objectives

- Build and organize a command-based robot project.
- Recreate subsystem structure with clear responsibilities.
- Understand how commands, controller bindings, and autonomous registration fit together.
- Add logging and debugging hooks intentionally instead of as an afterthought.
- Learn how vision and drivetrain code interact with odometry and pose estimation.
- Practice writing code that is readable, testable, and maintainable by the whole team.

## Suggested Rebuild Sequence

1. Project skeleton
   - Create the base project structure.
   - Set up `Robot`, `RobotContainer`, constants, and basic build/deploy flow.
2. Core drivetrain wiring
   - Recreate drivetrain setup and default drive behavior.
   - Understand generated CTRE swerve pieces vs team-owned code.
3. Simple subsystem rebuilds
   - Rebuild one or two easier subsystems first.
   - Apply team standards for setup, naming, constants, and logging.
4. Command and controls layer
   - Bind controller inputs.
   - Build simple commands and mode changes.
   - Trace how operator intent becomes subsystem behavior.
5. Logging and diagnostics
   - Recreate logging expectations.
   - Decide what should go to dashboard, NetworkTables, or data logs.
6. Vision and odometry integration
   - Rebuild the vision pipeline architecture.
   - Understand weighting, sample flow, and odometry correction points.
7. Autonomous and higher-level behaviors
   - Rebuild auto registration and command composition.
   - Compare path-based and code-driven approaches where useful.

## Deliverables

- A clean rebuild plan with subsystem ownership.
- A working skeleton project with shared conventions.
- Rebuilt core subsystems and controller bindings.
- Logging and debugging standards applied throughout the code.
- A short design review from students explaining how the rebuilt architecture works.

## Readiness Indicators

A student is ready for this track when they can:

- Read existing robot code and explain file responsibilities accurately.
- Create a class with fields, methods, constructor logic, and constants cleanly.
- Explain subsystem vs command responsibilities.
- Follow the team's subsystem-writing and logging patterns.
- Debug a problem by tracing data through multiple files.
- Work carefully with a larger codebase without getting lost immediately.

## Mentor Guidance

- Assign ownership by architecture area, not just by isolated task.
- Require students to explain the design before they start copying patterns.
- Use code reviews to reinforce team best practices.
- Keep the rebuild separate from the main competition robot code until the work is stable enough to merge ideas back.
