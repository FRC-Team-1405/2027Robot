# Experiments to run

Open this file to see what to run next on the robot. Each experiment links to its detail doc (what we're
testing, the run table, how to read the result). The rest of the open work is in [TODO.md](TODO.md).

When you finish one: move it to **Done** at the bottom with the date and a link to its results, and
commit the experiment's `manifest.json`, `results.json` and `data/` (the small extract, not the logs).

## Run next

### 1. Redo: 800x600 vs 1280x800 on the same autonomous  ·  about 30 minutes

**Why redo:** the 11-14 session ran fine, but the robot's AdvantageKit log from it wasn't saved (the runner
fetched the wrong file), so there are no numbers. The runner and LogBench are fixed.
**Detail:** [docs/experiments/vision/2026-11-14-pv-crossover-odometry/](docs/experiments/vision/2026-11-14-pv-crossover-odometry/README.md)

**Before you go:**

- [ ] Pull `beta` and deploy the robot code (it makes the vision filter use the right image size at 1280x800).
- [ ] On the laptop: `python -m pip install -r tools/exprunner/requirements.txt` (once).
- [ ] Start LogBench (VS Code task `LogBench`) and check it can fetch from the robot.
- [ ] Run it with `--redo` (below): the runner keeps the 11-14 entries under `history` in `manifest.json` and starts
      the runs again.

**At the robot** (from `tools/exprunner`):

```bash
python -m exprunner doctor ../../docs/experiments/vision/2026-11-14-pv-crossover-odometry/runs.toml
```

```bash
python -m exprunner run ../../docs/experiments/vision/2026-11-14-pv-crossover-odometry/runs.toml --redo
```

```bash
python -m exprunner finish ../../docs/experiments/vision/2026-11-14-pv-crossover-odometry/runs.toml
```

**Before you leave the robot** (this is the step that was missing on 11-14):

```bash
python docs/experiments/vision/2026-11-14-pv-crossover-odometry/analyze.py
```

- [ ] It prints a table of results per run. If it says "no raw estimates", "log not found" or shows `n = 0`, the log is
      wrong: fix it **now**, while the robot is still here (the right file is the `akit_*` log in `logs/`).
- [ ] The log is in `logs/offseason/` (gitignored). Don't lose it until the extract is committed.
- [ ] Commit `manifest.json`, `results.json` and `data/` in the experiment folder, then tell Claude to analyze.

---

### 2. Camera mounts: a trustworthy reference for the robot centreline  ·  an hour, then small tests

**Why:** the current camera constants match a tape measure, but we can't *measure* how accurate they are, and the
automatic calibration disagreed with the tape. Without a reference for the robot's own centreline and heading,
nothing else can be checked.
**Detail:** [docs/camera-mount-calibration-notes.md](docs/camera-mount-calibration-notes.md) (what we tried, the options,
the suggested order)

- [ ] Floor line perpendicular to the wall, and a mark at the front-centre and rear-centre of the bumpers.
- [ ] Redo the crosshair aim check against that line.
- [ ] One static truth stop at 2 m, then try "robot against the wall, back straight off".

---

## Smaller experiments (when there's time)

| Experiment | What it settles | Detail |
|---|---|---|
| Frame-budget **B6**: 800x600 @120, decimate 2 | Whether @120 reaches 108 results/s (it missed by 0.6 ms on 11-07; expect a miss). ~5 min, one run | [frame-budget](docs/experiments/vision/2026-11-10-pv-frame-budget/README.md) |
| **Range** experiment: stationary at 2 / 4 / 6 / 8 m | Whether a finer image sees tags farther. Needed before spending effort on faster pipelines | [pv-range](docs/experiments/vision/2026-11-03-pv-range/README.md) |
| roboRIO **loop overruns**: log the robot program's own CPU | Whether the roboRIO's 72-84% load is us. Then two 2-minute runs to measure run-to-run noise | [loop-overruns](docs/experiments/roborio/2026-11-03-loop-overruns/README.md) |
| Frame-cost bench: **2 workers x 2 threads** | Whether frames in flight keep most of the throughput with less added delay. Only if experiment 1 says finer images help | [frame-cost](docs/experiments/vision/2026-11-11-pv-frame-cost/README.md) |

## Parked

- **Camera auto-calibration** ("spin and drive"): built, but on the robot it didn't agree with the tape, because
  the vision it relies on isn't accurate enough. Parked until experiment 2 gives us a reference.
  [docs/camera-autocal-plan.md](docs/camera-autocal-plan.md)

## Done

| Date | Experiment | Result |
|---|---|---|
| 2026-11-14 | Frame cost on the Pi (bench) | The bench matches the robot; 4 frames in flight give ~4x the results/s, each ~10 ms later; grey decode saves 1.3-2.8 ms. [write-up](docs/experiments/vision/2026-11-11-pv-frame-cost/README.md) |
| 2026-11-14 | Camera mount check against tape and an aim check | Current constants match to ~0.2 in / 0.3 deg; keep them. [notes](docs/camera-mount-calibration-notes.md) |
| 2026-11-14 | First live run of the experiment runner (the crossover) | Runner worked (8 runs, settings confirmed); no results because the wrong log was fetched. See experiment 1 |

All finished write-ups, with their verdicts, are indexed in [docs/experiments/README.md](docs/experiments/README.md).
