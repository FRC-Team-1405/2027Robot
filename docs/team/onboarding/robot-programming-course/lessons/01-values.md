# 01 · Values that make a robot move

Requires 00. Learn double, boolean, assignment, arithmetic, and meaningful variable names.

Work in small steps. For each checkpoint, copy templates/SUBMISSION.md into your named submission folder. Include a source snapshot, exact commands, evidence, and answers. Do not overwrite an earlier attempt.

## Checkpoint A — Read values and units

**Learn:** A double stores a number with a fractional part. A boolean is true or false. Variable names should explain meaning and units; Java does not check meters against volts for you.

**Do:** Find manualVolts, targetMeters, heightMeters, and enabled in calculate(). Write their types and units. Calculate the GUI slider value needed for +1.5 V. Predict whether +1.5 V and +3 V initially accelerate upward at the same rate.

**Submit:** A type/unit table and prediction using a = 2*V - 1 - 3*v at v=0.

**Explain:** Why is double heightMeters clearer than double x?

## Checkpoint B — Change an expression

**Learn:** Assignment replaces a value. Multiplication scales it; it does not remember earlier commands.

**Do:** Change double requested = manualVolts; to double requested = manualVolts * 0.5;. Run the manual headless scenario. Compare its first second with the baseline. Revert after saving the evidence.

**Submit:** Before/after source snapshots and CSVs; quote height at 1.00 s for each.

**Explain:** Why does multiplying by 0.5 change negative requests too?

## Checkpoint C — Trace by hand

**Learn:** An expression is evaluated from its inputs. A hand trace can expose mistakes before a simulator runs.

**Do:** Make a table for manualVolts -4, 0, 2, 5 using the half-power expression. Use decimal division to compute 3.0/2.0; compare with Java integer expression 3/2 using a tiny separate main or jshell.

**Submit:** The hand table and observed division results.

**Explain:** Why could integer division corrupt a unit conversion?

## Ready to move on

You can reproduce your result from a clean start and explain it without reading a solution. Mark the submission ready-for-review. If feedback requests a change, create another attempt and describe what you learned.
