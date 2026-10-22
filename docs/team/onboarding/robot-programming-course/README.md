# Programming Robots in Java
## A simulation-first course for new programmers — draft 0.1

Start with no programming experience. Finish with a Java elevator subsystem that can be controlled, simulated, measured, tested, and explained. A physical robot is optional and earns no extra core credit.

**Suggested audience:** high-school beginners comfortable with arithmetic and negative numbers. **Planning estimate:** 24–36 hours, including revision and mentor conversations. Checkpoints usually take 15–30 minutes; installation and the WPILib bridge take longer. Pilot these estimates with two students before scheduling a cohort.

**First subsystem:** a one-stage elevator. One dimension makes cause and effect visible. Position, direction, units, limits, feedback, and command ownership transfer to arms, intakes, and other mechanisms. An arm or flywheel is an extension after the core course.

## Start here
1. Mentor: read `instructor/START-HERE.md`, then choose and record the cohort tool versions.
2. Student: open `lessons/00-first-run.md`. You need a Windows, macOS, or Linux computer with a full Java JDK (17 or newer for the teaching lab), a text editor, and permission to run desktop software. A phone alone is not the supported programming environment.
3. Early lessons use `student/lab/RobotLab.java`. It includes a visible elevator, a target/position graph, deterministic scenarios, CSV output, and lesson checks. No accounts, robot, gamepad, Python, or third-party Java dependencies are needed for this lab.
4. Lessons 10–12 move into a mentor-prepared WPILib project with its own physics model and dashboard. This package includes a bridge lab and acceptance contract, **not a prebuilt or verified WPILib project**.
5. Submit each checkpoint with source, evidence, and an explanation using `templates/SUBMISSION.md`.

## Course map
| Module | Java / robot idea | Observable result | Submission |
|---|---|---|---|
| 00 | Edit, save, run; errors | A repeatable 12-second run | Environment record + baseline |
| 01 | Variables, types, expressions | Different manual voltage changes motion | Prediction vs measurements |
| 02 | Methods, arguments, units | Encoder rotations convert to meters | Passing conversion checks + examples |
| 03 | Comparisons and conditionals | Voltage is limited to ±6 V | Boundary table + test output |
| 04 | Boolean logic and interlocks | Limits block outward motion; disabled requests zero | Direction table + disabled evidence |
| 05 | Loops, time, collections | 600 samples represent 12 simulated seconds | Timing experiment + CSV |
| 06 | Classes, state, interfaces | Two controllers keep independent settings | Refactor + instance test |
| 07 | Error and proportional feedback | Elevator moves toward a target | P-only graph + error explanation |
| 08 | Gravity and damping | Three targets settle with little overshoot | Measured tuning comparison |
| 09 | Testing and fault diagnosis | A deliberate bug is detected and fixed | Failing case → fix → passing case |
| 10 | WPILib subsystem + physics | Same control policy drives ElevatorSim | Diagram + source + sim evidence |
| 11 | Commands and interruption | Conflicting commands cannot own the elevator together | Scheduler trace + cancellation test |
| 12 | Dashboard, logs, integration | Results can be replayed and independently checked | Dashboard + timed acceptance table |
| 13 | Independent capstone | Another person reproduces a working subsystem | Complete submission + explanation |
| Optional | Real motor/sensor adapter | The same goals work on approved hardware | Sim/real comparison |

## How a checkpoint works
**Predict → make one change → run → measure → explain → submit → revise.** Do not submit only a screenshot. A submission must let a mentor rerun the code and check your reasoning. Passing checks support the review; they do not prove understanding.

Read `COURSE-DESIGN.md` for pacing, review gates, and design choices. Read `RESOURCES.md` for selected official documentation. Markdown is the source format so lessons remain easy to edit and review; PDFs can be exported later after the pilot.

## Package boundaries
The teaching simulator is a deliberately simplified Java model, not WPILib, a calibrated digital twin, or deployable robot software. Its physical hard stops can hide broken software limits; the direct output checks catch that distinction. The final WPILib/robot stage needs a separate project and mechanism-specific configuration. Do not deploy `RobotLab.java` to a robot.

**Instructor material:** remove `instructor/` from the student distribution. It contains solutions and review prompts. The example submission under `submissions/example-student/` is marked fictional.
