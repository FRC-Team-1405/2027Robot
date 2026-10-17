# wpilog-utils

Shared, stdlib-only library for reading and rewriting FRC `.wpilog` files. No UI, no analysis
opinions — just the file format, driver-station modes, and trimming. Used by
[`wpilog-janitor`](../wpilog-janitor), `logbench`, `vision-analyzer` and `camera-calibration`.
Design and rationale: [`docs/wpilog-janitor-plan.md`](../../docs/wpilog-janitor-plan.md).

## Modules

| Module | What it has |
|---|---|
| `records` | header, `iter_records` (with byte ranges), `encode_record` (minimal-width headers), `parse_control` (Start / Finish / SetMetadata) |
| `decode` | `parse_wpilog(path)` → `{signal: [(t, value), ...]}` (moved verbatim from `vision_analyzer.parser`) |
| `modes` | `compute_mode_spans` (disabled / auto / teleop), `filter_signals_by_time`. Mode comes from the first source a log has: AdvantageKit `DriverStation/Enabled` + `Autonomous`, WPILib `DS:enabled` + `DS:autonomous`, or the NT-mirrored FMS control word `NT:/FMSInfo/FMSControlData` (plain DataLogManager `FRC_*.wpilog`, e.g. competition logs) — see `mode_signals` |
| `index` | `build_index(raw)` → `LogIndex`: per-entry bytes, loop **cycles**, bytes per second, mode spans. One streaming pass, no payload decoding |
| `trim` | `trim_wpilog_bytes` (original single window) and the multi-segment engine: `TrimPlan`, `resolve_plan`, `dry_run`, `trim_log`. `TrimPlan.keep_everywhere` keeps chosen entries for the whole log, not just the segments (original timestamps only); `MATCH_CONTEXT_ENTRIES` is the battery/mode/match-info set the WPILog Janitor keeps by default |
| `reorder` | `order_report` (what is out of time order, one pass), `reorder_log` (stable sort by timestamp: a time-ordered copy with nothing dropped or changed), `verify_reorder` (independent check) — for plain WPILib logs, whose NT mirroring writes records late |
| `verify` | `verify_trim` — independent check of an output against its source and plan; streams the source, so memory scales with what is kept, not with the log |

## Using it

Tools reach it through a `paths.py` `sys.path` bridge (the repo's convention — no install step). It also
has a `pyproject.toml`, so `pip install -e tools/wpilog-utils` works and makes the bridge a no-op.

```python
from wpilog_utils.index import load_index
from wpilog_utils.trim import TrimPlan, mode_segments, estimate_size, dry_run, resolve_plan, trim_log
from wpilog_utils.verify import verify_trim

raw, index = load_index('match.wpilog')
plan = TrimPlan(mode_segments(index, ['auto']), gap_ms=200)     # keep every auto period
print(estimate_size(index, plan))                                # instant, from the index alone (within ~1%)
print(dry_run(raw, index, plan).bytes_out)                       # exact size, one pass, nothing built
out, stats = trim_log(raw, index, plan)
assert verify_trim(out, raw, index, plan, resolve_plan(index, plan)).ok
```

## How trimming keeps the output looking captured

* **Cycles, not records.** AdvantageKit writes all records of a loop iteration at one timestamp and logs an
  int64 `/Timestamp` once per iteration. A cycle is never split.
* **Re-timed, short seams.** Between kept segments the tool keeps `gap_ms` of *real* cycles from either side
  of the cut and joins them one normal cycle period apart. No invented samples.
* **Time inside payloads is rewritten.** `/Timestamp`'s value equals its record time, so it is re-stamped.
* **State is restated** at each range start for entries that changed (or first appeared) in dropped time.
* **Header untouched** (`AdvantageKit` marker survives byte-for-byte).
* **Recoverable.** `/Janitor/SegmentMap` (JSON string) holds `new = orig + offset` per segment.

## Tests

```bash
cd tools/wpilog-utils && python -m pytest
```

`tests/test_characterization.py` holds the moved parser/mode/trim code to fingerprints captured from the
original `vision_analyzer` code on the `notes/6-20` logs (skipped if those logs are absent).
`tests/wpilog_builder.py` builds synthetic logs; the WPILog Janitor's tests reuse it.

## Logging

Logs to the `wpilog_utils` logger and configures nothing. `vision_analyzer` and `camera_calibration` attach
their file handlers to it so the parser's "PARSING STOPPED EARLY" errors still reach their log files.

## Known limits

* Records must be in time order (true of every AdvantageKit log seen so far); an out-of-order log is refused
  rather than mis-trimmed.
* Finish records and SetMetadata after an entry started are not reproduced (counted in `TrimStats`).
* A truncated final record (log ended mid-write) is dropped.
