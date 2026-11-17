"""How much of a match's enabled time has a Pi vision frame, camera by camera, and where it does not.

A bundle can hold every frame that was recorded and still be thin: the recorder splits a match into
short sessions whenever the camera or NetworkTables flaps, and whatever fell between them was never
captured. Pairing cannot fix that, so it is shown instead: per camera, the share of the enabled
(auto + teleop) windows within FRAME_REACH_SEC of a frame, and the largest stretches with none. The
Health Check page shows these as rows (health_rows) so a sparse bundle is visible at a glance.

Times are seconds on the log's own axis, the same axis as a frame's `t_sec`. Gaps are reported
relative to the start of the log, matching the Health Check page's mode bands.
"""
import dataclasses
import pathlib
from typing import Iterable, List, Optional, Sequence, Tuple

import bundles
from health import engine

# A frame vouches for the time this far either side of it (the recorder samples a few times a second).
FRAME_REACH_SEC = 0.5
# An uncovered stretch shorter than this is not worth listing.
MIN_GAP_SEC = 2.0
MAX_GAPS_LISTED = 5

WARN_BELOW_PCT = 90.0
FAIL_BELOW_PCT = 50.0
WARN_GAP_SEC = 10.0
FAIL_GAP_SEC = 60.0

SECTION = 'Vision recording'


@dataclasses.dataclass
class CameraCoverage:
    camera: str
    frames: int
    sessions: int
    enabled_sec: float
    covered_sec: float
    gaps: List[Tuple[float, float]]      # largest first; (start, end) seconds into the log

    @property
    def fraction(self) -> Optional[float]:
        return self.covered_sec / self.enabled_sec if self.enabled_sec > 0 else None

    @property
    def longest_gap(self) -> float:
        return max((b - a for a, b in self.gaps), default=0.0)


def enabled_windows(mode_spans: Iterable[Tuple[float, float, str]], t0: float) -> List[Tuple[float, float]]:
    """Absolute [(start, end)] of the non-disabled spans of `log.mode_spans()` (which is relative to t0)."""
    return [(a + t0, b + t0) for a, b, mode in mode_spans if mode != 'disabled' and b > a]


def coverage_of(times: Sequence[float], windows: Sequence[Tuple[float, float]]):
    """(covered_sec, gaps) for sorted frame times against the enabled windows (absolute seconds).
    gaps are the uncovered stretches of at least MIN_GAP_SEC, largest first."""
    covered = 0.0
    gaps: List[Tuple[float, float]] = []
    for a, b in windows:
        cursor = a
        for t in times:
            if t + FRAME_REACH_SEC <= cursor:
                continue
            if t - FRAME_REACH_SEC >= b:
                break
            lo, hi = max(a, t - FRAME_REACH_SEC), min(b, t + FRAME_REACH_SEC)
            if lo > cursor:
                if lo - cursor >= MIN_GAP_SEC:
                    gaps.append((cursor, lo))
                covered += hi - lo
            else:
                covered += max(0.0, hi - cursor)
            cursor = max(cursor, hi)
        if b - cursor >= MIN_GAP_SEC:
            gaps.append((cursor, b))
    gaps.sort(key=lambda g: g[0] - g[1])
    return covered, gaps


def bundle_coverage(log_path, windows: Sequence[Tuple[float, float]], t0: float,
                    cameras: Sequence[str] = ()) -> Optional[List[CameraCoverage]]:
    """Per camera folder in the log's `.vision` directory (None when it has no vision recording).
    A folder takes the log's spelling of the camera name when they match ignoring case."""
    sessions = bundles.list_vision_sessions(log_path)
    if not sessions:
        return None
    spelling = {c.casefold(): c for c in cameras}
    total = sum(b - a for a, b in windows)
    out = []
    for folder, dirs in sessions.items():
        times: List[float] = []
        used = 0
        for d in dirs:
            frames = [t for t, _name in bundles.read_manifest(d).frames]
            if frames:
                used += 1
                times.extend(frames)
        times.sort()
        covered, gaps = coverage_of(times, windows)
        out.append(CameraCoverage(
            camera=spelling.get(folder.casefold(), folder or '(unnamed)'), frames=len(times), sessions=used,
            enabled_sec=total, covered_sec=covered,
            gaps=[(a - t0, b - t0) for a, b in gaps]))
    return sorted(out, key=lambda c: c.camera)


def _gap_text(gaps: Sequence[Tuple[float, float]], n: int) -> str:
    return ', '.join('%.0f-%.0f s (%.0f s)' % (a, b, b - a) for a, b in gaps[:n])


def _coverage_rule() -> str:
    return 'warn below %.0f%%, fail below %.0f%%' % (WARN_BELOW_PCT, FAIL_BELOW_PCT)


def health_rows(coverage: Optional[List[CameraCoverage]], expected_cameras: Sequence[str] = ()) -> List[dict]:
    """Health Check rows (engine.make_row shape). Nothing at all for a log that was not bundled with
    a vision recording, so a plain log's report is unchanged."""
    if coverage is None:
        return []
    rows = []
    have = {c.camera.casefold() for c in coverage}
    for cam in coverage:
        pct = None if cam.fraction is None else cam.fraction * 100
        if pct is None:
            status, detail = engine.NODATA, 'the log has no enabled time to compare against'
        else:
            status = engine.FAIL if pct < FAIL_BELOW_PCT else engine.WARN if pct < WARN_BELOW_PCT else engine.OK
            detail = '%d frames in %d session%s' % (cam.frames, cam.sessions, '' if cam.sessions == 1 else 's')
            if cam.gaps:
                detail += '; largest gaps: ' + _gap_text(cam.gaps, 3)
        rows.append(engine.make_row(
            id='vision.recording.coverage', section=SECTION, group=cam.camera, label='Enabled time with a frame',
            status=status, value=pct, display='n/a' if pct is None else '%.0f%%' % pct,
            unit='% of enabled time', rule=_coverage_rule(), detail=detail,
            help='Share of auto + teleop within %.1f s of a frame the Orange Pi recorded and this bundle '
                 'holds. What is missing was never captured.' % FRAME_REACH_SEC))
        gap = cam.longest_gap
        status = engine.FAIL if gap > FAIL_GAP_SEC else engine.WARN if gap > WARN_GAP_SEC else engine.OK
        rows.append(engine.make_row(
            id='vision.recording.gap', section=SECTION, group=cam.camera, label='Longest stretch with no frame',
            status=status, value=gap, display='%.0f s' % gap, unit='s',
            rule='warn above %.0f s, fail above %.0f s' % (WARN_GAP_SEC, FAIL_GAP_SEC),
            detail=('largest gaps: ' + _gap_text(cam.gaps, MAX_GAPS_LISTED)) if cam.gaps else 'no gaps',
            help='Seconds into the log. Gaps shared by every camera point at the Pi or the network '
                 '(NetworkTables flapping), not one camera.'))
    for cam in expected_cameras:
        if cam.casefold() not in have:
            rows.append(engine.make_row(
                id='vision.recording.coverage', section=SECTION, group=cam, label='Enabled time with a frame',
                status=engine.FAIL, value=None, display='none', unit='% of enabled time',
                rule=_coverage_rule(),
                detail='the robot logged this camera but the bundle has no recording folder for it',
                help='Cameras are matched to recorder folders ignoring case.'))
    return rows


def for_log(log_path, mode_spans, t0: float, cameras: Sequence[str] = ()) -> List[dict]:
    """Rows for one finished log; the caller adds them to the Health report."""
    windows = enabled_windows(mode_spans, t0)
    return health_rows(bundle_coverage(pathlib.Path(log_path), windows, t0, cameras), cameras)
