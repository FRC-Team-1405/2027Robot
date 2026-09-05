"""Window selection and two-Run comparison.

Two ways to pick the slice of a log to score, matching the two comparisons this tool
needs to support: "compare the autonomous window in log A against the autonomous window
in log B" (WindowSelector.mode) and "compare this arbitrary slice of A against that
arbitrary slice of B" (WindowSelector.manual). Both produce a Window and both feed the
same `compare()` -- neither the metric registry nor the delta/verdict table cares which
one picked the boundaries.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import composites as composites_mod
from . import metrics as metrics_mod
from .log import Log
from .runs import Run, Window

# Ratio band treated as noise rather than a real change, matching tools/ab-metrics'
# existing verdict() -- kept the same so a threshold tuned there carries over here.
VERDICT_THRESHOLD = 0.10

MODES = ('auto', 'teleop', 'disabled', 'whole')


@dataclass
class WindowSelector:
    """Exactly one of `mode` or `manual` should be set. `mode` picks a DS-mode span (or
    'whole' for no trim at all) independently in whichever log it's resolved against;
    `manual` is an explicit [lo, hi] in seconds relative to that log's own start."""
    mode: Optional[str] = None
    manual: Optional[Tuple[float, float]] = None

    def resolve(self, log: Log) -> Window:
        t0, t1 = log.bounds()
        if self.manual is not None:
            lo, hi = self.manual
            return Window(t0 + lo, t0 + hi)

        mode = self.mode or 'whole'
        if mode == 'whole':
            return Window(t0, t1)
        if mode not in MODES:
            raise ValueError(f'unknown mode {mode!r} (have: {", ".join(MODES)})')

        spans = log.mode_spans()
        matching = [(s, e) for s, e, m in spans if m == mode]
        if not matching:
            raise ValueError(
                f'no {mode!r} span found in {log.path.name} '
                f'(spans found: {[(round(s, 1), round(e, 1), m) for s, e, m in spans]})'
            )
        # A log should have one contiguous span per mode in the common case (one auto
        # period at the start of a match); if more than one exists, the longest is the
        # one worth scoring.
        lo, hi = max(matching, key=lambda span: span[1] - span[0])
        return Window(t0 + lo, t0 + hi)


def make_run(log: Log, selector: WindowSelector, label: str = '') -> Run:
    return Run(log=log, window=selector.resolve(log), label=label or log.path.name)


def _label(id_: str) -> str:
    if id_ in composites_mod.COMPOSITES:
        return composites_mod.COMPOSITES[id_].label
    return metrics_mod.METRICS[id_].label


def _unit(id_: str) -> Optional[str]:
    if id_ in composites_mod.COMPOSITES:
        return '%'
    return metrics_mod.METRICS[id_].unit


def _lower_is_better(id_: str) -> bool:
    if id_ in composites_mod.COMPOSITES:
        return composites_mod.COMPOSITES[id_].lower_is_better
    return metrics_mod.METRICS[id_].lower_is_better


def verdict(a: Optional[float], b: Optional[float], lower_is_better: bool,
            threshold: float = VERDICT_THRESHOLD) -> str:
    """'improved' / 'regressed' / 'neutral' (within +/-threshold) / 'n/a' (missing data).
    Mirrors tools/ab-metrics/compare.py's verdict() so an existing intuition for the
    labels carries over."""
    if a is None or b is None:
        return 'n/a'
    if a == 0:
        if b == 0:
            return 'neutral'
        improved = (b > 0) != lower_is_better
        return 'improved' if improved else 'regressed'
    ratio = b / a
    if ratio > 1 + threshold:
        return 'regressed' if lower_is_better else 'improved'
    if ratio < 1 - threshold:
        return 'improved' if lower_is_better else 'regressed'
    return 'neutral'


@dataclass
class MetricDelta:
    id: str
    label: str
    unit: Optional[str]
    camera: str
    a: Optional[float]
    b: Optional[float]
    delta: Optional[float]
    verdict: str


def compare(run_a: Run, run_b: Run, metric_ids: List[str], cameras: List[str]) -> List[MetricDelta]:
    out: List[MetricDelta] = []
    for metric_id in metric_ids:
        lower_is_better = _lower_is_better(metric_id)
        for camera in cameras:
            a = run_a.value(metric_id, camera)
            b = run_b.value(metric_id, camera)
            delta = (b - a) if (a is not None and b is not None) else None
            out.append(MetricDelta(
                id=metric_id, label=_label(metric_id), unit=_unit(metric_id), camera=camera,
                a=a, b=b, delta=delta, verdict=verdict(a, b, lower_is_better),
            ))
    return out
