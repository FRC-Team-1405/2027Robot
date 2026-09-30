"""
Independent check of a trimmed log against its source and plan.

Deliberately does not reuse the writer's logic: it re-reads both files and asserts the properties
that make the output trustworthy in AdvantageScope and replay tools:

  * the header (incl. the "AdvantageKit" marker) is byte-identical to the source
  * record timestamps never go backwards and every data record's entry was started before it
  * the output's cycle timeline is exactly the plan's ranges laid end to end (seams are one nominal
    period wide, no cycle split or duplicated)
  * every source record inside a kept range appears in the output, moved by that range's offset,
    with time-mirroring entries (AdvantageKit's /Timestamp) re-stamped to equal their record time
  * nothing else appears except: the segment-map entry, and restatement records sitting exactly on
    a range's first cycle
  * at the start of every range, each entry's value in the output equals its value in the source
    at that moment (the restatement did its job)
  * entries excluded by the plan are absent, and nothing but the plan's exclusions is missing
"""
import bisect
import json
import struct
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .index import LogIndex, build_index
from .records import iter_records, parse_control
from .trim import SEGMENT_MAP_ENTRY, ResolvedPlan, TrimPlan


@dataclass
class VerifyReport:
    issues: List[str] = field(default_factory=list)
    info: Dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.issues

    def __str__(self) -> str:
        head = 'OK' if self.ok else f'{len(self.issues)} ISSUE(S)'
        return head + ''.join(f'\n  - {i}' for i in self.issues[:25]) + \
            (f'\n  ... and {len(self.issues) - 25} more' if len(self.issues) > 25 else '')


def _records(raw: bytes, header_end: int):
    """(defs {id: (name,type)}, data [(eid, ts_us, payload)], starts [(eid, ts_us)]) in file order.
    Used for the OUTPUT, which is small; the source is scanned by `_scan_source` instead."""
    defs, data, starts = {}, [], []
    for eid, ts, payload, _s, _e in iter_records(raw, header_end):
        ts_us = int(round(ts * 1e6))
        if eid == 0:
            c = parse_control(payload)
            if c is not None and c.kind == 'start':
                defs[c.entry_id] = (c.name, c.type)
                starts.append((c.entry_id, ts_us))
        else:
            data.append((eid, ts_us, payload))
    return defs, data, starts


def _scan_source(raw: bytes, index: LogIndex, resolved: ResolvedPlan, mirror_names):
    """One streaming pass over the source (memory ~ what is kept, not the whole log). Returns
    (expected Counter of (name, new_ts, payload) for every record inside a kept range,
     snapshots: per range, {name: payload} = the source's state at and including the range's first cycle)."""
    ranges = resolved.ranges
    excluded = resolved.excluded_ids
    defs: Dict[int, str] = {}
    last: Dict[str, bytes] = {}
    expected: Counter = Counter()
    snaps: List[Dict[str, bytes]] = [{} for _ in ranges]
    next_snap = 0
    ri = 0
    for eid, ts_sec, payload, _s, _e in iter_records(raw, index.header_end):
        if eid == 0:
            c = parse_control(payload)
            if c is not None and c.kind == 'start':
                defs[c.entry_id] = c.name
            continue
        name = defs.get(eid)
        if name is None or eid in excluded:
            continue
        ts = int(round(ts_sec * 1e6))
        while next_snap < len(ranges) and ts > ranges[next_snap].lo_us:
            snaps[next_snap] = dict(last)              # state before this record = state as of the first cycle
            next_snap += 1
        last[name] = payload
        while ri < len(ranges) and ranges[ri].hi_us is not None and ts >= ranges[ri].hi_us:
            ri += 1
        if ri < len(ranges) and ts >= ranges[ri].lo_us:
            new_ts = ts + ranges[ri].offset_us
            expected[(name, new_ts, struct.pack('<q', new_ts) if name in mirror_names else payload)] += 1
    while next_snap < len(ranges):
        snaps[next_snap] = dict(last)
        next_snap += 1
    return expected, snaps


def verify_trim(out: bytes, raw: bytes, index: LogIndex, plan: TrimPlan, resolved: ResolvedPlan) -> VerifyReport:
    rep = VerifyReport()
    bad = rep.issues.append

    if out[:index.header_end] != raw[:index.header_end]:
        bad('header differs from the source (the AdvantageKit marker must survive byte-for-byte)')

    try:
        out_ix = build_index(out)
    except ValueError as exc:
        bad(f'output is not a readable WPILog: {exc}')
        return rep
    if not out_ix.time_ordered:
        bad('output timestamps go backwards')

    o_defs, o_data, o_starts = _records(out, out_ix.header_end)

    # start-before-use, and no timestamp regression across the whole record stream
    first_start = {}
    for eid, ts in o_starts:
        first_start.setdefault(eid, ts)
    seen_first_data: Dict[int, int] = {}
    for eid, ts, _p in o_data:
        seen_first_data.setdefault(eid, ts)
    for eid, ts in seen_first_data.items():
        if eid not in first_start:
            bad(f'entry {eid} has data but no Start record')
        elif first_start[eid] > ts:
            bad(f'entry {eid} ({o_defs[eid][0]}) starts at {first_start[eid]} after its first data at {ts}')
    out_names = {v[0] for v in o_defs.values()}

    # entry sets
    excluded_names = {index.entries[i].name for i in resolved.excluded_ids}
    for n in excluded_names & out_names:
        bad(f'excluded entry {n} is present in the output')
    missing_entries = ({e.name for e in index.entries.values()} - excluded_names) - out_names
    rep.info['entries_without_output_records'] = sorted(missing_entries)   # legitimately possible (no data in range)

    # cycle timeline
    cyc = index.cycles_us
    expected_cycles = [cyc[i] + r.offset_us for r in resolved.ranges for i in range(r.first, r.last + 1)]
    if list(out_ix.cycles_us) != expected_cycles:
        n_o, n_e = len(out_ix.cycles_us), len(expected_cycles)
        first_diff = next((k for k, (a, b) in enumerate(zip(out_ix.cycles_us, expected_cycles)) if a != b), None)
        bad(f'cycle timeline differs from the plan: {n_o} cycles vs {n_e} expected, first difference at index {first_diff}')
    period = resolved.nominal_period_us
    for a, b in zip(resolved.ranges, resolved.ranges[1:]):
        seam = (cyc[b.first] + b.offset_us) - (cyc[a.last] + a.offset_us)
        if resolved.ranges and plan.gap_policy == 'compact' and seam != period:
            bad(f'seam between cycles {a.last} and {b.first} is {seam} us wide, expected the nominal {period} us')

    # every kept source record present (moved), nothing else extra
    mirror_names = {e.name for e in index.entries.values() if e.time_mirror}
    expected, snapshots = _scan_source(raw, index, resolved, mirror_names)
    actual: Counter = Counter((o_defs[eid][0], ts, p) for eid, ts, p in o_data if eid in o_defs)
    lost = expected - actual
    extra = actual - expected
    if lost:
        (n, t, _p), c = next(iter(lost.items()))
        bad(f'{sum(lost.values())} source record(s) missing from the output, e.g. {n} at {t} us')
    range_starts = {r.lo_us + r.offset_us for r in resolved.ranges}
    stray = [(n, t) for (n, t, _p) in extra if n != SEGMENT_MAP_ENTRY and t not in range_starts]
    if stray:
        bad(f'{len(stray)} unexpected record(s) not on a range start, e.g. {stray[0][0]} at {stray[0][1]} us')
    rep.info['restated_records'] = sum(c for (n, t, _p), c in extra.items() if n != SEGMENT_MAP_ENTRY)

    # value continuity at each range start
    out_by_name: Dict[str, List[Tuple[int, bytes]]] = defaultdict(list)
    for eid, ts, p in o_data:
        if eid in o_defs:
            out_by_name[o_defs[eid][0]].append((ts, p))
    out_ts = {n: [t for t, _ in v] for n, v in out_by_name.items()}
    for r, snap in zip(resolved.ranges, snapshots):
        new_lo = r.lo_us + r.offset_us
        for name, want in snap.items():
            if name in mirror_names:
                continue
            j = bisect.bisect_right(out_ts.get(name, []), new_lo) - 1
            if j < 0:
                bad(f'{name}: no value in the output at range start {new_lo} us (source has one)')
            elif out_by_name[name][j][1] != want:
                bad(f'{name}: value at range start {new_lo} us differs from the source at {r.lo_us} us')

    # time-mirroring entries stay equal to their record time
    for eid, ts, p in o_data:
        if eid in o_defs and o_defs[eid][0] in mirror_names and struct.unpack('<q', p)[0] != ts:
            bad(f'{o_defs[eid][0]} payload {struct.unpack("<q", p)[0]} != record time {ts}')
            break

    # the recoverable note
    sm = out_by_name.get(SEGMENT_MAP_ENTRY)
    if not sm:
        bad(f'{SEGMENT_MAP_ENTRY} entry missing')
    else:
        try:
            note = json.loads(sm[0][1].decode('utf-8'))
            if len(note['segments']) != len(resolved.segments):
                bad('segment map lists a different number of segments than the plan')
        except (ValueError, KeyError) as exc:
            bad(f'segment map is not valid JSON of the expected shape: {exc}')

    rep.info.update(cycles_out=len(out_ix.cycles_us), bytes_out=len(out), bytes_source=len(raw))
    return rep
