# 9/22 — Notes cleanup (6/16 → 9/19)

This folder pulls the useful parts out of every note from the summer. **Nothing in the older
folders was moved or deleted.**

| File | What it is |
|---|---|
| [todos.md](todos.md) | Every to-do from the notes, checked against the repo and marked open or done |
| [drafts/guide-orangepi-access.md](drafts/guide-orangepi-access.md) | **Guide:** SSH into the Orange Pi / PhotonVision box (robot network, Windows internet sharing, Linux DHCP+NAT) plus the gotchas we hit |
| [drafts/reference-vision-tuning-log.md](drafts/reference-vision-tuning-log.md) | **Reference:** current camera and pipeline settings, a table of every tuning change with its log file and result, calibration intrinsics, tape-measure runs |
| [drafts/reference-coprocessor-and-field-facts.md](drafts/reference-coprocessor-and-field-facts.md) | **Reference:** Orange Pi thermals and power, the R704 bandwidth cap, the open DS wiring question |

## Trimmed logs and comparisons (added 9/22)

The originals in `logs/` (gitignored) are untouched. Each test day now has `trimmed/` (trimmed
`.wpilog`) and `analysis/` (logbench compare reports, `.html` for people and `.json` for LLMs).

**How they were trimmed:** `python tools/wpilog-janitor/run.py trim <log> --modes auto --preserve`.
The 9/1 logs use `--modes teleop`, since that day had no autos. No entries were dropped: dropping
duplicates saved under 1%, so auto-only trimming does all the work. `--preserve` (keep original
timestamps) was **required**, since without it latency reads 0 in logbench. It's now the WPILog Janitor's default (`c3c1012`). A check: the
trimmed logs reproduce your three existing comparisons with 0 mismatches out of 222 values.

| Day | Trimmed logs | Before → after |
|---|---|---|
| 6-16 | 5 feature-switch / high-res runs | 16.0 MB → 4.8 MB |
| 9-1 | 3 teleop sessions incl. `healthDashboardBaseline` | 250.5 MB → 15.5 MB |
| 9-5 | pre/post exposure change | 29.0 MB → 2.6 MB |
| 9-12 | circle auto "post-calibration", recorder test 5 | 12.4 MB → 3.7 MB |
| 9-15 | visionRecorder 1–3 | 37.6 MB → 7.1 MB |
| 9-19 | `MULTI_TAG_PNP_ON_RIO`, `LOWEST_AMBIGUITY` | 17.9 MB → 2.5 MB |
| **Total** | **17 logs** | **363.4 MB → 36.1 MB** (largest single file 7.3 MB) |

**Not trimmed:**
- Logs with no enabled period (9-1 `21-54-07`, `23-09-47`, `23-38-07`; 9-12 `VisionRecorderTest`),
  since there was nothing to keep.
- `9-5/akit_26-09-05_14-27-33.wpilog`, which is byte-identical to the `_PreCalibration` copy.
- The 6-20 logs, which are already committed in `notes/6-20/`.
- The 6-9 / 6-13 / top-level logs, since those days have no notes.
- Vision-recorder JPEG folders weren't copied (~50 MB of images).

Comparisons: your three (9/15 ×2, 9/19 ×1) were copied in as-is, and eight new ones were run
(6/16 ×3, 9/5, 9/12, 9/15 intrinsics, 9/19 ×2). The takeaways are in
`drafts/reference-vision-tuning-log.md`.

## What each old note turned into

| Note | Kept as | Safe to archive after promoting? |
|---|---|---|
| `testingVision_6-16.md` + `image*.png` | Three tuning-log rows, now backed by `6-16/trimmed/` + `6-16/analysis/` | Yes |
| `6-20/testingVision_6-20.md`, `*_summary.md`, `*_comparison.md` | Tuning-log rows with numbers | Yes. Keep the `.wpilog`s if you want to re-run the analysis. |
| ~~`6-20/trimmedTest`, `trimmedTest2`~~ | Deleted 9/22: never committed, output of the old vision-analyzer trim, superseded by the WPILog Janitor | — |
| `6-20/photonVisionSSH.txt`, `6-23/sshExport.txt` | SSH guide (the ntcore / no-internet failures) | Yes. **Redact the Wi-Fi password in `sshExport.txt` first** (see todos). |
| `6-23/notes.md` | Tape-measure runs → tuning log. The DHCP steps → SSH guide | Yes |
| `7-7/orangePiConnectedToInternet.md` | SSH guide, method 2 | Yes |
| `7-14/setupOrangePiMetricsService.md` | Coprocessor facts (thermals) + fan to-do | Yes |
| `7-21/bandwidthLimits.md` | Coprocessor facts (R704) | Yes |
| `7-26/orangepi-config-attempt.md` | SSH guide (method 3 + gotchas) + coprocessor facts (power) | Yes, but it's a good incident write-up. It could go to `docs/incidents/` as-is. |
| `7-28/cameraCalibrationAttempt2.md` | Tuning log (tape-measure runs) | Yes |
| `9-1/todo.md` | Done (circle auto) | Yes |
| `9-5.md`, `9-5/todo.md`, `9-5/*.png` | Tuning log + to-dos | Yes |
| `9-8/*` | Intrinsics → tuning log. The calibration JSONs are worth keeping. | Move the JSONs to `docs/vision/calibration/` |
| `9-12/*` | To-dos (recorder naming, pit-check crash). The recorder manifests are test data. | Yes |
| `9-15/notes.md`, `9-19/notes.md` | Tuning-log rows with results (analyzed 9/22) | Yes |

## Where these should live

I'd split things by **how long they stay useful**:

1. **`docs/` for things that stay true.** Guides and references that anyone on the team should be
   able to find. Proposed layout:
   ```
   docs/guides/orangepi-ssh-and-bench-access.md    ← drafts/guide-orangepi-access.md
                                                     (replaces docs/orangepi-internet-access.md)
   docs/vision/tuning-log.md                        ← drafts/reference-vision-tuning-log.md
   docs/vision/calibration/*.json                   ← notes/9-8/*.json
   docs/robot_details/vision_specs.md               ← append coprocessor-and-field-facts
   ```
   Over time, the `orangepi-*` setup docs could move into `docs/guides/` as well. A student would
   find "guides/" before a long flat list of files.

2. **`notes/` stays as an inbox of dated scratch.** Keep the `M-D/` folders exactly as you do now,
   raw and messy. Two small habits make the next cleanup much easier:
   - Start any to-do line with `TODO:` (you mostly already do) so they can be found with
     `grep -rn "TODO:" notes/`.
   - For every experiment, write down **the log filename + the one thing you changed**. The 9/15
     and 9/19 notes did this well; the 6/16 note was only screenshots, and it could only be analyzed because the log names said what changed (FSON/FSOFF, HighRes).

3. **Keep one open-to-do list.** Move `todos.md` to `notes/TODO.md` (not in a dated folder) and add
   to it when you write a note. For anything the students should see, GitHub Issues would work better.

4. **Run a cleanup like this about once a month.** Promote what's durable to `docs/`, then move old
   dated folders to `notes/archive/` rather than deleting them.

Commands to promote the drafts once you've read them (from the repo root):
```bash
mkdir -p docs/guides docs/vision/calibration
git mv docs/orangepi-internet-access.md docs/guides/orangepi-ssh-and-bench-access.md   # then paste in the draft
cp notes/9-22/drafts/reference-vision-tuning-log.md docs/vision/tuning-log.md
cp notes/9-8/*_photon_calibration_*.json docs/vision/calibration/
```
`docs/orangepi-nt-publisher-setup.md` links to `docs/orangepi-internet-access.md`. Update that
link if you move the file.
