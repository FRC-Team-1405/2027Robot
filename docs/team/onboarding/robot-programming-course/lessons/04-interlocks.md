# 04 · Limits and disabled behavior

Requires 03. Learn &&, ||, !, direction checks, and early returns.

Work in small steps. For each checkpoint, copy templates/SUBMISSION.md into your named submission folder. Include a source snapshot, exact commands, evidence, and answers. Do not overwrite an earlier attempt.

## Checkpoint A — Make limits directional

**Learn:** At the lower software limit, downward output is blocked but upward output must remain possible. A limit is not a command to freeze all motion.

**Do:** After clamping, block negative voltage at height <=0.05 m and positive voltage at height >=1.45 m. Keep motion away from a limit available. Run --test 03 and --test 04.

**Submit:** Source and a table of both voltage signs at 0.04, 0.05, 0.70, 1.45, 1.46 m, plus check output.

**Explain:** Why would if (height <=0.05) return 0 trap the elevator?

## Checkpoint B — Disabled is not holding

**Learn:** An early return exits a method. The controller should request zero when disabled. Separately, simulated hardware also ignores voltage while disabled. Gravity still exists.

**Do:** Trace calculate(false,...). Run --headless disabled disabled.csv. Check that every requested_V and applied_V is zero while height can fall. Explain what a controller bug returning +2 while disabled would look like in those two columns.

**Submit:** Disabled evidence and separate descriptions of the controller guard and hardware interlock.

**Explain:** Why does zero motor voltage not guarantee zero velocity?

## Checkpoint C — Explain the whole decision

**Learn:** Boolean logic combines conditions; parentheses make the intended grouping readable.

**Do:** Mentor supplies a new height and request. Predict the exact return before running it. Explain whether clamping or checking direction first changes this lab result, and give a case where forgetting sign causes a bug.

**Submit:** A short decision trace and mentor gate A record.

**Explain:** What is a software limit unable to guarantee if the encoder measurement is wrong?

## Ready to move on

You can reproduce your result from a clean start and explain it without reading a solution. Mark the submission ready-for-review. If feedback requests a change, create another attempt and describe what you learned.
