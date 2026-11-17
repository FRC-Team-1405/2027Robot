# 10 · Build the WPILib elevator

Requires gate B. This is a longer integration lab; use wpilib/BRIDGE.md. Mentor preparation is required.

Work in small steps. For each checkpoint, copy templates/SUBMISSION.md into your named submission folder. Include a source snapshot, exact commands, evidence, and answers. Do not overwrite an earlier attempt.

## Checkpoint A — Run a known-good example

**Learn:** A robot framework calls your code repeatedly. Simulation code computes sensor feedback from the motor output rather than setting position to the target.

**Do:** Mentor provides the pinned stable WPILib ElevatorSimulation example. Run Simulate Robot Code with desktop support enabled. Show the mechanism moving from model/sensor state. Record project and tool versions.

**Submit:** Unmodified example source/commit, launch steps, screenshot or dashboard recording, and a short log.

**Explain:** Why is drawing the requested target as the actual elevator position misleading?

## Checkpoint B — Implement one subsystem

**Learn:** A subsystem owns mechanism behavior and outputs. A small input/output boundary allows the same control policy to work against a simulated or real mechanism.

**Do:** Follow BRIDGE.md to add a subsystem, measured height/speed, clamped setGoalMeters(), manual mode, and disabled behavior. Port your controller policy; do not port the simplified Plant. Replace its physics with ElevatorSim and simulated sensor feedback.

**Submit:** Source, data-flow diagram, controller unit tests, and a simulation run.

**Explain:** Where does a simulated encoder value come from each cycle?

## Checkpoint C — Measure rather than reuse gains

**Learn:** Different models require different tuning. The early-lab gains are teaching values, not robot constants.

**Do:** With mentor help record the ElevatorSim motor count/model, gearing, mass, drum radius, bounds, and timestep. Tune using the same method as module 08. Use the same target schedule and acceptance process; state any new contract agreed before tuning.

**Submit:** Model card, simulation output, measured acceptance table, and rationale for differences.

**Explain:** Why can identical Java control code behave differently after replacing the model?

## Ready to move on

You can reproduce your result from a clean start and explain it without reading a solution. Mark the submission ready-for-review. If feedback requests a change, create another attempt and describe what you learned.
