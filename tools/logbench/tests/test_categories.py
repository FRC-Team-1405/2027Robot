"""docs/adr/0001, D1 and D2: metric categories, context kept out of every score, time-weighted
averages over change-only logs, factors measured only while a tag was in view, and the new
availability / context metrics.

Where a test builds a log by hand it mirrors how AdvantageKit writes one: a record only when a
value changes, so a value that held for 18 ms and one that held for 2 ms are one record each."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401

from core import categories as cat
from core import composites as composites_mod
from core import metrics as metrics_mod
from core.compare import RUN_LEVEL, CONTEXT_VERDICT, compare
from core.log import Log
from core.runs import Run, Window


def _run(signals: dict, lo: float = 0.0, hi: float = 2.0) -> Run:
    return Run(log=Log(path=pathlib.Path('fake.wpilog'), signals=signals), window=Window(lo, hi))


def _gated_cycles(open_value: float, cycles: int = 100, period: float = 0.02, open_frac: float = 0.95):
    """Robot-style series over `cycles` loops: `open_value` while a tag is in view, then 0 for the
    (1 - open_frac) of the loop the gate zeroed it. Returns (factor_series, reason_series)."""
    factor, reason = [], []
    for k in range(cycles):
        t = k * period
        factor += [(t, open_value), (t + period * open_frac, 0.0)]
        reason += [(t, ''), (t + period * open_frac, 'No tag in view')]
    return factor, reason


# --- categories -----------------------------------------------------------------------------

def test_every_metric_and_composite_declares_a_known_category():
    for m in metrics_mod.METRICS.values():
        assert m.category in cat.ALL_IDS, m.id
    for c in composites_mod.COMPOSITES.values():
        assert c.category in cat.ALL_IDS, c.id


def test_registering_an_unknown_category_is_rejected():
    with pytest.raises(ValueError):
        metrics_mod.register('x_bad', 'Bad', None, False, lambda run, cam: None, category='nonsense')


def _transitive_deps(composite_id: str) -> set:
    out, stack = set(), [composite_id]
    while stack:
        cid = stack.pop()
        for dep in composites_mod.COMPOSITES[cid].deps:
            out.add(dep)
            if dep in composites_mod.COMPOSITES:
                stack.append(dep)
    return out


def test_no_scored_composite_depends_on_a_context_metric():
    """The structural guard for "context is never in a score": an availability, quality or overall
    composite may not reach a context metric, directly or through another composite."""
    scored = [c for c in composites_mod.COMPOSITES.values()
              if c.category in (cat.AVAILABILITY, cat.QUALITY, cat.OVERALL)]
    assert {c.id for c in scored} >= {'availability_score', 'quality_score', 'health_score'}
    for c in scored:
        for dep in _transitive_deps(c.id):
            if dep in metrics_mod.METRICS:
                assert metrics_mod.METRICS[dep].category != cat.CONTEXT, (c.id, dep)
            else:
                assert composites_mod.COMPOSITES[dep].category != cat.CONTEXT, (c.id, dep)


def test_availability_score_only_uses_availability_metrics_and_quality_only_quality():
    for dep in composites_mod.COMPOSITES['availability_score'].deps:
        assert metrics_mod.METRICS[dep].category == cat.AVAILABILITY, dep
    for dep in composites_mod.COMPOSITES['quality_score'].deps:
        assert metrics_mod.METRICS[dep].category == cat.QUALITY, dep


def test_stillness_and_range_and_speed_are_context():
    for metric_id in ('stillness_pct', 'range_median_m', 'speed_mean_mps'):
        assert metrics_mod.METRICS[metric_id].category == cat.CONTEXT


def test_category_scores_multiply_their_factors_and_health_is_their_product():
    def run_with(**pct):
        keys = {'area': 'AreaPercent', 'ambiguity': 'AmbiguityPercent', 'acceptance': 'AcceptanceRateFactorPercent',
                'multitag': 'MultiTagRatioPercent', 'fps': 'FpsPercent', 'latency': 'LatencyPercent'}
        sigs = {f'Vision/Left/Health/{keys[k]}': [(0.0, v)] for k, v in pct.items()}
        # a tag was in view the whole window
        sigs['Vision/Left/Health/Reason'] = [(0.0, '')]
        return _run(sigs)

    run = run_with(area=50.0, ambiguity=100.0, acceptance=80.0, multitag=100.0,
                   fps=100.0, latency=100.0)
    assert run.composite('quality_score', 'Left') == pytest.approx(40.0)
    assert run.composite('availability_score', 'Left') == pytest.approx(100.0)   # tag in view 100%
    assert run.composite('health_score', 'Left') == pytest.approx(40.0)


def test_health_score_ignores_stillness_and_jitter_entirely():
    base = {'Vision/Left/Health/AreaPercent': [(0.0, 100.0)],
            'Vision/Left/Health/AmbiguityPercent': [(0.0, 100.0)],
            'Vision/Left/Health/AcceptanceRateFactorPercent': [(0.0, 100.0)],
            'Vision/Left/Health/MultiTagRatioPercent': [(0.0, 100.0)],
            'Vision/Left/Health/FpsPercent': [(0.0, 100.0)],
            'Vision/Left/Health/LatencyPercent': [(0.0, 100.0)],
            'Vision/Left/Health/Reason': [(0.0, '')]}
    moving = dict(base, **{'Vision/Left/Health/StillnessPercent': [(0.0, 0.0)],
                           'Vision/Left/Health/JitterPercent': [(0.0, 0.0)]})
    assert _run(moving).composite('health_score', 'Left') == pytest.approx(100.0)


# --- compare: context gets no judgement -------------------------------------------------------

def test_context_metrics_get_a_context_verdict_never_improved_or_regressed():
    a = _run({'Vision/Left/RawAvgDistancesMeters': [(0.5, [3.0, 3.0])]})
    b = _run({'Vision/Left/RawAvgDistancesMeters': [(0.5, [1.0, 1.0])]})
    d = compare(a, b, ['range_median_m'], ['Left'])[0]
    assert (d.a, d.b, d.delta, d.verdict, d.category) == (3.0, 1.0, -2.0, CONTEXT_VERDICT, cat.CONTEXT)


def test_a_whole_run_metric_produces_one_row_not_one_per_camera():
    sigs = {'Drivetrain/Speeds/vxMetersPerSecond': [(0.0, 3.0)],
            'Drivetrain/Speeds/vyMetersPerSecond': [(0.0, 4.0)]}
    rows = compare(_run(sigs), _run(sigs), ['speed_mean_mps'], ['Left', 'Right'])
    assert len(rows) == 1
    assert rows[0].camera == RUN_LEVEL
    assert rows[0].a == pytest.approx(5.0)


def test_a_scored_metric_still_gets_a_real_verdict():
    a = _run({'Vision/Left/Health/FpsPercent': [(0.0, 50.0)]})
    b = _run({'Vision/Left/Health/FpsPercent': [(0.0, 90.0)]})
    assert compare(a, b, ['fps_pct'], ['Left'])[0].verdict == 'improved'


# --- D2: time-weighting over change-only logs -------------------------------------------------

def test_a_factor_that_sat_at_100_for_ninety_percent_of_the_window_averages_90_not_50():
    """The regression test from the ADR. Alternating 100/0 records: 100 for 18 ms then 0 for 2 ms.
    Averaging *records* gives exactly 50; averaging *time* gives the true 90."""
    series = []
    for k in range(100):
        series += [(k * 0.02, 100.0), (k * 0.02 + 0.018, 0.0)]
    assert sum(v for _, v in series) / len(series) == 50.0          # what the old record-mean did
    assert _run({'Vision/Left/Health/FpsPercent': series}).metric('fps_pct', 'Left') == pytest.approx(90.0)


def test_a_value_set_before_the_window_still_counts_for_the_whole_window():
    # Logged once at t=0 (change-only), window is [5, 8]: the carried-in 70 is the answer.
    run = _run({'Vision/Left/Health/FpsPercent': [(0.0, 70.0)],
                'Other/Heartbeat': [(10.0, 1.0)]}, lo=5.0, hi=8.0)
    assert run.metric('fps_pct', 'Left') == pytest.approx(70.0)


def test_a_signal_with_no_data_in_the_window_is_none_not_zero():
    assert _run({}).metric('fps_pct', 'Left') is None


# --- D1: factors are measured only while a tag was in view -------------------------------------

def test_a_factor_is_not_diluted_by_loops_the_robot_zeroed_for_no_tag():
    """The robot logs 0 on the 5% of loops with no tag. That dropout belongs in tag_in_view_pct,
    once; it must not also drag every factor down by 5%."""
    factor, reason = _gated_cycles(open_value=80.0)
    run = _run({'Vision/Left/Health/FpsPercent': factor, 'Vision/Left/Health/Reason': reason})
    assert run.metric('fps_pct', 'Left') == pytest.approx(80.0)
    assert run.metric('tag_in_view_pct', 'Left') == pytest.approx(95.0)


def test_without_a_reason_signal_the_gate_is_derived_from_the_raw_pose_array():
    # Older logs: tag in view when the loop's raw pose array is non-empty.
    poses = [(0.0, [{'x': 1}]), (1.0, []), (1.02, [{'x': 1}])]
    run = _run({'Vision/Left/RawEstimatedPoses': poses}, lo=0.0, hi=2.0)
    assert run.metric('tag_in_view_pct', 'Left') == pytest.approx(99.0)


def test_tag_in_view_is_none_when_the_log_cannot_say():
    assert _run({}).metric('tag_in_view_pct', 'Left') is None


def test_longest_gap_is_the_longest_unbroken_hole_not_the_total():
    reason = [(0.0, ''), (1.00, 'No tag in view'), (1.02, ''), (1.50, 'No tag in view'), (1.56, '')]
    run = _run({'Vision/Left/Health/Reason': reason})
    # 20 ms + 60 ms of gap in total, but the longest single hole is 60 ms.
    assert run.metric('longest_gap_ms', 'Left') == pytest.approx(60.0)
    assert run.metric('tag_in_view_pct', 'Left') == pytest.approx(96.0)


def test_adjacent_gap_records_merge_into_one_gap():
    reason = [(0.0, ''), (1.0, 'No tag in view'), (1.02, 'Camera not connected'), (1.06, '')]
    assert _run({'Vision/Left/Health/Reason': reason}).metric('longest_gap_ms', 'Left') == pytest.approx(60.0)


# --- context metrics -------------------------------------------------------------------------

def test_range_median_is_taken_over_every_result_in_the_window():
    sigs = {'Vision/Left/RawAvgDistancesMeters': [(0.5, [1.0, 2.0]), (0.6, [3.0]), (5.0, [99.0])]}
    assert _run(sigs, lo=0.0, hi=1.0).metric('range_median_m', 'Left') == pytest.approx(2.0)


def test_speed_is_the_time_weighted_magnitude_of_the_chassis_velocity():
    sigs = {'Drivetrain/Speeds/vxMetersPerSecond': [(0.0, 3.0), (1.0, 0.0)],
            'Drivetrain/Speeds/vyMetersPerSecond': [(0.0, 4.0), (1.0, 0.0)]}
    # 5 m/s for the first second, 0 for the second: mean 2.5 over a 2 s window.
    assert _run(sigs).metric('speed_mean_mps', None) == pytest.approx(2.5)
