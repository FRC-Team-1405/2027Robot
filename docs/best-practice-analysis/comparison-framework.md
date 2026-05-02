# Comparison Framework

This framework is for comparing Team 1405 against elite Java FRC teams without drifting into architecture envy or rewrite-driven thinking.

## Comparison Rule

Only count a finding as a meaningful gap if it is one of these:

1. Team 1405 does not document the practice clearly enough
2. Team 1405 documents it, but the standard is too weak or too shallow
3. Elite teams use a practical idea Team 1405 has not considered
4. Elite teams define a decision boundary that Team 1405 currently leaves implicit

Do **not** count something as a gap just because another team uses a larger or more complex framework.

## Main Categories

## 1. Motor configuration and mechanism setup

Look for:

- how configuration is centralized
- what settings are always applied
- retry/error handling for vendor configuration
- current-limit philosophy
- soft limits and mechanism protection
- hardware abstraction around setup

Questions:

- What does Team 1405 already define well?
- What configuration steps are left implicit?
- What repeatability safeguards do elite teams add?

## 2. Logging, telemetry, and replay

Look for:

- separation between live telemetry and persistent logs
- conventions for what gets logged and why
- replay workflows
- debugging aids tied to subsystems or commands
- operator-facing vs developer-facing telemetry

Questions:

- Does Team 1405 define logging layers clearly enough?
- What logging standards do elite teams make explicit that Team 1405 currently leaves informal?

## 3. Battery, current draw, and power-awareness

Look for:

- brownout prevention habits
- current-limit tuning
- power-related telemetry
- how teams debug current spikes or voltage sag
- whether power is treated as part of drive/mechanism tuning

Questions:

- Does Team 1405 define a standard process for battery/current review?
- Are there power-related best practices the team should formalize?

## 4. Odometry, vision, and measurement trust

Look for:

- how teams validate geometry/constants
- when teams trust or distrust vision
- how they handle measurement weighting
- frame-of-reference discipline
- logging used for localization debugging

Questions:

- What assumptions does Team 1405 currently leave undocumented?
- What validation habits do elite teams apply more rigorously?

## 5. Subsystem boundaries and coordination

Look for:

- how teams coordinate multi-mechanism actions
- where they centralize state
- how they avoid cross-subsystem spaghetti
- what is adaptable without changing Team 1405's philosophy

Questions:

- Is Team 1405 missing a documentation standard for coordination boundaries?
- Are there small coordination practices worth adopting without changing architecture?

## 6. Testing, simulation, and validation

Look for:

- simulation expectations
- unit/integration testing where present
- bring-up checklists
- validation steps before tuning or deployment

Questions:

- Which validation habits should become explicit Team 1405 standards?
- What do elite teams verify before tuning that Team 1405 should write down?

## 7. Constants, configuration, and hardware mapping

Look for:

- separation of robot-specific constants from logic
- support for multiple robots or test robots
- configuration repeatability
- hardware mapping conventions

Questions:

- Where does Team 1405 need sharper standards for constants and mappings?
- Which patterns improve clarity without adding a lot of architecture overhead?

## 8. Documentation and operations

Look for:

- deployment procedures
- log retrieval procedures
- calibration instructions
- operator-facing references
- how teams preserve lessons across seasons

Questions:

- Which procedures should Team 1405 treat as official best practices?
- What is currently spread across too many docs?

## Output Format for Findings

Every finding should be labeled as one of:

- **Missing standard** - Team 1405 does not clearly define this today
- **Underspecified standard** - Team 1405 has the idea, but not a strong enough definition
- **Interesting optional idea** - useful, but not required
- **Not compatible without a rewrite** - intellectually interesting, but outside the intended scope

Each finding should also include:

- source team
- evidence link
- why it matters
- likely effort to adopt
- whether it is documentation-only, process-only, or code-impacting

## Success Criteria

This project succeeds if it produces:

- a better documented Team 1405 intended standard
- a short list of missing or weakly defined best practices
- a prioritized set of adoptable ideas
- no pressure to replace the team's whole architecture just because elite teams differ
