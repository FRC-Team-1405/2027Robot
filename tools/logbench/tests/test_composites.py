"""core/composites.py: still_score / motion_score math, and the registry's ability to
resolve a composite that itself depends on other composites."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401

from core import composites as composites_mod
from core.log import Log
from core.runs import Run

CAM = 'Left'


def _run_with_factors(**percents) -> Run:
    """Build a Run whose Health/*Percent series for CAM are constant at the given values.
    Missing factors default to 100 so a test can override just the ones it cares about."""
    defaults = dict(stillness=100.0, area=100.0, ambiguity=100.0, fps=100.0, jitter=100.0,
                     acceptance=100.0, latency=100.0, multitag=100.0)
    defaults.update(percents)
    suffix_to_key = {
        'stillness': 'StillnessPercent', 'area': 'AreaPercent', 'ambiguity': 'AmbiguityPercent',
        'fps': 'FpsPercent', 'jitter': 'JitterPercent', 'acceptance': 'AcceptanceRateFactorPercent',
        'latency': 'LatencyPercent', 'multitag': 'MultiTagRatioPercent',
    }
    signals = {
        f'Vision/{CAM}/Health/{suffix_to_key[k]}': [(10.0, v)] for k, v in defaults.items()
    }
    return Run.whole(Log(path=pathlib.Path('fake.wpilog'), signals=signals))


def test_still_score_is_100_when_every_factor_is_perfect():
    run = _run_with_factors()
    assert run.composite('still_score', CAM) == pytest.approx(100.0)


def test_still_score_counts_jitter_fully_when_the_robot_is_still():
    # stillness=100 -> effective_jitter == jitter exactly.
    run = _run_with_factors(stillness=100.0, jitter=50.0)
    assert run.composite('still_score', CAM) == pytest.approx(50.0)


def test_still_score_forgives_jitter_when_the_robot_is_moving():
    # stillness=0 -> effective_jitter == 1.0 regardless of the raw jitter reading, and the
    # stillness factor itself (0) already zeroes the score -- this is the double-penalty
    # bug fixed in VisionHealth.java: jitter must not ALSO drag the (already-zeroed) score
    # down as if it were an independent failure.
    still_and_bad_jitter = _run_with_factors(stillness=0.0, jitter=1.0).composite('still_score', CAM)
    still_and_perfect_jitter = _run_with_factors(stillness=0.0, jitter=100.0).composite('still_score', CAM)
    assert still_and_bad_jitter == pytest.approx(still_and_perfect_jitter)


def test_motion_score_ignores_stillness_and_jitter_entirely():
    perfect = _run_with_factors()
    moving_and_jittery = _run_with_factors(stillness=0.0, jitter=0.0)
    assert perfect.composite('motion_score', CAM) == pytest.approx(100.0)
    assert moving_and_jittery.composite('motion_score', CAM) == pytest.approx(100.0)


def test_motion_score_still_reacts_to_non_motion_factors():
    run = _run_with_factors(area=50.0)
    assert run.composite('motion_score', CAM) == pytest.approx(50.0)


def test_composite_is_none_if_any_dependency_is_missing():
    log = Log(path=pathlib.Path('fake.wpilog'), signals={})
    run = Run.whole(log)
    assert run.composite('still_score', CAM) is None


def test_composite_of_composites_resolves_recursively():
    """Proves the registry supports layering: a composite whose deps are themselves
    composites, not leaf metrics."""
    composites_mod.register(
        'test_average_score', 'Test average', ('still_score', 'motion_score'),
        lambda values: (values['still_score'] + values['motion_score']) / 2.0,
    )
    try:
        run = _run_with_factors(stillness=100.0, jitter=100.0)
        assert run.composite('test_average_score', CAM) == pytest.approx(100.0)
    finally:
        del composites_mod.COMPOSITES['test_average_score']
