"""
Trimming a WPILog to a time window.

`trim_wpilog_bytes` is the original single-window trim, moved verbatim from vision_analyzer.parser
(M0), kept for its existing callers. Below it is the multi-segment engine described in
docs/wpilog-janitor-plan.md ("Trim: how re-timing stays 'looks really captured'"):

    index = build_index(raw)
    plan = TrimPlan(segments=mode_segments(index, ['auto']), gap_ms=200)
    resolved = resolve_plan(index, plan)         # cycle-snapped ranges + new time offsets
    stats = dry_run(raw, index, plan)            # exact output size, nothing built
    out, stats = trim_log(raw, index, plan)      # the new .wpilog bytes

`dry_run` and `trim_log` share one code path (`_run`), so the size shown in a preview is the size of
the file you get.
"""
import bisect
import json
import logging
import struct
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .index import LogIndex
from .records import (build_record, encode_record, encode_start_payload, iter_records, parse_control,
                      wpilog_header_end)

log = logging.getLogger(__name__)


def trim_wpilog_bytes(raw: bytes, t_lo: float, t_hi: float) -> bytes:
    """
    Return a new WPILog byte stream containing only records within
    [t_lo, t_hi] (absolute seconds, same domain as parse_wpilog_bytes'
    timestamps), plus enough context to stay correct:

    - Control records (entry_id == 0, registering signal names/types) are
      always kept regardless of timestamp, since any kept data record needs
      its entry registered for the output to remain a valid log.
    - For every entry that has zero records inside the window at all (e.g. a
      config value or piece of metadata logged once at startup and never
      repeated), its last pre-window record is carried forward into the
      output, re-stamped to t_lo. Without this, such a signal would vanish
      from the trimmed log entirely, even though its value was still in
      effect throughout the window. Entries that already have at least one
      record inside the window are NOT carried forward — doing so would
      inject a record that never existed in the original log at that
      timestamp, skewing sample counts and any analysis that compares the
      trimmed log against the original over the same time range.

    Records that are kept verbatim are copied byte-for-byte — WPILog is a
    flat, sequential stream with no internal offset references, so trimming
    never requires re-encoding payloads. Carried-forward records are the one
    exception: they're rebuilt via build_record with a new timestamp, since
    the original record's timestamp field may be too narrow to hold t_lo.
    """
    header_end = wpilog_header_end(raw)
    control_records: List[bytes] = []
    inwindow_records: List[bytes] = []
    last_before: Dict[int, bytes] = {}  # entry_id -> payload of its last pre-window record
    entries_inwindow: set = set()

    n_total = 0
    for entry_id, ts_sec, payload, start, end in iter_records(raw, header_end):
        n_total += 1
        if entry_id == 0:
            control_records.append(raw[start:end])
        elif ts_sec < t_lo:
            last_before[entry_id] = payload
        elif ts_sec <= t_hi:
            inwindow_records.append(raw[start:end])
            entries_inwindow.add(entry_id)
        # else: ts_sec > t_hi — dropped, no carry-forward needed past the end

    new_ts_us = int(round(t_lo * 1_000_000.0))
    carried = [
        build_record(eid, new_ts_us, payload)
        for eid, payload in last_before.items()
        if eid not in entries_inwindow
    ]

    out = b''.join([raw[:header_end], *control_records, *carried, *inwindow_records])
    n_kept = len(control_records) + len(carried) + len(inwindow_records)
    log.info(
        'Trimmed wpilog to [%.1f, %.1f] s — %d/%d records kept (%d carried forward), '
        '%d bytes -> %d bytes (%.1f%% smaller)',
        t_lo, t_hi, n_kept, n_total, len(carried), len(raw), len(out),
        100.0 * (1 - len(out) / len(raw)) if raw else 0.0,
    )
    return out


# ═══ Multi-segment trim engine ════════════════════════════════════════════════════════════════

SEGMENT_MAP_ENTRY = '/Janitor/SegmentMap'
SEGMENT_MAP_SCHEMA = 'wpilog-janitor.segmap/v1'
_JANITOR_METADATA = '{"source":"wpilog-janitor"}'


@dataclass(frozen=True)
class Segment:
    """A time range to keep: [start, end) in seconds relative to the log's first record — the same
    domain as `LogIndex.mode_spans()`. Snapped to whole cycles when resolved."""
    start: float
    end: float
    label: str = ''
    pad_pre_ms: float = 0.0     # extra real cycles kept before `start`
    pad_post_ms: float = 0.0    # extra real cycles kept after `end`


@dataclass
class TrimPlan:
    segments: Sequence[Segment]
    # Real time kept on each seam between two kept segments (see resolve_plan); 'compact' only.
    gap_ms: float = 200.0
    gap_policy: str = 'compact'           # 'compact': re-time so seams are short | 'preserve': keep original timestamps
    exclude: Sequence[str] = ()           # entry names to drop entirely ('/' prefix optional)
    exclude_prefixes: Sequence[str] = ()  # drop these entries and everything beneath them
    source_name: str = ''                 # recorded in the segment map only


@dataclass
class KeptRange:
    """A run of consecutive source cycles [first, last] that is kept and moved by `offset_us`."""
    first: int
    last: int
    lo_us: int                  # source timestamp of cycle `first`
    hi_us: Optional[int]        # source timestamp of cycle last+1 (exclusive bound); None = end of log
    offset_us: int              # new_ts = source_ts + offset_us

    @property
    def n_cycles(self) -> int:
        return self.last - self.first + 1


@dataclass
class ResolvedSegment:
    label: str
    orig_first_s: float         # first / last kept cycle of the segment itself (pads excluded),
    orig_last_s: float          # seconds relative to the source's first record
    new_first_s: float          # the same, in the output log's clock (relative to output start)
    new_last_s: float
    offset_s: float             # new = orig + offset, in absolute log seconds
    pad_pre_ms: float
    pad_post_ms: float


@dataclass
class ResolvedPlan:
    ranges: List[KeptRange]
    segments: List[ResolvedSegment]
    seams: List[dict]
    nominal_period_us: int
    out_start_us: int
    gap_cycles: int
    excluded_ids: Set[int]
    warnings: List[str] = field(default_factory=list)


@dataclass
class TrimStats:
    bytes_out: int
    source_bytes: int
    n_records_out: int
    n_carried: int              # records written at a range start to restate state from a dropped stretch
    n_cycles_out: int
    n_cycles_source: int
    n_source_data_records: int
    n_excluded_records: int
    control_records_dropped: int    # source Finish / late SetMetadata records not reproduced

    @property
    def saved_bytes(self) -> int:
        return self.source_bytes - self.bytes_out

    @property
    def saved_pct(self) -> float:
        return 100.0 * self.saved_bytes / self.source_bytes if self.source_bytes else 0.0


def mode_segments(index: LogIndex, modes: Iterable[str], which: Optional[Iterable[int]] = None,
                  pad_pre_ms: float = 0.0, pad_post_ms: float = 0.0) -> List[Segment]:
    """One Segment per DriverStation span whose mode is in `modes` ('auto', 'teleop', 'disabled').
    `which` optionally picks spans by 0-based order *among the matching ones* (e.g. modes=['auto'],
    which=[0, 2] keeps the first and third autonomous periods)."""
    modes = set(modes)
    matching = [(a, b, m) for a, b, m in index.mode_spans() if m in modes]
    pick = set(which) if which is not None else None
    return [Segment(a, b, m, pad_pre_ms, pad_post_ms) for i, (a, b, m) in enumerate(matching)
            if pick is None or i in pick]


def _matches(name: str, exact: Set[str], prefixes: Sequence[str]) -> bool:
    n = name.lstrip('/')
    return n in exact or any(n == p or n.startswith(p + '/') for p in prefixes)


def resolve_excluded_ids(index: LogIndex, plan: TrimPlan) -> Set[int]:
    exact = {x.lstrip('/') for x in plan.exclude}
    prefixes = [x.strip('/') for x in plan.exclude_prefixes]
    return {e.id for e in index.entries.values() if _matches(e.name, exact, prefixes)}


def resolve_plan(index: LogIndex, plan: TrimPlan) -> ResolvedPlan:
    """Turn user segments into whole-cycle ranges and decide where each lands in the output clock.

    * Every segment is snapped to cycles: a cycle (all records of one loop iteration) is never split.
    * Overlapping / touching ranges merge.
    * 'compact': between two ranges that stay apart, keep `gap_ms` of REAL cycles taken from either
      side of the cut (half after the earlier range, half before the later one), so the seam is made
      of genuine disabled-time data. If the whole dropped stretch is no longer than that, it is kept
      whole and the ranges merge. The two sides are then joined one nominal cycle period apart.
    * 'preserve': no gap handling, original timestamps kept.
    """
    if plan.gap_policy not in ('compact', 'preserve'):
        raise ValueError(f"gap_policy must be 'compact' or 'preserve', got {plan.gap_policy!r}")
    if not index.time_ordered:
        raise ValueError('log records are not in time order; trimming that is not supported yet')
    cyc = index.cycles_us
    n = len(cyc)
    if n == 0:
        raise ValueError('log contains no data records')
    if not plan.segments:
        raise ValueError('no segments selected')

    warnings: List[str] = []
    period = index.cycle_period_us()
    t0 = index.t_min_us
    t_last = cyc[-1]

    def cycle_range(start_us: int, end_us: int) -> Tuple[int, int]:
        i0 = bisect.bisect_left(cyc, start_us)
        i1 = n if end_us > t_last else bisect.bisect_left(cyc, end_us)
        return i0, i1

    padded: List[List[int]] = []
    own: List[Tuple[Segment, int, int]] = []
    for seg in plan.segments:
        if not seg.end > seg.start:
            raise ValueError(f'segment end must be after start: {seg}')
        s_us, e_us = t0 + round(seg.start * 1e6), t0 + round(seg.end * 1e6)
        i0, i1 = cycle_range(s_us, e_us)
        if i0 >= i1:
            warnings.append(f'segment {seg.label or ""}[{seg.start:.3f}, {seg.end:.3f}) contains no cycles; skipped')
            continue
        p0, _ = cycle_range(s_us - round(seg.pad_pre_ms * 1000), e_us)
        _, p1 = cycle_range(s_us, e_us + round(seg.pad_post_ms * 1000))
        padded.append([min(p0, i0), max(p1, i1)])
        own.append((seg, i0, i1))
    if not padded:
        raise ValueError('none of the selected segments contain any data')
    own.sort(key=lambda t: (t[1], t[2]))

    padded.sort()
    merged: List[List[int]] = [padded[0]]
    for a, b in padded[1:]:
        if a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])

    budget = max(0, round(plan.gap_ms * 1000 / period)) if plan.gap_policy == 'compact' else 0
    h_before, h_after = (budget + 1) // 2, budget // 2
    seams: List[dict] = []
    if plan.gap_policy == 'compact':
        joined: List[List[int]] = [merged[0]]
        for a, b in merged[1:]:
            prev = joined[-1]
            dropped = a - prev[1]
            if dropped <= budget:
                prev[1] = b                        # short enough to keep whole: no seam at all
            else:
                seams.append({'dropped_cycles': dropped, 'real_cycles_kept_before': h_before,
                              'real_cycles_kept_after': h_after})
                prev[1] += h_before
                joined.append([a - h_after, b])
        merged = joined
    else:
        seams = [{'dropped_cycles': merged[i + 1][0] - merged[i][1], 'real_cycles_kept_before': 0,
                  'real_cycles_kept_after': 0} for i in range(len(merged) - 1)]

    ranges: List[KeptRange] = []
    out_start = cyc[merged[0][0]] if plan.gap_policy == 'preserve' else cyc[0]
    for i, (a, b) in enumerate(merged):
        if plan.gap_policy == 'preserve':
            off = 0
        elif i == 0:
            off = out_start - cyc[a]
        else:
            prev = ranges[-1]
            off = (cyc[prev.last] + prev.offset_us + period) - cyc[a]
        ranges.append(KeptRange(a, b - 1, cyc[a], cyc[b] if b < n else None, off))

    def range_of(ci: int) -> KeptRange:
        for r in ranges:
            if r.first <= ci <= r.last:
                return r
        raise AssertionError('segment cycle outside every kept range')

    segs: List[ResolvedSegment] = []
    for seg, i0, i1 in own:
        r = range_of(i0)
        segs.append(ResolvedSegment(
            label=seg.label,
            orig_first_s=(cyc[i0] - t0) / 1e6, orig_last_s=(cyc[i1 - 1] - t0) / 1e6,
            new_first_s=(cyc[i0] + r.offset_us - out_start) / 1e6,
            new_last_s=(cyc[i1 - 1] + r.offset_us - out_start) / 1e6,
            offset_s=r.offset_us / 1e6, pad_pre_ms=seg.pad_pre_ms, pad_post_ms=seg.pad_post_ms))

    excluded = resolve_excluded_ids(index, plan)
    if index.cycle_entry_id in excluded:
        warnings.append(f'{index.entries[index.cycle_entry_id].name} is excluded; the output has no cycle marker')
    return ResolvedPlan(ranges=ranges, segments=segs, seams=seams, nominal_period_us=period,
                        out_start_us=out_start, gap_cycles=budget, excluded_ids=excluded, warnings=warnings)


def segment_map(index: LogIndex, plan: TrimPlan, resolved: ResolvedPlan) -> dict:
    """The recoverable note stored in the output as /Janitor/SegmentMap. For every time inside a segment,
    new = orig + offset (absolute log seconds); all `orig_*` / `new_*` values are absolute log seconds."""
    from . import __version__
    t_src = index.t_min_us / 1e6
    t_out = resolved.out_start_us / 1e6
    return {
        'schema': SEGMENT_MAP_SCHEMA,
        'tool_version': __version__,
        'source_file': plan.source_name,
        'source_bytes': index.total_bytes,
        'source_t_min': t_src,
        'source_t_max': index.t_max_us / 1e6,
        'output_t_start': t_out,
        'gap_policy': plan.gap_policy,
        'gap_ms': plan.gap_ms,
        'cycle_period_ms': resolved.nominal_period_us / 1000.0,
        'segments': [{
            'kind': s.label,
            'orig_first': t_src + s.orig_first_s, 'orig_last': t_src + s.orig_last_s,
            'new_first': t_out + s.new_first_s, 'new_last': t_out + s.new_last_s,
            'offset': s.offset_s, 'pad_pre_ms': s.pad_pre_ms, 'pad_post_ms': s.pad_post_ms,
        } for s in resolved.segments],
        'seams': resolved.seams,
        'rewritten_time_entries': sorted(e.name for e in index.entries.values() if e.time_mirror),
        'excluded_entries': sorted(index.entries[i].name for i in resolved.excluded_ids),
    }


def _run(raw: bytes, index: LogIndex, plan: TrimPlan, resolved: ResolvedPlan,
         sink: Callable[[bytes], None]) -> TrimStats:
    """The one writer. Streams the source once, handing output chunks to `sink` in file order.

    Per kept range, the first cycle is buffered so that, before it is written, every entry that
    changed (or first appeared) during the dropped stretch gets one record restating its value —
    unless the cycle itself already writes that entry. Entries are (re)started lazily, right before
    their first written record, at that record's new timestamp.
    """
    ranges = resolved.ranges
    excluded = resolved.excluded_ids
    mirror_ids = {e.id for e in index.entries.values() if e.time_mirror}

    seg_map_id = max(index.entries, default=0) + 1
    seg_map_payload = json.dumps(segment_map(index, plan, resolved), separators=(',', ':')).encode('utf-8')

    defs: Dict[int, List[str]] = {}          # entry id -> [name, type, metadata] as last seen in the source
    started: Set[int] = set()
    last_src: Dict[int, bytes] = {}          # entry id -> source payload as of the latest source record
    last_out: Dict[int, bytes] = {}          # entry id -> source payload behind the latest record we wrote
    st = dict(bytes=0, records=0, carried=0, data=0, excluded=0, dropped_ctrl=0)

    def put(b: bytes) -> None:
        st['bytes'] += len(b)
        sink(b)

    def emit_data(eid: int, new_ts: int, payload: bytes) -> None:
        if eid not in started:
            name, typ, meta = defs[eid]
            put(encode_record(0, new_ts, encode_start_payload(eid, name, typ, meta)))
            started.add(eid)
        out = struct.pack('<q', new_ts) if eid in mirror_ids else payload
        put(encode_record(eid, new_ts, out))
        st['records'] += 1
        last_out[eid] = payload

    put(raw[:index.header_end])

    ri = 0
    opened = False
    buffering = False
    first_range_done = False
    pending: List[Tuple[int, bytes]] = []
    pending_ts = 0

    def flush_pending() -> None:
        nonlocal buffering, first_range_done
        if not buffering:
            return
        buffering = False
        new_ts = pending_ts + ranges[ri].offset_us
        if not first_range_done:
            first_range_done = True
            put(encode_record(0, new_ts, encode_start_payload(seg_map_id, SEGMENT_MAP_ENTRY, 'string', _JANITOR_METADATA)))
            put(encode_record(seg_map_id, new_ts, seg_map_payload))
            st['records'] += 1
        written = {eid for eid, _ in pending}
        for eid in sorted(last_src):
            if eid not in written and last_out.get(eid) != last_src[eid]:
                emit_data(eid, new_ts, last_src[eid])
                st['carried'] += 1
        for eid, payload in pending:
            emit_data(eid, new_ts, payload)
        pending.clear()

    for entry_id, ts_sec, payload, _s, _e in iter_records(raw, index.header_end):
        if entry_id == 0:
            ctrl = parse_control(payload)
            if ctrl is None:
                continue
            if ctrl.kind == 'start':
                defs[ctrl.entry_id] = [ctrl.name, ctrl.type, ctrl.metadata]
            elif ctrl.kind == 'set_metadata' and ctrl.entry_id in defs:
                defs[ctrl.entry_id][2] = ctrl.metadata
                if ctrl.entry_id in started:
                    st['dropped_ctrl'] += 1
            else:
                st['dropped_ctrl'] += 1
            continue
        if entry_id not in defs:
            continue
        st['data'] += 1
        if entry_id in excluded:
            st['excluded'] += 1
            continue
        ts_us = int(round(ts_sec * 1_000_000))

        while ri < len(ranges) and ranges[ri].hi_us is not None and ts_us >= ranges[ri].hi_us:
            flush_pending()
            ri += 1
            opened = False
        if ri < len(ranges) and ts_us >= ranges[ri].lo_us:
            if not opened:
                opened, buffering, pending_ts = True, True, ts_us
            if buffering and ts_us != pending_ts:
                flush_pending()
            if buffering:
                pending.append((entry_id, payload))
            else:
                emit_data(entry_id, ts_us + ranges[ri].offset_us, payload)
        last_src[entry_id] = payload
    if ri < len(ranges):
        flush_pending()

    return TrimStats(bytes_out=st['bytes'], source_bytes=len(raw), n_records_out=st['records'],
                     n_carried=st['carried'], n_cycles_out=sum(r.n_cycles for r in ranges),
                     n_cycles_source=len(index.cycles_us), n_source_data_records=st['data'],
                     n_excluded_records=st['excluded'], control_records_dropped=st['dropped_ctrl'])


def dry_run(raw: bytes, index: LogIndex, plan: TrimPlan,
            resolved: Optional[ResolvedPlan] = None) -> TrimStats:
    """Exact size and record counts of `trim_log`'s output without building it."""
    resolved = resolved or resolve_plan(index, plan)
    return _run(raw, index, plan, resolved, lambda b: None)


def trim_log(raw: bytes, index: LogIndex, plan: TrimPlan,
             resolved: Optional[ResolvedPlan] = None) -> Tuple[bytes, TrimStats]:
    resolved = resolved or resolve_plan(index, plan)
    chunks: List[bytes] = []
    stats = _run(raw, index, plan, resolved, chunks.append)
    return b''.join(chunks), stats
