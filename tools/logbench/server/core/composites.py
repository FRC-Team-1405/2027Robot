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

from . import categories as cat

Combine = Callable[[Dict[str, float]], Optional[float]]


@dataclass
class Composite:
    id: str
    label: str
    deps: Tuple[str, ...]
    combine: Combine
    lower_is_better: bool = False
    # Defaults to legacy: a composite has to opt in to being an availability/quality/overall
    # score, and the structural test on those (no context dependency) then covers it.
    category: str = cat.LEGACY


COMPOSITES: Dict[str, Composite] = {}


def register(id_: str, label: str, deps: Tuple[str, ...], combine: Combine,
             lower_is_better: bool = False, category: str = cat.LEGACY) -> Composite:
    if category not in cat.ALL_IDS:
        raise ValueError(f'unknown category {category!r} for composite {id_!r}')
    c = Composite(id=id_, label=label, deps=deps, combine=combine,
                  lower_is_better=lower_is_better, category=category)
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


register('still_score', 'Still score (legacy)', _STILL_DEPS, _combine_still)


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


register('motion_score', 'Motion score (legacy)', _MOTION_DEPS, _combine_motion)


# --- Category scores (docs/adr/0001, D1) -----------------------------------------------------
#
# still_score and motion_score above predate the availability/quality/context split: still_score
# multiplies stillness (context) in, and motion_score multiplies availability and quality
# factors into one number, so neither can say which axis moved. They stay registered (existing
# scripts and exports name them) but are filed as legacy.
#
# The scores below are one per scored category, never mixed, and never depend on a context
# metric (tests/test_categories.py enforces that structurally). Each is a product, mirroring the
# robot's own composition: one bad factor craters the score instead of being averaged away.
#
# The quality factors are already averaged only over the times a tag was in view (metrics.py), so a
# dropout is not counted inside each of them -- it shows up once, in availability, as tag_in_view.
# Jitter is deliberately left out of quality_score, for the same reason motion_score leaves it out:
# pose scatter rises with motion for physical reasons that have nothing to do with camera quality,
# and the only motion-aware treatment we have (blending by stillness) would pull a context
# metric into the score. It remains available as its own quality metric.

_AVAILABILITY_DEPS = ('tag_in_view_pct', 'fps_pct', 'latency_pct')


def _combine_availability(values: Dict[str, float]) -> float:
    product = 1.0
    for dep in _AVAILABILITY_DEPS:
        product *= values[dep] / 100.0
    return 100.0 * product


register('availability_score', 'Availability score', _AVAILABILITY_DEPS, _combine_availability,
         category=cat.AVAILABILITY)


_QUALITY_DEPS = ('area_pct', 'ambiguity_pct', 'acceptance_pct', 'multitag_pct')


def _combine_quality(values: Dict[str, float]) -> float:
    product = 1.0
    for dep in _QUALITY_DEPS:
        product *= values[dep] / 100.0
    return 100.0 * product


register('quality_score', 'Quality score', _QUALITY_DEPS, _combine_quality, category=cat.QUALITY)


def _combine_health(values: Dict[str, float]) -> float:
    return values['availability_score'] * values['quality_score'] / 100.0


# Optional convenience number; the two scores above are the headline. Because it only depends
# on the two scored composites it inherits their exclusion of context.
register('health_score', 'Health score (availability x quality)',
         ('availability_score', 'quality_score'), _combine_health, category=cat.OVERALL)
