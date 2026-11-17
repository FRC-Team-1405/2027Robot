# 09 · Tests that reveal mistakes

Requires 08. Learn hypotheses, regression checks, and fault injection.

Work in small steps. For each checkpoint, copy templates/SUBMISSION.md into your named submission folder. Include a source snapshot, exact commands, evidence, and answers. Do not overwrite an earlier attempt.

## Checkpoint A — Create a failing case

**Learn:** A useful test would fail for a plausible bug. Tests copied from an implementation without an independent expected result can repeat its mistake.

**Do:** Choose one bug in a copy: reversed error sign, absolute error driving output, missing lower-limit direction check, or wrong encoder ratio. Write or identify a check with a hand-calculated answer. Demonstrate failure.

**Submit:** Bugged source snapshot, failing output, and reason the case detects the bug.

**Explain:** What realistic wrong implementation would pass your current test?

## Checkpoint B — Repair and rerun

**Learn:** A fix should address the cause. Regression checks show earlier requirements still hold.

**Do:** Restore correct behavior. Run 02,03,04,07,08 checks and the nominal scenario. Attach outputs. Explain why the hardware disable interlock can mask a controller disable bug in applied_V.

**Submit:** Repaired source, complete check output, acceptance rerun, and root-cause explanation.

**Explain:** Why is changing the expected answer until the test passes not a fix?

## Checkpoint C — Find the simulator limitation

**Learn:** A model can reproduce its assumptions perfectly and still misrepresent a robot. Stress experiments make those assumptions visible.

**Do:** In a disposable copy change the gravity coefficient in Plant.step from 1.0 to 1.6. Keep gains unchanged. Predict and measure the steady error. Restore the nominal model. Describe friction or sensor faults this lab does not model.

**Submit:** Perturbed CSV, prediction vs result, restored-source confirmation, and gate B conversation.

**Explain:** What evidence would you need before trusting these gains on hardware?

## Ready to move on

You can reproduce your result from a clean start and explain it without reading a solution. Mark the submission ready-for-review. If feedback requests a change, create another attempt and describe what you learned.
