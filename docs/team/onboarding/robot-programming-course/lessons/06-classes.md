# 06 · A subsystem has state and a boundary

Requires 05. Learn instances, fields, constructors, encapsulation, and an interface.

Work in small steps. For each checkpoint, copy templates/SUBMISSION.md into your named submission folder. Include a source snapshot, exact commands, evidence, and answers. Do not overwrite an earlier attempt.

## Checkpoint A — Separate two instances

**Learn:** A class is a definition; an object is one instance. Instance fields belong to that object. static fields would be shared.

**Do:** Create two StudentController instances in a disposable test method. Set kP to 2 on one and 7 on the other, then print both. Do not add static to kP. Explain which object the lab uses.

**Submit:** Test source and two independent values.

**Explain:** What would go wrong if every subsystem shared one static target?

## Checkpoint B — Name a contract

**Learn:** An interface specifies methods a caller can use without knowing the implementation. Keep the contract small.

**Do:** Add a ControlPolicy interface declaring calculate(...) and atGoal(...) with their existing arguments and return types. Make StudentController implement it; both implementing methods must be public. Type the lab controller field as ControlPolicy. Run a headless scenario. Keep tests that construct StudentController directly working.

**Submit:** Refactored source and unchanged scenario result. If stuck, complete the interface as a separate small exercise before refactoring the lab.

**Explain:** Why does an interface not need to contain the simulated plant?

## Checkpoint C — Draw the boundary

**Learn:** Sensors report state, control code chooses a voltage, and an output adapter applies it. Real and simulated output adapters should not choose different control algorithms.

**Do:** Draw or describe the boundary between StudentController, Plant, and GUI. Mark which part must be replaced for WPILib physics, and which policy should remain the same.

**Submit:** One diagram or paragraph with method names and data directions.

**Explain:** Why should clicking a GUI button not directly write simulated height?

## Ready to move on

You can reproduce your result from a clean start and explain it without reading a solution. Mark the submission ready-for-review. If feedback requests a change, create another attempt and describe what you learned.
