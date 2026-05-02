# Team 1405 Intended Software Standard

This document describes Team 1405's intended software practices **as they should work when done well**. It is meant to capture the team's current philosophy and preferred patterns without being distorted by implementation mistakes in the current robot code.

## Philosophy

- Build on command-based Java robot code instead of replacing the project with a completely different architecture.
- Prefer practical, readable, team-maintainable code over cleverness.
- Use reusable patterns and shared conventions so students can work in the same style across subsystems.
- Favor incremental improvements, strong debugging support, and operational reliability.
- Treat software as part of the whole robot system, not as an isolated code exercise.

## Core Architecture

- `Robot.java` owns startup, logging startup, mode transitions, and robot-wide periodic scheduling.
- `RobotContainer.java` owns controller bindings, subsystem construction, high-level command wiring, auto registration, and odometry correction flow.
- `subsystems/` contains mechanism-specific behavior and hardware interaction.
- `commands/` contains higher-level actions and motion/control behaviors.
- `lib/` contains shared utilities, logging helpers, auto registration helpers, field abstractions, and reusable support code.
- `constants/` and `Constants.java` hold configuration and tuning values instead of scattering numbers through subsystem logic.

## Subsystem Standard

The intended subsystem pattern is defined primarily by `Guides/SubsystemWritingGuide.md` and reinforced by current subsystem implementations such as `Intake.java`.

### Each subsystem should:

- own its hardware directly instead of hiding basic control flow in many layers
- have a clear `setupMotors()` or equivalent configuration path
- apply all critical motor configuration in one place
- use constants for gains, current limits, positions, and thresholds
- expose clear state query methods
- publish useful telemetry for debugging
- support simulation when practical
- use protection features appropriate to the mechanism

### Motor configuration should cover:

- PID and feedforward gains
- Motion Magic or motion-profile settings where applicable
- current limits
- neutral mode
- inversion
- soft limits or other travel protection when applicable
- bus optimization or update-rate tuning where useful

### Safety and protection expectations

- protect mechanisms with soft limits, current limits, stall detection, or disable flags when appropriate
- avoid silent unsafe behavior
- surface configuration failures explicitly
- use feature switches only for intentional behavior gates, not to hide unknown issues

## Logging and Telemetry Standard

Team 1405 already uses multiple telemetry layers. The intended standard should define what each layer is for.

### Layer 1: dashboard / live NT telemetry

Use SmartDashboard or NetworkTables for:

- live status values needed during tuning
- operator-visible mechanism state
- per-match debugging values
- values worth graphing live during testing

This data should be selectively published and feature-switched when high volume is not needed all the time.

### Layer 2: structured debug logging

`FinneyLogger` is intended for human-readable subsystem-specific debug information.

Use it for:

- state transitions
- important command entry/exit notes
- warnings that help explain subsystem behavior
- occasional diagnostic text that does not need to be logged every loop

### Layer 3: file-based match logging

`Robot.java` and the `.wpilog` guide show that persistent logs are expected to be part of the official workflow.

Use `.wpilog` logging for:

- post-match replay
- debugging time-based sequences
- validating command behavior
- correlating robot state with match events

### Layer 4: CTRE / drivetrain-specific logs

`Telemetry.java` and CTRE `SignalLogger` show that low-level drivetrain and controller telemetry is also part of the intended toolkit.

Use CTRE logging for:

- module state and target review
- closed-loop drive behavior
- drivetrain-specific debug sessions
- tuning work where vendor tooling is useful

### Intended logging rule

The team should explicitly define **what belongs in SmartDashboard / NT, what belongs in `.wpilog`, and what belongs in CTRE logs** so logging choices are intentional instead of ad hoc.

## Power, Current, and Battery Standard

The team's current docs and code show that power-awareness is already part of the philosophy, even if it is not yet fully centralized.

### Intended practices

- configure current limits explicitly rather than relying on defaults
- measure and monitor subsystem and drivetrain current during testing
- use battery and brownout behavior as a real debugging signal
- treat power draw as part of drivetrain tuning and match reliability, not just an electrical issue
- keep battery status and battery-health observations documented

### Expected workflow

- collect drive current and mechanism current during testing
- review `.wpilog` and CTRE logs after suspicious behavior or brownouts
- connect current draw to robot actions, not just raw numbers
- use competition and practice evidence to refine limits and tuning

## Odometry and Vision Standard

Team 1405's intended approach is to use drivetrain odometry plus vision corrections with explicit trust management, not blind acceptance of vision data.

### Intended practices

- validate mechanical and kinematic constants before debugging odometry quality
- measure and verify wheel radius, gear ratio, and module geometry
- control when vision odometry updates are allowed
- weight vision measurements based on confidence and robot motion
- publish enough pose and module telemetry to debug drift and estimator behavior
- treat frame-of-reference correctness as a first-class concern

### Practical expectations

- odometry should be validated against measured distances and rotations
- vision should be reviewed for timing, weighting, and trust assumptions
- drift should be investigated systematically instead of patched with arbitrary constants

## Tuning and Validation Standard

The tuning guides imply a strong intended standard even when the standard is not yet centralized into one document.

### Intended practices

- verify hardware and constants before tuning control loops
- tune steer behavior before drive behavior when working on swerve
- use measured feedforward values instead of guessing
- run SysId when appropriate
- validate on carpet and at realistic robot weight
- compare tuning results across multiple test conditions instead of trusting one good run

## Simulation Standard

Simulation is part of the intended workflow, not just an extra.

### Intended practices

- include simulation support for subsystems when feasible
- use simulation to validate control flow and approximate mechanism behavior
- keep simulation useful for student learning and early debugging
- avoid making simulation-only assumptions that diverge too far from real hardware behavior

## Documentation Standard

Team 1405 already has multiple valuable guides. The missing piece is a more canonical standard that ties them together.

### Intended practices

- document procedures that are easy to forget during pressure
- keep tuning and debugging guides close to the relevant code patterns
- write guides that explain both the "what" and the "why"
- record operational procedures for log retrieval, deployment, and setup
- update best-practice docs when lessons are learned, not just when code changes

## Where the Standard Is Currently Defined

This intended standard is currently inferred from:

- `README.md`
- `Guides/SubsystemWritingGuide.md`
- `Guides/WpilogDebuggingGuide.md`
- `Guides/HowToTuneASwerveDrive.md`
- `Guides/AutoPilotDriveGainsTuning.md`
- `Robot.java`
- `Telemetry.java`
- subsystem examples such as `Intake.java`
- drivetrain code in `CommandSwerveDrivetrain.java`

## What This Document Is For

This is the baseline for later comparison work. The question is not "where is Team 1405 failing today?" The question is:

> If Team 1405 executed this philosophy cleanly and consistently, what would still be missing compared to elite teams?
