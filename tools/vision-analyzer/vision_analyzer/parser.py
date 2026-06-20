"""
WPILog binary parser. No Streamlit or Plotly dependency.
"""
import logging
import pathlib
import struct
import time
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from .constants import POSE2D_SIZE, POSE3D_SIZE

log = logging.getLogger(__name__)


def _parse_wpilog_bytes(raw: bytes) -> Dict[str, List[Tuple[float, Any]]]:
    """
    Parse raw WPILog bytes.

    Returns a dict mapping signal name -> list of (timestamp_seconds, value) tuples.
    Values are decoded based on the type string registered in the log:
      boolean        -> bool
      int64          -> int
      double         -> float
      double[]       -> list[float]
      int64[]        -> list[int]
      boolean[]      -> list[bool]
      struct:Pose2d  -> list[dict] with keys x, y, rot
      struct[]:Pose2d -> list[dict] with keys x, y, rot   (0 or more per record)
      struct:Pose3d  -> list[dict] with keys x, y, z, qw, qx, qy, qz
      struct[]:Pose3d -> list[dict] (0 or more per record)
    Unknown types are silently skipped.
    """
    if len(raw) < 12 or raw[0:6] != b'WPILOG':
        raise ValueError("Not a WPILog file (bad magic bytes)")
    extra_len = struct.unpack_from('<I', raw, 8)[0]
    pos = 12 + extra_len

    entries: Dict[int, Dict[str, str]] = {}
    signals: Dict[str, List[Tuple[float, Any]]] = defaultdict(list)

    t0 = time.monotonic()
    while pos < len(raw):
        if pos >= len(raw):
            break
        bitfield = raw[pos]
        pos += 1

        eid_sz   = (bitfield & 0x3) + 1
        psz_sz   = ((bitfield >> 2) & 0x3) + 1
        tsz      = ((bitfield >> 4) & 0xF) + 1

        needed = eid_sz + psz_sz + tsz
        if pos + needed > len(raw):
            break

        entry_id     = int.from_bytes(raw[pos:pos + eid_sz], 'little')
        pos         += eid_sz
        payload_size = int.from_bytes(raw[pos:pos + psz_sz], 'little')
        pos         += psz_sz
        ts_us        = int.from_bytes(raw[pos:pos + tsz],    'little')
        pos         += tsz
        ts_sec       = ts_us / 1_000_000.0

        if pos + payload_size > len(raw):
            break
        payload = raw[pos:pos + payload_size]
        pos    += payload_size

        if entry_id == 0:
            _handle_control(payload, entries)
        else:
            entry = entries.get(entry_id)
            if entry is None:
                continue
            value = _decode(payload, entry['type'])
            if value is not None:
                signals[entry['name']].append((ts_sec, value))

    elapsed = time.monotonic() - t0
    log.debug(
        'Parsed %d bytes in %.2f s — %d signals, %d entries registered',
        len(raw), elapsed, len(signals), len(entries),
    )
    return dict(signals)


def parse_wpilog(path: str) -> Dict[str, List[Tuple[float, Any]]]:
    """Parse a WPILib DataLog (.wpilog) file by path."""
    p = pathlib.Path(path)
    size_kb = p.stat().st_size / 1024 if p.exists() else 0
    log.info('Reading %s (%.1f KB)', p.name, size_kb)
    raw = p.read_bytes()
    try:
        signals = _parse_wpilog_bytes(raw)
        log.info('Parsed %s — %d signals total', p.name, len(signals))
        return signals
    except ValueError as exc:
        log.error('Failed to parse %s: %s', path, exc, exc_info=True)
        raise ValueError(f"{exc}: {path}") from exc


def _handle_control(payload: bytes, entries: Dict) -> None:
    if not payload:
        return
    ctrl = payload[0]
    if ctrl != 0:
        return
    pos = 1
    if pos + 4 > len(payload):
        return
    new_id = struct.unpack_from('<I', payload, pos)[0]
    pos += 4
    name,     pos = _lp_str(payload, pos)
    type_str, pos = _lp_str(payload, pos)
    entries[new_id] = {'name': name.lstrip('/'), 'type': type_str}


def _lp_str(data: bytes, pos: int) -> Tuple[str, int]:
    if pos + 4 > len(data):
        return '', pos
    length = struct.unpack_from('<I', data, pos)[0]
    pos += 4
    s = data[pos:pos + length].decode('utf-8', errors='replace')
    return s, pos + length


def _decode(payload: bytes, typ: str) -> Any:
    try:
        t = typ.lower()

        if t == 'boolean':
            return bool(payload[0]) if payload else None

        if t in ('int64', 'integer', 'int'):
            return struct.unpack_from('<q', payload)[0] if len(payload) >= 8 else None

        if t == 'double':
            return struct.unpack_from('<d', payload)[0] if len(payload) >= 8 else None

        if t == 'float':
            return struct.unpack_from('<f', payload)[0] if len(payload) >= 4 else None

        if t in ('string', 'json'):
            return payload.decode('utf-8', errors='replace')

        if t == 'double[]':
            count = len(payload) // 8
            return list(struct.unpack_from(f'<{count}d', payload)) if count else []

        if t in ('int64[]', 'integer[]', 'int[]'):
            count = len(payload) // 8
            return list(struct.unpack_from(f'<{count}q', payload)) if count else []

        if t == 'float[]':
            count = len(payload) // 4
            return list(struct.unpack_from(f'<{count}f', payload)) if count else []

        if t == 'boolean[]':
            return [bool(b) for b in payload]

        if 'pose2d' in t:
            n = len(payload) // POSE2D_SIZE
            poses = []
            for i in range(n):
                x, y, r = struct.unpack_from('<3d', payload, i * POSE2D_SIZE)
                poses.append({'x': x, 'y': y, 'rot': r})
            return poses

        if 'pose3d' in t:
            n = len(payload) // POSE3D_SIZE
            poses = []
            for i in range(n):
                vals = struct.unpack_from('<7d', payload, i * POSE3D_SIZE)
                poses.append({'x': vals[0], 'y': vals[1], 'z': vals[2],
                              'qw': vals[3], 'qx': vals[4], 'qy': vals[5], 'qz': vals[6]})
            return poses

    except Exception as exc:
        log.debug(
            '_decode error: type=%r payload_len=%d error=%s',
            typ, len(payload), exc,
        )
    return None
