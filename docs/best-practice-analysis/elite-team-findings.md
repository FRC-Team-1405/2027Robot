# Elite Team Findings

This document collects evidence-backed findings from elite Java FRC teams and translates them into Team 1405-relevant observations.

## Maintainability and Operability Findings

Source slice:

- Team 2767 - Stryke Force
- Team 1619 - Up-A-Creek Robotics
- Team 3005 - RoboChargers

## Highest-Value Low-Risk Practices

### 1. Small written coding standard for subsystem shape

- **Source:** Team 2767
- **Evidence:** `strykeforce/reefscape:src/main/java/frc/robot/standards/standards.txt`
- **Finding type:** Missing standard
- **Why it matters:** Team 1405 has subsystem guidance, but not yet a short canonical "this is the expected class shape and naming pattern" standard for all robot code.
- **Adoptability:** High
- **Likely output for Team 1405:** a short written standard covering layout order, method naming, state naming, telemetry section expectations, and common query-method naming.

### 2. Common subsystem interfaces for predictable patterns

- **Source:** Team 2767
- **Evidence:** `ClosedLoopPosSubsystem.java`, `ClosedLoopSpeedSubsystem.java`, `OpenLoopSubsystem.java`
- **Finding type:** Interesting optional idea
- **Why it matters:** Team 1405 already wants consistent subsystem structure. Small interfaces could reinforce consistency without forcing a major architecture change.
- **Adoptability:** High if kept lightweight
- **Caution:** should only be added if they reflect real repeated patterns rather than becoming ceremony.

### 3. Driver/operator reference docs committed in-repo

- **Source:** Team 2767
- **Evidence:** `docs/driver-controls.png`, `docs/operator-controls.png`
- **Finding type:** Missing standard
- **Why it matters:** This is a low-effort operational best practice that keeps controls documented near code and easier to update.
- **Adoptability:** Very high

### 4. Editable state diagrams in the repo

- **Source:** Team 2767
- **Evidence:** `docs/reefscape-states.drawio`
- **Finding type:** Missing standard
- **Why it matters:** Team 1405 has stateful behavior and growing boot camp/training goals. Editable state diagrams would help onboarding and debugging.
- **Adoptability:** Very high

### 5. WPILib `Alert` API for runtime warnings

- **Source:** Team 2767
- **Evidence:** `BattMonSubsystem.java`
- **Finding type:** Interesting optional idea
- **Why it matters:** Team 1405 already logs and publishes telemetry. Alerts would give a clearer operator/developer-facing warning layer for things like thermal, battery, or config problems.
- **Adoptability:** High

### 6. Batched Phoenix signal refresh

- **Source:** Team 1619
- **Evidence:** `GlobalStatusRefresher.java`
- **Finding type:** Interesting optional idea
- **Why it matters:** If Team 1405 is refreshing many CTRE signals independently, a batched refresh pattern could reduce CAN overhead and improve loop consistency.
- **Adoptability:** Medium to high
- **Caution:** useful only if it fits how Team 1405 currently reads Phoenix signals.

### 7. Reusable "at target" debouncer utility

- **Source:** Team 1619
- **Evidence:** `AreWeThereYetDebouncer.java`
- **Finding type:** Missing standard
- **Why it matters:** Team 1405 already uses settle counts and tolerance logic. A shared utility would turn this into an explicit team pattern and reduce subtle bugs when setpoints change.
- **Adoptability:** Very high

### 8. Explicit borrowed-code attribution

- **Source:** Team 1619
- **Evidence:** `util/FromOtherTeams/`
- **Finding type:** Missing standard
- **Why it matters:** This is a nearly free documentation improvement that helps preserve context and attribution for utilities borrowed from other teams.
- **Adoptability:** Very high

### 9. Central hardware map file

- **Source:** Team 3005
- **Evidence:** `HardwareMap.java`
- **Finding type:** Interesting optional idea
- **Why it matters:** Team 1405 currently mixes constants and subsystem-owned configuration. A clearer hardware-ID map could make wiring changes and onboarding easier without changing the larger architecture.
- **Adoptability:** High
- **Caution:** should complement subsystem constants, not create a second confusing source of truth.

### 10. Robot identity / practice-vs-comp selection

- **Source:** Team 3005
- **Evidence:** `RobotName.java`
- **Finding type:** Interesting optional idea
- **Why it matters:** If Team 1405 uses multiple robots or test chassis, this is a practical way to avoid recompiling or maintaining branches.
- **Adoptability:** Medium

### 11. Dedicated programming-bot / characterization container

- **Source:** Team 3005
- **Evidence:** `ProgrammingBot.java`
- **Finding type:** Interesting optional idea
- **Why it matters:** This supports safe SysId and drivetrain-only bring-up without the full robot stack.
- **Adoptability:** Medium
- **Caution:** only valuable if Team 1405 actually has a test chassis or repeated characterization workflow.

### 12. Reusable small utilities for noisy thresholds and live tuning

- **Source:** Teams 1619 and 3005
- **Evidence:** `ValueTrackingQueue.java`, `Hysteresis.java`, `LoggedTunableNumber.java`
- **Finding type:** Underspecified standard
- **Why it matters:** Team 1405's docs say to log and tune, but do not yet define preferred small utilities for noisy sensor logic, threshold stability, or safe tuning workflows.
- **Adoptability:** Medium

## Early Gap Assessment Against Team 1405 Baseline

These are the strongest gaps suggested by this maintainability slice alone:

1. **No concise canonical coding standard**
   - Team 1405 has good guides, but not yet a short universal standard for class shape, naming, query methods, and telemetry sections.

2. **No documented standard for state diagrams and operator references**
   - Current docs are richer on tuning than on operability artifacts like control maps and editable behavior diagrams.

3. **No shared utility standard for completion/debounce logic**
   - Team 1405 uses mechanism-specific solutions, but not yet a named cross-team pattern.

4. **No explicit policy for borrowed-code attribution**
   - This is useful for maintainability and teaching, especially for offseason training.

5. **Potentially weak standard for hardware-ID organization**
   - Team 1405 documents subsystem structure well, but hardware mapping conventions appear less explicit.

## Provisional Recommendations

These are strong candidates for the later actionable-insights document:

- Add a short Team 1405 coding-standard reference beside the subsystem guide.
- Add control-map docs to the repo.
- Add editable state diagrams for complex robot flows.
- Standardize a shared "at target" debounce helper.
- Add a policy for borrowed-code attribution.
- Decide whether Team 1405 wants a dedicated hardware-map convention.

## Pending Additional Findings

The remaining comparison slices are now merged below.

## Logging, Replay, Power, and Odometry Findings

Source slice:

- Team 254 - The Cheesy Poofs
- Team 1678 - Citrus Circuits
- Team 6328 - Mechanical Advantage

## Strongest Findings

### 1. Logging layers should be explicit, not implied

- **Sources:** Teams 254, 1678, 6328
- **Finding type:** Missing standard
- **Why it matters:** These teams make sharp decisions about live telemetry, persistent logs, replay, and vendor-specific logging. Team 1405 already uses multiple layers, but the boundaries are not yet codified clearly enough.
- **Team 1405 implication:** define what belongs in SmartDashboard/NT, `.wpilog`, CTRE logs, and human-readable debug logs.

### 2. Command lifecycle logging should be standard

- **Source:** Team 1678
- **Finding type:** Missing standard
- **Why it matters:** Knowing what commands started, ended, or were interrupted is a high-value debugging signal and does not require a large architecture change.
- **Adoptability:** Very high

### 3. State-machine / coordination state should be logged every loop

- **Sources:** Teams 254 and 6328
- **Finding type:** Missing standard
- **Why it matters:** Elite teams make robot intent visible in logs, not just motor outputs. Team 1405 should define this as a standard for any subsystem or coordinator with meaningful states.

### 4. Power-awareness should be treated as a formal software concern

- **Sources:** Teams 254, 1678, 6328
- **Finding type:** Underspecified standard
- **Why it matters:** These teams explicitly configure supply and stator limits, set brownout behavior intentionally, and log power-related signals. Team 1405 already cares about current and battery behavior, but the standard should be much more explicit.

### 5. Vision trust rules should be codified

- **Sources:** Teams 254, 1678, 6328
- **Finding type:** Missing standard
- **Why it matters:** Elite teams do not simply pass every camera estimate into the pose estimator. They define field-boundary rejection, multi-tag vs. single-tag trust, post-reset suppression, and timing/trust logic.
- **Team 1405 implication:** turn current odometry/vision instincts into explicit documented rules.

### 6. Loop timing and runtime health are first-class telemetry

- **Sources:** Teams 254, 1678, 6328
- **Finding type:** Missing standard
- **Why it matters:** These teams measure loop timing, track runtime health, and care about scheduler consistency. Team 1405 should define its expected loop timing budget and how to detect overruns.

## Highest-Value Low-Risk Ideas

### 1. Explicit brownout voltage setting

- **Source:** 1678 / repeated pattern
- **Finding type:** Interesting optional idea
- **Why it matters:** Makes power behavior intentional instead of default-driven.
- **Adoptability:** Very high

### 2. Command lifecycle logging

- **Source:** 1678
- **Finding type:** Missing standard
- **Why it matters:** Cheap visibility into command behavior during tuning and match review.
- **Adoptability:** Very high

### 3. CAN bus health monitoring

- **Source:** 254
- **Finding type:** Interesting optional idea
- **Why it matters:** Turns "maybe the bus was bad" into an observable signal.
- **Adoptability:** High

### 4. Git metadata in logs

- **Sources:** 254, 6328
- **Finding type:** Interesting optional idea
- **Why it matters:** Helps tie logs back to the exact code build.
- **Adoptability:** High

### 5. Log retrieval script or standard procedure

- **Source:** 254
- **Finding type:** Missing standard
- **Why it matters:** Team 1405 already has logging guidance, but log retrieval should become a standard competition workflow instead of a best-effort habit.
- **Adoptability:** High

### 6. Vision rejection / suppression rules

- **Sources:** 254, 1678, 6328
- **Finding type:** Missing standard
- **Why it matters:** Likely one of the biggest areas where elite teams are more explicit than Team 1405 today.
- **Adoptability:** High

## Early Gap Assessment Against Team 1405 Baseline

1. **Logging categories are not yet codified sharply enough**
2. **Command and coordinator state logging are not yet defined as universal standards**
3. **Power/current policy is present, but too informal**
4. **Vision acceptance and trust rules need a written standard**
5. **Loop-time and runtime-health monitoring need to become official expectations**

## Configuration, Architecture-Boundary, and Simulation Findings

Source slice:

- Team 2910 - Jack in the Bot
- Team 1114 - Simbotics
- Team 694 - StuyPulse

## Strongest Findings

### 1. Hardware/config data should be more strongly typed

- **Sources:** Teams 2910, 1114, 694
- **Finding type:** Underspecified standard
- **Why it matters:** These teams consistently avoid scattering raw CAN IDs, bus names, and gain values as loose primitives. Their configs bundle hardware identity and configuration more intentionally.
- **Team 1405 implication:** define a clearer standard for hardware IDs, bus names, and motor configuration objects.

### 2. `config` vs. `constants` separation is a useful clarity boundary

- **Source:** 2910
- **Finding type:** Interesting optional idea
- **Why it matters:** Separating robot-specific wiring/tuning from game-specific constants keeps intent clearer and reduces cross-contamination in large constants files.
- **Adoptability:** High

### 3. `SensorToMechanismRatio` and physical-unit motor configuration should be a standard

- **Source:** 1114
- **Finding type:** Missing standard
- **Why it matters:** This is a subtle but powerful best practice. It removes repeated unit conversion logic from command code and reduces mechanism-control mistakes.
- **Adoptability:** High

### 4. Follower configuration should reference the leader structurally

- **Source:** 1114
- **Finding type:** Missing standard
- **Why it matters:** Typed follower config reduces a real class of copy/paste or wrong-ID mistakes.
- **Adoptability:** High

### 5. `RobotContainer` should stay thin

- **Source:** 1114
- **Finding type:** Underspecified standard
- **Why it matters:** `CommandFactory` and `TriggerFactory` are strong examples of keeping orchestration separate from composition logic. This fits Team 1405's philosophy without changing command-based itself.
- **Adoptability:** High

### 6. CAN signal batching should be intentional

- **Sources:** 1114, 694, also echoed by 1619
- **Finding type:** Missing standard
- **Why it matters:** Reading Phoenix signals independently can introduce bus overhead and inconsistent timestamps. Elite teams tend to batch refreshes.
- **Adoptability:** High

### 7. Simulation and unit testing are part of the standard, not extra credit

- **Sources:** 2910, 1114, 694
- **Finding type:** Missing standard
- **Why it matters:** These teams consistently make space for sim implementations, mechanism visualizations, and tests for pure math/geometry.
- **Adoptability:** High

### 8. Multi-robot identity handling is worth planning early

- **Source:** 2910
- **Finding type:** Interesting optional idea
- **Why it matters:** Even if Team 1405 only has one active competition robot today, a clean robot-identity scaffold prevents future drift.
- **Adoptability:** Medium

## Highest-Value Low-Risk Ideas

### 1. Small typed config objects for TalonFX setup

- **Sources:** 1114, 694
- **Finding type:** Interesting optional idea
- **Why it matters:** Better repeatability and less scattered config logic.

### 2. `CommandFactory` and `TriggerFactory` split

- **Source:** 1114
- **Finding type:** Interesting optional idea
- **Why it matters:** Strong fit if Team 1405's `RobotContainer` grows unwieldy.

### 3. JUnit tests for pure geometry / math

- **Source:** 2910
- **Finding type:** Missing standard
- **Why it matters:** Very high leverage for pose math, interpolation, and field-logic helpers.

### 4. Post-scheduler periodic hook for final state updates

- **Source:** 694
- **Finding type:** Interesting optional idea
- **Why it matters:** Useful for a subset of coordination/state problems without changing overall architecture.

### 5. Smart-value change detection before reapplying config

- **Source:** 694
- **Finding type:** Interesting optional idea
- **Why it matters:** Prevents unnecessary config writes and CAN spam during live tuning.

## Early Gap Assessment Against Team 1405 Baseline

1. **No strong standard yet for typed motor/config objects**
2. **No clear standard for physical-unit motor configuration through sensor-to-mechanism mapping**
3. **No stated standard for follower config safety**
4. **No explicit unit-test policy for pure functions**
5. **No explicit standard for keeping `RobotContainer` thin as the project grows**
6. **No codified CAN signal batching rule**

## Cross-Cutting Comparison Summary

Across all three analysis slices, the biggest likely gaps are:

1. **Missing standards**
   - logging boundaries
   - vision trust/acceptance rules
   - command lifecycle logging
   - state/coordinator logging
   - shared completion/debounce utilities
   - physical-unit motor config
   - unit testing for pure math
   - CAN signal batching

2. **Underspecified standards**
   - hardware-ID organization
   - current-limit philosophy
   - runtime health/loop-time monitoring
   - `RobotContainer` growth boundaries
   - tuning/live-config utilities

3. **Interesting optional ideas**
   - hardware map file
   - robot identity / practice-vs-comp selection
   - programming-bot container
   - `Alert` API usage
   - post-scheduler update hooks
   - typed subsystem interfaces
