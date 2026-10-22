# Reference controller and review anchors
The separate reference RobotLab.java implements the intended completed lab controller. Source-launch it from its directory or provide its full path. It does not implement the module 06 interface refactor, student fault experiments, WPILib subsystem, or commands. Those are student integration exercises.

Expected ideas:
- Conversion: motor rotations / 10 * 0.20 m; 45 turns at 15:1 and 0.30 m circumference gives 0.90 m.
- Clamp preserves sign and interior values; both ends need boundary checks.
- Lower limit blocks negative requests only; upper limit blocks positive requests only.
- Disabled controller returns zero; the separate simulated hardware interlock also applies zero. Gravity can move a disabled mechanism.
- P-only equilibrium error in the interior is approximately 0.5/kP meters for the nominal model. This does not guarantee a segment reaches equilibrium.
- Nominal gravity hold is +0.5 V. Damping term is negative for upward velocity and positive for downward velocity.
- Reference gains kP=8, kD=3, kG=0.5 meet the nominal sampled acceptance in the verified headless model. See VALIDATION.md for measured values.
- Module 06 calculate and atGoal must become public when implementing its interface; tests can still construct the concrete controller.
- New model gravity term 1.6 with old kG=0.5 leaves a mismatch of 0.6 acceleration units. Interior equilibrium error with kP=8 is about 0.0375 m. That deliberately exceeds nominal 0.03 m tolerance.

For a student who passes tests by hardcoding test cases, ask for a new interior value, a random boundary case, and an explanation. Require general behavior, not only known outputs. For a student who finishes quickly, assign a new model and a justified acceptance contract rather than more repetitive worksheets.
