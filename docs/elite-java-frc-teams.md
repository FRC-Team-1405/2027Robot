# Elite FRC Teams with Public Java Robot Code

This document is a study list of elite FRC teams that:

- are **top 400 or better globally in 2026**
- use **Java**
- have a **public robot-code repository**
- use a **2026 repo when available**, otherwise a **2025 repo**

## Methodology

- **Ranking source:** 2026 global rank from the Statbotics team-year API.
- **Cutoff:** included only if the 2026 global rank is **400 or better**.
- **Repo requirement:** public GitHub robot-code repo from **2026**, or **2025** if no 2026 public repo was found.
- **Language requirement:** repo had to be clearly Java-based from its repo structure, README, or `src/main/java` layout.
- **Philosophy / reputation notes:** based on public repo structure, README notes, public libraries, and public documentation. When a point is synthesis rather than an explicit claim from the team, it is phrased as an observation.

## Quick Reference

| Team | 2026 Global Rank | Public Java Repo | Known For | Distinct Philosophy / Pattern |
|---|---:|---|---|---|
| [254 - The Cheesy Poofs](#254---the-cheesy-poofs) | 3 | [FRC-2025-Public](https://github.com/Team254/FRC-2025-Public) | polished controls, auto, simulation, visualization | heavy superstructure/state-machine coordination with modal controls |
| [2910 - Jack in the Bot](#2910---jack-in-the-bot) | 6 | [2025CompetitionRobot-Public](https://github.com/FRCTeam2910/2025CompetitionRobot-Public) | advanced architecture, strong automation, testing | explicit move away from standard command-based toward custom state-machine architecture |
| [1114 - Simbotics](#1114---simbotics) | 10 | [2025-Simbot-CMD-Public](https://github.com/Simbotics/2025-Simbot-CMD-Public) | polished command-based patterns, reusable abstractions | command-factory and trigger-factory driven structure |
| [1678 - Citrus Circuits](#1678---citrus-circuits) | 11 | [C2025-Public](https://github.com/frc1678/C2025-Public) | auto-scoring integration, vision usage, operator UX | aggressive automation with single-controller philosophy and IO abstraction |
| [694 - StuyPulse](#694---stuypulse) | 41 | [Tribecbot](https://github.com/StuyPulse/Tribecbot) | clean utilities, modern Java stack, public team library | custom `StuyLib` ecosystem and strong multi-camera integration |
| [6328 - Mechanical Advantage](#6328---mechanical-advantage) | 79 | [RobotCode2026Public](https://github.com/Mechanical-Advantage/RobotCode2026Public) | logging, replay, IO abstraction, open-source tooling | deterministic logging and hardware-abstraction patterns centered on AdvantageKit |
| [2767 - Stryke Force](#2767---stryke-force) | 125 | [reefscape](https://github.com/strykeforce/reefscape) | drivetrain software, reusable swerve tooling | library-first approach through `thirdcoast` |
| [1619 - Up-A-Creek Robotics](#1619---up-a-creek-robotics) | 220 | [2025_Daedalus](https://github.com/Team1619/2025_Daedalus) | robust, repeatable code and practical documentation | simplicity and repeatability over novelty |
| [3005 - RoboChargers](#3005---robochargers) | 370 | [Reefscape-2025](https://github.com/FRC3005/Reefscape-2025) | clean hardware mapping and programming-bot support | clear separation of hardware IDs and dedicated test/programming robot patterns |

## Team Notes

### 254 - The Cheesy Poofs

- **2026 rank source:** [Statbotics team-year API](https://api.statbotics.io/v3/team_year/254/2026)
- **Public repo:** [Team254/FRC-2025-Public](https://github.com/Team254/FRC-2025-Public)
- **Why study them**
  - Very polished full-robot integration.
  - Strong autonomous and alignment infrastructure.
  - Public code shows mature simulation, visualization, and state tracking.
- **Observed software patterns**
  - Modal control system with a central superstructure state machine.
  - Strong separation between team library code and robot-specific code.
  - Heavy use of logging and 3D visualization workflows.
- **Evidence links**
  - [Repo README](https://github.com/Team254/FRC-2025-Public)
  - [Pathfinding / auto-related codebase entry point](https://github.com/Team254/FRC-2025-Public)

### 2910 - Jack in the Bot

- **2026 rank source:** [Statbotics team-year API](https://api.statbotics.io/v3/team_year/2910/2026)
- **Public repo:** [FRCTeam2910/2025CompetitionRobot-Public](https://github.com/FRCTeam2910/2025CompetitionRobot-Public)
- **Why study them**
  - Widely respected for clean architecture and high-end autonomous behavior.
  - Public repo shows serious attention to configuration, testing, and vision relocalization.
- **Observed software patterns**
  - Explicitly uses a custom finite-state-machine architecture instead of standard WPILib command-based as the main organizing idea.
  - Central `Superstructure` ownership for multi-mechanism coordination.
  - Config system designed so the same code can run across multiple robots for testing.
- **Evidence links**
  - [Repo README](https://github.com/FRCTeam2910/2025CompetitionRobot-Public)
  - [MIT-licensed public repo root](https://github.com/FRCTeam2910/2025CompetitionRobot-Public)

### 1114 - Simbotics

- **2026 rank source:** [Statbotics team-year API](https://api.statbotics.io/v3/team_year/1114/2026)
- **Public repo:** [Simbotics/2025-Simbot-CMD-Public](https://github.com/Simbotics/2025-Simbot-CMD-Public)
- **Why study them**
  - The repo is explicitly framed as a proof-of-concept for best practices in command-based architecture.
  - Strong example of turning command-based into a more disciplined system instead of a pile of one-off commands.
- **Observed software patterns**
  - Command factory for higher-level actions.
  - Trigger factory for centralized bindings and orchestration.
  - `RobotState` used as a coordination layer instead of only relying on direct command chaining.
  - IO abstraction split between real hardware and sim implementations.
- **Evidence links**
  - [Repo README](https://github.com/Simbotics/2025-Simbot-CMD-Public)
  - [Public repo root](https://github.com/Simbotics/2025-Simbot-CMD-Public)

### 1678 - Citrus Circuits

- **2026 rank source:** [Statbotics team-year API](https://api.statbotics.io/v3/team_year/1678/2026)
- **Public repo:** [frc1678/C2025-Public](https://github.com/frc1678/C2025-Public)
- **Why study them**
  - Strong end-to-end automation and operator workflow design.
  - Good example of software supporting a highly optimized driver experience.
- **Observed software patterns**
  - Single-controller philosophy for primary operation, with secondary controls treated more as override/debug.
  - Heavy automation around scoring flow.
  - IO abstraction and subsystem organization consistent with modern logging/replay-friendly architecture.
  - Dual-camera vision strategy with different roles for different pipelines.
- **Evidence links**
  - [Repo README](https://github.com/frc1678/C2025-Public)
  - [Public repo root](https://github.com/frc1678/C2025-Public)

### 694 - StuyPulse

- **2026 rank source:** [Statbotics team-year API](https://api.statbotics.io/v3/team_year/694/2026)
- **Public repo:** [StuyPulse/Tribecbot](https://github.com/StuyPulse/Tribecbot)
- **Repo year:** 2026
- **Why study them**
  - One of the few confirmed elite teams with a public 2026 Java robot repo already available.
  - Strong public utility-library culture through `StuyLib`.
- **Observed software patterns**
  - Custom shared-library approach instead of keeping all abstractions inside the season repo.
  - Multi-camera vision stack visible in the public robot description.
  - Good team to study if you want a modern Java codebase that is current-season public.
- **Evidence links**
  - [Repo root](https://github.com/StuyPulse/Tribecbot)
  - [StuyLib](https://github.com/StuyPulse/StuyLib)

### 6328 - Mechanical Advantage

- **2026 rank source:** [Statbotics team-year API](https://api.statbotics.io/v3/team_year/6328/2026)
- **Public repo:** [Mechanical-Advantage/RobotCode2026Public](https://github.com/Mechanical-Advantage/RobotCode2026Public)
- **Repo year:** 2026
- **Why study them**
  - Major open-source influence on the FRC software ecosystem.
  - Team behind AdvantageKit and closely associated with AdvantageScope workflows.
  - Very strong reference team for logging, replay, and abstraction strategy.
- **Observed software patterns**
  - Deterministic logging and replay as a first-class design requirement.
  - Hardware-agnostic IO interfaces with separate real/sim implementations.
  - Public mirror of the season code updated from an internal development repo.
- **Evidence links**
  - [RobotCode2026Public](https://github.com/Mechanical-Advantage/RobotCode2026Public)
  - [AdvantageKit](https://github.com/Mechanical-Advantage/AdvantageKit)
  - [AdvantageScope](https://github.com/Mechanical-Advantage/AdvantageScope)

### 2767 - Stryke Force

- **2026 rank source:** [Statbotics team-year API](https://api.statbotics.io/v3/team_year/2767/2026)
- **Public repo:** [strykeforce/reefscape](https://github.com/strykeforce/reefscape)
- **Why study them**
  - Strong team to study for drivetrain infrastructure and reusable library design.
  - Public ecosystem includes their long-running `thirdcoast` swerve library.
- **Observed software patterns**
  - Library-first mindset: reusable drivetrain software lives outside the season repo.
  - Good fit if you want examples of long-term software reuse rather than only year-to-year code.
- **Evidence links**
  - [reefscape repo](https://github.com/strykeforce/reefscape)
  - [thirdcoast swerve library](https://github.com/strykeforce/thirdcoast)

### 1619 - Up-A-Creek Robotics

- **2026 rank source:** [Statbotics team-year API](https://api.statbotics.io/v3/team_year/1619/2026)
- **Public repo:** [Team1619/2025_Daedalus](https://github.com/Team1619/2025_Daedalus)
- **Why study them**
  - Useful counterexample to teams that chase complexity for its own sake.
  - Public notes emphasize robust, repeatable code rather than flashy architecture.
- **Observed software patterns**
  - Simplicity and reliability are treated as core design goals.
  - Good study target for practical code organization and maintainability.
- **Evidence links**
  - [Repo README](https://github.com/Team1619/2025_Daedalus)
  - [Public repo root](https://github.com/Team1619/2025_Daedalus)

### 3005 - RoboChargers

- **2026 rank source:** [Statbotics team-year API](https://api.statbotics.io/v3/team_year/3005/2026)
- **Public repo:** [FRC3005/Reefscape-2025](https://github.com/FRC3005/Reefscape-2025)
- **Why study them**
  - Worth reading for their project organization choices more than for a headline-grabbing philosophy.
  - Public repo includes patterns that are useful for student onboarding and hardware clarity.
- **Observed software patterns**
  - `HardwareMap` pattern for centralized hardware IDs and mappings.
  - `ProgrammingBot` pattern for a dedicated programming/test robot target.
  - Practical separation of hardware concerns from command/subsystem logic.
- **Evidence links**
  - [Repo root](https://github.com/FRC3005/Reefscape-2025)
  - [Java source tree entry point](https://github.com/FRC3005/Reefscape-2025/tree/main/src/main/java/frc/robot)

## Patterns That Show Up Repeatedly

### 1. Centralized superstructure coordination

Teams like 254, 2910, 1114, and 1678 all show some version of a central coordination layer instead of letting subsystems free-float independently.

### 2. Logging and replay are now architecture decisions, not add-ons

6328 is the clearest example, but 254, 1678, and 1114 also reflect the shift toward logging-friendly IO abstractions and replay/debug workflows.

### 3. Elite teams often split reusable infrastructure away from season code

6328 has AdvantageKit, 2767 has `thirdcoast`, and 694 has `StuyLib`. That is a different mindset from building everything directly inside one robot repo every year.

### 4. There is no single elite-team philosophy

- Some teams lean hard into custom state machines: 2910, 254.
- Some try to systematize command-based instead of discarding it: 1114.
- Some optimize for operator simplicity and highly assisted workflows: 1678.
- Some emphasize reliability and repeatability over complexity: 1619.

## Strong Teams I Did Not Put In The Main List

These teams look relevant, but I did **not** include them in the main list because the 2026 top-400 evidence was incomplete during research:

- [4481 - Team Rembrandts](https://github.com/FRC-4481-Team-Rembrandts/2025-robot-public) - excellent public repo, but I did not get a clean 2026 Statbotics confirmation during this pass
- [5940 - BREAD](https://github.com/BREAD5940/2025-Public) - strong public Java repo and strong 2025 standing, but incomplete 2026 ranking evidence during this pass
- [3476 - Code Orange](https://github.com/FRC3476/FRC-2025) - very interesting public Java repo and notable state-machine philosophy, but ranking verification was not reliable enough during this pass

## Practical Use

If you want this list for mentoring or curriculum planning, the most useful study order is:

1. **6328** for logging, replay, and IO abstraction
2. **254** and **2910** for full-system architecture and state coordination
3. **1678** for operator workflow and automation philosophy
4. **1114** for a disciplined command-based approach
5. **694** and **2767** for modern Java/library patterns
6. **1619** and **3005** for practical maintainability patterns students can realistically adopt
