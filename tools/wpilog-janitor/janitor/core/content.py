"""One streaming pass over a log's records, giving every entry a fingerprint and some statistics.

Everything the Content page (and, later, the LLM extract) says about an entry comes from here:

  * sizes and rates inside the analysis window (the whole log, or just the periods being kept)
  * a hash of the *sequence of values* and another of the *(time, value) sequence* -- two entries with the
    same value hash logged the same data; the same time hash too means they did so at the same instants
  * how many distinct values it took (capped), and how often the value changed -- "constant" means one
  * min / max / mean for plain numbers, and the first few distinct raw values for display

Nothing here decodes a payload except a handful of scalar types for min/max/mean. Time-ordered logs only
(the index refuses anything else before this is called).
"""
import hashlib
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from wpilog_utils.records import iter_records, parse_control

Range = Tuple[int, Optional[int]]      # [lo_us, hi_us) in source microseconds; hi None = to the end of the log

DISTINCT_CAP = 64
SAMPLE_COUNT = 3
SAMPLE_BYTES = 96

_SCALAR = {
    'double': ('<d', 8), 'float': ('<f', 4), 'int64': ('<q', 8), 'boolean': ('<B', 1),
}


@dataclass
class EntryStats:
    id: int
    name: str
    type: str
    n_records: int = 0
    bytes: int = 0
    n_changes: int = 0                 # records whose value differs from the previous record's
    distinct: int = 0                  # distinct values seen; stops counting at DISTINCT_CAP
    first_ts_us: Optional[int] = None
    last_ts_us: Optional[int] = None
    seq_hash: str = ''                 # hex digest of the value sequence
    time_hash: str = ''                # hex digest of the (time, value) sequence
    samples: List[bytes] = field(default_factory=list)   # first distinct raw values, truncated
    num_min: Optional[float] = None
    num_max: Optional[float] = None
    num_sum: float = 0.0
    num_n: int = 0

    @property
    def constant(self) -> bool:
        return self.n_records >= 1 and self.distinct == 1

    @property
    def distinct_capped(self) -> bool:
        return self.distinct >= DISTINCT_CAP

    @property
    def num_mean(self) -> Optional[float]:
        return self.num_sum / self.num_n if self.num_n else None


def _digest() -> 'hashlib._Hash':
    return hashlib.blake2b(digest_size=8)


def analyze_content(raw: bytes, header_end: int, ranges: Optional[Sequence[Range]] = None, entries: Optional[Dict] = None) -> Dict[int, EntryStats]:
    """Walk the log once. `ranges` (sorted, source microseconds, as in `resolve_plan(...).ranges`) restricts
    the analysis to those periods; None means the whole log. Entries with no record in the window are still
    returned, with n_records == 0.

    Pass `entries` (a LogIndex's `entries`) to stop reading as soon as the last period ends: the log is
    time-ordered, so nothing after it can matter, and every entry is already known from the index. Without it
    the whole file is read so that entries started after the window are still listed."""
    stats: Dict[int, EntryStats] = {}
    hv: Dict[int, 'hashlib._Hash'] = {}
    ht: Dict[int, 'hashlib._Hash'] = {}
    prev: Dict[int, bytes] = {}
    seen: Dict[int, set] = {}
    ri = 0
    early_stop = ranges is not None and entries is not None
    if entries is not None:
        for e in entries.values():
            stats[e.id] = EntryStats(e.id, e.name, e.type)
            hv[e.id], ht[e.id], seen[e.id] = _digest(), _digest(), set()

    for eid, ts_sec, payload, start, end in iter_records(raw, header_end):
        if eid == 0:
            c = parse_control(payload)
            if c is not None and c.kind == 'start' and c.entry_id not in stats:
                stats[c.entry_id] = EntryStats(c.entry_id, c.name, c.type)
                hv[c.entry_id] = _digest()
                ht[c.entry_id] = _digest()
                seen[c.entry_id] = set()
            continue
        st = stats.get(eid)
        if st is None:
            continue
        ts = int(round(ts_sec * 1_000_000))
        if ranges is not None:
            while ri < len(ranges) and ranges[ri][1] is not None and ts >= ranges[ri][1]:
                ri += 1
            if ri >= len(ranges):
                if early_stop:
                    break
                continue
            if ts < ranges[ri][0]:
                continue

        n = len(payload)
        lp = n.to_bytes(4, 'little')
        hv[eid].update(lp)
        hv[eid].update(payload)
        ht[eid].update(ts.to_bytes(8, 'little', signed=False))
        ht[eid].update(lp)
        ht[eid].update(payload)

        st.n_records += 1
        st.bytes += end - start
        if st.first_ts_us is None:
            st.first_ts_us = ts
        st.last_ts_us = ts

        p = prev.get(eid)
        if p is None or p != payload:
            if p is not None:
                st.n_changes += 1
            prev[eid] = payload
        s = seen[eid]
        if payload not in s and len(s) < DISTINCT_CAP:
            s.add(payload)
            st.distinct = len(s)
            if len(st.samples) < SAMPLE_COUNT:
                st.samples.append(payload[:SAMPLE_BYTES])

        sc = _SCALAR.get(st.type)
        if sc is not None and n == sc[1]:
            v = float(struct.unpack_from(sc[0], payload)[0])
            if v == v:                                   # not NaN
                st.num_n += 1
                st.num_sum += v
                if st.num_min is None or v < st.num_min:
                    st.num_min = v
                if st.num_max is None or v > st.num_max:
                    st.num_max = v

    for eid, st in stats.items():
        st.seq_hash = hv[eid].hexdigest()
        st.time_hash = ht[eid].hexdigest()
    return stats


def collect_sequences(raw: bytes, header_end: int, wanted: set, ranges: Optional[Sequence[Range]] = None) -> Dict[int, List[int]]:
    """For the entries in `wanted` only: the value of every record in the window, as an int fingerprint
    (`hash(payload)`, stable within this process), in order. Used to compare candidate near-duplicates."""
    seqs: Dict[int, List[int]] = {eid: [] for eid in wanted}
    ri = 0
    for eid, ts_sec, payload, _s, _e in iter_records(raw, header_end):
        if eid == 0 or eid not in seqs:
            continue
        if ranges is not None:
            ts = int(round(ts_sec * 1_000_000))
            while ri < len(ranges) and ranges[ri][1] is not None and ts >= ranges[ri][1]:
                ri += 1
            if ri >= len(ranges):
                break                                    # time-ordered: nothing after the last period matters
            if ts < ranges[ri][0]:
                continue
        seqs[eid].append(hash(payload))
    return seqs


def preview_value(payload: bytes, typ: str, limit: int = 90) -> str:
    """A short, human-readable rendering of one raw value."""
    from wpilog_utils.decode import decode_payload
    try:
        v = decode_payload(payload, typ)
    except Exception:
        v = None
    if v is None:
        if typ in ('string', 'json'):
            text = payload.decode('utf-8', 'replace')
        else:
            text = f'{len(payload)} bytes'
    elif isinstance(v, list) and len(v) > 4:
        text = '[' + ', '.join(_short(x) for x in v[:4]) + f', … {len(v)} items]'
    elif isinstance(v, list):
        text = '[' + ', '.join(_short(x) for x in v) + ']'
    else:
        text = _short(v)
    return text if len(text) <= limit else text[:limit - 1] + '…'


def _short(x) -> str:
    if isinstance(x, float):
        return f'{x:.6g}'
    if isinstance(x, dict):
        return '{' + ', '.join(f'{k}={_short(v)}' for k, v in x.items()) + '}'
    return repr(x) if isinstance(x, str) else str(x)
