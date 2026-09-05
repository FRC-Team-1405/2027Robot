"""Metric primitives: a named `(run, camera) -> value | None` function, registered by id.

Two families, deliberately built differently:

  - Health-factor metrics (stillness_pct, area_pct, ...) read the values VisionHealth.java
    already computed and logged under Vision/<cam>/Health/<Suffix>Percent. This library
    does NOT reimplement the LerpTable curves behind them: camera_calibration/nt_client.py
    used to do exactly that and silently drifted out of sync with VisionConstants.java
    until it was rewritten to be a pure display client (see that module's docstring).
    composites.py recombines these already-correct values into new scores; it never
    re-derives a factor from a raw sensor reading.

  - Log-derived metrics (acceptance_rate, fps_mean, ...) wrap vision_analyzer.metrics'
    existing per-camera computation instead of a second implementation of the same math,
    for the same reason -- one place to fix a bug in "how do we count an accepted pose".

Both families are registered into the same METRICS dict, so a Composite or a CLI caller
never needs to know or care which family a dependency comes from.
"""
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from vision_analyzer import metrics as va_metrics

from . import signals as sig

Compute = Callable[[object, Optional[str]], Optional[float]]


@dataclass
class Metric:
    id: str
    label: str
    unit: Optional[str]
    lower_is_better: bool
    compute: Compute


METRICS: Dict[str, Metric] = {}


def register(id_: str, label: str, unit: Optional[str], lower_is_better: bool,
             compute: Compute) -> Metric:
    m = Metric(id=id_, label=label, unit=unit, lower_is_better=lower_is_better, compute=compute)
    METRICS[id_] = m
    return m


def _mean_in_window(run, series) -> Optional[float]:
    values = [v for _, v in run.in_window(series) if v is not None]
    return sum(values) / len(values) if values else None


# ─── Health-factor metrics (already scored on the robot) ───────────────────────────────

# (id suffix, log-key suffix, label) -- mirrors specs/camera_health.py's FACTORS table so
# a track on the replay chart and a metric id here name the same factor identically.
_HEALTH_FACTORS = [
    ('stillness', 'StillnessPercent', 'Stillness'),
    ('area', 'AreaPercent', 'Tag area'),
    ('ambiguity', 'AmbiguityPercent', 'Ambiguity'),
    ('fps', 'FpsPercent', 'FPS'),
    ('jitter', 'JitterPercent', 'Jitter'),
    ('acceptance', 'AcceptanceRateFactorPercent', 'Acceptance'),
    ('latency', 'LatencyPercent', 'Latency'),
    ('multitag', 'MultiTagRatioPercent', 'Multi-tag'),
    ('score', 'ScorePercent', 'Robot-reported score'),
]


def _make_health_factor_compute(log_suffix: str) -> Compute:
    def compute(run, camera):
        if camera is None:
            return None
        series = sig.find_signal(run.log.signals, f'Vision/{camera}/Health/{log_suffix}')
        if not series:
            return None
        return _mean_in_window(run, series)
    return compute


for _suffix, _log_suffix, _label in _HEALTH_FACTORS:
    register(f'{_suffix}_pct', _label, '%', False, _make_health_factor_compute(_log_suffix))


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
    ('acceptance_rate', 'Acceptance rate (raw)', '%', False),
    ('fps_mean', 'FPS (mean)', 'fps', False),
    ('fps_min', 'FPS (min)', 'fps', False),
    ('conn_uptime_pct', 'Connection uptime', '%', False),
    ('latency_mean_ms', 'Latency (mean)', 'ms', True),
    ('stationary_quality', 'Stationary acceptance rate', '%', False),
]

for _field, _label, _unit, _lower in _VA_FIELDS:
    register(_field, _label, _unit, _lower, _make_va_field_compute(_field))
