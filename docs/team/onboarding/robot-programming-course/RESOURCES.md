# Selected resources
Checked 2026-10-18. Prefer official documentation and select a small reading for the current task. Students do not need to read entire manuals before coding. The stable/latest links move over time; record a cohort version and verify pages against it.

| Resource | Use in this course | Student task |
|---|---|---|
| [Dev.java: Learn Java](https://dev.java/learn/) | Optional targeted support in 01–06 | Look up one language feature and apply it to a new robot example |
| [Dev.java: Classes and Objects](https://dev.java/learn/language/oop/classes-objects/) | Objects, methods, fields; module 06 | Explain independent controller instances |
| [WPILib installation guide](https://docs.wpilib.org/en/stable/docs/zero-to-robot/step-2/wpilib-setup.html) | Mentor setup and module 10 | Record exact installed toolchain |
| [Create a robot program](https://docs.wpilib.org/en/stable/docs/software/vscode-overview/creating-robot-program.html) | Framework project creation | Identify repeated versus initialization callbacks |
| [Simulation introduction](https://docs.wpilib.org/en/stable/docs/software/wpilib-tools/robot-simulation/introduction.html) | Desktop support and local simulation | Run without robot hardware |
| [Simulation GUI](https://docs.wpilib.org/en/stable/docs/software/wpilib-tools/robot-simulation/simulation-gui.html) | Correct VS Code launch workflow | Launch using Simulate Robot Code |
| [Physics simulation](https://docs.wpilib.org/en/stable/docs/software/wpilib-tools/robot-simulation/physics-sim.html) | ElevatorSim and feedback/model loop | Trace output to simulated measurement |
| [Mechanism2d](https://docs.wpilib.org/en/stable/docs/software/dashboards/glass/mech2d-widget.html) | Measured-state mechanism drawing; bundled elevator/arm examples | Show actual position separately from target |
| [Device simulation](https://docs.wpilib.org/en/stable/docs/software/wpilib-tools/robot-simulation/device-sim.html) | Optional simulated encoder path | Explain why real-device code must not call simulation-only mutation methods |
| [Command-based project structure](https://docs.wpilib.org/en/stable/docs/software/commandbased/structuring-command-based-project.html) | Module 11 architecture | Identify mechanism ownership |
| [Commands](https://docs.wpilib.org/en/stable/docs/software/commandbased/commands.html) | Command lifecycle | Explain initialize, finish, interruption |
| [WPILib unit testing](https://docs.wpilib.org/en/stable/docs/software/wpilib-tools/robot-simulation/unit-testing.html) | Framework-backed tests after pure Java checks | Test a subsystem boundary |
| [AdvantageScope welcome](https://docs.advantagescope.org/) | Log review and visualization | Reopen and inspect a saved run |
| [AdvantageScope mechanism tab](https://docs.advantagescope.org/tab-reference/mechanism/) | Module 12 | View a measured mechanism in a saved run |
| [AdvantageScope line graphs](https://docs.advantagescope.org/tab-reference/line-graph/) | Module 12 | Compare target, position, speed, and output |
| [WPILib latest yearly changes](https://docs.wpilib.org/en/latest/docs/yearly-overview/yearly-changelog.html) | Mentor-only future migration check | Check 2027 changes before updating cohort tools |

## What to use first
The best technical starting point for the final project is WPILib's bundled ElevatorSimulation example: physics and mechanism visualization already exist there. Let students learn the control policy in a small file first, then replace the teaching model with that established simulator. Add command scheduling and telemetry only after motion and units make sense.

## What to defer
Swerve, path planning, vision pose estimation, full PID tuning, and vendor configuration introduce many interacting ideas. They work better as later electives. Suggested next projects: arm with angle limits and gravity compensation; intake with a beam-break sensor and jam timeout; flywheel with speed feedback and a ready-to-shoot condition. Each needs its own model and measurable acceptance contract.
