# wpilog-janitor

Make `.wpilog` files smaller **on purpose**: keep only the periods you care about, drop entries you
don't need, see what it saves. Per log, by hand — nothing is trimmed automatically.

Plan and design decisions: [`docs/wpilog-janitor-plan.md`](../../docs/wpilog-janitor-plan.md).
File-format work lives in [`wpilog-utils`](../wpilog-utils); this is the tool on top of it.

**Status:** CLI done (analyze, trim, segmap). The Trim page and Content page (web UI), duplicate detection
and the LLM extract are planned — see the plan's milestones M3–M5.

## CLI

```bash
cd tools/wpilog-janitor
python -m janitor analyze  match.wpilog                       # modes, sizes, where the bytes are
python -m janitor trim     match.wpilog --modes auto --dry-run  # exact output size, nothing written
python -m janitor trim     match.wpilog --modes auto            # -> match_trimmed.wpilog, then verifies it
python -m janitor segmap   match_trimmed.wpilog               # original-time map stored in the output
```

Times are **seconds from the log's first record**, the same clock `analyze` prints.

| Option | Meaning |
|---|---|
| `--modes auto,teleop` | keep every span of these DriverStation modes |
| `--only 0,2` | with `--modes`: keep only those spans (0-based among the matching ones) |
| `--range 40:55` | keep an arbitrary range; repeatable, mixes with `--modes` |
| `--gap-ms 200` | real time kept on each seam between kept segments (default 200 ms ≈ 10 cycles) |
| `--pad-pre-ms` / `--pad-post-ms` | extra real cycles around each segment (e.g. keep the disable→enable edge) |
| `--preserve` | keep original timestamps (leaves a hole instead of a short seam) |
| `--exclude NAME` / `--exclude-prefix P` | drop entries (the Content page will drive these) |
| `--dry-run` | print the size the real run would produce, exactly |
| `-o OUT` | default: `<log>_trimmed.wpilog` next to the source |

Example — keep both autonomous periods with a 200 ms seam between them, drop vision outputs:

```bash
python -m janitor trim match.wpilog --modes auto --exclude-prefix /RealOutputs/Vision
```

## What the output is

A normal AdvantageKit log: same header, cycles evenly spaced (a seam is one normal cycle period, built from
real cycles either side of the cut), `/Timestamp` re-stamped to match, state restated where dropped time had
changed it. Original times are recoverable from `/Janitor/SegmentMap` (`janitor segmap`).
The Pi recorder frames and `.hoot` files are **not** re-aligned to the new times (planned, later).

## Caution: don't drop replay inputs

`/Vision/*`, `/DriverStation/*`, `/SystemStats/*` and other `processInputs` entries are what `simulateJava`
replay and `logbench` read; `/RealOutputs/*` is regenerated. The Content page will protect inputs by default;
the CLI's `--exclude*` will not stop you.

## Tests

```bash
cd tools/wpilog-janitor && python -m pytest
```
