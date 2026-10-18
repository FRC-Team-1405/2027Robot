# Course design and mastery gates
## What completion means
A student can read and modify short Java methods; track numeric units and signs; separate input, control, and output; describe a repeating control loop; write boundary tests; build a subsystem and command in WPILib; run it against a physics model; explain a graph; and provide reproducible evidence. They can explain an unfamiliar change rather than only reproduce a known solution.

## Small steps, real artifacts
Each module has three checkpoints. Give one checkpoint at a time if a student is overwhelmed. Keep the support code visible but mark it mentor-owned until it becomes relevant. Never require a beginner to understand Swing or the entire robot framework to change a controller method.

Use a five-minute demonstration and then independent work. Give hints in this order: ask for a prediction; point to a measurement; identify the relevant method; offer a partial example. Ask the student to explain any borrowed or AI-assisted code and make a small new change without being given its answer. Documentation use is welcome and must be attributed in the submission.

## Review gates
| Gate | After | Student demonstration |
|---|---|---|
| A | 04 | Predict signs and limits; explain disabled vs holding; change one boundary live |
| B | 09 | Read a graph; trace a function call; isolate a bug; justify a test |
| C | 12 | Explain sensor → controller → output → physics → sensor; cancel a command |
| Completion | 13 | Independent change, repeatable acceptance evidence, short oral explanation |

Do not require a meeting after every tiny checkpoint. A mentor can acknowledge routine artifacts asynchronously; use the gates for 5–10 minute conversations. Students may continue reading while waiting, but complete requested gate revisions before starting work that depends on the missing concept.

## Feedback and resubmission
Use statuses `draft`, `ready-for-review`, `changes-requested`, `reviewed`. Only the mentor sets `reviewed`; it means accepted for this checkpoint, not merely opened. Store attempts as separate directories so the original evidence stays intact. A reviewed checkpoint remains accepted while later lessons change the working source. Keep immutable source snapshots per submission.

Use a learner ID or name agreed with the team. Avoid placing student-identifying submissions in a public repository. A shared private folder works; Git is optional until students understand files and revisions. For a larger cohort, private student repositories or assignments can use the same structure.

## Assessment
For every checkpoint, mark each relevant dimension `not yet` or `demonstrated`: behavior, Java reasoning, evidence/reproducibility, explanation. Acceptance requires all applicable dimensions, not an average score. Cosmetic polish does not compensate for missing understanding. Give one concrete next action in feedback.

## Simulation and hardware
Core assessment is identical for students with and without robot access. Use model changes and injected faults to provide additional feedback without hardware. A robot adds unmodeled friction, load, sensor offsets, latency, backlash, and wiring errors. The optional hardware lab compares those differences; it does not replace simulation evidence.

## Tools and version policy
Use one mentor-approved stable WPILib release per cohort; record exact installer, Java version, OS, dashboard version, and vendor dependencies. The initial recommendation is the stable 2026 release family, subject to mentor verification at course setup. Do not mix 2026 snippets with 2027 alpha APIs. Official 2027 prerelease notes describe package/API changes. The independent lab uses Java 17 language features and standard desktop APIs; the final robot project must use the JDK shipped with its selected WPILib release.

Before teaching: verify installation on each supported OS, prepare a known-good WPILib ElevatorSimulation example, save a dashboard layout and baseline log, and test a student account without robot access. The included Java lab has command-line verification; GUI and WPILib classroom pilots are still required.
