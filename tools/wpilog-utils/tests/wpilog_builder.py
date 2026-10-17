"""Builds small, fully controlled .wpilog byte strings for tests.

Deliberately independent of wpilog_utils.records.build_record: tests that check the writer must not
share an encoder with the code under test. Supports the wire-format variations real logs have
(minimal-width record headers, wide ones) since those are what break naive trimmers.
"""
import struct
from typing import List, Optional, Tuple

MAGIC = b'WPILOG'


def _le(n: int, width: int) -> bytes:
    return n.to_bytes(width, 'little')


def _min_width(n: int) -> int:
    return max(1, (n.bit_length() + 7) // 8)


def record(entry_id: int, ts_us: int, payload: bytes, minimal: bool = True) -> bytes:
    """One record. minimal=True uses the smallest legal field widths (what WPILib's DataLog writes)."""
    if minimal:
        e, s, t = _min_width(entry_id), _min_width(len(payload)), _min_width(ts_us)
    else:
        e, s, t = 4, 4, 8
    bitfield = (e - 1) | ((s - 1) << 2) | ((t - 1) << 4)
    return bytes([bitfield]) + _le(entry_id, e) + _le(len(payload), s) + _le(ts_us, t) + payload


def _lp(s: str) -> bytes:
    b = s.encode()
    return struct.pack('<I', len(b)) + b


def start(entry_id: int, name: str, typ: str, metadata: str = '{"source":"AdvantageKit"}',
          ts_us: int = 0, minimal: bool = True) -> bytes:
    return record(0, ts_us, b'\x00' + struct.pack('<I', entry_id) + _lp(name) + _lp(typ) + _lp(metadata), minimal)


def finish(entry_id: int, ts_us: int, minimal: bool = True) -> bytes:
    return record(0, ts_us, b'\x01' + struct.pack('<I', entry_id), minimal)


def header(extra: str = 'AdvantageKit') -> bytes:
    e = extra.encode()
    return MAGIC + struct.pack('<H', 0x0100) + struct.pack('<I', len(e)) + e


def boolean(v: bool) -> bytes:
    return b'\x01' if v else b'\x00'


def double(v: float) -> bytes:
    return struct.pack('<d', v)


def int64(v: int) -> bytes:
    return struct.pack('<q', v)


class LogBuilder:
    """Accumulates entries and records in call order; .build() returns the file bytes."""

    def __init__(self, extra: str = 'AdvantageKit', minimal: bool = True):
        self.extra, self.minimal = extra, minimal
        self._parts: List[bytes] = []
        self._next_id = 1
        self.ids = {}

    def entry(self, name: str, typ: str, ts_us: int = 0, metadata: str = '{"source":"AdvantageKit"}') -> int:
        eid = self._next_id
        self._next_id += 1
        self.ids[name] = eid
        self._parts.append(start(eid, name, typ, metadata, ts_us, self.minimal))
        return eid

    def data(self, name_or_id, ts_us: int, payload: bytes) -> None:
        eid = self.ids[name_or_id] if isinstance(name_or_id, str) else name_or_id
        self._parts.append(record(eid, ts_us, payload, self.minimal))

    def raw(self, b: bytes) -> None:
        self._parts.append(b)

    def build(self) -> bytes:
        return header(self.extra) + b''.join(self._parts)


def ds_log(spans: List[Tuple[str, float]], cycle_ms: int = 20, t0_us: int = 1_000_000,
           extra_entries: Optional[List[Tuple[str, str]]] = None,
           extra_records: Optional[List[Tuple[str, int, bytes]]] = None,
           minimal: bool = True, with_timestamp_entry: bool = True) -> Tuple[bytes, dict]:
    """A realistic AdvantageKit-shaped log: one /Timestamp record per cycle (value == record ts in µs),
    /DriverStation/{Enabled,Autonomous} written on change only, a changing double '/Sensor/X' every cycle.

    `spans` = [('disabled'|'auto'|'teleop', seconds), ...]. Returns (bytes, info) where info holds the
    expected mode boundaries in seconds (absolute) and the cycle timestamps in µs.

    `extra_entries` registers more entries; `extra_records` = [(name, cycle_index, payload)] writes one
    record for that entry inside the given 0-based cycle (one-shot config values, mid-log changes).
    """
    b = LogBuilder(minimal=minimal)
    if with_timestamp_entry:
        b.entry('/Timestamp', 'int64', t0_us)
    b.entry('/DriverStation/Enabled', 'boolean', t0_us)
    b.entry('/DriverStation/Autonomous', 'boolean', t0_us)
    b.entry('/Sensor/X', 'double', t0_us)
    for n, t in (extra_entries or []):
        b.entry(n, t, t0_us)
    ts, bounds, t_us, k = [], [], t0_us, 0
    cur_en = cur_au = None
    for mode, secs in spans:
        en, au = mode != 'disabled', mode == 'auto'
        bounds.append((mode, t_us / 1e6, (t_us + int(secs * 1e6)) / 1e6))
        end = t_us + int(round(secs * 1e6))
        while t_us < end:
            if with_timestamp_entry:
                b.data('/Timestamp', t_us, int64(t_us))
            if en != cur_en:
                b.data('/DriverStation/Enabled', t_us, boolean(en)); cur_en = en
            if au != cur_au:
                b.data('/DriverStation/Autonomous', t_us, boolean(au)); cur_au = au
            b.data('/Sensor/X', t_us, double(k * 0.5))
            for n, ci, payload in (extra_records or []):
                if ci == k:
                    b.data(n, t_us, payload)
            k += 1
            ts.append(t_us)
            t_us += cycle_ms * 1000
    return b.build(), {'bounds': bounds, 'cycles_us': ts, 'ids': b.ids}
