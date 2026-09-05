"""core/compare.py: window selection (DS-mode span and manual slice) and the
delta/verdict table two Runs are compared with."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401

from core.compare import WindowSelector, compare, make_run, verdict
from core.log import Log


def _log_with_mode_spans() -> Log:
    """disabled[0,5) -> auto[5,10) -> teleop[10,20) -> disabled[20,30] -- the trailing
    disabled span is made longer than the leading one so a "pick the longest span" test
    isn't tripped up by max() breaking a length tie by first occurrence."""
    signals = {
        'DriverStation/Enabled': [(0.0, False), (5.0, True), (10.0, True), (20.0, False)],
        'DriverStation/Autonomous': [(0.0, False), (5.0, True), (10.0, False)],
        # Anchors the log's end at t=30 -- bounds() looks at every signal, not just DS ones.
        'Other/Heartbeat': [(30.0, 1.0)],
    }
    return Log(path=pathlib.Path('fake.wpilog'), signals=signals)


def test_mode_selector_auto():
    window = WindowSelector(mode='auto').resolve(_log_with_mode_spans())
    assert (window.lo, window.hi) == (5.0, 10.0)


def test_mode_selector_teleop():
    window = WindowSelector(mode='teleop').resolve(_log_with_mode_spans())
    assert (window.lo, window.hi) == (10.0, 20.0)


def test_mode_selector_disabled_picks_the_longer_span():
    # Two disabled spans exist ([0,5) and [20,30]); disabled should pick the longer one.
    window = WindowSelector(mode='disabled').resolve(_log_with_mode_spans())
    assert (window.lo, window.hi) == (20.0, 30.0)


def test_mode_selector_whole_is_the_default():
    log = _log_with_mode_spans()
    window = WindowSelector().resolve(log)
    assert (window.lo, window.hi) == log.bounds()


def test_mode_selector_raises_a_helpful_error_for_a_missing_mode():
    log = Log(path=pathlib.Path('fake.wpilog'), signals={})  # no DriverStation signals at all
    with pytest.raises(ValueError, match="no 'auto' span found"):
        WindowSelector(mode='auto').resolve(log)


def test_manual_selector_is_relative_to_log_start():
    log = _log_with_mode_spans()
    t0, _ = log.bounds()
    window = WindowSelector(manual=(2.0, 4.0)).resolve(log)
    assert (window.lo, window.hi) == (t0 + 2.0, t0 + 4.0)


@pytest.mark.parametrize('a,b,lower_is_better,expected', [
    (100.0, 120.0, False, 'improved'),   # higher-is-better, went up a lot
    (100.0, 80.0, False, 'regressed'),   # higher-is-better, went down a lot
    (100.0, 105.0, False, 'neutral'),    # within the +/-10% band
    (100.0, 80.0, True, 'improved'),     # lower-is-better, went down a lot
    (100.0, 120.0, True, 'regressed'),   # lower-is-better, went up a lot
    (0.0, 0.0, False, 'neutral'),
    (0.0, 5.0, False, 'improved'),
    (None, 5.0, False, 'n/a'),
    (5.0, None, False, 'n/a'),
])
def test_verdict_table(a, b, lower_is_better, expected):
    assert verdict(a, b, lower_is_better) == expected


def _run_with_metric(value: float, metric_series_key: str, camera: str = 'Left'):
    log = Log(path=pathlib.Path('fake.wpilog'), signals={metric_series_key: [(10.0, value)]})
    return make_run(log, WindowSelector())


def test_compare_reports_delta_and_verdict_per_camera():
    run_a = _run_with_metric(50.0, 'Vision/Left/Health/StillnessPercent')
    run_b = _run_with_metric(90.0, 'Vision/Left/Health/StillnessPercent')
    deltas = compare(run_a, run_b, ['stillness_pct'], ['Left'])
    assert len(deltas) == 1
    d = deltas[0]
    assert (d.a, d.b, d.delta, d.verdict) == (50.0, 90.0, 40.0, 'improved')


def test_compare_reports_n_a_when_a_camera_has_no_data():
    run_a = _run_with_metric(50.0, 'Vision/Left/Health/StillnessPercent')
    run_b = make_run(Log(path=pathlib.Path('fake.wpilog'), signals={}), WindowSelector())
    d = compare(run_a, run_b, ['stillness_pct'], ['Left'])[0]
    assert (d.a, d.b, d.delta, d.verdict) == (50.0, None, None, 'n/a')
