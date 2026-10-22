# 12 · A dashboard that proves behavior

Requires 11. Learn telemetry, logs, replay, and an honest visualization.

Work in small steps. For each checkpoint, copy templates/SUBMISSION.md into your named submission folder. Include a source snapshot, exact commands, evidence, and answers. Do not overwrite an earlier attempt.

## Checkpoint A — Publish the right signals

**Learn:** Useful telemetry shows intent and measurements separately. Log enough to explain a run after the live simulator closes.

**Do:** Publish/log target meters, measured meters, measured m/s, position error, requested/applied volts where available, mode, enabled, atGoal, and command state. Draw the elevator from measured height using Mechanism2d. Display target separately.

**Submit:** Dashboard layout, logging setup, and a log with all named signals.

**Explain:** Which signal helps distinguish a bad target from a broken sensor?

## Checkpoint B — Replay independently

**Learn:** A reviewer must be able to reopen evidence without the student recreating a live session.

**Do:** Open a saved WPILib log in AdvantageScope. Graph target and measured height on one axis with units and velocity/output in separate plots. Include a mechanism view. If a signal is missing, rerun and explain the evidence gap.

**Submit:** Log, dashboard/layout instructions, screenshot, and exact reproduction steps.

**Explain:** Why is an attractive animation insufficient evidence that feedback works?

## Checkpoint C — Run the full contract

**Learn:** A repeatable scenario controls the inputs so that comparisons are meaningful.

**Do:** Run the nominal schedule, both software limits, disable while moving, conflicting commands, and an unreachable/blocked goal that times out. Use ACCEPTANCE.md. Have a partner or mentor reproduce one run from your instructions.

**Submit:** Completed acceptance table, independently reproduced result, and gate C record.

**Explain:** Which result would change first if a sensor sign were reversed?

## Ready to move on

You can reproduce your result from a clean start and explain it without reading a solution. Mark the submission ready-for-review. If feedback requests a change, create another attempt and describe what you learned.
