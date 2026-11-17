# 05 · Time and repeated updates

Requires 04. Learn loops, changing state, lists, and sample timing.

Work in small steps. For each checkpoint, copy templates/SUBMISSION.md into your named submission folder. Include a source snapshot, exact commands, evidence, and answers. Do not overwrite an earlier attempt.

## Checkpoint A — Count time

**Learn:** One update advances the model by DT. A fixed-step simulation may compute many seconds faster than wall-clock time.

**Do:** Read the headless for loop and Plant.step(). Compute 600*0.020. Run auto and verify the number of rows and final time. Explain why ticks is an int but time is a double.

**Submit:** Counting method, last row, and explanation of simulated versus wall-clock time.

**Explain:** Why is a fast headless run still a 12-second simulation?

## Checkpoint B — Change duration without changing physics

**Learn:** Changing the number of updates changes duration. Changing DT changes the integration and possibly the outcome.

**Do:** In a disposable copy only, change 600 headless iterations to 300. Keep DT unchanged. Predict last timestamp and number of rows, then verify. Restore the support file afterward.

**Submit:** Prediction and actual 6-second CSV. Explain the first sample at 0.02 rather than 0.

**Explain:** Why is changing DT to 0.04 a different experiment?

## Checkpoint C — Inspect a sequence

**Learn:** A list holds many samples in order. An individual sample describes a moment, not a whole run.

**Do:** Find height at 1.00 s and 2.00 s in manual output. Estimate average velocity over that interval from the two positions. Compare it with velocity_mps at 2.00 s.

**Submit:** Calculation, units, and an explanation of average versus instantaneous velocity.

**Explain:** Why might those two velocities differ?

## Ready to move on

You can reproduce your result from a clean start and explain it without reading a solution. Mark the submission ready-for-review. If feedback requests a change, create another attempt and describe what you learned.
