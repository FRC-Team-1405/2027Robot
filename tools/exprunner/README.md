# exprunner — the experiment runner

Runs an experiment from its plan file (`runs.toml`, next to the experiment's README), run by run,
and records what actually ran in `manifest.json`. Design and roadmap:
[docs/experiment-runner-plan.md](../../docs/experiment-runner-plan.md).

**Built so far: bench experiments.** Steps that run on the Orange Pis over SSH, with no robot:
the runner copies a bench bundle to each Pi, runs each step, and fetches the results. **Not
built yet:** robot experiments (set PhotonVision on both Pis, hand over for an auto, fetch the log
through LogBench).

## Use

From this folder:

```bash
python -m exprunner check  ../../docs/experiments/vision/2026-11-11-pv-frame-cost/runs.toml
python -m exprunner run    ../../docs/experiments/vision/2026-11-11-pv-frame-cost/runs.toml
python -m exprunner status ../../docs/experiments/vision/2026-11-11-pv-frame-cost/runs.toml
```

| Command | Does |
|---|---|
| `check PLAN` | Validates the plan; prints each run's prompt, boards and the exact command it runs on the Pi |
| `sync PLAN [--board B]` | Builds the bench bundle and copies it to the plan's Pis (copy only; nothing is installed) |
| `run PLAN [IDS...]` | Syncs, then runs every run not done yet, in order. Named IDs run again even if done. `--redo` reruns everything, `--board B` limits to one Pi, `--yes` skips prompts, `--keep-going` carries on after a failure, `--no-sync` skips the copy |
| `status PLAN` | Done / failed / to do, per run and board |

Stopping (Ctrl+C) or a failure is safe: run it again and it carries on from what's left. A rerun
keeps the previous attempt under `history` in the manifest.

## What it needs

- **The team SSH key** at `~/.ssh/id_ed25519_orangepi`. `coprocessor/Bootstrap-OrangePi.ps1` puts
  it there the first time it runs on a laptop.
- **OpenSSH client** (`ssh`, `scp`): built into Windows 10+, macOS and Linux.
- **WPILib installed and the robot code built once.** The bench program is compiled here, with
  WPILib's JDK, against WPILib's jars (from the WPILib install or the Gradle cache).
- Python 3.11+ (standard library only).
- The Pis listed in `coprocessor/robots.json`; boards are named as there.

## Plan files

See the docstring at the top of [`exprunner/plan.py`](exprunner/plan.py), and
[the frame-cost plan](../../docs/experiments/vision/2026-11-11-pv-frame-cost/runs.toml) for a full
example. In short: `experiment`, `kind = "bench"`, `boards`, optional `[defaults.<step>]` tables,
then `[[runs]]` with `id`, `step`, `what`, an optional `prompt` (the runner waits for Enter), and
`args` (passed to the step as `--key value`; lists become `1,2,3`, booleans `yes`/`no`).

The steps are those of [`coprocessor/bench/run.sh`](../../coprocessor/bench/README.md).

## Where things go

| Where | What |
|---|---|
| Pi: `~/bench/code/` | The bundle: `run.sh`, compiled `classes/`, `BUILD.txt` (commit it was built from). Replaced on every sync |
| Pi: `~/bench/frames/` | Captured frames (`<name>.mjpg`). Kept between runs; they're big, so they stay on the Pi |
| Pi: `~/bench/results/<experiment>/<run>/` | One run's output, cleared before the run |
| Laptop: `<plan folder>/data/<run>/<board>/` | That output fetched back, plus `step.log` (everything the step printed) |
| Laptop: `<plan folder>/manifest.json` | Per run and board: status, exit code, command, start/finish, git commit, Pi host |

## Tests

```bash
python -m pytest
```

The run loop is tested against a fake Pi. `test_build.py` really compiles `FrameCost.java` when a
JDK and WPILib's jars are present, so a broken bench program shows up before it reaches a Pi.
