# From the teaching lab to a WPILib robot project
Status: integration instructions and design contract; no ready-to-deploy WPILib project is included. The mentor must prepare and verify the version-specific starter before module 10.

## Mentor preparation
1. Record the exact stable WPILib installer and JDK. This draft targets the 2026 documentation family; verify current releases. Avoid adopting 2027 alpha examples into a 2026 project.
2. In WPILib VS Code create the bundled Java ElevatorSimulation example with desktop support. Build and run it unchanged using **WPILib: Simulate Robot Code**, selecting the simulation GUI. Use the project build/Gradle tasks, not the generic Java run button.
3. Confirm the physics model, motor/encoder device simulation, and mechanism drawing work on student OSes without a robot or gamepad. Save a clean starter and reference run. Choose keyboard/dashboard controls for all required actions.
4. Prepare a small command-based Java project with the same simulated elevator. Introduce framework wiring in a guided lab rather than asking beginners to invent it.
5. Record a model card: motor type/count; gear ratio convention; carriage mass kg; drum radius m; min/max height m; gravity enabled; encoder conversion; dt; motor limit. Ensure all units and sensor zero are documented.
6. Provide one short example of a command with a subsystem requirement, a CSV/log or WPILib test fixture, and an AdvantageScope layout. Keep vendor dependencies out of the first simulator project where possible.

## Desired code layout (design, not generated files)
- `subsystems/ElevatorSubsystem.java`: owns goal/manual mode, controller policy, limits, telemetry, and input/output calls.
- `subsystems/elevator/ElevatorIO.java`: `readInputs()` returning measured position/velocity; `setVoltage(volts)`; optional `updateSimulation(dt)` on the simulated implementation only. A subsystem passes the requested voltage into the adapter. Record requested and applied output distinctly if the adapter can constrain output.
- `subsystems/elevator/ElevatorIOSim.java`: ElevatorSim and its configured motor, gearing, mass, drum radius, travel bounds and gravity. A known-good WPILib example can instead use simulated motor/encoder devices directly. Choose ONE approach for the cohort; teach the other later.
- `subsystems/elevator/ElevatorIOReal.java`: optional motor controller/encoder adapter, created only once hardware is selected.
- `commands/MoveElevator.java`: requires subsystem, requests goal, checks dwell and timeout; handles interruption.
- `RobotContainer.java`: constructs the selected adapter/subsystem and binds dashboard/keyboard/optional gamepad controls.

The API names above are course design choices, not official WPILib interfaces. Use the chosen WPILib version's actual API signatures in the prepared project. A simpler cohort may keep IO inline in the subsystem first, then extract it as a refactor.

## One 20 ms iteration
1. Read measured height and velocity from the selected input adapter (the previous model step in simulation).
2. Determine mode and requested goal. Check enable state; disabled requests zero.
3. Calculate signed feedback + gravity compensation + damping. Apply voltage clamp and directional software limits.
4. Send voltage to the adapter. Update telemetry from measured state, separately displaying the goal.
5. During simulation-only update, feed the APPLIED voltage to ElevatorSim, advance by the configured dt, and expose the resulting measurements for the next iteration. Do not advance the model both here and in another loop.

This adds the usual sample delay relative to the simple lab's CSV convention. Explain it when comparing traces. Do not set model height equal to requested height. Do not implement separate real/sim control logic. Disabled physics still advances with zero applied motor voltage; it may fall unless a modeled brake or mechanical restraint holds it.

## Required subsystem behavior
- SI units at the control boundary; names include units.
- `setGoalMeters` accepts finite values and clamps them to software travel; rejects NaN/infinity and logs the reason.
- Manual and automatic modes are explicit. Disable overrides both.
- The same limits apply to manual and automatic requests.
- A controller recalculates every framework cycle without a blocking sleep or while-loop.
- The dashboard mechanism uses measured state, with a separately labeled goal.
- Tests call controller and limit logic directly so model hard stops cannot hide mistakes.

## Command behavior
- Declare the elevator requirement.
- initialize: set goal, clear dwell/timeout state.
- execute: no blocking; the subsystem handles repeated control.
- finish: continuous 0.20 s dwell within position/speed tolerance OR configured timeout.
- end: log whether completed/interrupted/timed out; preserve an enabled hold at an appropriate goal or capture measured position on interruption, per the agreed policy. Disabled still requests zero. Treat timeout as a fault outcome, not successful arrival.
- Test two conflicting commands and manual takeover. Define whether new commands interrupt or are rejected, then verify the selected behavior.

## Done when
The prepared project builds with the pinned toolchain, runs without robot hardware, meets ACCEPTANCE.md (or its prior agreed model adaptation), produces a reopenable WPILib log, and passes the module 11 command transition tests. A mentor verifies the starter before assigning this bridge. The package does not claim this integration has already been built or tested.
