# Repo layout, and where things moved (2026-11-17)

Branch `feature/repo-organization`. The goal: few files at the root, one place for docs, dated folders that read as simple dates, and
nothing in git that is only there by accident.

## Layout now

| | |
|---|---|
| Root | Only what a tool requires: `build.gradle`, `settings.gradle`, `gradlew*`, `gradle/`, `vendordeps/`, `src/`, `.wpilib/`, `.vscode/`, `.gitignore`, `README.md`, `CLAUDE.md`, `AGENTS.md`, `TODO.md`, `WPILib-License.md` |
| `docs/` | `guides/`, `logging/`, `vision/`, `coprocessor/`, `tools/`, `performance/`, `experiments/`, `adr/`, `inventory/`, `robot_details/` (index: `docs/README.md`) |
| `resources/` | Reference assets: AprilTag layouts, motor configs, `dashboards/` (AdvantageScope and Elastic layouts), `photonvision-calibrations/`, `choreo/` |
| `notes/` | `notes/<MM-DD>/`, zero-padded; no loose files at the top |
| `logs/` | `logs/<MM-DD>/`, **local only, never committed** (3.3 GB); `python tools/organize_logs.py` files new logs |

## What was removed

- `data/` and `unins001.dat`: Choreo's own program files and uninstaller, committed by accident on 2026-09-05. Choreo installs itself.
- `docs/team/`: lives in `~/robotics/FinneyTeam` (all 35 files there, content identical). It had come back through the merge of `beta`.
- The two trimmed logs that were tracked in `logs/` (`akit_26-10-14_*_trimmed.wpilog`): out of git, kept on disk in `logs/10-14/`. They remain in git history.

Nothing Choreo-related that is configuration, a path or a trajectory was removed: the root files went to `resources/choreo/`
(see its README).

## Where things went

- `Guides/` -> `docs/guides/` (same layout inside).
- Root dashboard layouts -> `resources/dashboards/`; the four `*_photon_calibration_*.json` -> `resources/photonvision-calibrations/`;
  root `*.traj` and `*.chor` -> `resources/choreo/`.
- Notes date folders zero-padded: `notes/10-3` -> `notes/10-03`, `notes/11-7` -> `notes/11-07`, `notes/6-16` -> `notes/06-16`, `notes/6-20` -> `notes/06-20`, `notes/6-23` -> `notes/06-23`, `notes/7-14` -> `notes/07-14`, `notes/7-21` -> `notes/07-21`, `notes/7-26` -> `notes/07-26`, `notes/7-28` -> `notes/07-28`, `notes/7-7` -> `notes/07-07`, `notes/9-1` -> `notes/09-01`, `notes/9-12` -> `notes/09-12`, `notes/9-15` -> `notes/09-15`, `notes/9-19` -> `notes/09-19`, `notes/9-22` -> `notes/09-22`, `notes/9-29` -> `notes/09-29`, `notes/9-5` -> `notes/09-05`, `notes/9-8` -> `notes/09-08`. Loose `notes/9-5.md` -> `notes/09-05/`; `testingVision_6-16.md` and its 12 images -> `notes/06-16/`.
- Logs: `logs/offseason/<d>/` -> `logs/<MM-DD>/` (`11-3` -> `11-03`, `6-13-26` -> `06-13`); loose `FRC_*` files and simulation folders
  -> the day in their name (UTC); file names unchanged. Experiment `analyze.py` scripts and READMEs point at `logs/`.
- Docs and resources moved by file (links and mentions across the repo were rewritten; no link broke that wasn't already broken):

| From | To |
|---|---|
| `docs/BatteryStatus.md` | `docs/logging/BatteryStatus.md` |
| `docs/akit-architecture.md` | `docs/logging/akit-architecture.md` |
| `docs/akit-logging-replay.md` | `docs/logging/akit-logging-replay.md` |
| `docs/akit-subsystem-guide.md` | `docs/guides/akit-subsystem-guide.md` |
| `docs/akit-swerve-integration.md` | `docs/logging/akit-swerve-integration.md` |
| `docs/battery-insights.md` | `docs/logging/battery-insights.md` |
| `docs/camera-autocal-plan.md` | `docs/vision/camera-autocal-plan.md` |
| `docs/camera-mount-calibration-notes.md` | `docs/vision/camera-mount-calibration-notes.md` |
| `docs/can-bus-load-ab-test.md` | `docs/performance/can-bus-load-ab-test.md` |
| `docs/console-load-ab-test.md` | `docs/performance/console-load-ab-test.md` |
| `docs/coprocessor-research.md` | `docs/coprocessor/coprocessor-research.md` |
| `docs/experiment-runner-plan.md` | `docs/tools/experiment-runner-plan.md` |
| `docs/health-check.md` | `docs/logging/health-check.md` |
| `docs/helpful-info-for-drivers.md` | `docs/guides/driver-info/helpful-info-for-drivers.md` |
| `docs/image.png` | `docs/guides/driver-info/image.png` |
| `docs/logbench-e2e-test-plan.md` | `docs/tools/logbench-e2e-test-plan.md` |
| `docs/orangepi-internet-access.md` | `docs/coprocessor/orangepi-internet-access.md` |
| `docs/orangepi-nt-publisher-setup.md` | `docs/coprocessor/orangepi-nt-publisher-setup.md` |
| `docs/orangepi-vision-recorder-setup.md` | `docs/coprocessor/orangepi-vision-recorder-setup.md` |
| `docs/photonvision-camera-intrinsics-calibration.md` | `docs/vision/photonvision-camera-intrinsics-calibration.md` |
| `docs/replay-workflow.md` | `docs/logging/replay-workflow.md` |
| `docs/two-orangepi-vision-ab-test.md` | `docs/vision/two-orangepi-vision-ab-test.md` |
| `docs/vision-ab-test-plan.md` | `docs/vision/vision-ab-test-plan.md` |
| `docs/vision-analysis-2026.md` | `docs/vision/vision-analysis-2026.md` |
| `docs/vision-improvements-2027.md` | `docs/vision/vision-improvements-2027.md` |
| `docs/vision-log-analysis.md` | `docs/vision/vision-log-analysis.md` |
| `docs/vision-testing-protocol.md` | `docs/vision/vision-testing-protocol.md` |
| `docs/wpilog-janitor-plan.md` | `docs/tools/wpilog-janitor-plan.md` |
| `resources/Autonomous.md` | `docs/guides/autonomous/Autonomous.md` |
| `resources/ControllerLayouts.md` | `docs/guides/controller-layouts/ControllerLayouts.md` |
| `resources/RadioConfigurations.md` | `docs/guides/RadioConfigurations.md` |
| `resources/driverControls.png` | `docs/guides/controller-layouts/driverControls.png` |
| `resources/handyLinks.md` | `docs/guides/handyLinks.md` |
| `resources/image-1.png` | `docs/guides/autonomous/image-1.png` |
| `resources/image-2.png` | `docs/guides/autonomous/image-2.png` |
| `resources/image-3.png` | `docs/guides/autonomous/image-3.png` |
| `resources/image-4.png` | `docs/guides/autonomous/image-4.png` |
| `resources/image-5.png` | `docs/guides/autonomous/image-5.png` |
| `resources/image.png` | `docs/guides/autonomous/image.png` |
| `resources/operatorControls.png` | `docs/guides/controller-layouts/operatorControls.png` |
| `resources/swerveTuneLog.md` | `docs/guides/swerveTuneLog.md` |

## Not done

- `docs/` pages themselves are unedited; only their location and links changed.
