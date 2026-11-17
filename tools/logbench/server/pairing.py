"""Pure pairing of roboRIO .wpilog files to Orange Pi vision sessions. No filesystem, network or
paramiko: suggest_pairings() and select_for_log() are trivially unit-testable with synthetic
RioLogInfo/PiSessionInfo lists. server/main.py is the only caller that fetches those lists for real
(via remote_fetch.py / log_clock.py) and turns the result into JSON.

Pi frame timestamps (`t_sec`, NT-server clock) and a wpilog's own timestamps are the same axis:
FPGA seconds since the roboRIO booted. That axis restarts at every boot, so "which boot?" is the only
question, and a boot has an exact identity, its *epoch*: the wall clock at axis t=0.

  * A log's epoch is recorded by the robot (WallClockEpoch.java; the plain WPILib log has
    NT:/RobotTime/WallClockMs, minus the sample's time). See log_clock.py.
  * A Pi session is named with the roboRIO's wall clock, so  name time - first frame t_sec  is the
    same epoch to within a few seconds (a row's `timestamp_utc`, when present, makes it exact).
    Different boots are minutes apart.

Selection therefore goes, best first:
  1. exact:    the log's epoch is known (after it is downloaded) -> every session of that boot whose
               t_sec range overlaps the log's own. select_for_log() / suggest_pairings().
  2. inferred: only the file name is known. The AdvantageKit/WPILib file time is when the Driver
               Station first synced the roboRIO's clock, `epoch + 20 s ... epoch + several minutes`
               in real logs, so a boot (a cluster of sessions with one epoch) belongs to the first
               log named shortly after it. No assumed match duration is involved.
  3. window:   sessions with no epoch at all (empty manifest, listing failed) fall back to the file
               name's clock plus an assumed duration, as before.

The two logs one boot writes (akit_* and FRC_*, named a few seconds apart, sharing the FMS
event/match suffix) are twins and share their sessions; sessions are claimed once per boot, not per file.

All `wall_clock`/`epoch` datetimes must be directly comparable (all naive or all aware). The RIO
names its logs in UTC and the recorder names sessions in US Eastern, so remote_fetch.py parses each to
a timezone-aware datetime.
"""
import dataclasses
import datetime as dt
import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Last-resort: a wpilog's duration isn't in a directory listing, so an unknown-duration log is
# treated as spanning this long from its DS-renamed start (stage 3 only). Generous, because a
# window is always cut short at the next log's start.
DEFAULT_ASSUMED_DURATION_SEC = 30 * 60

# Slop on both ends of a filename-based window (DS-rename lag, residual clock jitter).
TOLERANCE_SEC = 60

# A session matched at least this far inside a window's edges is 'high' confidence.
HIGH_CONFIDENCE_SLOP_SEC = 15

# Two session epochs closer than this are the same boot. Name-derived epochs agree to ~3 s (the
# name is stamped when the session opens, the first frame arrives a little later); boots are
# minutes apart.
EPOCH_TOL_SEC = 15

# Stage 2: a log's file time is at most this long after its boot's epoch (observed: 20-412 s).
MAX_SYNC_DELAY_SEC = 20 * 60
# ...and an inferred match this close to the epoch is 'high' confidence, further out only 'low'.
CONFIDENT_SYNC_DELAY_SEC = 10 * 60

# The akit_* and FRC_* logs of one boot are named this close together (3 s at Ruckus).
TWIN_WINDOW_SEC = 30

# Slack when asking whether a session's frames overlap a log's time range.
RANGE_PAD_SEC = 5.0

# t_sec at or above this is the Pi's own wall clock stamped in place of robot time, not robot time.
MAX_ROBOT_T_SEC = 1e6

_SUFFIX_RE = re.compile(r'_([a-z0-9]+_(?:[a-z]+\d+|\d+))\.wpilog$', re.IGNORECASE)


@dataclasses.dataclass
class RioLogInfo:
    name: str                              # e.g. 'FRC_20260115_143022.wpilog'
    wall_clock: Optional[dt.datetime]      # None if the DS never renamed it (FRC_TBD_*)
    duration_sec: Optional[float] = None   # only known once the log has been parsed locally
    epoch: Optional[dt.datetime] = None    # wall clock at log t=0; only known once downloaded
    boot_id: Optional[str] = None          # robot-recorded id shared by the two logs of one run
    t_range: Optional[Tuple[float, float]] = None  # first/last record time; only once downloaded


@dataclasses.dataclass
class PiSessionInfo:
    camera: str                            # '' for a legacy, non-namespaced layout
    name: str                              # e.g. 'boot0007-20260115-143511'
    wall_clock: Optional[dt.datetime]      # None if unparseable
    pi: str = ''                           # which Orange Pi recorded it ('' = the only one)
    epoch: Optional[dt.datetime] = None    # wall clock at t_sec=0 of the boot it was recorded in
    t_first: Optional[float] = None        # first / last frame t_sec (robot axis)
    t_last: Optional[float] = None


@dataclasses.dataclass
class Pairing:
    rio_log: str
    pi_sessions: List[PiSessionInfo]
    confidence: str  # 'high' | 'low' | 'none'
    reason: str
    method: str = 'none'   # 'epoch' | 'inferred' | 'filename' | 'none'


# ── session clock, from the first/last manifest rows ──────────────────────────────────────────

def _parse_utc(text) -> Optional[dt.datetime]:
    if not isinstance(text, str):
        return None
    try:
        out = dt.datetime.fromisoformat(text.strip().replace('Z', '+00:00'))
    except ValueError:
        return None
    return out if out.tzinfo else out.replace(tzinfo=dt.timezone.utc)


def _row_t(row) -> Optional[float]:
    try:
        t = float(row['t_sec'])
    except (KeyError, TypeError, ValueError):
        return None
    return t if 0 <= t < MAX_ROBOT_T_SEC else None


def session_clock(head_rows: Sequence[dict], tail_rows: Sequence[dict],
                  name_wall: Optional[dt.datetime]):
    """(epoch, t_first, t_last) of a session from its first and last manifest rows; any may be None.

    Prefers a row's own `timestamp_utc` (the robot's wall clock at that frame, written by newer
    recorders) and otherwise uses the session name's time. Rows stamped with the Pi's own clock
    (t_sec >= MAX_ROBOT_T_SEC) are ignored.
    """
    valid = [(t, row) for row in head_rows for t in [_row_t(row)] if t is not None]
    t_first = valid[0][0] if valid else None
    epoch = None
    for t, row in valid:
        utc = _parse_utc(row.get('timestamp_utc')) if row.get('timestamp_status', 'synced') == 'synced' else None
        if utc is not None:
            epoch = utc - dt.timedelta(seconds=t)
            break
    if epoch is None and t_first is not None and name_wall is not None:
        epoch = name_wall - dt.timedelta(seconds=t_first)
    t_last = next((t for row in reversed(list(tail_rows)) for t in [_row_t(row)] if t is not None), t_first)
    return epoch, t_first, t_last


# ── helpers ───────────────────────────────────────────────────────────────────────────────────

def _is_akit(name: str) -> bool:
    return name.startswith('akit_')


def _suffix(name: str) -> Optional[str]:
    m = _SUFFIX_RE.search(name)
    return m.group(1).lower() if m else None


def _secs(a: dt.datetime, b: dt.datetime) -> float:
    return (a - b).total_seconds()


def _same_boot(a: Optional[dt.datetime], b: Optional[dt.datetime]) -> bool:
    return a is not None and b is not None and abs(_secs(a, b)) <= EPOCH_TOL_SEC


def _overlaps(sess: PiSessionInfo, t_range: Optional[Tuple[float, float]]) -> bool:
    """False only when both ranges are known and clearly disjoint."""
    if t_range is None or sess.t_first is None or sess.t_last is None:
        return True
    return sess.t_last >= t_range[0] - RANGE_PAD_SEC and sess.t_first <= t_range[1] + RANGE_PAD_SEC


def _sorted(sessions: Iterable[PiSessionInfo]) -> List[PiSessionInfo]:
    return sorted(sessions, key=lambda s: (s.wall_clock.timestamp() if s.wall_clock else 0, s.camera, s.name))


@dataclasses.dataclass
class _Group:
    """One boot's log files: normally an akit_* and an FRC_* twin, sometimes just one."""
    logs: List[RioLogInfo]

    @property
    def wall(self) -> Optional[dt.datetime]:
        walls = [r.wall_clock for r in self.logs if r.wall_clock is not None]
        return min(walls) if walls else None

    @property
    def epoch(self) -> Optional[dt.datetime]:
        return next((r.epoch for r in self.logs if r.epoch is not None), None)

    @property
    def duration(self) -> Optional[float]:
        durations = [r.duration_sec for r in self.logs if r.duration_sec is not None]
        return max(durations) if durations else None

    @property
    def t_range(self) -> Optional[Tuple[float, float]]:
        ranges = [r.t_range for r in self.logs if r.t_range is not None]
        return (min(r[0] for r in ranges), max(r[1] for r in ranges)) if ranges else None


def _twins(a: RioLogInfo, b: RioLogInfo) -> bool:
    if _is_akit(a.name) == _is_akit(b.name):
        return False
    if a.wall_clock is None or b.wall_clock is None:
        return False
    if abs(_secs(a.wall_clock, b.wall_clock)) > TWIN_WINDOW_SEC:
        return False
    if a.boot_id and b.boot_id and a.boot_id != b.boot_id:
        return False
    if a.epoch is not None and b.epoch is not None and not _same_boot(a.epoch, b.epoch):
        return False
    sa, sb = _suffix(a.name), _suffix(b.name)
    return sa is None or sb is None or sa == sb


def _twin_groups(rio_logs: Sequence[RioLogInfo]) -> List[_Group]:
    """Each akit_* log with its FRC_* twin (nearest in time, one-to-one); everything else alone."""
    used: set = set()
    groups: List[_Group] = []
    akits = [r for r in rio_logs if _is_akit(r.name) and r.wall_clock is not None]
    for akit in sorted(akits, key=lambda r: r.wall_clock):
        twins = [r for r in rio_logs if id(r) not in used and _twins(akit, r)]
        group = [akit]
        if twins:
            best = min(twins, key=lambda r: abs(_secs(r.wall_clock, akit.wall_clock)))
            group.append(best)
        used.update(id(r) for r in group)
        groups.append(_Group(group))
    for r in rio_logs:
        if id(r) not in used:
            groups.append(_Group([r]))
    groups.sort(key=lambda g: (g.wall is None, g.wall.timestamp() if g.wall else 0, g.logs[0].name))
    return groups


def _epoch_clusters(sessions: Sequence[PiSessionInfo]) -> List[List[PiSessionInfo]]:
    """Sessions with an epoch, grouped into boots: epochs within EPOCH_TOL_SEC of their neighbour."""
    withe = sorted((s for s in sessions if s.epoch is not None), key=lambda s: s.epoch)
    clusters: List[List[PiSessionInfo]] = []
    for s in withe:
        if clusters and _secs(s.epoch, clusters[-1][-1].epoch) <= EPOCH_TOL_SEC:
            clusters[-1].append(s)
        else:
            clusters.append([s])
    return clusters


def _cluster_epoch(cluster: Sequence[PiSessionInfo]) -> dt.datetime:
    ordered = sorted(cluster, key=lambda s: s.epoch)
    return ordered[len(ordered) // 2].epoch


def _cameras(matched: Iterable[PiSessionInfo]) -> str:
    return ', '.join(sorted({s.camera or '(unnamed)' for s in matched}))


# ── selection ─────────────────────────────────────────────────────────────────────────────────

def select_for_log(rio: RioLogInfo, pi_sessions: Sequence[PiSessionInfo]) -> Optional[Pairing]:
    """Exact selection once the log's own epoch is known (after it is downloaded): every session
    recorded in that boot whose frames overlap the log's time range. None when the log has no
    epoch or nothing matches, so the caller keeps whatever it had."""
    if rio.epoch is None:
        return None
    matched = _sorted(s for s in pi_sessions if _same_boot(s.epoch, rio.epoch) and _overlaps(s, rio.t_range))
    if not matched:
        return None
    return Pairing(rio_log=rio.name, pi_sessions=matched, confidence='high', method='epoch',
                   reason='matched %s by boot clock (epoch %s)' % (_cameras(matched), rio.epoch.isoformat()))


def suggest_pairings(rio_logs: List[RioLogInfo], pi_sessions: List[PiSessionInfo]) -> List[Pairing]:
    """One Pairing per input log, in input order. Twin logs of one boot get the same sessions;
    a session belongs to one boot (a non-epoch session is claimed by one log window)."""
    groups = _twin_groups(rio_logs)
    result: Dict[int, Tuple[List[PiSessionInfo], str, str, str]] = {}   # group index -> sessions, conf, method, reason
    clusters = _epoch_clusters(pi_sessions)
    cluster_taken = [False] * len(clusters)

    # 1. exact: a group whose epoch is known takes every cluster of that boot.
    for gi, g in enumerate(groups):
        if g.epoch is None:
            continue
        got = []
        for ci, cluster in enumerate(clusters):
            if _same_boot(_cluster_epoch(cluster), g.epoch):
                cluster_taken[ci] = True
                got.extend(s for s in cluster if _overlaps(s, g.t_range))
        if got:
            got = _sorted(got)
            result[gi] = (got, 'high', 'epoch',
                          'matched %s by boot clock (epoch %s)' % (_cameras(got), g.epoch.isoformat()))

    # 2. inferred: the earliest log named at/after a boot's epoch (within MAX_SYNC_DELAY_SEC) owns it.
    for ci, cluster in enumerate(clusters):
        if cluster_taken[ci]:
            continue
        epoch = _cluster_epoch(cluster)
        for gi, g in enumerate(groups):
            if g.wall is None or g.epoch is not None:
                continue
            delay = _secs(g.wall, epoch)
            if delay < -EPOCH_TOL_SEC:
                continue
            if delay <= MAX_SYNC_DELAY_SEC:
                cluster_taken[ci] = True
                conf = 'high' if delay <= CONFIDENT_SYNC_DELAY_SEC else 'low'
                got, _c, _m, reason = result.get(gi, ([], conf, 'inferred', ''))
                got = _sorted(got + cluster)
                if _c == 'low':
                    conf = 'low'
                result[gi] = (got, conf, 'inferred',
                              'matched %s by boot clock, boot %d s before the log was named' % (_cameras(got), delay))
            break   # only the earliest eligible log; later ones in the window are not the same boot's first log

    # 3. window: sessions of no claimed boot (no epoch, or a boot no log was named for), by file-name
    # clock and an assumed duration.
    claimed: set = {i for ci, cluster in enumerate(clusters) if cluster_taken[ci]
                    for i, s in enumerate(pi_sessions) if any(s is c for c in cluster)}
    timed = [(gi, g) for gi, g in enumerate(groups) if g.wall is not None]
    for pos, (gi, g) in enumerate(timed):
        next_start = timed[pos + 1][1].wall if pos + 1 < len(timed) else None
        lo, hi = g.wall - dt.timedelta(seconds=TOLERANCE_SEC), None
        duration = g.duration if g.duration is not None else DEFAULT_ASSUMED_DURATION_SEC
        hi = g.wall + dt.timedelta(seconds=duration + TOLERANCE_SEC)
        if next_start is not None and next_start > g.wall:
            hi = min(hi, next_start)
        found, slops = [], []
        for i, s in enumerate(pi_sessions):
            if i in claimed or s.wall_clock is None or (s.epoch is not None and g.epoch is not None):
                continue
            if lo <= s.wall_clock <= hi and (next_start is None or s.wall_clock < next_start or next_start <= g.wall):
                claimed.add(i)
                found.append(s)
                slops.append(min(abs(_secs(s.wall_clock, lo)), abs(_secs(hi, s.wall_clock))))
        if not found:
            continue
        got, conf, method, reason = result.get(gi, ([], 'high', 'filename', ''))
        got = _sorted(got + found)
        if method == 'filename':
            conf = 'high' if min(slops) >= HIGH_CONFIDENCE_SLOP_SEC else 'low'
            reason = 'matched %s by file-name clock (no boot clock to compare)' % _cameras(got)
        else:
            reason += '; plus %d session(s) with no boot clock matched by file-name clock' % len(found)
        result[gi] = (got, conf, method, reason)

    out = []
    group_of = {id(r): gi for gi, g in enumerate(groups) for r in g.logs}
    for rio in rio_logs:
        gi = group_of[id(rio)]
        if gi in result:
            got, conf, method, reason = result[gi]
            out.append(Pairing(rio_log=rio.name, pi_sessions=list(got), confidence=conf, reason=reason, method=method))
        elif rio.wall_clock is None and groups[gi].wall is None and groups[gi].epoch is None:
            out.append(Pairing(rio_log=rio.name, pi_sessions=[], confidence='none', method='none',
                               reason='no wall-clock start (filename was never DS-renamed from FRC_TBD_*)'))
        else:
            out.append(Pairing(rio_log=rio.name, pi_sessions=[], confidence='none', method='none',
                               reason='no Pi session found for this boot or time'))
    return out
