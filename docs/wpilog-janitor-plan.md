# wpilog-janitor — plan

A `.wpilog` utility for **making logs smaller on purpose**: cut a log down to the time ranges
you care about, drop the entries you don't, and see exactly what that saves. Two pages over one
core, same shape as `logbench` (CLI + web UI as two views of one library).

Status: **M0–M4 built** (shared library, index, trim engine + verifier, CLI, FastAPI server, Trim page, Content page:
size tree, duplicate detection, protection, exclusions feeding the Trim savings). M2's AdvantageScope acceptance check passed.
Not built yet: the LLM extract (M5), and the "structural / derived" duplicate kinds (see M4 notes).

### Build notes — where the code differs from the plan below

* **M4 (Content page):**
  * **Evidence floor.** On real logs the plan's warning came true: two-value booleans (`/RadioStatus/Connected`,
    `/RealOutputs/Intake/AtTarget`, …) hash-match by chance. A group whose members changed fewer than 6 times is marked
    `weak` and tucked into a collapsed list, never a suggestion. The strong groups found in the sample logs are real:
    `/Vision/*/VisibleTagIds` is byte-identical to `/Vision/*/RawTagIdsFlat` (~1% of the file), and each `/Pickup|Hopper|Indexer/VelocityRPS`
    input has a `/RealOutputs/...` copy.
  * **Protection is a set, not one profile.** Two checkboxes (`replay` inputs, what `logbench` reads) instead of `replay | logbench | none`,
    because logbench reads *outputs* (`RealOutputs/Vision/...`) that replay does not need. Cycle marker and struct schemas are always protected.
    `LOGBENCH_PREFIXES` is a hand-kept list, guarded by a test that runs logbench/vision-analyzer's real lookups on a sample log.
  * **Exclusions are exact entry names** written by the UI (a folder checkbox adds every entry under it); `exclude_prefixes` still works from
    the CLI and is honoured and preserved by the UI. Stored per log in the browser; the Trim page reads them for its savings.
  * **The analysis can be limited to the periods being kept** (default when a Trim selection exists): duplicates can appear inside the kept
    periods that do not exist over the whole log. One pass, cached per (log, window); changing the protection setting reuses it.
  * **Near-duplicates** exist (>=99.9% of values equal, same type and record count, candidates bucketed) but no real log has produced one yet,
    so the code is proven only on synthetic data. **Not built:** structural/derived duplicates (a struct logged again as its fields, unit-scaled
    copies); the plan marked those as a stretch.
  * `python -m janitor dupes LOG` prints the same analysis on the command line.
  * Speed: one pass, 1.3 s for 9.8 MB, 4.8 s for 36 MB, 35 s for 134 MB (whole log). With a window, reading stops when the last kept period
    ends: a period near the start of the 134 MB log takes 0.2 s instead of 10 s.

* **M3 (Trim page):** `dry_run` is 6–10 s on 85–135 MB logs, so the UI shows an instant `estimate_size` (index only; within 0.2% on
  the sample logs, 0.03% on an 86 MB one) and computes the exact size automatically only under 40 MB, otherwise on a button.
  The estimate needed a per-record count per cycle and a per-entry bytes-per-second histogram in the index, so that exclusions
  and the narrower timestamps after re-timing are accounted for.
* **The verifier now streams the source** (one pass, memory ~ what is kept); before, it held every source record (14 s and
  gigabytes for a 134 MB log).
* Found and fixed while building it: a segment ending exactly at the last record (which is how the final mode span ends)
  dropped the last cycle; and `LogIndex.window_bytes` had the same off-by-one.
* Ports: server 8767, Vite dev 5174 (logbench uses 8765 / 5173 and `.claude/launch.json` uses 8766).

* **Segment times are seconds from the log's first record** (same clock as `mode_spans()`), not absolute.
* **Entries are Started lazily**, right before their first written record at that record's new timestamp,
  not all at the front — it reads like the source (which registers entries as they first log) and means an entry
  with no data in the kept ranges simply doesn't appear.
* **`dry_run` streams the source once** (~0.8 s for the 9.8 MB sample) through the *same* writer as the export,
  rather than estimating from the index. Byte-exact by construction; a cheaper estimate for slider-dragging
  can be added in M3 if it's needed (`LogIndex.cycle_bytes` supports it).
* **Gap = real cycles from both sides of the cut**; the seam replaces exactly one normal cycle spacing, so
  `--gap-ms 200` yields 200 ms of disabled time (10 cycles at 20 ms), not 220.
* **Segment order is canonicalised** (sorted by time) so the segment map doesn't depend on click order.
* **Logging:** moving the parser changed its logger name; `vision_analyzer` and `camera_calibration` now also attach
  their file handlers to `wpilog_utils`, otherwise the parser's "PARSING STOPPED EARLY" errors would have reached no file.
* **Verified by mutation:** deliberately breaking state restatement, the `/Timestamp` rewrite and the seam width
  each fail the suite.
* Pre-existing, unrelated: `logbench/tests/test_main_live_endpoints.py::test_connect_without_ntcore_installed_returns_a_clean_501`
  fails on machines that have `ntcore` installed (it did before this work).

## Decisions (settled)

| Question | Decision |
|---|---|
| Name / location | `tools/wpilog-janitor/` |
| UI stack | FastAPI + Vite/React/TS, like `logbench`. Thin UI over a stdlib-only core + CLI |
| Time handling | **Keep original timestamps by default** (changed 9/22). Re-timing (`compact`) is opt-in for viewing only: it moves the log's clock but not timestamps stored in the data (`/Vision/*/RawTimestamps`), which broke logbench latency and would mis-time replay. Either way the output must be clean in **AdvantageScope** (acceptance test is the user opening it there) |
| Default gap between kept segments (`compact` only) | **200 ms** |
| Recovering original times | A note **inside the output log** maps new ↔ original times (see "Segment map") |
| Alignment with Pi recorder frames | Not a goal. Noted in the segment map; a later feature can re-stamp the Pi frames from that map |
| Entry exclusion | **Content page only.** Trim page is only about the timeline |
| Standalone or in logbench | Standalone tool |
| Shared code | New shared library **`tools/wpilog-utils/`**; `wpilog-janitor`, `logbench`, `vision-analyzer`, `camera-calibration` all depend on it |

## Goals

1. **Trim** — import a log, see the disabled / auto / teleop bands on a timeline, pick any mix of modes and/or
   arbitrary start–end ranges, keep only those, export a valid `.wpilog`. Per log, by hand — never an automatic
   "always keep auto".
2. **Content** — see where the bytes are, find data that is logged more than once, mark entries to drop, and produce
   an extract an LLM can read to judge "do we need this?".
3. **Savings, live** — every change shows original → output bytes and % saved before anything is written.

Non-goals: metric computation (that's `logbench`), editing values inside records, live NT capture, merging logs.

## Three-package layout

The parser, mode detection and trimming are format-level facts about `.wpilog`, not about vision or about
the janitor. Today they live in `vision_analyzer` and get reached through `sys.path` bridges (`logbench/server/paths.py`,
`camera_calibration/logger.py`). That's the wrong home for a trim engine that three tools now want.

```
tools/
  wpilog-utils/                  NEW  shared library. stdlib-only. no UI, no analysis opinions.
    pyproject.toml
    wpilog_utils/
      records.py       header, iter_records (with byte ranges), build_record, control-record parse (Start/Finish/SetMetadata)
      decode.py        _decode + parse_wpilog / parse_wpilog_bytes  (moved verbatim from vision_analyzer.parser)
      modes.py         compute_mode_spans, filter_signals_by_time    (moved from vision_analyzer.metrics)
      index.py         one-pass LogIndex: entries, bytes, per-second byte histogram, cycles, mode spans
      trim.py          TrimPlan / Segment / writer / dry_run / segment map   <- the multi-segment trim engine
      verify.py        re-parse an output and check it against a plan
    tests/
  wpilog-janitor/                NEW  the tool
    janitor/
      core/  dedupe.py, classify.py, extract.py         (content analysis — janitor-specific)
      cli.py                                             janitor trim | analyze | extract | verify
      server/main.py                                     FastAPI
    web/                                                 Vite + React + TS: /trim and /content
    tests/
  logbench/ vision-analyzer/ camera-calibration/         depend on wpilog-utils
```

What goes where: anything about *the file format or time* → `wpilog-utils`. Anything about *judging what's worth
keeping* (duplicates, protected prefixes, LLM extract) → `wpilog-janitor`. Rule of thumb: if `logbench` could
plausibly want it, it's utils; if only the janitor has an opinion, it stays in the janitor.

### How the sharing works

Follow the repo's existing convention: a `paths.py` bridge that puts `tools/wpilog-utils` on `sys.path` (zero install
step for students). Give `wpilog-utils` a `pyproject.toml` anyway so `pip install -e tools/wpilog-utils` works later
without moving anything. One bridge helper, not three copies.

### Migration (do this first, it's the riskiest non-new work)

1. Write **characterization tests** in `wpilog-utils` *before* moving anything: `parse_wpilog` on
   `notes/6-20/*.wpilog` (skip if absent) and synthetic logs; `compute_mode_spans`; `trim_wpilog_bytes` output bytes.
   `vision-analyzer` has no tests today, so nothing currently guards this code.
2. Move the code **verbatim** into `wpilog_utils`. `POSE2D_SIZE`/`POSE3D_SIZE` move with the decoder;
   `vision_analyzer/constants.py` re-imports them.
3. Turn `vision_analyzer/parser.py` into a **shim** that re-exports the same names (`parse_wpilog`,
   `_parse_wpilog_bytes`, `_iter_records`, `_build_record`, `trim_wpilog_bytes`, …) and `metrics.compute_mode_spans` /
   `filter_signals_by_time` likewise. Callers (`logbench/core/log.py`, `camera_calibration/*`, `verify_trim.py`,
   `vision_analyzer/cli.py`, `tabs/export.py`) keep working untouched.
4. Run the existing suites (`logbench/tests`) + `verify_trim.py` on a real log: identical results before/after.
5. *Later, separate change:* point callers at `wpilog_utils` directly and delete the shim; retire
   `trim_wpilog_bytes` in favor of `wpilog_utils.trim`.

## What the existing code can't do (so `wpilog_utils.trim` is new)

`trim_wpilog_bytes` is one window, verbatim timestamps, no per-entry filtering, and control records copied unparsed to
the front. The new engine needs N segments, re-timing, entry exclusion (which requires parsing control records — the
entry id is in the payload), and a dry-run. Also: the current parse decodes everything (seconds on 10 MB, worse on
100 MB); the index pass should only decode the few DriverStation entries.

## Findings from a real log (`notes/6-20/…decimateBack.wpilog`, 9.8 MB, 314 entries)

- **Bytes are concentrated**: `/RealOutputs` 43 %, `/Vision` 41 %, `/SystemStats` 10 %, `/PowerDistribution` 4 %; the
  two `/Vision/{Left,Right}/RawEstimatedPoses` entries are 14.5 % alone. Size views must roll up by path prefix.
- **A real duplicate exists**: `/Pickup/VelocityRPS` (from `processInputs`) and `/RealOutputs/Pickup/VelocityRPS`.
- **Naive duplicate detection is mostly noise**: 206 of 314 entries are constant (zero axes, empty arrays, protocol
  versions) and hash-match each other. Constants must be classified separately.
- Names carry a leading `/` (`/RealOutputs/…`).
- **Inputs vs outputs**: `/Vision/*`, `/Pickup/*`, `/SystemStats/*`, `/DriverStation/*` are replay inputs
  (`Logger.processInputs`); `/RealOutputs/*` is regenerated by replay. Dropping an input silently breaks
  `simulateJava` replay and `logbench`.
- **The header's extra string is `AdvantageKit`** — third-party tools may key off it. The writer preserves the
  header byte-for-byte. Every entry's metadata is `{"source":"AdvantageKit"}`.
- **`/Timestamp` (int64, AdvantageKit) holds the record's own timestamp in µs** (`1331908` at t = 1.331908 s), one
  per loop cycle (8375 records in this log). It is a *copy of the record time inside the payload*.
- **AdvantageKit writes a whole loop cycle's records at the same timestamp and only logs values that changed**
  (`/DriverStation/Enabled` has 3 records in the entire log). So a "frame" is a distinct log timestamp, and re-timing
  must move whole cycles, never split one.
- The log's first record is at t ≈ 1.33 s, not 0.

## Trim: how re-timing stays "looks really captured" (the core design)

Goal: AdvantageScope should open the output and show a normal-looking log. Rules the writer enforces:

1. **Cycle-atomic.** Kept unit = one AdvantageKit cycle (all records sharing a timestamp). Segment edges snap to
   cycle boundaries; a cycle is never split or straddled.
2. **Timestamps only ever increase, and cycle spacing stays natural.** Within a segment, spacing is the original
   spacing (offset by a constant per segment). Across a seam, spacing between the last cycle of the previous segment and
   the first of the next is one **nominal cycle period** (the log's measured median cycle dt, not an assumed 20 ms).
3. **The gap is made of real cycles, not synthetic ones.** The 200 ms of "disabled" between two autos is composed
   from the actual disabled cycles: the first ~G/2 after the previous segment ends and the last ~G/2 before the next
   begins (whole disabled span if it's shorter than G). Real cadence, real values, zero invented samples. Because
   AdvantageKit only logs changes, the disabled stretch is mostly a flat hold — exactly like a real short disable.
   Gap `G` is set in ms; the UI also shows the equivalent cycle count from the measured cycle period (default 200 ms
   ≈ 10 cycles). `G` = one cycle is allowed.
4. **Payload-embedded time is rewritten.** `/Timestamp` payload := the new record timestamp (µs), so it keeps equalling
   the record time. Any other entry known to mirror record time (detected by "value == its own record ts in µs for
   ≥ 99 % of records") is rewritten the same way and listed in the report. Wall-clock-ish entries
   (`systemTime`-like) are reported, not silently changed — decision at M2 after seeing which exist.
5. **State at each seam is correct.** Control records first (re-stamped to output start), for kept entries only.
   At the first cycle of each segment, for every entry whose value differs from the last value *we emitted* for it, emit
   that value (a diff, so unchanged signals cost nothing and a signal that changed inside the dropped gap is right).
   This replaces `trim_wpilog_bytes`'s "carry forward only if no in-window record", which is wrong for N segments.
6. **Output starts at the source log's own first timestamp** (e.g. 1.33 s), not at the first kept segment's original
   time (e.g. 38 s), so it looks like a normal log.
7. **Header and metadata preserved**; control records re-encoded with the same entry ids and metadata. Non-decreasing
   timestamps and Start-before-data are enforced.
8. **One added entry**, the segment map (below). Its metadata `{"source":"wpilog-janitor"}` distinguishes it from robot data.

A `preserve` gap policy (original timestamps, hole left in place) is a trivial subset of the same writer; keep it as
a non-default option — off the main path and not part of the "looks captured" requirement.

### Segment map (the recoverable note)

Entry `/Janitor/SegmentMap` (type `string`, JSON payload, one record at output start; schema `wpilog-janitor.segmap/v1`):

```json
{ "schema": "wpilog-janitor.segmap/v1",
  "tool_version": "…",
  "source_file": "akit_26-06-20_15-20-19_decimateBack.wpilog",
  "source_bytes": 9768960, "source_t_min": 1.331908, "source_t_max": 396.2,
  "gap_ms": 200, "cycle_period_ms": 20.0,
  "segments": [
    {"kind": "auto", "orig_start": 38.119, "orig_end": 54.015, "new_start": 1.33, "new_end": 17.23, "offset": -36.79,
     "pad_pre_ms": 0, "pad_post_ms": 100}
  ],
  "seams": [{"after_segment": 0, "real_cycles_pre": 5, "real_cycles_post": 5}],
  "rewritten_time_entries": ["/Timestamp"],
  "excluded_entries": ["/RealOutputs/Pickup/VelocityRPS"] }
```

`new = orig + offset` per segment recovers any original time; the same map is what a future "re-stamp the Pi
recorder frames" feature reads. Open check: confirm AdvantageScope displays a string entry like this cleanly (it
should; it's the same as any AKit metadata-style string) — part of the acceptance test.

## `wpilog_utils.index` — the one pass everything reads

Single streaming walk of the records, no payload decode except the DS entries:

```
LogIndex
  header_end, extra_header, total_bytes, t_min, t_max
  cycles: sorted distinct timestamps (array('q') in µs) + median period
  entries[id]: name, type, metadata, first_ts, last_ts, n_records, bytes
  ds_signals: decoded Enabled / Autonomous
  byte_hist: bytes per 1 s bucket (overall + per top-level prefix)   -> timeline density
  mode_spans: [(t0, t1, 'disabled'|'auto'|'teleop')]
```

Records kept as `(entry_id, ts_us, start, end)` in `array.array`, never payload slices, so 100 MB logs are fine.
Cached by `(path, mtime)` like `logbench/server/main.py`.

## Page 1 — Trim (timeline only)

- **Timeline**: canvas strip; auto = green, teleop = blue, disabled = grey (matches vision-analyzer); a
  bytes-per-second density curve behind it; zoom/pan; segment list.
- **Selecting**: click a mode band to add/remove that span (each auto span is its own band — "auto 1 + auto 3, not
  auto 2" works; shift-click for several). Drag for an arbitrary range. Segment rows have editable start/end
  (seconds relative to log start, as `logbench` shows them) and per-segment pre/post pad.
- **Gap**: one global value, default 200 ms.
- **Live savings panel**: original → output bytes, saved bytes and %, per-segment byte cost. Computed by
  `trim.dry_run()`, **the same code path** as the real export, so the preview equals the file you get. (Re-timing
  re-encodes every record with minimal-width headers, which can shrink output slightly vs a verbatim copy.)
  Includes savings from Content-page exclusions, shown as a separate line.
- **Export**: download, or "save next to source as `<stem>_trimmed.wpilog`" (keep the original stem so
  `logbench/server/pairing.py`'s `akit_YY-MM-DD_HH-MM-SS_*` parse still works). Runs `verify` and shows the result.

## Page 2 — Content

Analyses default to the *currently selected time window* (toggle: whole log).

**Where the bytes are** — tree table by path prefix (`/Vision` → `/Vision/Left` → entry): bytes, %, records, Hz,
type; flags `constant`, `replay-input`, `output`, `nt-mirror`. A checkbox per row/subtree adds it to the
**exclusion list** (this is the only place exclusions are made); running savings total.

**Duplicates** — each entry lands in exactly one bucket, in order:
1. *Constant* — one distinct payload across the window. Its own list; never grouped as duplicates of each other.
2. *Exact duplicate* — same type, identical payload sequence. Split: byte-identical (same times) vs value-identical
   with differing times (tolerance setting).
3. *Near duplicate* — step-function resample, ≥ threshold (default 99.9 %) equal; candidates bucketed by type +
   distinct-value fingerprint so it isn't O(n²).
4. *Structural / derived* (stretch) — array-element vs scalar, unit-scaled copies (|r| ≈ 1), `Foo` vs `Foo/Bar`.

Name hints only *propose* pairs (strip `/RealOutputs`, `/NT:` prefixes, compare tails); values *confirm*. A name match
with different values is shown as "same name, different data". Each group: members, bytes each, **bytes recoverable**,
**suggested keeper** (replay-input side over `/RealOutputs`, then shorter path), editable; "apply" adds non-keepers
to the exclusion list. Never auto-drops anything.

**LLM extract** (`wpilog-janitor.extract/v1`, Markdown default + JSON), tiered so it fits in context:
`summary` (size, duration, mode spans, prefix rollup) · `top_offenders` (top 50 by bytes: rate, type, distinct count,
min/max/mean, samples, change rate) · `duplicates` (groups + evidence + keeper) · `constants` (name, type, value) ·
`catalog` (one dense line per entry, optional) · `source_hints` (stretch: grep the robot code for `@AutoLogOutput(key=…)`,
`Logger.recordOutput(…)`, `Logger.processInputs(…)` and attach `file:line`) · `how_to_read` + a prompt template
("keep / drop / dedupe-to-X per entry, cite the field, say what would break replay"), modeled on `logbench.compare/v2`.
"Fit under N tokens" truncates the catalog first, never duplicates/top-offenders. A schema test requires every field to
have a description (same trick as `compare_export.DESCRIPTIONS`).

**Protected profiles** (`classify.py`): `replay` (all `processInputs` inputs + `/DriverStation`, `/SystemStats`,
**`/Timestamp`**), `logbench` (entries `logbench`/`vision-analyzer` read — derived from their lookups, not a second
hand-kept list), `none`. Excluding a protected entry needs an explicit override; `verify` warns if the output can't
serve the chosen profile.

## Verification (`wpilog_utils.verify`, runs after every export)

- Re-parse with the real parser: valid header identical to source; every data record's entry has a control record;
  timestamps non-decreasing; entry set == kept set (+ `/Janitor/SegmentMap`).
- **AdvantageScope-shape checks**: `/Timestamp` payload == record ts for every record; cycle spacing at seams within
  1.5× nominal period; no timestamp regressions; first timestamp == source `t_min`.
- Mode spans in the output match the plan (auto count and durations, within one pad).
- Per-entry record counts == kept segments' counts (+ seam diffs, reported separately).
- `dry_run()` byte total == written file size, exactly.
- Golden: `preserve` mode, no exclusions → `vision-analyzer` metrics over each segment equal the original
  (`verify_trim.py`'s idea).
- **Manual acceptance**: user opens output in AdvantageScope — plays through seams, mode bars right, no warnings,
  `/Janitor/SegmentMap` displays.

## Milestones

Each ends with tests passing and is useful alone.

| # | Deliverable |
|---|---|
| **M0** | `tools/wpilog-utils/` scaffold, `paths.py` bridge, characterization tests, verbatim move of parser + mode spans, `vision_analyzer` shim. Existing logbench tests + `verify_trim.py` unchanged. Synthetic-log builder for tests |
| **M1** | `wpilog_utils.index` + `janitor analyze` CLI (size tree, mode spans, cycle period) — answers "where are my bytes" from the terminal |
| **M2** | `wpilog_utils.trim` (segments, compact re-timing, cycle-atomic, real-cycle gaps, `/Timestamp` rewrite, seam diffs, segment map, exclusions, `dry_run`) + `verify` + `janitor trim` CLI. **Open in AdvantageScope here** — before any UI exists. Biggest correctness risk |
| **M3** | FastAPI + Trim page (timeline, segments, gap, live savings, export). Front-end scaffolding from `logbench/web`; single-file build like `player.singlefile.html` |
| **M4** ✅ | `dedupe.py`, `classify.py` + Content page (tree, constants, duplicate groups, exclusions → savings) |
| **M5** | `extract.py` + export + prompt template; run it on a real log through an LLM and iterate the format on what it gets wrong |
| **M6** | Docs: READMEs, CLAUDE.md "Tools" entry, note in `logbench` README. Later: repoint callers, remove shim; Pi-recorder re-stamp feature |

## Testing

- **Synthetic logs** (builder in `wpilog-utils/tests`): segment edge exactly on a record; edge mid-cycle (snaps);
  pad crossing into another segment (merge); touching/overlapping segments; zero and one-cycle gap; disabled span
  shorter than G; entry existing only in a dropped region; entry started in a dropped region but used later;
  timestamps > 2³² µs (header widths); minimal vs wide source headers; truncated final record; log with no
  `DriverStation/Enabled` (manual segments only); log with no `/Timestamp` entry.
- **Round-trip**: parse(output) == parse(source) restricted to kept cycles, per entry, after applying the segment
  map's offsets (also proves the map is sufficient to recover original times).
- **Golden real logs** (`notes/6-20/*`, skipped if absent): the verification list above.
- **Dedupe**: one synthetic case per bucket, incl. constants-must-not-group and same-name-different-data.
- **Extract**: schema snapshot + description coverage.
- Performance: index 100 MB in ~10 s; dry-run over an existing index ~2 s; timeline interaction fully client-side.

## Remaining risks

1. **AdvantageScope quirks I can't check from here** — hence M2 ends with the user opening a real output before UI work.
   Things to look at: seam smoothness, that a string entry `/Janitor/SegmentMap` is fine, and that the rewritten
   `/Timestamp` is consistent.
2. **AdvantageKit replay across a seam.** Viewing is the requirement; deterministic `simulateJava` replay of a
   compacted log is untested. One manual check before relying on it.
3. **Other payload-embedded time** (`systemTime`-like entries, DS-match-time) — the "value == own ts" detector will
   tell us at M2 what exists; anything wall-clock-ish is reported rather than silently altered.
4. **Dedupe false positives** on low-entropy signals — distinct-value floor + visible evidence, never auto-drop.
5. **Multi-file `.hoot`** logs are separate and untouched; the extract says so.
6. **Shim drift** — until the shim is removed, both import paths exist; the characterization tests are what keep
   them honest.

## Still open (small)

- Are you OK with `pyproject.toml` + bridge now, `pip install -e` later? (Assumed yes.)
- ~~Should `preserve` gap policy exist at all?~~ Settled 9/22: `preserve` is the default, `compact` is opt-in (see Decisions).
