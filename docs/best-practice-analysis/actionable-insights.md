# Actionable Insights for Team 1405

This document turns the elite-team comparison into a prioritized list of adoptable improvements for Team 1405.

## Scope Rule

These recommendations are intentionally limited to practices that fit Team 1405's current philosophy. They are not proposals to replace command-based structure or rebuild the whole robot architecture.

## Highest-Priority Documentation Additions

These are the best candidates for best-practice documentation updates first.

### 1. Define logging layers explicitly

**Why this is high priority**

Team 1405 already uses SmartDashboard/NT, `.wpilog`, CTRE logging, and text-style debug logging. The missing piece is a formal standard for what belongs in each layer.

**Add to docs**

- what should be live-only telemetry
- what must persist to match logs
- what should be logged for subsystem states and command lifecycle
- what belongs in CTRE-specific logs
- when high-volume telemetry should be feature-switched

**Likely result**

Better debugging consistency without changing core architecture.

### 2. Define vision trust and rejection rules

**Why this is high priority**

Elite teams are much more explicit about when vision is trusted, when it is rejected, and how it is weighted.

**Add to docs**

- field-boundary rejection
- single-tag vs. multi-tag trust
- heading trust rules for ambiguous single-tag measurements
- velocity / motion gates if used
- post-reset suppression windows
- early-auto suppression rules if used

**Likely result**

A more disciplined odometry/vision process and less ad hoc estimator tuning.

### 3. Add a concise coding-standard reference

**Why this is high priority**

The subsystem guide is useful, but Team 1405 still lacks a short canonical standard for class shape, naming, query methods, and telemetry sections.

**Add to docs**

- expected class layout order
- method naming conventions
- state enum naming conventions
- standard query method naming (`isAtTarget`, `isFinished`, etc.)
- standard telemetry section expectations

### 4. Define motor configuration expectations more sharply

**Why this is high priority**

Elite teams consistently make motor configuration more explicit, more typed, and more physically meaningful.

**Add to docs**

- all required config categories
- use of `SensorToMechanismRatio` where applicable
- follower configuration safety rules
- current-limit expectations
- retry/error-handling expectations
- signal refresh expectations

### 5. Define what should be tested without hardware

**Why this is high priority**

Pure math, field geometry, interpolation, and vision helpers should not require robot time to validate.

**Add to docs**

- what counts as a unit-test candidate
- expectation that pure functions belong in `src/test/java`
- parameterized test examples for geometry and lookup logic

## Best Small Practices Worth Adopting

These are small-to-medium ideas with good return and low architecture risk.

| Practice | Source Teams | Why it matters | Effort |
|---|---|---|---|
| Command lifecycle logging | 1678 | Makes command behavior visible during debug | Low |
| State/coordinator enum logging every loop | 254, 6328 | Shows robot intent, not just outputs | Low |
| Shared "at target" debouncer utility | 1619 | Prevents stale completion logic bugs | Low |
| Control maps committed in repo | 2767 | Better operability and onboarding | Low |
| Editable state diagrams in repo | 2767 | Faster onboarding and debugging | Low |
| Borrowed-code attribution folder | 1619 | Preserves provenance and teaching context | Very low |
| CAN bus health monitoring | 254 | Turns bus quality into observable telemetry | Low |
| `Alert` API for runtime warnings | 2767, 6328 pattern-adjacent | Better operator/developer visibility | Low |
| Log pull script / SOP | 254 | Makes log retrieval repeatable | Low |
| JUnit tests for pure math | 2910 | Cheap regression protection | Low |
| `CommandFactory` / `TriggerFactory` split | 1114 | Keeps `RobotContainer` maintainable | Medium |
| Typed motor config objects | 1114, 694 | Cleaner, safer hardware config | Medium |
| Central hardware-map convention | 3005 | Cleaner wiring and port organization | Medium |
| Programming-bot / characterization container | 3005 | Safer drivetrain-only testing | Medium |

## Sharper Standards Team 1405 Likely Needs

These are the places where the elite-team comparison suggests Team 1405's current standard is weak or incomplete even if current code quality improved.

### Logging and Runtime Health

- command lifecycle logging
- state machine / coordinator state logging
- loop-time and runtime-health monitoring
- explicit NT vs `.wpilog` vs CTRE log boundaries

### Power and Motor Configuration

- brownout policy
- supply and stator current-limit policy
- physical-unit motor configuration expectations
- follower config safety
- CAN signal batching expectations

### Odometry and Vision

- measurement acceptance / rejection criteria
- single-tag heading trust policy
- field-boundary checks
- post-reset and early-auto suppression rules

### Structure and Maintainability

- concise coding-standard reference
- `RobotContainer` size and responsibility boundaries
- hardware-ID organization policy
- borrowed-code attribution policy

### Validation and Simulation

- unit-test policy for pure functions
- minimal simulation expectations for new subsystems
- operational debug SOP for post-match review

## Recommended Implementation Order

If this work is done incrementally, the best order is:

1. **Documentation-only changes first**
   - logging-layer standard
   - vision trust rules
   - coding-standard reference
   - motor config expectations
   - test policy
2. **Low-risk process improvements**
   - control maps
   - state diagrams
   - log retrieval SOP
   - borrowed-code attribution
3. **Low-risk code utilities**
   - command lifecycle logging
   - state enum logging
   - shared debounce helper
   - CAN bus health monitoring
4. **Medium-scope structural cleanup**
   - typed motor config objects
   - hardware-map convention
   - `CommandFactory` / `TriggerFactory`
   - practice/comp robot identity handling if needed

## Non-Goals

These are explicitly outside the current recommendation scope:

- replacing command-based with a different global architecture
- wholesale AdvantageKit migration
- a full superstructure/state-machine rewrite
- adopting elite-team patterns that only make sense with a full replay/IO-layer stack
