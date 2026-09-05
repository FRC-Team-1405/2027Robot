"""Composite = a named function of other metrics/composites, resolved recursively.

The registry is deliberately tiny: a Composite is its id, its dependency ids (metric or
other composite ids), and a `combine(values) -> value | None` function. `resolve()` walks
the dependency ids, fetching each one from the Run (which itself doesn't care whether an
id names a Metric or a Composite -- see Run.value), and short-circuits to None if any
dependency is missing rather than let a composite silently score off partial data.

Composites can depend on composites: nothing here restricts a dependency to being a leaf
Metric, so a new composite can be built on top of still_score/motion_score without
touching the resolver.
"""
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

Combine = Callable[[Dict[str, float]], Optional[float]]


@dataclass
class Composite:
    id: str
    label: str
    deps: Tuple[str, ...]
    combine: Combine
    lower_is_better: bool = False


COMPOSITES: Dict[str, Composite] = {}


def register(id_: str, label: str, deps: Tuple[str, ...], combine: Combine,
             lower_is_better: bool = False) -> Composite:
    c = Composite(id=id_, label=label, deps=deps, combine=combine, lower_is_better=lower_is_better)
    COMPOSITES[id_] = c
    return c


def resolve(run, composite_id: str, camera: Optional[str] = None) -> Optional[float]:
    comp = COMPOSITES[composite_id]
    values = {dep: run.value(dep, camera) for dep in comp.deps}
    if any(v is None for v in values.values()):
        return None
    return comp.combine(values)


# ─── Vision composites ──────────────────────────────────────────────────────────────────
#
# Both read the same eight Vision/*/Health/*Percent factors (as 0-1 fractions); they only
# differ in how they combine them. See VisionHealth.java's computeCameraHealthFromFactors
# for the on-robot formula still_score mirrors, and its comment on effectiveJitterFactor
# for why jitter is blended by stillness rather than multiplied in outright: jitter (pose
# stddev) rises with motion for physical reasons that have nothing to do with camera
# health, so multiplying the raw factor in unconditionally double-counts "the robot is
# moving" against a run that's expected to be moving the whole time (an autonomous replay,
# not a pit "hold it still" check).

_STILL_DEPS = (
    'stillness_pct', 'area_pct', 'ambiguity_pct', 'fps_pct', 'jitter_pct',
    'acceptance_pct', 'latency_pct', 'multitag_pct',
)


def _combine_still(values: Dict[str, float]) -> float:
    stillness = values['stillness_pct'] / 100.0
    jitter = values['jitter_pct'] / 100.0
    effective_jitter = 1.0 - stillness * (1.0 - jitter)
    factors = (
        stillness, values['area_pct'] / 100.0, values['ambiguity_pct'] / 100.0,
        values['fps_pct'] / 100.0, effective_jitter, values['acceptance_pct'] / 100.0,
        values['latency_pct'] / 100.0, values['multitag_pct'] / 100.0,
    )
    product = 1.0
    for f in factors:
        product *= f
    return 100.0 * product


register('still_score', 'Still score', _STILL_DEPS, _combine_still)


_MOTION_DEPS = (
    'area_pct', 'ambiguity_pct', 'fps_pct', 'acceptance_pct', 'latency_pct', 'multitag_pct',
)


def _combine_motion(values: Dict[str, float]) -> float:
    factors = (
        values['area_pct'] / 100.0, values['ambiguity_pct'] / 100.0, values['fps_pct'] / 100.0,
        values['acceptance_pct'] / 100.0, values['latency_pct'] / 100.0,
        values['multitag_pct'] / 100.0,
    )
    product = 1.0
    for f in factors:
        product *= f
    return 100.0 * product


register('motion_score', 'Motion score', _MOTION_DEPS, _combine_motion)
