# wpilog-janitor

Make `.wpilog` files smaller **on purpose**: keep only the periods you care about, drop entries you
don't need, see what it saves. Per log, by hand — nothing is trimmed automatically.

Plan and design decisions: [`docs/wpilog-janitor-plan.md`](../../docs/wpilog-janitor-plan.md).
File-format work lives in [`wpilog-utils`](../wpilog-utils); this is the tool on top of it.

**Status:** CLI, the **Trim page** and the **Content page** are done. The LLM extract is planned — see the plan's milestone M5.

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
* **Timing**: *Keep original timestamps* (default) or *Close the gap* (for viewing only; see [Timing](#timing)).
* The **Result** panel shows original → trimmed size. It is an instant estimate (within about 1%), and turns *exact* on its
  own for logs under 40 MB; for bigger logs press *Compute exact size* (one pass over the file).
* **Export** saves `<log>_trimmed.wpilog` next to the original (never overwriting; a number is added instead) and checks it
  against the original, or downloads it.
* Your selection is remembered per log in the browser.

**Content page** — where the bytes are, and what you can leave out. Exclusions made here are counted in the Trim page's savings.

* **Sizes**: every entry in a tree by path, with size, share, record count and rate. Tick a row (or a whole folder) to exclude it;
  a folder shows a dash when only some of its entries are excluded.
* **Duplicates**: entries that record the same data twice, with a suggested one to keep (the replay-input side beats an output copy),
  how much you would recover, and a button to exclude the others. Groups whose members barely changed are listed separately as
  *weak* — two short series can match by chance. Entries that share a name but not their data are listed too.
* **Constants**: entries that never changed. There are usually hundreds and they cost almost nothing; they are listed so you can see that.
* **Analyse** the periods you are keeping (from the Trim page) or the whole log — a pair can be identical inside the kept periods and not elsewhere.
* **Protect**: entries that replay reads back (`replay inputs`) or that logbench/vision-analyzer look up are marked 🔒, and excluding one asks
  first ("Exclude all", "Only the unprotected", "Cancel"). The cycle marker and struct schemas are always protected: without them
  AdvantageScope cannot read the file. Nothing is ever excluded without a click.

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
python -m janitor dupes    match.wpilog                        # constants and duplicate entries (add --modes auto to look at just those periods)
python -m janitor serve    --logs logs                         # web UI
```

Times are **seconds from the log's first record**, the same clock `analyze` prints.

| Option | Meaning |
|---|---|
| `--modes auto,teleop` | keep every span of these DriverStation modes |
| `--only 0,2` | with `--modes`: keep only those spans (0-based among the matching ones) |
| `--range 40:55` | keep an arbitrary range; repeatable, mixes with `--modes` |
| `--compact` | re-time so each cut becomes a short seam instead of a hole. For viewing only; see [Timing](#timing) |
| `--gap-ms 200` | with `--compact`: real time kept on each seam (default 200 ms ≈ 10 cycles) |
| `--pad-pre-ms` / `--pad-post-ms` | extra real cycles around each segment (e.g. keep the disable→enable edge) |
| `--exclude NAME` / `--exclude-prefix P` | drop entries (the Content page builds this list for you) |
| `--dry-run` | print the size the real run would produce, exactly |
| `-o OUT` | default: `<log>_trimmed.wpilog` next to the source |

Example — keep both autonomous periods, drop vision outputs:

```bash
python -m janitor trim match.wpilog --modes auto --exclude-prefix /RealOutputs/Vision
```

## What the output is

A normal AdvantageKit log: same header and entries, only the kept cycles, state restated where dropped time had
changed it. `/Janitor/SegmentMap` (`janitor segmap`) records what was kept.

## Timing

**Default: keep original timestamps.** Every kept record keeps its time, and cut periods become empty holes.
AdvantageScope plays across the hole without trouble.

**`--compact` / *Close the gap*** re-times what follows each cut so the log plays straight through: cycles are evenly spaced,
a seam is one normal cycle period built from real cycles either side of the cut, and `/Timestamp` is re-stamped to match.
It only moves the *log's* clock, though. Values that are themselves times on that clock, such as the camera capture
times in `/Vision/*/RawTimestamps`, are not moved. So anything that compares the two breaks:

* logbench latency (`latency_mean_ms`) reads **0**, because every sample falls outside its valid range (found 9/22; every
  other metric matched exactly);
* `simulateJava` replay hands the pose estimator vision timestamps that no longer match the replayed clock;
* Pi recorder frames and `.hoot` files no longer line up.

Shifting those values too would need a list of which entries hold times, and it can't reach times inside struct or
PhotonVision payloads. Keeping the original timestamps costs about 3–8% more file size, so it is the default. Use
`--compact` only for a copy you just want to watch.

## Caution: don't drop replay inputs

`/Vision/*`, `/DriverStation/*`, `/SystemStats/*` and other `processInputs` entries are what `simulateJava`
replay and `logbench` read; `/RealOutputs/*` is regenerated. The Content page protects inputs by default and asks before
excluding one; the CLI's `--exclude*` will not stop you.

## Tests

```bash
cd tools/wpilog-janitor && python -m pytest             # CLI + API (needs fastapi)
cd web && npm test           # front-end logic
```
