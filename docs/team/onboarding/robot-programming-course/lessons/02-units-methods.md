# 02 · Methods and encoder units

Requires 01. Learn parameters, return values, method calls, and a consistent unit convention.

Work in small steps. For each checkpoint, copy templates/SUBMISSION.md into your named submission folder. Include a source snapshot, exact commands, evidence, and answers. Do not overwrite an earlier attempt.

## Checkpoint A — Convert motor rotations

**Learn:** A method names a reusable calculation. Parameters are its inputs; return gives its output. For this lab only: 10 motor rotations make one drum rotation and each drum rotation moves 0.20 m.

**Do:** Implement metersFromRotations(). Predict outputs for 0, 10, 25, 50, and -10 motor rotations before running checks. Explain every factor in the conversion.

**Submit:** The source, prediction table, and java RobotLab.java --test 02 output.

**Explain:** Why does multiplying by the gear ratio give the wrong result here?

## Checkpoint B — Use a method

**Learn:** Writing a method does not call it. A return value must be used by a caller to affect behavior.

**Do:** In a temporary main or jshell exercise, call the conversion for 25 rotations and print the returned value with m. In RobotLab, search for metersFromRotations and identify why implementing it does not change the plant motion yet.

**Submit:** Call site and printed output, plus the explanation. Keep unrelated temporary exercises separate.

**Explain:** Where should the conversion happen when a real encoder reports motor rotations?

## Checkpoint C — Check a new mechanism

**Learn:** A conversion depends on the mechanism, not just the sensor name. Negative position can describe direction relative to a zero.

**Do:** On paper, change the drum circumference to 0.30 m and gearing to 15:1. Find the distance for 45 motor rotations. Do not change the assessed lab constants. State where the encoder zero is assumed.

**Submit:** Worked conversion with units and a zero-reference description.

**Explain:** What physical measurement would you need before trusting this on a real robot?

## Ready to move on

You can reproduce your result from a clean start and explain it without reading a solution. Mark the submission ready-for-review. If feedback requests a change, create another attempt and describe what you learned.
