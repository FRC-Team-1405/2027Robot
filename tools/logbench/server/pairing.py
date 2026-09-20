"""Pure wall-clock pairing of roboRIO .wpilog files to Orange Pi vision sessions.

This step is needed even though Pi frame timestamps (`t_sec`, NT-server-clock domain)
already share the *same* clock domain as a wpilog's own internal relative timestamps --
raw `t_sec` overlap alone is unsafe for the *initial* pairing because that domain resets
every roboRIO boot, so two unrelated boots could coincidentally overlap. Wall-clock is
the only signal that stays unambiguous across boots, so it is used once, here, purely to
decide which Pi session belongs with which RIO log. Once a pairing is fixed (auto or
manual), no further time conversion is needed for frame-level sync -- `t_sec` drops
straight onto the wpilog's own t0..t1 axis.

Pure and stdlib-only: no filesystem, no network, no paramiko. suggest_pairings() is
trivially unit-testable with synthetic RioLogInfo/PiSessionInfo lists. server/main.py is
the only caller that has to go fetch those lists for real (via remote_fetch.py) and turn
the result into JSON.

All `wall_clock` datetimes passed in must be directly comparable (same tzinfo-ness, same
timezone if aware) -- remote_fetch.py parses both the RIO's DS-renamed filename and the
Pi's session-folder name as naive local time, since both are ultimately derived from the
same DS-laptop clock (see orangepi-vision-recorder.py's module docstring), so no
conversion between them is needed or done here.
"""
import dataclasses
import datetime as dt
from typing import Dict, List, Optional

# A wpilog's actual duration isn't knowable from a remote directory listing alone (that
# needs downloading and parsing the file), so an unknown-duration RIO log is treated as
# spanning this long from its DS-renamed start when computing overlap -- long enough to
# cover a full FRC match plus setup/teardown, short enough that two matches recorded
# back-to-back on the same Pi boot don't both plausibly claim the same session.
DEFAULT_ASSUMED_DURATION_SEC = 10 * 60

# Slop applied to both ends of a RIO log's window, to absorb DS-rename lag and any
# residual clock-sync jitter between the RIO and the Pi.
TOLERANCE_SEC = 60

# A Pi session matched at least this far inside a window's edges is 'high' confidence;
# closer to an edge (but still inside it) is 'low' -- tune from real bench data once some
# exists.
HIGH_CONFIDENCE_SLOP_SEC = 15


@dataclasses.dataclass
class RioLogInfo:
    name: str                              # e.g. 'FRC_20260115_143022.wpilog'
    wall_clock: Optional[dt.datetime]      # None if the DS never renamed it (FRC_TBD_*)
    duration_sec: Optional[float] = None   # only known once the log has been parsed locally


@dataclasses.dataclass
class PiSessionInfo:
    camera: str                            # '' for a legacy, non-namespaced layout
    name: str                              # e.g. 'boot0007-20260115-143511'
    wall_clock: Optional[dt.datetime]      # None if unparseable


@dataclasses.dataclass
class Pairing:
    rio_log: str
    pi_sessions: List[PiSessionInfo]
    confidence: str  # 'high' | 'low' | 'none'
    reason: str


def _window(rio: RioLogInfo):
    duration = rio.duration_sec if rio.duration_sec is not None else DEFAULT_ASSUMED_DURATION_SEC
    lo = rio.wall_clock - dt.timedelta(seconds=TOLERANCE_SEC)
    hi = rio.wall_clock + dt.timedelta(seconds=duration + TOLERANCE_SEC)
    return lo, hi


def suggest_pairings(rio_logs: List[RioLogInfo], pi_sessions: List[PiSessionInfo]) -> List[Pairing]:
    """One Pairing per entry in rio_logs (same order back out), each matching at most one
    Pi session per camera: the candidate closest in time to the RIO log's own start,
    among sessions whose folder timestamp falls in
    [start - tolerance, start + duration + tolerance].

    A Pi session is claimed by at most one RIO log. RIO logs are considered earliest-
    wall-clock first, so if two logs' windows both cover the same session (e.g. very
    short back-to-back logs from one boot), the earlier log wins it and the later log is
    left unmatched for that camera rather than double-booking. This is always a
    *suggestion* -- the caller/UI lets a person override it either way.
    """
    claimed_indices: set = set()
    ordered = sorted(
        rio_logs,
        key=lambda r: (r.wall_clock is None, r.wall_clock or dt.datetime.max),
    )

    results: Dict[str, Pairing] = {}
    for rio in ordered:
        if rio.wall_clock is None:
            results[rio.name] = Pairing(
                rio_log=rio.name, pi_sessions=[], confidence='none',
                reason='no wall-clock start (filename was never DS-renamed from FRC_TBD_*)',
            )
            continue

        lo, hi = _window(rio)
        by_camera: Dict[str, list] = {}
        for i, sess in enumerate(pi_sessions):
            if i in claimed_indices or sess.wall_clock is None:
                continue
            if lo <= sess.wall_clock <= hi:
                by_camera.setdefault(sess.camera, []).append((i, sess))

        matched: List[PiSessionInfo] = []
        edge_slops: List[float] = []
        for candidates in by_camera.values():
            i, sess = min(
                candidates,
                key=lambda pair: abs((pair[1].wall_clock - rio.wall_clock).total_seconds()),
            )
            claimed_indices.add(i)
            matched.append(sess)
            edge_slops.append(min(
                abs((sess.wall_clock - lo).total_seconds()),
                abs((hi - sess.wall_clock).total_seconds()),
            ))

        if not matched:
            results[rio.name] = Pairing(
                rio_log=rio.name, pi_sessions=[], confidence='none',
                reason='no Pi session found in [%s, %s]' % (lo.isoformat(), hi.isoformat()),
            )
        else:
            confidence = 'high' if min(edge_slops) >= HIGH_CONFIDENCE_SLOP_SEC else 'low'
            cams = ', '.join(sorted(s.camera or '(unnamed)' for s in matched))
            results[rio.name] = Pairing(
                rio_log=rio.name, pi_sessions=matched, confidence=confidence,
                reason='matched %s by wall-clock overlap' % cams,
            )

    return [results[r.name] for r in rio_logs]
