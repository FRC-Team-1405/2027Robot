"""
WPILog binary parser. No Streamlit or Plotly dependency.
"""
import logging
import pathlib
import struct
import time
from collections import defaultdict
from typing import Any, Dict, Iterator, List, Tuple

from .constants import POSE2D_SIZE, POSE3D_SIZE

log = logging.getLogger(__name__)

# Above this many trailing unparsed bytes, an early stop in _iter_records is
# treated as a loud anomaly rather than the normal "writer was killed
# mid-record" tail. The largest a legitimate record header can ever be is
# 4 (entry id) + 4 (payload size) + 16 (timestamp) = 24 bytes, so anything
# meaningfully larger than that indicates real data is being dropped.
_TRUNCATION_WARN_BYTES = 256


def _wpilog_header_end(raw: bytes) -> int:
    """Validate magic bytes and return the byte offset where records begin."""
    if len(raw) < 12 or raw[0:6] != b'WPILOG':
        raise ValueError("Not a WPILog file (bad magic bytes)")
    extra_len = struct.unpack_from('<I', raw, 8)[0]
    return 12 + extra_len


def _warn_early_stop(raw: bytes, record_start: int, n_yielded: int,
                      last_ts: float, reason: str) -> None:
    """
    Called whenever _iter_records stops before consuming the whole buffer.

    This used to be a silent `break` with no logging at all: a single
    corrupted or misaligned record anywhere in a multi-hundred-second log
    would drop every record after it with zero indication, producing a
    dashboard/chart that looked like the log just ended early. Log loudly
    enough (ERROR, not DEBUG) that it shows up in both this tool's own log
    file and — via camera_calibration's logging bridge — the calibration
    tool's session log, instead of just quietly returning fewer records.
    """
    remaining = len(raw) - record_start
    if remaining <= _TRUNCATION_WARN_BYTES:
        log.info(
            'WPILog record stream ended %d bytes before EOF after %d record(s) '
            '(last good timestamp %.3f s) — %s. This is expected for a log whose '
            'writer was killed mid-record (e.g. robot power loss / unclean shutdown).',
            remaining, n_yielded, last_ts, reason,
        )
    else:
        log.error(
            'WPILog PARSING STOPPED EARLY at byte %d/%d — %d bytes (%.1f%% of the file) '
            'were NOT parsed, after %d good record(s) ending at timestamp %.3f s. '
            'Reason: %s. Everything after this point in the log is silently missing '
            'from the parsed signals — if the log should be longer than %.1f s, this is why.',
            record_start, len(raw), remaining, 100.0 * remaining / len(raw),
            n_yielded, last_ts, reason, last_ts,
        )


def _iter_records(raw: bytes, pos: int) -> Iterator[Tuple[int, float, bytes, int, int]]:
    """
    Walk WPILog records starting at byte offset `pos` (just past the header).
    Yields (entry_id, timestamp_seconds, payload, record_start, record_end) for
    each well-formed record. record_start:record_end is the exact byte range of
    the record in `raw`, including its bitfield/entry-id/size/timestamp header —
    useful for byte-for-byte copying (e.g. trimming) without re-encoding.
    """
    n_yielded = 0
    last_ts = 0.0
    while pos < len(raw):
        record_start = pos
        bitfield = raw[pos]
        pos += 1

        eid_sz = (bitfield & 0x3) + 1
        psz_sz = ((bitfield >> 2) & 0x3) + 1
        tsz    = ((bitfield >> 4) & 0xF) + 1

        needed = eid_sz + psz_sz + tsz
        if pos + needed > len(raw):
            _warn_early_stop(
                raw, record_start, n_yielded, last_ts,
                'record header (entry-id/payload-size/timestamp fields) runs past end of file',
            )
            break

        entry_id     = int.from_bytes(raw[pos:pos + eid_sz], 'little')
        pos         += eid_sz
        payload_size = int.from_bytes(raw[pos:pos + psz_sz], 'little')
        pos         += psz_sz
        ts_us        = int.from_bytes(raw[pos:pos + tsz],    'little')
        pos         += tsz
        ts_sec       = ts_us / 1_000_000.0

        if pos + payload_size > len(raw):
            _warn_early_stop(
                raw, record_start, n_yielded, last_ts,
                f'declared payload size ({payload_size} bytes) runs past end of file '
                '— likely a corrupted or misaligned record',
            )
            break
        payload = raw[pos:pos + payload_size]
        pos    += payload_size

        n_yielded += 1
        last_ts    = ts_sec
        yield entry_id, ts_sec, payload, record_start, pos


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
    Unrecognized types are skipped, but logged (see `_decode`) — not silently.
    """
    pos = _wpilog_header_end(raw)

    entries: Dict[int, Dict[str, str]] = {}
    signals: Dict[str, List[Tuple[float, Any]]] = defaultdict(list)
    unregistered_ids: Dict[int, int] = defaultdict(int)

    t0 = time.monotonic()
    for entry_id, ts_sec, payload, _start, _end in _iter_records(raw, pos):
        if entry_id == 0:
            _handle_control(payload, entries)
        else:
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
            value = _decode(payload, entry['type'])
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
    return dict(signals)


def _build_record(entry_id: int, ts_us: int, payload: bytes) -> bytes:
    """
    Encode a fresh WPILog record from scratch. Always uses 4-byte entry-id,
    4-byte payload-size, and 8-byte timestamp fields — comfortably wide
    enough for any real entry_id/payload/timestamp, so unlike a verbatim
    byte-slice, this never breaks if the timestamp no longer fits in the
    original record's (possibly minimal) field width.
    """
    eid_sz, psz_sz, tsz = 4, 4, 8
    bitfield = (eid_sz - 1) | ((psz_sz - 1) << 2) | ((tsz - 1) << 4)
    return (
        bytes([bitfield])
        + entry_id.to_bytes(eid_sz, 'little')
        + len(payload).to_bytes(psz_sz, 'little')
        + ts_us.to_bytes(tsz, 'little')
        + payload
    )


def trim_wpilog_bytes(raw: bytes, t_lo: float, t_hi: float) -> bytes:
    """
    Return a new WPILog byte stream containing only records within
    [t_lo, t_hi] (absolute seconds, same domain as _parse_wpilog_bytes'
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
    exception: they're rebuilt via _build_record with a new timestamp, since
    the original record's timestamp field may be too narrow to hold t_lo.
    """
    header_end = _wpilog_header_end(raw)
    control_records: List[bytes] = []
    inwindow_records: List[bytes] = []
    last_before: Dict[int, bytes] = {}  # entry_id -> payload of its last pre-window record
    entries_inwindow: set = set()

    n_total = 0
    for entry_id, ts_sec, payload, start, end in _iter_records(raw, header_end):
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
        _build_record(eid, new_ts_us, payload)
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
