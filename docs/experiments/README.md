# Experiments

Write-ups of tests we run on the robot: one question, a few controlled runs, logs, numbers, and a
verdict. `notes/<date>/` is the lab notebook (rough, written during testing). This folder is the
cleaned-up record we can find and compare later.

## Layout

```
docs/experiments/
  README.md                  ← this index
  _template.md               ← copy this to start an experiment
  <area>/
    YYYY-MM-DD-<slug>/
      README.md              ← the write-up (front matter + sections from the template)
      analyze.py             ← script that produces every number in README.md from the logs
      results.json           ← its output, committed so numbers can be diffed between experiments
      *.png                  ← plots/screenshots, if any
```

Areas: `vision`, `coprocessor`, `roborio` (loop timing, CPU), `can`, `power` (battery,
brownout), `drivetrain`, `mechanisms`, `tools`. Add an area when the first experiment needs it.

## Conventions

- **Logs stay in `logs/`** (gitignored, too big for git). The write-up names each run's log file,
  and `analyze.py` reads them from there. Trim with the WPILog Janitor first, so scripts only see
  enabled time.
- **One question per experiment, one variable per run.** A run added mid-session gets a decimal
  ID (e.g. T5.1) and a line saying why.
- **Write the setting into the run table before enabling.** PhotonVision and Pi settings are not
  in the robot log, so the notes are the only record.
- **Use the same maneuver for every run** (e.g. `CircleFacingTag`), or say why not.
- **Repeat small effects.** A difference that is smaller than the run-to-run noise needs at
  least two runs per setting, interleaved (A, B, A, B), so drift (battery, Pi temperature) hits both.
- **Every run gets a verdict** against a named reference: gain, loss or neutral, with the numbers.
- **Status** in the front matter: `planned` → `running` → `analyzed` → `decided`. `decided` means
  the code or config was changed (or deliberately left alone), and the change is linked.
- Bigger cross-cutting decisions that come out of an experiment go to `docs/adr/`.

## Index

| Date | Area | Experiment | Status | Result |
|---|---|---|---|---|
| 2026-10-27 | vision | [PhotonVision throughput vs resolution, decimate, fps, recorder](vision/2026-10-27-pv-throughput/README.md) | analyzed | 800x600@120 dec 3 is best; heavier settings halve results/s; recorder (or a browser stream) costs frames |
| 2026-10-28 | vision | [PhotonVision frame pacing: Low Latency Mode, detector threads, streams](vision/2026-10-28-pv-frame-pacing/README.md) | planned | Hypothesis: Low Latency Mode (on by default) causes the half-rate cliff |

### Earlier experiment docs (not yet moved into this layout)

| Area | Doc |
|---|---|
| vision | [vision-testing-protocol.md](../vision-testing-protocol.md), [vision-ab-test-plan.md](../vision-ab-test-plan.md), [two-orangepi-vision-ab-test.md](../two-orangepi-vision-ab-test.md), [vision-log-analysis.md](../vision-log-analysis.md) |
| roborio / can | [can-bus-load-ab-test.md](../can-bus-load-ab-test.md), [console-load-ab-test.md](../console-load-ab-test.md) |
