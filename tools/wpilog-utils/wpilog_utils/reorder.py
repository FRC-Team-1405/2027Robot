"""
Putting an out-of-order WPILog back in time order, and saying how out of order it was.

Plain WPILib DataLogManager logs (FRC_*.wpilog) mirror NetworkTables into the file stamped with each
value's *publish* time, and values published off the main thread (CTRE swerve telemetry, PhotonVision)
reach the file a few ms -- occasionally a few hundred -- after newer records were written. In the
Albany 2026 match logs over half the records sit behind the newest one already in the file. Each
entry's OWN records are still in order; only the interleaving across entries is off.

So reordering is a stable sort of the records by timestamp. Nothing is dropped, no timestamp or payload
changes, and an entry that was in order keeps exactly its sequence. The trim engine (trim.py) needs
time order, so this is what makes these logs trimmable.

    report = order_report(raw)                  # what is out of order, one pass, nothing built
    out, stats = reorder_log(raw, 'x.wpilog')   # the time-ordered copy
    check = verify_reorder(out, raw)            # independent check: nothing lost, moved or altered

Control records follow their data: an entry's Start is written right before its first record (or at
its own time if it has none), a Finish after its last record, and a SetMetadata that would land before
its entry's Start is folded into that Start. One /Janitor/Reorder string entry records what was done.
"""
import json
from array import array
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .records import encode_record, encode_start_payload, iter_records, parse_control, wpilog_header_end

REORDER_ENTRY = '/Janitor/Reorder'
REORDER_SCHEMA = 'wpilog-janitor.reorder/v1'
_JANITOR_METADATA = '{"source":"wpilog-janitor"}'

# How far behind the newest record so far a late record is, for the summary table.
LATENESS_BUCKETS_MS = (1, 5, 20, 100, 1000)


def _bucket(late_us: int) -> str:
    for edge in LATENESS_BUCKETS_MS:
        if late_us < edge * 1000:
            return f'< {edge} ms'
    return f'>= {LATENESS_BUCKETS_MS[-1]} ms'


def _us(ts_sec: float) -> int:
    return int(round(ts_sec * 1_000_000))


@dataclass
class EntryOrder:
    name: str
    n_records: int = 0
    n_late: int = 0              # records behind the newest record in the file so far
    max_late_us: int = 0
    n_backwards: int = 0         # records older than this entry's own previous record


@dataclass
class OrderReport:
    n_records: int
    n_late: int
    max_late_us: int
    lateness: Dict[str, int]     # bucket label -> late records, in bucket order
    entries: List[EntryOrder]    # entries with late or backwards records, most late first
    n_backwards: int             # records out of order within their own entry (0: reordering keeps every sequence)

    @property
    def ordered(self) -> bool:
        return self.n_late == 0

    def as_dict(self, top: int = 25) -> dict:
        return {
            'ordered': self.ordered, 'n_records': self.n_records, 'n_late': self.n_late,
            'late_pct': 100.0 * self.n_late / max(1, self.n_records), 'max_late_ms': self.max_late_us / 1000.0,
            'lateness': [{'bucket': k, 'records': v} for k, v in self.lateness.items()],
            'n_backwards': self.n_backwards,
            'n_entries_late': len(self.entries),
            'entries': [{'name': e.name, 'records': e.n_records, 'late': e.n_late, 'max_late_ms': e.max_late_us / 1000.0,
                         'backwards': e.n_backwards} for e in self.entries[:top]],
        }


def order_report(raw: bytes) -> OrderReport:
    names: Dict[int, str] = {}
    per: Dict[int, EntryOrder] = {}
    last: Dict[int, int] = {}
    buckets: Counter = Counter()
    newest: Optional[int] = None
    n = late = backwards = max_late = 0
    for eid, ts, payload, _s, _e in iter_records(raw, wpilog_header_end(raw)):
        if eid == 0:
            c = parse_control(payload)
            if c is not None and c.kind == 'start':
                names[c.entry_id] = c.name
            continue
        if eid not in names:
            continue
        ts_us = _us(ts)
        n += 1
        e = per.get(eid)
        if e is None:
            e = per[eid] = EntryOrder(names[eid])
        e.n_records += 1
        if eid in last and ts_us < last[eid]:
            e.n_backwards += 1
            backwards += 1
        last[eid] = ts_us
        if newest is not None and ts_us < newest:
            d = newest - ts_us
            late += 1
            e.n_late += 1
            e.max_late_us = max(e.max_late_us, d)
            max_late = max(max_late, d)
            buckets[_bucket(d)] += 1
        newest = ts_us if newest is None else max(newest, ts_us)
    order = [_bucket(edge * 1000 - 1) for edge in LATENESS_BUCKETS_MS] + [_bucket(10 ** 12)]
    entries = sorted((e for e in per.values() if e.n_late or e.n_backwards), key=lambda e: (-e.n_late, e.name))
    return OrderReport(n_records=n, n_late=late, max_late_us=max_late,
                       lateness={k: buckets[k] for k in order if buckets[k]}, entries=entries, n_backwards=backwards)


@dataclass
class ReorderStats:
    bytes_out: int
    source_bytes: int
    n_records: int               # data records written (the source's, plus the one /Janitor/Reorder record)
    n_moved: int                 # source records that were behind the newest one before them
    control_folded: int          # SetMetadata records folded into their entry's Start


def reorder_log(raw: bytes, source_name: str = '') -> Tuple[bytes, ReorderStats]:
    header_end = wpilog_header_end(raw)
    # Every record that goes to the output, keyed by the time it is written at. Parallel arrays keep
    # 1.5 M records to a few tens of MB.
    keys, starts, ends, kinds = array('q'), array('Q'), array('Q'), array('b')   # kind: 0 data, 1 control
    eids = array('I')
    start_of: Dict[int, Tuple[int, str, str, str]] = {}     # eid -> (ts_us, name, type, metadata)
    last_data: Dict[int, int] = {}
    finishes: List[Tuple[int, int, int, int]] = []         # (ts_us, eid, start, end)
    metas: List[Tuple[int, int, str, int, int]] = []       # (ts_us, eid, metadata, start, end)
    finished = set()
    newest: Optional[int] = None
    moved = 0
    for eid, ts, payload, s, e in iter_records(raw, header_end):
        ts_us = _us(ts)
        if eid == 0:
            c = parse_control(payload)
            if c is None:                                   # unknown control record: keep it where its time says
                keys.append(ts_us); starts.append(s); ends.append(e); kinds.append(1); eids.append(0)
            elif c.kind == 'start':
                if c.entry_id in start_of:
                    raise ValueError(f'entry id {c.entry_id} is started twice ({start_of[c.entry_id][1]!r} and {c.name!r}); '
                                     'reordering a log that reuses entry ids is not supported')
                start_of[c.entry_id] = (ts_us, c.name, c.type, c.metadata)
            elif c.kind == 'finish':
                finishes.append((ts_us, c.entry_id, s, e))
                finished.add(c.entry_id)
            else:
                metas.append((ts_us, c.entry_id, c.metadata, s, e))
            continue
        if eid not in start_of or eid in finished:          # dangling, or data after its Finish: as the parser does, skip
            continue
        if newest is not None and ts_us < newest:
            moved += 1
        newest = ts_us if newest is None else max(newest, ts_us)
        keys.append(ts_us); starts.append(s); ends.append(e); kinds.append(0); eids.append(eid)
        last_data[eid] = max(last_data.get(eid, ts_us), ts_us)

    n_data = len(keys) - sum(kinds)
    # Entries with no data are still declared, at their own time (before any Finish at that same time).
    for eid, (ts_us, *_rest) in start_of.items():
        if eid not in last_data:
            keys.append(ts_us); starts.append(0); ends.append(0); kinds.append(2); eids.append(eid)
    # A Finish goes after its entry's last record; SetMetadata stays at its own time.
    for ts_us, eid, s, e in finishes:
        keys.append(max(ts_us, last_data.get(eid, ts_us))); starts.append(s); ends.append(e); kinds.append(1); eids.append(eid)
    meta_at = len(keys)
    for ts_us, eid, _meta, s, e in metas:
        keys.append(ts_us); starts.append(s); ends.append(e); kinds.append(1); eids.append(eid)
    meta_payload = {meta_at + i: m[2] for i, m in enumerate(metas)}

    order = sorted(range(len(keys)), key=keys.__getitem__)     # stable: ties keep file order

    chunks: List[bytes] = [raw[:header_end]]
    n_out = 0
    folded = 0
    declared = set()
    pending_meta: Dict[int, str] = {}

    def declare(eid: int, at_us: int) -> None:
        ts_us, name, typ, meta = start_of[eid]
        meta = pending_meta.pop(eid, meta)
        chunks.append(encode_record(0, min(ts_us, at_us), encode_start_payload(eid, name, typ, meta)))
        declared.add(eid)

    first_ts = keys[order[0]] if order else 0
    note_id = max(start_of, default=0) + 1
    note = json.dumps({'schema': REORDER_SCHEMA, 'source_file': source_name, 'source_bytes': len(raw),
                       'records_moved': moved, 'records': n_data},
                      separators=(',', ':')).encode('utf-8')
    chunks.append(encode_record(0, first_ts, encode_start_payload(note_id, REORDER_ENTRY, 'string', _JANITOR_METADATA)))
    chunks.append(encode_record(note_id, first_ts, note))
    n_out += 1

    for i in order:
        kind, eid, at = kinds[i], eids[i], keys[i]
        if kind == 0:
            if eid not in declared:
                declare(eid, at)
            chunks.append(raw[starts[i]:ends[i]])
            n_out += 1
        elif kind == 2:
            if eid not in declared:
                declare(eid, at)
        elif i in meta_payload and eid not in declared:
            if eid in start_of:
                pending_meta[eid] = meta_payload[i]
                folded += 1
        elif eid == 0 or eid in declared:
            chunks.append(raw[starts[i]:ends[i]])
    out = b''.join(chunks)
    return out, ReorderStats(bytes_out=len(out), source_bytes=len(raw), n_records=n_out, n_moved=moved,
                             control_folded=folded)


@dataclass
class ReorderCheck:
    issues: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def verify_reorder(out: bytes, raw: bytes) -> ReorderCheck:
    """Re-reads both files. Passes when: the header is identical; output record times never go backwards;
    every record's entry is declared first; the same entries exist (plus /Janitor/Reorder) with the same
    type and final metadata; and each entry's records are exactly the source's, in the source's order
    wherever the source had them in order (sorted by time where it did not)."""
    issues: List[str] = []
    src_h, out_h = wpilog_header_end(raw), wpilog_header_end(out)
    if raw[:src_h] != out[:out_h]:
        issues.append('header differs from the source')

    def read(b: bytes, h: int, check_order: bool):
        defs: Dict[int, List[str]] = {}
        per: Dict[str, List[Tuple[int, bytes]]] = defaultdict(list)
        newest = None
        for eid, ts, payload, _s, _e in iter_records(b, h):
            ts_us = _us(ts)
            if eid == 0:
                c = parse_control(payload)
                if c is not None and c.kind == 'start':
                    defs[c.entry_id] = [c.name, c.type, c.metadata]
                elif c is not None and c.kind == 'set_metadata' and c.entry_id in defs:
                    defs[c.entry_id][2] = c.metadata
                continue
            if eid not in defs:
                if check_order:
                    issues.append(f'record for entry id {eid} at {ts_us} µs before that entry was declared')
                continue
            if check_order and newest is not None and ts_us < newest and len(issues) < 25:
                issues.append(f'{defs[eid][0]}: record at {ts_us} µs is before the previous record ({newest} µs)')
            newest = ts_us if newest is None else max(newest, ts_us)
            per[defs[eid][0]].append((ts_us, payload))
        return {v[0]: (v[1], v[2]) for v in defs.values()}, per

    src_defs, src = read(raw, src_h, False)
    out_defs, got = read(out, out_h, True)
    extra = set(out_defs) - set(src_defs) - {REORDER_ENTRY}
    missing = set(src_defs) - set(out_defs)
    if extra:
        issues.append(f'{len(extra)} entries not in the source, e.g. {sorted(extra)[:3]}')
    if missing:
        issues.append(f'{len(missing)} source entries missing, e.g. {sorted(missing)[:3]}')
    for name in sorted(set(src_defs) & set(out_defs)):
        if src_defs[name] != out_defs[name]:
            issues.append(f'{name}: type/metadata {out_defs[name]} differs from the source {src_defs[name]}')
        want = sorted(src.get(name, []), key=lambda r: r[0])     # stable: an in-order entry is unchanged
        if got.get(name, []) != want:
            issues.append(f'{name}: {len(got.get(name, []))} records, expected the source\'s {len(want)} in time order')
    return ReorderCheck(issues)
