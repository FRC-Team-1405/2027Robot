"""Pure scoring functions for the live camera-health heuristic (Tab 5).

No NetworkTables or Streamlit imports here on purpose — this keeps the scoring
math independently testable and reusable regardless of where the numbers come
from (live NT4, a replayed log, a unit test).

This is a *tuning aid*, not a match-accuracy tool (that's ../vision-analyzer).
It answers "does this camera look healthy right now, with a tag in view and
the robot held still" — not "how did vision perform last match." A camera
sitting at a worse mount angle than another will always read lower here; the
useful signal is the same camera's score moving up or down as you change its
configuration, not the absolute number.
"""
from dataclasses import dataclass, field
from typing import Optional


def _lerp(table: list[tuple[float, float]], x: float) -> float:
    """Piecewise-linear interpolation, clamped at the ends. Mirrors lib/LerpTable.java."""
    if x <= table[0][0]:
        return table[0][1]
    if x >= table[-1][0]:
        return table[-1][1]
    for (x0, y0), (x1, y1) in zip(table, table[1:]):
        if x0 <= x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return table[-1][1]


# Mirrors VisionConstants.Filtering.AREA_WEIGHT_COEFFICIENT (2026 baseline) — the
# same curve the robot itself uses to trust an accepted pose, in percent-of-image
# units. Keep in sync if that Java table changes.
_AREA_CURVE = [(0.0, 0.0), (0.2, 0.35), (1.0, 0.45), (4.0, 0.70), (7.5, 1.0)]

# Mirrors Vision.java's single-tag ambiguity rejection cutoff
# (FeatureSwitches.VISION_AMBIGUITY_THRESHOLD: reject when ambiguity >= 0.2).
_AMBIGUITY_REJECT_AT = 0.2

# Stillness curves are independent of the trust LerpTables above — those trust a
# pose already accepted mid-match (a little motion is fine); this gates a
# *deliberate* health-check snapshot, where near-zero velocity is a precondition
# for the other readings meaning anything. The near-zero step matches the
# stationary-window detector in tabs/session_tab.py (_LIN_THRESH/_ANG_THRESH = 0.06).
_LIN_STILL_CURVE = [(0.0, 1.0), (0.06, 0.95), (0.3, 0.25), (0.6, 0.0)]
_ANG_STILL_CURVE = [(0.0, 1.0), (0.06, 0.95), (1.0, 0.25), (2.0, 0.0)]


def stillness_factor(lin_speed_mps: float, ang_speed_radps: float) -> float:
    return _lerp(_LIN_STILL_CURVE, abs(lin_speed_mps)) * _lerp(_ANG_STILL_CURVE, abs(ang_speed_radps))


def area_factor(sum_tag_area_pct: float) -> float:
    return _lerp(_AREA_CURVE, max(0.0, sum_tag_area_pct))


def ambiguity_factor(ambiguity: float) -> float:
    # -1.0 is the multi-tag sentinel (see VisionIO.java) — PnP is well-constrained
    # with 2+ tags regardless of the single-tag ambiguity score, so it never hurts.
    if ambiguity < 0:
        return 1.0
    return _lerp([(0.0, 1.0), (_AMBIGUITY_REJECT_AT, 0.0)], ambiguity)


def fps_factor(current_fps: float, target_fps: float) -> float:
    if target_fps <= 0:
        return 0.0
    return max(0.0, min(1.0, current_fps / target_fps))


@dataclass
class HealthReading:
    score: Optional[float]  # 0-100, or None if unmeasurable right now
    reason: Optional[str]   # why score is None
    stillness_pct: float = 0.0
    area_pct: float = 0.0
    ambiguity_pct: float = 0.0
    fps_pct: float = 0.0
    raw: dict = field(default_factory=dict)


def compute_health(*, connected: bool, has_tag: bool, lin_speed: float, ang_speed: float,
                    sum_tag_area: float, ambiguity: float, current_fps: float,
                    target_fps: float) -> HealthReading:
    raw = dict(lin_speed=lin_speed, ang_speed=ang_speed, sum_tag_area=sum_tag_area,
               ambiguity=ambiguity, current_fps=current_fps, target_fps=target_fps)

    if not connected:
        return HealthReading(score=None, reason='Camera not connected', raw=raw)
    if not has_tag:
        return HealthReading(score=None, reason='No tag in view', raw=raw)

    sf = stillness_factor(lin_speed, ang_speed)
    af = area_factor(sum_tag_area)
    mf = ambiguity_factor(ambiguity)
    ff = fps_factor(current_fps, target_fps)

    # Multiplicative, mirroring Vision.java's own `trust *= ...` composition — one
    # bad factor (e.g. the robot rolling during the check) craters the whole
    # reading instead of being averaged away by three good ones.
    score = 100.0 * sf * af * mf * ff
    return HealthReading(
        score=score, reason=None,
        stillness_pct=sf * 100, area_pct=af * 100, ambiguity_pct=mf * 100, fps_pct=ff * 100,
        raw=raw,
    )
