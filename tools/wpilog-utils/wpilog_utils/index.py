"""
One streaming pass over a .wpilog that answers "what is in this file and where are the bytes?"
without decoding payloads (except the driver-station mode signals, see modes.mode_signals).

The index holds no per-record data, so it stays small on 100 MB logs; the trim writer (trim.py)
re-walks the file itself. What it keeps:

  * per-entry stats (records, bytes, first/last time) -- the size table
  * cycles: the log's loop-cycle timestamps + bytes per cycle -- the unit trimming snaps to
  * bytes per second -- the timeline density curve
  * driver-station mode spans -- the timeline bands

A "cycle" is one AdvantageKit loop iteration. AdvantageKit writes every record of an iteration at
one timestamp and logs a `/Timestamp` int64 entry once per iteration, so when that entry exists a
cycle boundary is one of its records (a stray record between two of them belongs to the earlier
cycle). Logs without it (plain WPILib DataLog) fall back to "every distinct timestamp is a cycle".
"""
import bisect
import pathlib
import statistics
from array import array
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .decode import decode_payload
from .modes import MODE_SIGNAL_NAMES, compute_mode_spans, mode_signals
from .records import iter_records, parse_control, wpilog_header_end

CYCLE_ENTRY_NAME = '/Timestamp'
_DS_SIGNALS = set(MODE_SIGNAL_NAMES)
# An entry whose int64 payload equals its own record timestamp (in µs) on at least this fraction of
# its records is treated as a copy of the record time (AdvantageKit's /Timestamp) and re-stamped
# when the writer re-times the log.
TIME_MIRROR_MIN_FRACTION = 0.99
TIME_MIRROR_MIN_RECORDS = 3


@dataclass
class IndexEntry:
    id: int
    name: str                  # as in the file, leading '/' included
    type: str
    metadata: str
    n_records: int = 0
    bytes: int = 0             # data-record bytes (header + payload); control records are counted on the index
    first_ts_us: Optional[int] = None
    last_ts_us: Optional[int] = None
    _mirror_hits: int = 0      # int64 records whose payload == record ts in µs

    @property
    def time_mirror(self) -> bool:
        return (self.type == 'int64' and self.n_records >= TIME_MIRROR_MIN_RECORDS
                and self._mirror_hits >= TIME_MIRROR_MIN_FRACTION * self.n_records)


@dataclass
class LogIndex:
    total_bytes: int
    header_end: int
    extra_header: bytes
    entries: Dict[int, IndexEntry]
    t_min_us: int
    t_max_us: int
    cycles_us: array = field(repr=False)          # 'q': timestamp of each cycle, ascending
    cycle_bytes: array = field(repr=False)        # 'Q': data-record bytes belonging to each cycle
    cycle_records: array = field(repr=False)      # 'I': data records belonging to each cycle
    byte_hist: List[int] = field(repr=False)      # data-record bytes per 1 s bucket, from t_min
    entry_hist: Dict[int, array] = field(repr=False)  # entry id -> 'I' array of its data bytes per 1 s bucket
    cycle_entry_id: Optional[int]
    time_ordered: bool
    control_bytes: int
    n_control: Dict[str, int]                     # counts by kind ('start', 'finish', 'set_metadata', 'other')
    n_unregistered_records: int                   # data records whose entry was never started
    ds_signals: Dict[str, List[Tuple[float, object]]] = field(repr=False, default_factory=dict)   # raw values; see modes.mode_signals
    n_late_records: int = 0       # records behind the newest record before them (reorder.py fixes these)
    max_late_us: int = 0

    # ---- derived -------------------------------------------------------------------------------
    @property
    def duration_s(self) -> float:
        return (self.t_max_us - self.t_min_us) / 1e6

    @property
    def n_records(self) -> int:
        return sum(e.n_records for e in self.entries.values())

    @property
    def data_bytes(self) -> int:
        return sum(e.bytes for e in self.entries.values())

    def cycle_period_us(self) -> int:
        """Median spacing between consecutive cycles (robust to the multi-second boot gaps real logs have)."""
        c = self.cycles_us
        if len(c) < 2:
            return 20_000
        return max(1, int(statistics.median(c[i + 1] - c[i] for i in range(len(c) - 1))))

    def window_bytes(self, start_s: float, end_s: float) -> int:
        """Data-record bytes in cycles whose time falls in [start_s, end_s), seconds from the first record."""
        lo = bisect.bisect_left(self.cycles_us, self.t_min_us + round(start_s * 1e6))
        hi = bisect.bisect_left(self.cycles_us, self.t_min_us + round(end_s * 1e6))
        if self.t_min_us + round(end_s * 1e6) >= self.t_max_us:       # the last span ends AT the last record: include it
            hi = len(self.cycles_us)
        return sum(self.cycle_bytes[lo:hi])

    def mode_spans(self) -> List[Tuple[float, float, str]]:
        """[(rel_start_s, rel_end_s, 'disabled'|'auto'|'teleop'), ...] relative to this log's first record.
        Empty when the log has no mode data from any source modes.mode_signals knows."""
        if self.mode_source is None:
            return []
        t0, t1 = self.t_min_us / 1e6, self.t_max_us / 1e6
        return compute_mode_spans(self.ds_signals, t0, t1)

    @property
    def mode_source(self) -> Optional[str]:
        """The entry the mode bands come from (e.g. 'DS:enabled'), or None when there are none."""
        return mode_signals(self.ds_signals)[2]

    def entry_by_name(self, name: str) -> Optional[IndexEntry]:
        for e in self.entries.values():
            if e.name == name:
                return e
        return None


def build_index(raw: bytes) -> LogIndex:
    header_end = wpilog_header_end(raw)
    entries: Dict[int, IndexEntry] = {}
    cycles, cycle_bytes, cycle_records = array('q'), array('Q'), array('I')
    hist: Dict[int, int] = {}
    entry_hist: Dict[int, array] = {}
    ds: Dict[str, List[Tuple[float, bool]]] = {}
    ds_ids: Dict[int, str] = {}
    cycle_entry_id: Optional[int] = None
    n_control = {'start': 0, 'finish': 0, 'set_metadata': 0, 'other': 0}
    control_bytes = n_unreg = 0
    cur_ts: Optional[int] = None
    t_min = t_max = None
    ordered = True
    n_late = max_late = 0

    for entry_id, ts_sec, payload, start, end in iter_records(raw, header_end):
        size = end - start
        if entry_id == 0:
            control_bytes += size
            ctrl = parse_control(payload)
            if ctrl is None:
                n_control['other'] += 1
            else:
                n_control[ctrl.kind] += 1
                if ctrl.kind == 'start':
                    entries[ctrl.entry_id] = IndexEntry(ctrl.entry_id, ctrl.name, ctrl.type, ctrl.metadata)
                    if ctrl.name == CYCLE_ENTRY_NAME and ctrl.type == 'int64':
                        cycle_entry_id = ctrl.entry_id
                    if ctrl.name.lstrip('/') in _DS_SIGNALS:
                        ds_ids[ctrl.entry_id] = ctrl.name.lstrip('/')
                elif ctrl.kind == 'set_metadata' and ctrl.entry_id in entries:
                    entries[ctrl.entry_id].metadata = ctrl.metadata
            continue

        ent = entries.get(entry_id)
        if ent is None:
            n_unreg += 1
            continue
        ts_us = int(round(ts_sec * 1_000_000))
        if t_min is None:
            t_min = t_max = ts_us
        else:
            if ts_us < t_max:
                ordered = False
                n_late += 1
                max_late = max(max_late, t_max - ts_us)
            t_min, t_max = min(t_min, ts_us), max(t_max, ts_us)

        if cur_ts is None or (ts_us != cur_ts and (cycle_entry_id is None or entry_id == cycle_entry_id)):
            cycles.append(ts_us)
            cycle_bytes.append(0)
            cycle_records.append(0)
            cur_ts = ts_us
        cycle_bytes[-1] += size
        cycle_records[-1] += 1

        ent.n_records += 1
        ent.bytes += size
        if ent.first_ts_us is None or ts_us < ent.first_ts_us:
            ent.first_ts_us = ts_us
        if ent.last_ts_us is None or ts_us > ent.last_ts_us:
            ent.last_ts_us = ts_us
        if ent.type == 'int64' and len(payload) == 8 and int.from_bytes(payload, 'little', signed=True) == ts_us:
            ent._mirror_hits += 1

        bucket = max(0, (ts_us - t_min) // 1_000_000)
        hist[bucket] = hist.get(bucket, 0) + size
        eh = entry_hist.get(entry_id)
        if eh is None:
            eh = entry_hist[entry_id] = array('I')
        if bucket >= len(eh):
            eh.extend(array('I', bytes(4 * (bucket + 1 - len(eh)))))
        eh[bucket] += size

        if entry_id in ds_ids:
            v = decode_payload(payload, ent.type)
            if v is not None:
                ds.setdefault(ds_ids[entry_id], []).append((ts_sec, v))

    if t_min is None:
        t_min = t_max = 0
    n_buckets = (max(hist) + 1) if hist else 0
    return LogIndex(
        total_bytes=len(raw), header_end=header_end, extra_header=raw[12:header_end], entries=entries,
        t_min_us=t_min, t_max_us=t_max, cycles_us=cycles, cycle_bytes=cycle_bytes, cycle_records=cycle_records,
        byte_hist=[hist.get(i, 0) for i in range(n_buckets)], entry_hist=entry_hist, cycle_entry_id=cycle_entry_id,
        time_ordered=ordered, n_late_records=n_late, max_late_us=max_late, control_bytes=control_bytes, n_control=n_control,
        n_unregistered_records=n_unreg, ds_signals=ds,
    )


def load_index(path) -> Tuple[bytes, LogIndex]:
    """Read a file and index it. Returns (raw bytes, index) since the writer needs both."""
    raw = pathlib.Path(path).read_bytes()
    return raw, build_index(raw)
