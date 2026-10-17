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

All `wall_clock` datetimes passed in must be directly comparable (all naive or all
aware). Both clocks come from the DS laptop (see orangepi-vision-recorder.py's module
docstring), but they are *written* in different zones -- the RIO names its logs in UTC,
the recorder names sessions in US Eastern -- so remote_fetch.py parses each to a
timezone-aware datetime and the comparison here is between real instants.
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
    pi: str = ''                           # which Orange Pi recorded it ('' = the only one)


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
    """Pair every session in a log's window, including separate auto/teleop enables.

    Each session is claimed once, with AdvantageKit logs preferred over WPILib logs.
    A window ends at the next same-kind RIO log's start so a ten-minute fallback
    duration cannot swallow the following match. The UI still permits overrides.
    """
    claimed_indices: set = set()
    # Every boot writes an akit_* (AdvantageKit) log and an FRC_* (WPILib) log about a
    # second apart, so both windows cover the same sessions. The AdvantageKit log is the
    # one with Vision/ inputs and poses, so akit_* logs claim first; otherwise the
    # FRC_* log, a second earlier, would take every session and leave the akit_ log bare.
    ordered = sorted(
        rio_logs,
        key=lambda r: (r.wall_clock is None, not r.name.startswith('akit_'),
                       r.wall_clock.timestamp() if r.wall_clock else float('inf')),
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
        next_starts = [other.wall_clock for other in rio_logs
                       if other.wall_clock is not None and other.wall_clock > rio.wall_clock
                       and other.name.startswith('akit_') == rio.name.startswith('akit_')]
        next_start = min(next_starts) if next_starts else None
        if next_start is not None:
            hi = min(hi, next_start)
        candidates = []
        for i, sess in enumerate(pi_sessions):
            if i in claimed_indices or sess.wall_clock is None:
                continue
            if lo <= sess.wall_clock <= hi and (next_start is None or sess.wall_clock < next_start):
                candidates.append((i, sess))

        matched: List[PiSessionInfo] = []
        edge_slops: List[float] = []
        for i, sess in sorted(candidates, key=lambda pair: pair[1].wall_clock):
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
