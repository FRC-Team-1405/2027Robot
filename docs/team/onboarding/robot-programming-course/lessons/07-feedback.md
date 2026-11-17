# 07 · Move to a target with feedback

Requires 06. Learn signed error, proportional gain, tolerance, and changing inputs.

Work in small steps. For each checkpoint, copy templates/SUBMISSION.md into your named submission folder. Include a source snapshot, exact commands, evidence, and answers. Do not overwrite an earlier attempt.

## Checkpoint A — Calculate signed error

**Learn:** Position error is target minus measured height. A positive error requests upward motion when positive voltage moves upward.

**Do:** In automatic mode only, set requested = kP*(targetMeters-heightMeters). Set kP to 4 initially. Implement atGoal() using absolute position error <=0.03 m AND absolute speed <=0.05 m/s. Run --test 07 and earlier checks.

**Submit:** Source, checks, and hand calculations for target 0.8 / measured 0.3 and target 0.3 / measured 0.8.

**Explain:** Why does Math.abs(error) belong in a tolerance check but not in the signed motor command?

## Checkpoint B — Observe proportional control

**Learn:** Higher gain changes response; it does not fix every physical effect. Gravity can cause a P-only steady error.

**Do:** Run auto with kP=2 and kP=8, kD=kG=0. Save separate CSVs. Graph target and height. Measure error near the end of the first four-second segment.

**Submit:** Two graphs or a comparison table backed by CSVs, and a prediction of the effect of gain.

**Explain:** Why can the mechanism stop below the requested height with P-only control?

## Checkpoint C — Avoid false completion

**Learn:** Being near the target at high speed is not the same as being settled. State can change on the next update.

**Do:** Check atGoal for exact target with speed 0.2, error 0.02 with speed 0.02, and error -0.20 with speed 0. Record expected results first.

**Submit:** Three cases and explanation. Do not claim the P-only controller meets the final tuning goal yet.

**Explain:** Why should a command not finish just because the elevator crosses the target?

## Ready to move on

You can reproduce your result from a clean start and explain it without reading a solution. Mark the submission ready-for-review. If feedback requests a change, create another attempt and describe what you learned.
