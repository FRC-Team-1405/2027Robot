# Instructor guide
## First decisions for a pilot
Defaults in this draft: FRC Java; high-school beginners; one elevator; Markdown lessons; private named submission folders; mastery gates; no required robot or gamepad. Adjust reading level and pace after observing a beginner complete module 00.

Before distribution:
- Remove instructor/ from the student copy. Keep your reference solution privately.
- Verify the Java GUI on each student OS. Headless scenarios are already useful, but students need an accessible way to graph CSV if they cannot run desktop graphics.
- Select exact tool versions in COHORT-SETUP.md. Download installers ahead of time if students lack reliable internet. Confirm student install permissions.
- Build and verify the separate WPILib starter described in wpilib/BRIDGE.md. This is the main unfinished implementation needed before teaching modules 10–12.
- Pilot 00–04 with two students. Track time, confusing instructions, installation blockers, and revisions per checkpoint. Revise those lessons before expanding.

## Acceptance and conversations
Use templates/SUBMISSION.md. Accept only when behavior, reasoning, evidence, and explanation are demonstrated. A passing test with an incorrect explanation needs a conversation and revision. Ask students to trace a new input, make a small change, and explain the effect. Do not equate typing speed with understanding.

Gate A prompts: What happens at the bottom for each output sign? Does disabled mean stationary? Show a conversion with a new number.
Gate B prompts: Why is error signed? Which signal would expose a stuck sensor? What wrong code does your test catch? Why does mass/gravity invalidate old tuning assumptions?
Gate C prompts: Who owns output? What happens on interruption? Where does simulated position come from? Reopen a log and locate a target transition.

## Scope and remaining work
Included: 14 modules / 42 checkpoint briefs, runnable teaching simulator with student edit area and incremental checks, mentor reference controller, submission/review templates, resource list, acceptance contract, WPILib bridge instructions, and optional hardware lab.

Not included: an LMS, automated submission server, a prebuilt WPILib project, vendor-specific deploy code, cross-platform GUI validation, or a finished 2027 migration. These are deliberate follow-on tasks. The student must complete the WPILib bridge or an equivalent validated project to meet the final subsystem outcome; the early Java simulator alone is not the whole course.

## Suggested rollout
Week 1: 00–02. Week 2: 03–04 + gate A. Week 3: 05–06. Week 4: 07–08. Week 5: 09 + gate B. Weeks 6–7: 10–12 + gate C. Week 8: 13. This is a planning example for multiple short work periods each week, not a validated schedule.

Reference solution: instructor/reference/RobotLab.java. It is intentionally separate from student/lab/RobotLab.java. Treat numerical reference performance as evidence about the teaching model, not hardware readiness.
