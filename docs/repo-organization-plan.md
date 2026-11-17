# Repo organization plan

Branch: `feature/repo-organization` (from `main` after the 2026-11-17 merge of `beta` and the swerve replay branch).
Goal: few files at the root, one place for docs, dated folders that read as simple dates, nothing that is only there by accident.

Status: **survey done, nothing moved yet.** Edit this file to change the plan; the moves follow it.

## What's at the root today, and where it goes

Must stay at the root (the tools expect them there): `build.gradle`, `settings.gradle`, `gradlew`, `gradlew.bat`, `gradle/`,
`vendordeps/`, `src/`, `.wpilib/`, `.vscode/`, `.gitignore`, `README.md`, `CLAUDE.md`, `AGENTS.md`, `TODO.md`, `WPILib-License.md`.

| Now at the root | What it is | Proposed |
|---|---|---|
| `AdvantageScope-CameraHealth.json`, `AdvantageScope_layout.json`, `elastic-layout.json` | Dashboard layouts | `resources/dashboards/` |
| `left_photon_calibration_*.json`, `right_photon_calibration_*.json` (4 files, 1.2 MB) | PhotonVision camera calibration exports, 800x600 and 1280x800 | `resources/photonvision-calibrations/` (only comments in `VisionConstants.java` and two notes name them) |
| `Left_To_Field.traj`, `Right_To_Field.traj` | Choreo trajectories, **byte-identical** to the copies in `src/main/deploy/` | delete |
| `Right_To_Alliance.traj` | Choreo trajectory, **differs** from the deploy copy | decide: archive or delete (see Questions) |
| `MacyTestAuto1.traj`, `NewPath.traj`, `Constraint-Honoring Omnidirectional Route Editor and Optimizer.chor` | Choreo files that exist only at the root, from July and September | archive in `resources/choreo-archive/` or delete (see Questions) |
| `data/` (19 files, 3.9 MB) | **The Choreo desktop app's own program files** (Flutter assets: field images, icons, fonts), committed by accident on 2026-09-05 when Choreo was set up in this folder. Nothing in the repo reads them | delete |
| `unins001.dat` | The same Choreo install's Windows uninstaller record, same commit | delete |
| `Guides/` (13 files) | How-to guides (tuning, checklists, logs, GitHub setup) | `docs/guides/` (one reference to it needs updating) |
| `resources/*.md` (`Autonomous.md`, `ControllerLayouts.md`, `RadioConfigurations.md`, `handyLinks.md`, `swerveTuneLog.md`) | Reference notes, not assets | `docs/guides/` with their images |
| `resources/` the rest | AprilTag layouts, motor configs, images, `fuel_detector.vpr`, `vision-dashboard.html` | stays as `resources/` (the assets folder) |

That takes the root from **28 files plus 9 folders** to about **9 files plus 8 folders**, all of them required by a tool.

## notes/

The structure (`notes/<date>/`) is good. The problems:

- **14 loose files at the top**: `9-5.md`, `testingVision_6-16.md`, and 12 pasted `image*.png` (`testingVision_6-16.md` is the one
  that uses them). Proposed: `notes/9-5/` and `notes/6-16/` take them (images in `notes/6-16/images/`).
- **Date folders don't sort**: `10-3`, `11-7`, `9-1` sort after `10-27`. Proposed: zero-padded `MM-DD`
  (`09-01`, `10-03`, `11-07`). Links in docs that name `notes/11-7/...`, `notes/9-5.md` etc. are updated in the same step.

## logs/ (local only: 3.3 GB, not in git)

Today: `logs/offseason/<date>/` (real robot logs, with `.bundles`, `.vision`, `.trimmed` beside them) next to 22 dated
simulation folders (`2026-10-18_17-39-33`), 17 loose `FRC_*.wpilog`, and two tracked trimmed logs.

Proposed: **`logs/<MM-DD>/` holds everything from that day**, nothing else at the top.

- `logs/offseason/<d>/` becomes `logs/<MM-DD>/` (the folder name already says which session day it was, which can differ from the UTC
  date in the file name for evening sessions, so the existing grouping is kept).
- Loose `FRC_*.wpilog` and the `2026-MM-DD_HH-MM-SS` folders go to the day in their name.
- File names are **not** changed: the time of day in `akit_26-11-14_20-26-00` tells sessions apart, and the experiment manifests and
  `analyze.py` scripts refer to those names.
- A one-off script (`tools/organize_logs.py`, dry run first) does the move and prints what it will do.
- 19 files mention `logs/offseason` (experiment `analyze.py` scripts and READMEs, `vision_analyzer`, `CircleFacingTagCommand`,
  the Janitor UI, `.claude/launch.json`); they change to `logs/`. Each `analyze.py` already joins a `<date>/<name>` path onto one
  constant, so it is a one-line change per script.

## docs/ (after Guides move in)

`docs/` has 28 files at its top. Proposed grouping, **as a second step once the above lands**: `docs/guides/` (how-tos), `docs/vision/`,
`docs/logging/` (akit, replay, battery, health check), `docs/coprocessor/` (Pi setup docs), with `adr/`, `experiments/` and `team/` as they are.

## Questions

- **Delete `data/` and `unins001.dat`?** They are Choreo's own program files; if anyone wants Choreo, it installs itself. Yes/no.
- **The unique Choreo files** (`MacyTestAuto1.traj`, `NewPath.traj`, `Right_To_Alliance.traj`, the `.chor`): keep them in
  `resources/choreo-archive/`, or delete? (`src/main/deploy/` already holds the Choreo files the robot uses.)
- **Zero-padded dates** (`09-01`) so folders sort correctly, in both `notes/` and `logs/`: OK?
- **Group `docs/` now or later?**

## Order of work

- [ ] Root: move the layouts and calibrations; delete the stray duplicates.
- [ ] `Guides/` and the `resources/` notes into `docs/guides/`.
- [ ] `data/` and `unins001.dat` removed (if yes).
- [ ] `notes/`: loose files into dated folders; rename date folders; fix links.
- [ ] `logs/`: script with a dry run, run it, point the 19 files at `logs/`.
- [ ] `docs/` grouping (second step).
- [ ] Update `README.md`, `CLAUDE.md` and `TODO.md` for the new layout; run the tool tests and `gradlew build`.
