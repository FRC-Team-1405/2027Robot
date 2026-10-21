"""Counting regressions: changed-only arrays, batching, interval edges and missing data."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import paths  # noqa: F401
from core.log import Log
from core.runs import Run, Window
from core.throughput import Counts, analyze, summary


def run(signals, lo=0, hi=5):
    return Run(Log(pathlib.Path('test.wpilog'), signals), Window(lo, hi))


def signals():
    return {
        '/Timestamp': [(i / 10, i * 100000) for i in range(51)],
        'Vision/Left/RawEstimatedPoses': [(0, [{}, {}]), (2, []), (3, [{}])],
        'RealOutputs/Vision/Left/AcceptedPoses': [(0, [{}]), (2, []), (3, [{}])],
    }


def test_unchanged_arrays_count_every_loop_and_every_pose():
    r = run(signals())
    result = summary(r, 'Left')
    assert result['generated_count'] == 60  # 20 loops * 2 + 20 loops * 1
    assert result['accepted_count'] == 40
    assert result['accepted_poses_per_sec'] == 8
    assert result['acceptance_pct'] == pytest.approx(100 * 40 / 60)
    assert r.metric('accepted_poses_per_sec', 'Left') == 8
    assert r.metric('generated_poses_per_sec', 'Left') == 12


def test_custom_window_carries_prior_state_and_excludes_end():
    r = run(signals(), 1, 2)
    assert summary(r, 'Left')['generated_count'] == 20
    assert summary(r, 'Left')['accepted_count'] == 10
    assert summary(r, 'Left')['best_3s_accepted_poses_per_sec'] is None


def test_fresh_capture_batches_recover_identical_stationary_poses_without_cycles():
    s = signals()
    del s['/Timestamp']
    s['Vision/Left/rawTimestampsSec'] = [(0, [0.0]), (1, [1.0]), (2, []), (3, [3.0])]
    r = run(s)
    assert summary(r, 'Left')['generated_count'] == 5
    assert summary(r, 'Left')['accepted_count'] == 3


def test_no_nearest_future_pose_and_unsorted_input():
    s = {
        '/Timestamp': [(0, 0), (1, 1), (2, 2)],
        'Vision/Left/RawEstimatedPoses': [(1, [{}, {}])],
        'Vision/Left/AcceptedPoses': [(2, [{}]), (1, [])],
    }
    assert summary(run(s, 0, 2), 'Left')['generated_count'] == 2
    assert summary(run(s, 0, 2), 'Left')['accepted_count'] == 0


def test_missing_sources_are_unknown_not_zero():
    s = signals()
    del s['/Timestamp']
    result = summary(run(s), 'Left')
    assert result['accepted_count'] is None
    assert result['warnings']
    s['/Timestamp'] = [(0, 0), (5, 5)]
    del s['Vision/Left/RawEstimatedPoses']
    result = summary(run(s), 'Left')
    assert result['generated_count'] is None
    assert result['accepted_count'] == 1
    assert result['acceptance_pct'] is None


def test_zero_output_is_measured_zero_but_acceptance_is_undefined():
    s = signals()
    s['Vision/Left/RawEstimatedPoses'] = [(0, [])]
    s['RealOutputs/Vision/Left/AcceptedPoses'] = [(0, [])]
    result = summary(run(s), 'Left')
    assert result['accepted_count'] == 0
    assert result['acceptance_pct'] is None


def test_full_sliding_three_seconds_not_three_aligned_buckets():
    counts = Counts([(1.2, 5), (2.2, 5), (3.2, 5), (4.2, 5)])
    assert counts.best(0, 5) == 5
    assert counts.best(0, 2.9) is None
    # A burst straddling fixed bucket edges is still one sustained window.
    assert Counts([(0.9, 3), (3.8, 6)]).best(0, 5) == 3


def test_chart_warmup_and_interval_summary_share_counts():
    report = analyze(run(signals()), 1)
    cam = report['cameras'][0]
    assert cam['series'][0]['accepted'] is None
    assert cam['series'][10]['accepted'] == 10
    assert cam['series'][20]['generated'] == 20
    assert cam['accepted_count'] == 40
    assert cam['series'][0]['multitag'] is None


@pytest.mark.parametrize('lo, hi, rolling', [(2, 1, 1), (-1, 5, 1), (0, 6, 1), (0, 5, 0), (0, 5, float('nan'))])
def test_invalid_windows_rejected(lo, hi, rolling):
    with pytest.raises(ValueError):
        analyze(run(signals(), lo, hi), rolling)


def tracking_signals():
    # 0.1s loops over 20s: poses (2 per loop) 0-3s, a 0.8s dropout, poses 3.8-5s, then nothing until 15-16s.
    return {
        '/Timestamp': [(i / 10, i * 100000) for i in range(201)],
        'Vision/Left/RawEstimatedPoses': [(0, [{}, {}]), (3, []), (3.8, [{}, {}]), (5, []), (15, [{}, {}]), (16, [])],
        'RealOutputs/Vision/Left/AcceptedPoses': [(0, [{}, {}]), (3, []), (3.8, [{}, {}]), (5, []), (15, [{}, {}]), (16, [])],
    }


def test_tracking_bridges_short_dropouts_and_drops_long_silence():
    from core.throughput import tracking
    r = run(tracking_signals(), 0, 20)
    result = tracking(r, 'Left', gap=1.0)
    # One span 0-5s (the 0.8s dropout is flapping) and one 15-16s; 10s of silence between is not tracking.
    assert [(round(s['lo'], 1), round(s['hi'], 1)) for s in result['spans']] == [(0.0, 5.0), (15.0, 16.0)]
    assert result['active_sec'] == pytest.approx(6.0)
    assert result['coverage_pct'] == pytest.approx(30.0)
    assert result['accepted_count'] == 2 * (30 + 12 + 10)
    # The whole-interval rate is diluted by the silence; the tracking rate is not.
    assert result['accepted_poses_per_sec'] == pytest.approx(104 / 6)
    assert summary(r, 'Left')['accepted_poses_per_sec'] == pytest.approx(104 / 20)


def test_tracking_gap_controls_what_counts_as_flapping():
    from core.throughput import tracking
    r = run(tracking_signals(), 0, 20)
    assert len(tracking(r, 'Left', gap=0.5)['spans']) == 3  # the 0.8s dropout now splits the span
    assert len(tracking(r, 'Left', gap=11)['spans']) == 1


def test_rejected_poses_still_count_as_tracking():
    from core.throughput import tracking
    s = tracking_signals()
    s['RealOutputs/Vision/Left/AcceptedPoses'] = [(0, [])]
    result = tracking(run(s, 0, 20), 'Left')
    assert result['basis'] == 'generated'
    assert result['accepted_poses_per_sec'] == 0
    assert result['acceptance_pct'] == 0


def test_no_tags_is_zero_coverage_and_unknown_rate_not_zero_throughput():
    from core.throughput import tracking
    s = tracking_signals()
    s['Vision/Left/RawEstimatedPoses'] = [(0, [])]
    s['RealOutputs/Vision/Left/AcceptedPoses'] = [(0, [])]
    result = tracking(run(s, 0, 20), 'Left')
    assert result['coverage_pct'] == 0 and result['spans'] == []
    assert result['accepted_poses_per_sec'] is None


def test_robot_tracking_is_the_union_of_cameras_without_double_counting_time():
    from core.throughput import tracking
    s = tracking_signals()
    s['Vision/Right/RawEstimatedPoses'] = [(0, []), (2, [{}]), (4, [])]
    s['RealOutputs/Vision/Right/AcceptedPoses'] = [(0, []), (2, [{}]), (4, [])]
    robot = tracking(run(s, 0, 20))
    assert robot['active_sec'] == pytest.approx(6.0)  # Right's 2-4s lies inside Left's span
    assert robot['accepted_count'] == 104 + 20


def test_analyze_reports_tracking_per_camera_and_rejects_bad_gap():
    r = run(tracking_signals(), 0, 20)
    report = analyze(r, 1.0, 2.0)
    assert report['tracking_gap_sec'] == 2.0
    assert report['cameras'][0]['tracking']['span_count'] == 2
    assert report['tracking']['coverage_pct'] == pytest.approx(30.0)
    with pytest.raises(ValueError):
        analyze(r, 1.0, 0)
