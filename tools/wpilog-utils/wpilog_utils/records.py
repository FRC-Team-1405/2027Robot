"""
Low-level WPILog record access: header, record walker (with exact byte ranges), record encoder.

Moved verbatim from vision_analyzer.parser (see docs/wpilog-janitor-plan.md, M0); only the leading
underscores were dropped from the names. No decoding of payloads happens here.
"""
import logging
import struct
from dataclasses import dataclass
from typing import Iterator, Optional, Tuple

log = logging.getLogger(__name__)


# Above this many trailing unparsed bytes, an early stop in iter_records is
# treated as a loud anomaly rather than the normal "writer was killed
# mid-record" tail. The largest a legitimate record header can ever be is
# 4 (entry id) + 4 (payload size) + 16 (timestamp) = 24 bytes, so anything
# meaningfully larger than that indicates real data is being dropped.
TRUNCATION_WARN_BYTES = 256



def wpilog_header_end(raw: bytes) -> int:
    """Validate magic bytes and return the byte offset where records begin."""
    if len(raw) < 12 or raw[0:6] != b'WPILOG':
        raise ValueError("Not a WPILog file (bad magic bytes)")
    extra_len = struct.unpack_from('<I', raw, 8)[0]
    return 12 + extra_len


def warn_early_stop(raw: bytes, record_start: int, n_yielded: int,
                      last_ts: float, reason: str) -> None:
    """
    Called whenever iter_records stops before consuming the whole buffer.

    This used to be a silent `break` with no logging at all: a single
    corrupted or misaligned record anywhere in a multi-hundred-second log
    would drop every record after it with zero indication, producing a
    dashboard/chart that looked like the log just ended early. Log loudly
    enough (ERROR, not DEBUG) that it shows up in both this tool's own log
    file and — via camera_calibration's logging bridge — the calibration
    tool's session log, instead of just quietly returning fewer records.
    """
    remaining = len(raw) - record_start
    if remaining <= TRUNCATION_WARN_BYTES:
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


def iter_records(raw: bytes, pos: int) -> Iterator[Tuple[int, float, bytes, int, int]]:
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
            warn_early_stop(
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
            warn_early_stop(
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


def build_record(entry_id: int, ts_us: int, payload: bytes) -> bytes:
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


# ─── Additions since the move (not in the original vision_analyzer parser) ────────────────────

def _min_width(n: int) -> int:
    return max(1, (n.bit_length() + 7) // 8)


def encode_record(entry_id: int, ts_us: int, payload: bytes) -> bytes:
    """
    Encode a record with the smallest legal entry-id / payload-size / timestamp field widths — what
    WPILib's own DataLog writer emits. (`build_record` always uses 4/4/8, which is fine for one-off
    carried records but wastes ~8 bytes per record when re-encoding a whole log.)
    """
    e, s, t = _min_width(entry_id), _min_width(len(payload)), _min_width(ts_us)
    bitfield = (e - 1) | ((s - 1) << 2) | ((t - 1) << 4)
    return (bytes([bitfield]) + entry_id.to_bytes(e, 'little') + len(payload).to_bytes(s, 'little')
            + ts_us.to_bytes(t, 'little') + payload)


def _lp(s: str) -> bytes:
    b = s.encode('utf-8')
    return struct.pack('<I', len(b)) + b


def encode_start_payload(entry_id: int, name: str, typ: str, metadata: str) -> bytes:
    """Payload of a Start control record (goes in a record with entry id 0)."""
    return b'\x00' + struct.pack('<I', entry_id) + _lp(name) + _lp(typ) + _lp(metadata)


@dataclass(frozen=True)
class ControlRecord:
    """A parsed control record. `name` keeps its leading '/' (unlike decode.parse_wpilog's signal keys)."""
    kind: str            # 'start' | 'finish' | 'set_metadata'
    entry_id: int
    name: str = ''
    type: str = ''
    metadata: str = ''


def _read_lp(data: bytes, pos: int) -> Tuple[str, int]:
    (n,) = struct.unpack_from('<I', data, pos)
    pos += 4
    if pos + n > len(data):
        raise ValueError('string runs past end of control record')
    return data[pos:pos + n].decode('utf-8', errors='replace'), pos + n


def parse_control(payload: bytes) -> Optional[ControlRecord]:
    """Parse the payload of an entry-id-0 record. None if it is malformed or an unknown control type."""
    try:
        if not payload:
            return None
        kind = payload[0]
        if kind == 0:
            (eid,) = struct.unpack_from('<I', payload, 1)
            name, pos = _read_lp(payload, 5)
            typ, pos = _read_lp(payload, pos)
            meta, _ = _read_lp(payload, pos)
            return ControlRecord('start', eid, name, typ, meta)
        if kind == 1:
            (eid,) = struct.unpack_from('<I', payload, 1)
            return ControlRecord('finish', eid)
        if kind == 2:
            (eid,) = struct.unpack_from('<I', payload, 1)
            meta, _ = _read_lp(payload, 5)
            return ControlRecord('set_metadata', eid, metadata=meta)
    except (struct.error, ValueError):
        log.warning('Malformed control record (%d bytes) skipped', len(payload))
    return None
