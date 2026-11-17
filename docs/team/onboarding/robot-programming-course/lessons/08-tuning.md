# 08 · Hold against gravity and reduce overshoot

Requires 07. Learn simple feedforward, measured-velocity damping, controlled experiments, and acceptance criteria.

Work in small steps. For each checkpoint, copy templates/SUBMISSION.md into your named submission folder. Include a source snapshot, exact commands, evidence, and answers. Do not overwrite an earlier attempt.

## Checkpoint A — Add terms with a purpose

**Learn:** For this teaching model, +0.5 V balances gravity at rest. kG is a feedforward term. Subtracting kD*velocity opposes motion. This is measured-velocity damping; a full PID derivation is not required.

**Do:** In automatic mode use kP*error + kG - kD*velocity. Keep manual unchanged and apply limits last. Start with kP=8, kD=3, kG=0.5. Run --test 08 and the earlier tests.

**Submit:** Source, checks, and units for all three terms.

**Explain:** What sign should the damping term have while moving downward?

## Checkpoint B — Tune one thing at a time

**Learn:** A fair comparison holds initial state, target schedule, timestep, and model constant. Save each run separately.

**Do:** Run auto with (kP,kD,kG)=(8,0,0.5), then (8,3,0.5). Compare overshoot, settling time, and final error at each target. Define your measurement method before choosing a winner.

**Submit:** Two CSVs, a target/height graph, and a numeric tuning table.

**Explain:** Can a controller with less overshoot still be worse for a task? Give an example.

## Checkpoint C — Meet a measurable contract

**Learn:** Settling means remaining within position and velocity tolerances, not briefly entering them.

**Do:** Use wpilib/ACCEPTANCE.md for the nominal three-step scenario. Measure each segment. Required: settle within 2.0 s of each target change, stay within 0.03 m and 0.05 m/s afterward, overshoot <=0.08 m, and all requests <=6 V in magnitude. Explain sampled-data limits.

**Submit:** Acceptance table with measurement procedure and CSV. Ask for mentor help if the reference starting gains fail; do not silently loosen limits.

**Explain:** Why does a graph without labeled units fail to establish this result?

## Ready to move on

You can reproduce your result from a clean start and explain it without reading a solution. Mark the submission ready-for-review. If feedback requests a change, create another attempt and describe what you learned.
