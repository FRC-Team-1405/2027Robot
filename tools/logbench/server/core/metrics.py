"""Metric primitives: a named `(run, camera) -> value | None` function, registered by id.

Two families, deliberately built differently:

  - Health-factor metrics (stillness_pct, area_pct, ...) read the values VisionHealth.java
    already computed and logged under Vision/<cam>/Health/<Suffix>Percent. This library
    does NOT reimplement the LerpTable curves behind them: camera_calibration/nt_client.py
    used to do exactly that and silently drifted out of sync with VisionConstants.java
    until it was rewritten to be a pure display client (see that module's docstring).
    composites.py recombines these already-correct values into new scores; it never
    re-derives a factor from a raw sensor reading.

  - Log-derived metrics (acceptance_rate, fps_mean, tag_in_view_pct, ...) are computed from the
    raw log. The vision_analyzer ones wrap its existing per-camera computation instead of a
    second implementation of the same math, for the same reason -- one place to fix a bug in
    "how do we count an accepted pose".

Both families are registered into the same METRICS dict, so a Composite or a CLI caller
never needs to know or care which family a dependency comes from.

Every metric also declares a category (availability / quality / context, see categories.py).
Two rules from docs/adr/0001 are enforced here for the health factors:

  - Averages are time-weighted. AdvantageKit logs a value only when it changes, so averaging
    records weights by how often a value changed rather than how long it lasted.
  - Factors are averaged only over the times a tag was in view. The robot zeroes every factor on
    a loop with no tag; counting those zeros inside each factor would count one dropout once per
    factor. The dropout is reported once, as its own availability metric (tag_in_view_pct).
"""
import math
import statistics
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from vision_analyzer import metrics as va_metrics

from . import categories as cat
from . import signals as sig

Compute = Callable[[object, Optional[str]], Optional[float]]


@dataclass
class Metric:
    id: str
    label: str
    unit: Optional[str]
    lower_is_better: bool
    compute: Compute
    category: str
    # False for a whole-run fact that is the same whichever camera you ask about (robot speed):
    # compare() computes it once instead of once per camera.
    per_camera: bool = True


METRICS: Dict[str, Metric] = {}


def register(id_: str, label: str, unit: Optional[str], lower_is_better: bool,
             compute: Compute, *, category: str, per_camera: bool = True) -> Metric:
    if category not in cat.ALL_IDS:
        raise ValueError(f'unknown category {category!r} for metric {id_!r}')
    m = Metric(id=id_, label=label, unit=unit, lower_is_better=lower_is_better,
               compute=compute, category=category, per_camera=per_camera)
    METRICS[id_] = m
    return m


def _mean_in_window(run, series, only_where_tag_in_view: Optional[str] = None) -> Optional[float]:
    """Time-weighted mean of a logged series over the run's window (sample-and-hold, see
    signals.hold_intervals). If `only_where_tag_in_view` names a camera, only the stretches
    where that camera had a tag in view count. Falls back to the plain values at that instant
    for a zero-length window (a log with a single record)."""
    lo, hi = run.window.lo, run.window.hi
    if hi <= lo:
        values = [v for t, v in series if lo <= t <= hi and v is not None]
        return sum(values) / len(values) if values else None
    pieces = [p for p in sig.hold_intervals(series, lo, hi) if p[2] is not None]
    if only_where_tag_in_view is not None:
        spans = _tag_in_view_spans(run, only_where_tag_in_view)
        if spans is not None:
            pieces = sig.clip_to_spans(pieces, spans)
    return sig.time_weighted_mean(pieces)


# ─── Tag in view ────────────────────────────────────────────────────────────────────────

def _tag_state_pieces(run, camera: str) -> Optional[List[Tuple[float, float, bool]]]:
    """(start, end, tag_in_view) pieces over the run window, or None if the log records
    nothing from which to tell.

    Preferred source is the robot's own Health/Reason: '' when a tag-bearing result arrived
    this loop, otherwise the reason the score was zeroed -- the exact gate VisionHealth.java
    applies. Older logs without it fall back to whether the loop's raw pose array was
    non-empty, which is the same condition (Camera.periodic only records a pose when a
    result had targets)."""
    key = ('_tag_state_pieces', camera)
    if key in run.cache:
        return run.cache[key]
    lo, hi = run.window.lo, run.window.hi
    pieces = None
    reason = sig.find_signal(run.log.signals, f'Vision/{camera}/Health/Reason')
    if reason:
        pieces = [(a, b, v == '') for a, b, v in sig.hold_intervals(reason, lo, hi)]
    else:
        raw = sig.find_signal(run.log.signals, f'Vision/{camera}/RawEstimatedPoses')
        if raw:
            pieces = [(a, b, bool(v)) for a, b, v in sig.hold_intervals(raw, lo, hi)]
    run.cache[key] = pieces
    return pieces


def _tag_in_view_spans(run, camera: str) -> Optional[List[Tuple[float, float]]]:
    pieces = _tag_state_pieces(run, camera)
    if pieces is None:
        return None
    return sig.merge_spans([(a, b) for a, b, in_view in pieces if in_view])


def _tag_in_view_pct(run, camera) -> Optional[float]:
    """Share of the window during which a tag-bearing result was in view. Route-dependent (a
    robot facing away from the tags lowers it without any camera fault), which the metric
    description says out loud. Denominator is the time the log actually covers."""
    if camera is None:
        return None
    pieces = _tag_state_pieces(run, camera)
    if not pieces:
        return None
    total = sum(b - a for a, b, _ in pieces)
    if total <= 0:
        return None
    return 100.0 * sum(b - a for a, b, in_view in pieces if in_view) / total


def _longest_gap_ms(run, camera) -> Optional[float]:
    """The longest unbroken stretch with no tag in view. Same fraction of time can be fifty
    20 ms blips or one 1 s hole; only the second starves odometry of corrections."""
    if camera is None:
        return None
    pieces = _tag_state_pieces(run, camera)
    if not pieces:
        return None
    gaps = sig.merge_spans([(a, b) for a, b, in_view in pieces if not in_view])
    return 1000.0 * max((b - a for a, b in gaps), default=0.0)


# ─── Context: what the run looked like (never scored) ───────────────────────────────────

def _range_median_m(run, camera) -> Optional[float]:
    """Median range to the tags actually used, over every result in the window. Per-result,
    not time-weighted: each camera result is one observation of the range."""
    if camera is None:
        return None
    raw = sig.find_signal(run.log.signals, f'Vision/{camera}/RawAvgDistancesMeters')
    if not raw:
        return None
    values = [d for _, arr in run.in_window(raw) for d in (arr or []) if d and d > 0]
    return statistics.median(values) if values else None


def _speed_mean_mps(run, camera) -> Optional[float]:
    """Time-weighted mean chassis speed magnitude (m/s) over the window."""
    vx = sig.find_signal(run.log.signals, 'Drivetrain/Speeds/vxMetersPerSecond')
    vy = sig.find_signal(run.log.signals, 'Drivetrain/Speeds/vyMetersPerSecond')
    lo, hi = run.window.lo, run.window.hi
    if not vx or hi <= lo:
        return None
    vy_by_t = {t: v for t, v in vy} if vy else {}
    speeds = []
    last_vy = 0.0
    for t, x in vx:
        last_vy = vy_by_t.get(t, last_vy)
        speeds.append((t, math.hypot(x, last_vy)))
    return sig.time_weighted_mean(sig.hold_intervals(speeds, lo, hi))


# ─── Health-factor metrics (already scored on the robot) ───────────────────────────────

# (id suffix, log-key suffix, label, category) -- mirrors specs/camera_health.py's FACTORS
# table so a track on the replay chart and a metric id here name the same factor identically.
# Categories follow the "what would you fix" test in categories.py. Multi-tag is filed under
# quality provisionally: it partly reflects route geometry (docs/adr/0001, D1).
_HEALTH_FACTORS = [
    ('stillness', 'StillnessPercent', 'Stillness', cat.CONTEXT),
    ('area', 'AreaPercent', 'Tag area', cat.QUALITY),
    ('ambiguity', 'AmbiguityPercent', 'Ambiguity', cat.QUALITY),
    ('fps', 'FpsPercent', 'FPS', cat.AVAILABILITY),
    ('jitter', 'JitterPercent', 'Jitter', cat.QUALITY),
    ('acceptance', 'AcceptanceRateFactorPercent', 'Acceptance', cat.QUALITY),
    ('latency', 'LatencyPercent', 'Latency', cat.AVAILABILITY),
    ('multitag', 'MultiTagRatioPercent', 'Multi-tag', cat.QUALITY),
]


def _make_health_factor_compute(log_suffix: str) -> Compute:
    def compute(run, camera):
        if camera is None:
            return None
        series = sig.find_signal(run.log.signals, f'Vision/{camera}/Health/{log_suffix}')
        if not series:
            return None
        return _mean_in_window(run, series, only_where_tag_in_view=camera)
    return compute


for _suffix, _log_suffix, _label, _category in _HEALTH_FACTORS:
    register(f'{_suffix}_pct', _label, '%', False, _make_health_factor_compute(_log_suffix),
             category=_category)


def _robot_score(run, camera) -> Optional[float]:
    """The robot's own overall score, exactly as it reported it: time-weighted but NOT
    conditioned on tag-in-view, so it still includes the loops the robot scored 0. It also
    multiplies stillness in, which is why it is filed as legacy rather than as a health score."""
    if camera is None:
        return None
    series = sig.find_signal(run.log.signals, f'Vision/{camera}/Health/ScorePercent')
    return _mean_in_window(run, series) if series else None


register('score_pct', 'Robot-reported score', '%', False, _robot_score, category=cat.LEGACY)

# New in docs/adr/0001 D1: availability and context, derived from the raw log so existing logs
# are covered without a robot deploy.
register('tag_in_view_pct', 'Tag in view', '%', False, _tag_in_view_pct,
         category=cat.AVAILABILITY)
register('longest_gap_ms', 'Longest gap', 'ms', True, _longest_gap_ms,
         category=cat.AVAILABILITY)
register('range_median_m', 'Median range to tags', 'm', False, _range_median_m,
         category=cat.CONTEXT)
register('speed_mean_mps', 'Mean robot speed', 'm/s', False, _speed_mean_mps,
         category=cat.CONTEXT, per_camera=False)


# ─── Log-derived metrics (vision_analyzer's per-camera computation) ────────────────────

def _va_metrics_for(run, camera: str) -> dict:
    """vision_analyzer.metrics.compute_camera_metrics, memoized per (run, camera) since
    several Metric entries below pull different fields out of one call. Signals are
    pre-filtered to the run's window first -- compute_camera_metrics itself only
    relativizes timestamps, it does not restrict to a time range."""
    key = ('_va_metrics', camera)
    if key not in run.cache:
        windowed = va_metrics.filter_signals_by_time(
            run.log.signals, run.window.lo, run.window.hi)
        fmt = va_metrics.detect_format(windowed, camera)
        linear_key, omega_key = va_metrics.find_drivetrain_speeds(windowed)
        linear_sig = windowed.get(linear_key) if linear_key else None
        omega_sig = windowed.get(omega_key) if omega_key else None
        run.cache[key] = va_metrics.compute_camera_metrics(
            windowed, camera, fmt, run.window.lo, run.window.hi, linear_sig, omega_sig)
    return run.cache[key]


def _make_va_field_compute(field_name: str) -> Compute:
    def compute(run, camera):
        if camera is None:
            return None
        return _va_metrics_for(run, camera).get(field_name)
    return compute


_VA_FIELDS = [
    ('acceptance_rate', 'Acceptance rate (raw)', '%', False, cat.QUALITY),
    ('fps_mean', 'FPS (mean)', 'fps', False, cat.AVAILABILITY),
    ('fps_min', 'FPS (min)', 'fps', False, cat.AVAILABILITY),
    ('conn_uptime_pct', 'Connection uptime', '%', False, cat.AVAILABILITY),
    ('latency_mean_ms', 'Latency (mean)', 'ms', True, cat.AVAILABILITY),
    ('stationary_quality', 'Stationary acceptance rate', '%', False, cat.QUALITY),
]

for _field, _label, _unit, _lower, _category in _VA_FIELDS:
    register(_field, _label, _unit, _lower, _make_va_field_compute(_field), category=_category)
