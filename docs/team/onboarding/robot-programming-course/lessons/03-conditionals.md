# 03 · Limit a motor request

Requires 02. Learn if statements, comparisons, boundaries, and tests.

Work in small steps. For each checkpoint, copy templates/SUBMISSION.md into your named submission folder. Include a source snapshot, exact commands, evidence, and answers. Do not overwrite an earlier attempt.

## Checkpoint A — Clamp voltage

**Learn:** A clamp keeps a number in an allowed interval. It must preserve requests already inside that interval.

**Do:** In limitVoltage(), clamp requests to -6..+6 V. Use if statements or Math.min/Math.max; explain their order. Run --test 03.

**Submit:** Source, check output, and a prediction table for -9, -6, -2, 0, 2, 6, 9 at height 0.7 m.

**Explain:** Why must -2 stay -2 rather than become +2?

## Checkpoint B — Test the boundary

**Learn:** A boundary test checks just below, exactly on, and just above a threshold. Typical middle values miss many bugs.

**Do:** Add your own direct examples at -6.01, -6, -5.99, 5.99, 6, 6.01. Show expected and actual returns in a small Java test or temporary lab test case.

**Submit:** Your additional test source and results.

**Explain:** Which test detects using 6 for every positive request?

## Checkpoint C — Separate policy from hardware

**Learn:** The teaching motor can apply up to 12 V; your policy allows only 6 V. A physical motor controller and your software can each impose different limits.

**Do:** In a disposable copy, change the clamp to 8 V and show a 9 V direct request returning 8. Restore 6 V and show it returns 6. Explain why merely seeing the elevator stop at its hard stop is insufficient.

**Submit:** Failing policy example, restored passing example, and reasoning.

**Explain:** What is the difference between requested_V and applied_V?

## Ready to move on

You can reproduce your result from a clean start and explain it without reading a solution. Mark the submission ready-for-review. If feedback requests a change, create another attempt and describe what you learned.
