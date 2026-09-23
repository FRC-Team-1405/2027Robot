"""
WPILog payload decoding and whole-file parsing into {signal name: [(t_seconds, value), ...]}.

Moved verbatim from vision_analyzer.parser (see docs/wpilog-janitor-plan.md, M0). Signal names have
their leading '/' stripped (an existing convention every caller relies on).
"""
import logging
import pathlib
import struct
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from .records import iter_records, wpilog_header_end

log = logging.getLogger(__name__)

POSE2D_SIZE = 24   # double x, double y, double rotation_radians
POSE3D_SIZE = 56   # double x,y,z, double qw,qx,qy,qz


def parse_wpilog_bytes(raw: bytes, stats: Optional[dict] = None) -> Dict[str, List[Tuple[float, Any]]]:
    """
    Parse raw WPILog bytes.

    If `stats` is given it is filled with 'n_records', 'n_late' (data records behind the newest record
    before them -- a plain WPILib log's NT mirroring does this; reorder.py fixes it) and 'max_late_s'.
    Each signal's samples are returned in file order either way.

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
    Unrecognized types are skipped, but logged (see `decode_payload`) — not silently.
    """
    pos = wpilog_header_end(raw)

    entries: Dict[int, Dict[str, str]] = {}
    signals: Dict[str, List[Tuple[float, Any]]] = defaultdict(list)
    unregistered_ids: Dict[int, int] = defaultdict(int)

    t0 = time.monotonic()
    n_records = n_late = 0
    newest = max_late = 0.0
    for entry_id, ts_sec, payload, _start, _end in iter_records(raw, pos):
        if entry_id == 0:
            handle_control(payload, entries)
        else:
            n_records += 1
            if ts_sec < newest:
                n_late += 1
                max_late = max(max_late, newest - ts_sec)
            else:
                newest = ts_sec
            entry = entries.get(entry_id)
            if entry is None:
                # No control record ever registered this entry id — normally
                # impossible for a well-formed log (control records precede
                # the data they describe), so this is itself a corruption
                # signal. Counted and summarized below rather than logged
                # per-record, since a single dangling id can repeat thousands
                # of times and would otherwise flood the log.
                unregistered_ids[entry_id] += 1
                continue
            value = decode_payload(payload, entry['type'])
            if value is not None:
                signals[entry['name']].append((ts_sec, value))

    elapsed = time.monotonic() - t0
    log.debug(
        'Parsed %d bytes in %.2f s — %d signals, %d entries registered',
        len(raw), elapsed, len(signals), len(entries),
    )
    if unregistered_ids:
        log.warning(
            'Skipped %d data record(s) referencing %d entry ID(s) with no matching '
            'control record (e.g. %s) — the log never told us how to decode them, so '
            'their data is missing from the parsed signals. This usually means the '
            'log is corrupted or was truncated mid-write.',
            sum(unregistered_ids.values()), len(unregistered_ids),
            sorted(unregistered_ids)[:5],
        )
    if stats is not None:
        stats.update(n_records=n_records, n_late=n_late, max_late_s=max_late)
    return dict(signals)


def parse_wpilog(path: str, stats: Optional[dict] = None) -> Dict[str, List[Tuple[float, Any]]]:
    """Parse a WPILib DataLog (.wpilog) file by path. See parse_wpilog_bytes for `stats`."""
    p = pathlib.Path(path)
    size_kb = p.stat().st_size / 1024 if p.exists() else 0
    log.info('Reading %s (%.1f KB)', p.name, size_kb)
    raw = p.read_bytes()
    try:
        signals = parse_wpilog_bytes(raw, stats)
        log.info('Parsed %s — %d signals total', p.name, len(signals))
        return signals
    except ValueError as exc:
        log.error('Failed to parse %s: %s', path, exc, exc_info=True)
        raise ValueError(f"{exc}: {path}") from exc



def handle_control(payload: bytes, entries: Dict) -> None:
    if not payload:
        return
    ctrl = payload[0]
    if ctrl != 0:
        return
    pos = 1
    if pos + 4 > len(payload):
        log.warning(
            'Malformed "start" control record (payload too short to contain an entry '
            'id, len=%d) — the entry this record was supposed to register is lost, so '
            'any data records referencing it will be reported as unregistered.',
            len(payload),
        )
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


# Types we've already logged a "don't know how to decode this" notice for,
# so a log full of e.g. a custom struct type doesn't spam one line per record.
_warned_unknown_types: set = set()


def decode_payload(payload: bytes, typ: str) -> Any:
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
        log.warning(
            'Failed to decode record: declared type=%r payload_len=%d error=%s '
            '— dropping this record; its value is missing from the parsed signals.',
            typ, len(payload), exc,
        )
        return None

    # Fell through every known-type branch above with no exception: this is a
    # type this parser simply has no decoder for (not necessarily corruption —
    # e.g. a custom struct type). Previously this returned None with zero
    # logging. Log it once per type so it's visible without spamming a line
    # per record.
    if typ not in _warned_unknown_types:
        _warned_unknown_types.add(typ)
        log.info(
            'Unrecognized WPILog entry type %r — records of this type are skipped '
            '(no decoder for it in this parser).',
            typ,
        )
    return None
