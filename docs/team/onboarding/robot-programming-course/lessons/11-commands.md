# 11 · Commands, ownership, and interruption

Requires 10. Learn scheduler lifecycle and exclusive subsystem requirements.

Work in small steps. For each checkpoint, copy templates/SUBMISSION.md into your named submission folder. Include a source snapshot, exact commands, evidence, and answers. Do not overwrite an earlier attempt.

## Checkpoint A — Request a goal

**Learn:** A command expresses an action and declares the subsystem it needs. The subsystem owns repeated control and output calculation.

**Do:** Implement a move-to-height command requiring the elevator. Initialize sets a clamped goal. isFinished checks a 0.20 s continuous dwell within tolerance and low speed. Add a bounded timeout so a fault cannot wait forever.

**Submit:** Command source and trace of initialize, running, and normal finish.

**Explain:** Why must one loop inside a command never block waiting for the elevator?

## Checkpoint B — Interrupt predictably

**Learn:** A second command requiring the same subsystem is scheduled according to interruption behavior. Specify the policy instead of relying on accidental writes.

**Do:** Choose the normal policy where the incoming command replaces the active one. Schedule two conflicting height commands. Log cancellation and the new goal. Explicitly define end behavior: on interruption capture current height as a hold goal while enabled; on disable request zero.

**Submit:** Source and ordered event log showing one owner at a time.

**Explain:** Why does zero voltage on interruption differ from holding the current height?

## Checkpoint C — Test mode transitions

**Learn:** An enabled hold command may use nonzero gravity compensation. Disabled must override every mode. Limits and timeout still apply.

**Do:** Test normal completion, manual takeover, cancellation, timeout, and disable during movement. Confirm zero requested output while disabled and no hidden auto command fighting manual control.

**Submit:** Five-row behavior table and evidence; record gate C preparation.

**Explain:** What should happen if a move command times out because a sensor stops changing?

## Ready to move on

You can reproduce your result from a clean start and explain it without reading a solution. Mark the submission ready-for-review. If feedback requests a change, create another attempt and describe what you learned.
