# Proposed Best-Practice Additions for Team 1405

This document is a draft of the specific standards that should likely be added to Team 1405's official best-practice documentation based on the elite-team comparison.

## 1. Logging Standard Additions

### Logging layers

Team 1405 should define four logging layers explicitly:

1. **Live dashboard / NT telemetry**
   - tuning values
   - operator-visible state
   - values worth graphing live
2. **Structured debug logging**
   - state transitions
   - warnings
   - command-level debug notes
3. **Persistent match logging**
   - command lifecycle
   - subsystem/coordinator state
   - values needed for post-match analysis
4. **Vendor-specific logs**
   - drivetrain/controller diagnostics
   - module telemetry
   - low-level tuning sessions

### Required logging additions

- command start / finish / interrupt logging
- subsystem or superstructure state logging each loop
- loop cycle time monitoring
- explicit rules for high-volume telemetry feature switches

## 2. Vision and Odometry Standard Additions

### Vision acceptance policy

Every vision pipeline should define:

- field-boundary rejection
- single-tag vs. multi-tag acceptance rules
- heading trust rules for ambiguous single-tag observations
- max distance or low-quality rejection rules if used
- post-reset suppression window
- early-auto suppression window if needed

### Odometry validation policy

- validate wheel radius, gear ratio, and module geometry before tuning estimator behavior
- test straight-line and rotational odometry against measured distances
- document what evidence is needed before changing weighting constants

## 3. Motor Configuration Standard Additions

### Every motor config should define

- control gains
- feedforward gains where applicable
- current limits
- neutral mode
- inversion
- soft limits or travel protection where applicable
- signal update strategy / batching expectations

### Mechanism control expectations

- use physical-unit configuration (`SensorToMechanismRatio`) where applicable so command code operates in real units
- follower motors should reference their leader config structurally instead of by duplicated magic IDs
- configuration retry/error handling should be standardized

## 4. Runtime Health and Power Standard Additions

- define brownout voltage intentionally
- define supply and stator current-limit expectations
- document what current signals must be reviewed during testing
- define when CAN bus health should be checked and how it should be surfaced
- define loop-time budget and what counts as an overrun

## 5. Code Structure Standard Additions

### Concise coding standard

Add a short companion standard beside the subsystem guide that defines:

- expected class layout order
- method naming conventions
- state enum naming conventions
- query method naming conventions
- telemetry section expectations

### `RobotContainer` boundary

Define that:

- `RobotContainer` wires triggers and subsystems together
- complex command composition belongs in helper/factory code
- non-trivial trigger conditions should be named and extracted

## 6. Testing and Simulation Standard Additions

- any pure math / geometry / interpolation helper should be considered for JUnit tests
- each new major subsystem should have at least a minimal simulation strategy when practical
- characterization and test-only workflows should be documented clearly

## 7. Documentation and Operations Additions

- commit control maps into the repo
- keep editable state diagrams in the repo for complex flows
- define a log retrieval SOP
- define a post-match debug SOP
- define a borrowed-code attribution policy for utilities or patterns imported from other teams

## Suggested Destination Docs

These additions likely belong in:

- `Guides/SubsystemWritingGuide.md`
- a new concise coding-standard guide
- drivetrain / tuning guides
- logging / debug SOP docs
- operator/control reference docs
