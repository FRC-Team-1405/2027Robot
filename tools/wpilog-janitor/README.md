# wpilog-janitor

Make `.wpilog` files smaller **on purpose**: keep only the periods you care about, drop entries you
don't need, see what it saves. Per log, by hand — nothing is trimmed automatically.

Plan and design decisions: [`docs/wpilog-janitor-plan.md`](../../docs/wpilog-janitor-plan.md).
File-format work lives in [`wpilog-utils`](../wpilog-utils); this is the tool on top of it.

**Status:** CLI and the **Trim page** are done. The Content page (size tree, duplicate detection, choosing entries to
drop, LLM extract) is planned — see the plan's milestones M4–M5.

## Web UI

```bash
cd tools/wpilog-janitor/web && npm install && cd ../../..     # first time only
```

Then run the **Janitor** task in VS Code (builds the front end, serves `logs/`), or by hand:

```bash
npm --prefix tools/wpilog-janitor/web run build
python tools/wpilog-janitor/run.py serve --logs logs          # http://127.0.0.1:8767/
```

**Trim page**

* A timeline shows the log's disabled / auto / teleop bands over a bytes-per-second curve.
* **Click a band** to keep or drop that period (each autonomous period is its own band). **Drag** across the timeline to keep
  an arbitrary range. **Drag a highlighted edge** to adjust it, or type exact seconds in the table. Wheel zooms, alt-drag pans,
  double-click resets. Per-period padding keeps extra real cycles around a period (e.g. the disable→enable edge).
* **Timing**: *Close the gap* (default, 200 ms of real time kept at each cut) or *Keep original timestamps*.
* The **Result** panel shows original → trimmed size. It is an instant estimate (within about 1%), and turns *exact* on its
  own for logs under 40 MB; for bigger logs press *Compute exact size* (one pass over the file).
* **Export** saves `<log>_trimmed.wpilog` next to the original (never overwriting; a number is added instead) and checks it
  against the original, or downloads it.
* Your selection is remembered per log in the browser.

The first open of a big log takes a while (about 10 s for 86 MB, 15 s for 130 MB); after that it is cached and instant.

**Developing the front end:** `cd web && npm run dev` (http://localhost:5174, proxies `/api` to port 8767; run the server
alongside), `npm test` (unit tests for the timeline geometry and segment operations), `npm run typecheck`.

## CLI

```bash
cd tools/wpilog-janitor
python -m janitor analyze  match.wpilog                       # modes, sizes, where the bytes are
python -m janitor trim     match.wpilog --modes auto --dry-run  # exact output size, nothing written
python -m janitor trim     match.wpilog --modes auto            # -> match_trimmed.wpilog, then verifies it
python -m janitor segmap   match_trimmed.wpilog               # original-time map stored in the output
python -m janitor serve    --logs logs                         # web UI
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
cd tools/wpilog-janitor && python -m pytest             # CLI + API (needs fastapi)
cd web && npm test           # front-end logic
```
