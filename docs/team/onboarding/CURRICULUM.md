# Software Onboarding Ladder — FRC 1405

Twelve rungs, from "never opened this repo" to "can read `Vision.java` and propose a
change to it." Every rung is a **real change to this codebase** (or a real replay of a
real match log), not an exercise. Every rung ends with a commit **carrying a
`Student: <Name>` line in the message** — that's non-negotiable; the commit history
(searchable by that trailer) is the student's season portfolio.

Students commit from the team's shared `Student` account, on purpose — not a placeholder
to fix later. Individual GitHub accounts were considered and rejected: these are shared
school laptops with low general tech fluency, and per-student account + git + VS Code
setup, repeated every time a student switches machines, is a real onboarding tax that
isn't worth what it buys. The `Student:` trailer plus the roster table below gets the
"my work has my name on it" effect without any of that setup cost.

Assumes: a student with "basic programming" ability (a semester of intro coding — loops,
functions, maybe classes), a laptop with WPILib VS Code installed, and this repo cloned.
No robot required until it's convenient; rungs 1–8 run entirely in simulation.

**How to use this document**

- One rung per meeting is the expected pace. Faster is fine; a student who can
  demonstrate a rung's "done" checklist may skip it.
- A "session" below ≈ 1.5–2 hours. Software students here typically show up 1-2 days a
  week during build season (a committed student ≈ 8-10 hrs/week: one weekday session
  plus one longer Saturday session) — so a rung marked "2 sessions" is roughly a week of
  calendar time, not a single evening. **Rungs 1-6 are meant to happen mostly during a
  fall on-ramp, before build season's 6-10 week crunch starts** (see
  `docs/team/GROWTH-PLAN.md`), because there usually isn't enough build-season calendar
  time alone to reach rung 12 from zero.
- Rung 1 needs no lab, no robot, and no team resources — just this repo and a laptop.
  It's the one rung that's realistic to do at home, and doing programming work outside
  of meetings isn't the norm here yet. If a student finishes rung 1 in a session and
  seems into it, explicitly tell them they can keep driving the sim at home — that
  invitation matters more than it sounds like it should.
- Each rung names the concept it teaches. When a student asks "why," the answer is in
  the named concept — teach it *then*, at the moment it's needed, not as a lecture up
  front.
- Mentor sign-off = the student walks the mentor (any mentor — see
  `docs/team/MENTOR-PLAYBOOK.md`) through the "Done when" checklist. Then they commit:
  message starts with `rung-N:`, e.g. `rung-2: log hopper roller velocity`, with a
  `Student: <Name>` trailer line in the body.
- Rungs 2–8 should be done on a branch and can be reverted after sign-off if the change
  was purely for learning — the *commit* still exists, trailer and all, either way.
  Rungs that improve the robot for real (many will) get merged.

---

## Rung 1 — Build it, drive it (no code)

**Concept: the toolchain, and the fact that the robot is drivable without a robot.**
**Time: 1 session.**

1. `./gradlew build` — watch it compile. Find the generated
   `ClimberIOInputsAutoLogged` class under `build/` and marvel that code wrote code
   (that's the `@AutoLog` annotation processor; it comes back in rung 7).
2. `./gradlew simulateJava` — the sim GUI and DriverStation open. Attach a gamepad,
   enable teleop, drive the swerve around.
3. Open AdvantageScope, connect to the simulator, drag `Drivetrain/Pose` onto the
   odometry/field view, and watch the robot you're driving move on the field.

**Done when:** the student can start the sim unaided and show the robot's pose moving in
AdvantageScope. No commit for this rung — instead, add your name to the roster table at
the bottom of this file (that's your first PR).

---

## Rung 2 — Log one new value (`@AutoLogOutput`)

**Concept: observability — if it isn't logged, it didn't happen.**
**Time: 1 session.**

Look at `src/main/java/frc/robot/subsystems/Climber.java`: fields like
`climberPositionTarget` carry `@AutoLogOutput(key = "Climber/ArmPositionTarget")`, and
methods like `isClimberAtTarget()` do too. That one annotation makes the value appear in
NetworkTables and in every `.wpilog`.

**Task:** pick any subsystem (`Hopper`, `Intake`, `Indexer`...) and log one value that
isn't logged yet but that you'd want when debugging — a target, a boolean state, a
computed error. Add the annotated field or method, run the sim, find your key in
AdvantageScope, and watch it change as you trigger the mechanism.

**Done when:** the new key is visible and moving in AdvantageScope, and the key name
follows the `Subsystem/FieldName` convention.

---

## Rung 3 — Rebind a button

**Concept: Triggers and Commands — how a driver's button press becomes robot behavior.**
**Time: 1 session.**

`src/main/java/frc/robot/RobotContainer.java` (~lines 247–360) is where every button
maps to a command: `operatorJoystick.y().onTrue(new SetHoodPosition(hood,
HoodAngles.SHORT))`, chords like `.and(driverJoystick.back())`, negations like
`.negate()`.

**Task:** in simulation, (a) move an existing binding to a different button and verify
it, then (b) add one new binding of your own choosing that runs an existing command
factory (e.g. `climber.runOpenClaw()` from `Climber.java`). Notice the commands have
`.withName(...)` — find the running command's name in the log.

**Done when:** the student can trace, out loud, the path from button press → `Trigger` →
`Command` → subsystem method → `io.` call, for their new binding.

---

## Rung 4 — Change a number that changes behavior (Constants + LerpTable)

**Concept: constants live in one place; interpolation tables shape continuous behavior.**
**Time: 1 session.**

Read `src/main/java/frc/robot/lib/LerpTable.java` — it's 43 lines and the whole thing is
understandable with intro-level math. It's used all over vision filtering and drive
scaling.

**Task:** find one `LerpTable` in use (grep for `new LerpTable`) and one plain constant
in `Constants.java` that affect something you can feel in the sim (drive scaling, a
position target). Change each, predict what will happen *before* running, then run the
sim and check the prediction. Put the values back (or keep them, if they're genuinely
better — that's a real tuning contribution).

**Done when:** the student made a written prediction, tested it, and can explain what
`lerp()` returns for an x below the first entry and above the last (clamping).

---

## Rung 5 — Write this repo's first unit test

**Concept: tests as executable proof; edge cases.**
**Time: 1–2 sessions.**

`./gradlew test` is configured (JUnit 5) but **`src/test/` doesn't exist yet — this repo
has zero tests.** The first test in the codebase gets written by a first-year student.

**Task:** create `src/test/java/frc/robot/lib/LerpTableTest.java`. Test `LerpTable`:
exact table points, a midpoint between two entries, clamping below/above the table, and
`lerpKeepSign()` with a negative input. Then look hard at the `return 0;` fall-through
at the bottom of `lerp()` — can any input actually reach it? Write down your answer.

**Done when:** `./gradlew test` runs green with ≥5 assertions, and the student can
explain why testing pure math classes like this is easy while testing `Climber` isn't
(that difference is *why* the IO pattern in rung 7 exists).

---

## Rung 6 — Add a feature switch and wire it to one `if`

**Concept: feature gating — shipping a change that's off by default.**
**Time: 1–2 sessions.**

Read `src/main/java/frc/robot/constants/FeatureSwitches.java`. Every flag is a
`public static final boolean` with a comment saying what OFF (baseline) and ON mean.
See how `INTAKE_SAFTEY_MODE_NO_DEPLOY` is consumed in `Intake.java` (~line 73) and
`PUBLISH_INDIVIDUAL_DRIVE_CURRENTS` in `CommandSwerveDrivetrain.java` (~line 477).

**Task:** invent one small optional behavior — e.g. an extra debug log, a slower "demo
mode" drive scale for outreach events, an alternate rumble cue — add a flag for it
(default `false`, comment documents both states), and wire it to a single `if`. Verify
both flag states in sim.

**Done when:** with the flag `false`, behavior is provably identical to before (that's
the point); with `true`, the new behavior appears. Bonus: explain why the vision
switches in that file defaulting to "2026 behavior" makes A/B testing possible.

---

## Rung 7 — Add one input to an IO layer (all three files)

**Concept: the IO pattern — the architectural heart of this codebase.**
**Time: 2 sessions.**

Read the trio: `ClimberIO.java` (interface + `@AutoLog` inputs class),
`ClimberIOTalonFX.java` (real hardware), `ClimberIOSim.java` (physics model), and how
`Climber.periodic()` calls `io.updateInputs(inputs)` then
`Logger.processInputs("Climber", inputs)`.

**Task:** add one new field to a subsystem's `FooIOInputs` class (e.g. motor temperature
in the TalonFX implementation — `getDeviceTemp()` — with a plausible constant or simple
model on the sim side). Populate it in **both** implementations, rebuild (the annotation
processor regenerates `FooIOInputsAutoLogged`), and find it in AdvantageScope.

**Done when:** the student can answer: "Why do reads go into `inputs` instead of the
subsystem just calling the motor directly?" (Answer involves: sim runs without hardware,
and replay — rung 9 — needs every hardware read captured in the log.)

---

## Rung 8 — Break the sim physics, then fix it

**Concept: closed-loop control (P gain), and sims as safe crash-test dummies.**
**Time: 1–2 sessions.**

`ClimberIOSim.java` has a `PIDController` with `CLIMBER_KP = 0.66`, a `DCMotorSim` with
a gearing of 10.0, and a voltage clamp of ±8V.

**Task:** run the sim, command the climber up/down (your rung-3 binding!), and plot
`Climber/ClimberIOInputs/climberClosedLoopError` in AdvantageScope. Now: set kP to 0.05
(sluggish), then to 20 (watch it ring/overshoot), then find a value you can defend.
Change the gearing and observe what that does to the same gain.

**Done when:** the student can describe, from their own plots, what "too little P" and
"too much P" each look like. This is the exact skill swerve/shooter tuning needs on the
real robot — see `2026Robot/Guides/HowToTuneASwerveDrive.md` for where it goes next.

---

## Rung 9 — Replay a real match

**Concept: deterministic replay — this team's superpower.**
**Time: 1 session.**

Read `docs/replay-workflow.md` and `2026Robot/Guides/DownloadMatchLogsForReplay.md`.
On the real robot, every match writes a `.wpilog` to `/home/lvuser/logs/`; a copy of at
least one real match log should live wherever the team keeps them (ask a mentor).

**Task:** run `./gradlew replayWatch` against a real match log. Scrub the timeline in
AdvantageScope. Find: the moment autonomous ended, the robot's path on the field, one
moment where a vision estimate was rejected. You are watching a match that already
happened, re-executed through the code on your laptop.

**Done when:** the student can explain the difference between *viewing* a log and
*replaying* one (replay re-runs the actual Java code against recorded inputs — which is
why changing the code changes the replay).

---

## Rung 10 — Change the code, replay the same match, watch history change

**Concept: the replay boundary, and scientific A/B testing against real data.**
**Time: 2 sessions.**

Read `Vision.periodic()` in `src/main/java/frc/robot/subsystems/vision/Vision.java`
(from ~line 206). The comment at ~line 221 is load-bearing: **all filter logic runs
after `Logger.processInputs()`** — raw camera inputs are recorded, filtering happens
downstream, so filters can be changed and re-run against old matches. Skim
`docs/vision-testing-protocol.md` for the methodology.

**Task:** flip one vision switch in `FeatureSwitches.java` (e.g.
`VISION_AMBIGUITY_THRESHOLD` off, since baseline-vs-on is documented in its comment) and
replay the *same* match log as rung 9. Compare accepted/rejected counts and pose
behavior between the two runs.

**Done when:** the student can state what would break if a filter ran *before*
`processInputs()` (the log would record post-filter data, and replay could no longer
test different filters). This question is the ladder's midterm exam — answering it
means they understand the architecture.

---

## Rung 11 — Extend the team's own tooling (logbench)

**Concept: reading a spec-driven system; Python; tools are code too.**
**Time: 2–3 sessions.**

`tools/logbench/` plays back a `.wpilog` in a web UI. The front end and server are
generic; everything vision-specific lives in one file:
`tools/logbench/server/specs/camera_health.py`. Read its docstring — it says exactly
this: "adding a different kind of match playback means writing a sibling of this file."

**Task (pick one, ascending difficulty):**
- (a) Add one already-logged signal as a new track in `camera_health.py`'s `build()`
  (the `find_signal` → `Track` → `data[tid]` pattern repeats a dozen times in that
  file — copy it).
- (b) Write a small sibling spec, e.g. `climber.py`: field pose plus the climber
  position/error/current signals you've been logging since rung 2, registered next to
  `camera_health`. Per the README/CLAUDE.md: no front-end changes needed.

**Done when:** the new track/spec renders in the logbench web UI against a real log.
(If `web/src` was touched — it shouldn't need to be — remember
`cd web && npm run build:single` per `CLAUDE.md`.)

---

## Rung 12 — Capstone: own a slice of the vision pipeline

**Concept: synthesis; teaching as proof of understanding.**
**Time: 2–4 sessions.**

**Task, all three parts:**
1. Read `Vision.java` end to end, plus `VisionConstants.java`. Draw the pipeline on one
   page: raw estimates → replay boundary → boundary rejection → velocity jump → trust
   scalars → `samples` queue → `RobotContainer.correctOdometry()` →
   `addVisionMeasurement()`.
2. Propose one improvement or experiment as a **new feature switch defaulting to
   `false`** (the P1/P2/P3 switches show the pattern; `VISION_TAG_RANKINGS_FILTER`'s
   `TODO do more research` is a ready-made research assignment). Measure it with the
   rung-10 replay method and the rung-11 tooling.
3. Present the pipeline to the team for 15 minutes (`docs/vision/VisionTalk.md` is the
   house style for this).

**Done when:** the presentation happens. A student who completes rung 12 is a
near-mentor: they should be signing off rungs 1–8 for next year's students.

---

## Roster

| Student (name) | Started | Current rung | Rung-12 capstone topic |
|---|---|---|---|
| _add yourself here in rung 1_ | | | |
