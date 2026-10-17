"""core/metrics.py: health-factor lookups, windowing, and the vision_analyzer wrapper."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401  (side effect: puts vision_analyzer on sys.path)

from core.log import Log
from core.runs import Run, Window


def _health_series(t0=10.0, n=5, dt=0.02, value=80.0):
    return [(t0 + i * dt, value) for i in range(n)]


def _log(signals: dict) -> Log:
    return Log(path=pathlib.Path('fake.wpilog'), signals=signals)


def test_health_factor_metric_reads_the_robots_own_scoring():
    log = _log({'Vision/Left/Health/StillnessPercent': _health_series(value=95.0)})
    run = Run.whole(log)
    assert run.metric('stillness_pct', 'Left') == 95.0


def test_health_factor_metric_averages_over_the_run_window():
    # 90, 90, 10, 10, 10 -- windowing to the first two samples should see only the 90s.
    series = [(10.0, 90.0), (10.02, 90.0), (10.04, 10.0), (10.06, 10.0), (10.08, 10.0)]
    log = _log({'Vision/Left/Health/StillnessPercent': series})
    run = Run(log=log, window=Window(10.0, 10.03))
    assert run.metric('stillness_pct', 'Left') == 90.0


def test_health_factor_metric_is_none_when_signal_absent():
    log = _log({})
    run = Run.whole(log)
    assert run.metric('stillness_pct', 'Left') is None


def test_health_factor_metric_requires_a_camera():
    log = _log({'Vision/Left/Health/StillnessPercent': _health_series()})
    run = Run.whole(log)
    assert run.metric('stillness_pct', None) is None


def _new_format_signals(cam='Left', t0=10.0, n=5, dt=0.02):
    times = [t0 + i * dt for i in range(n)]
    return {
        f'Vision/{cam}/connected': [(t, True) for t in times],
        f'Vision/{cam}/currentFps': [(t, 50.0) for t in times],
        # One raw pose every loop; accepted alternates 1,0,1,0,1 -- 3/5 = 60%.
        f'Vision/{cam}/rawEstimatedPoses': [(t, [{'x': 1.0, 'y': 2.0, 'z': 0.0}]) for t in times],
        f'Vision/{cam}/AcceptedPoses': [
            (t, [{'x': 1.0, 'y': 2.0, 'rot': 0.0}] if i % 2 == 0 else [])
            for i, t in enumerate(times)
        ],
        f'Vision/{cam}/rawAmbiguities': [(t, [0.1]) for t in times],
        f'Vision/{cam}/rawSumTagAreas': [(t, [2.0]) for t in times],
        f'Vision/{cam}/visibleTagIds': [(t, [10]) for t in times],
    }


def test_va_wrapped_metric_reuses_vision_analyzers_own_math():
    log = _log(_new_format_signals())
    run = Run.whole(log)
    assert run.metric('acceptance_rate', 'Left') == 60.0


def test_va_wrapped_metric_respects_the_run_window():
    # Same log as above, but windowed to only the first two loops (1 accepted / 2 raw).
    log = _log(_new_format_signals())
    run = Run(log=log, window=Window(10.0, 10.03))
    assert run.metric('acceptance_rate', 'Left') == 50.0


def test_va_wrapped_metric_is_memoized_per_camera():
    """Several Metric ids pull fields from one compute_camera_metrics() call; make sure
    that call actually only happens once per (run, camera)."""
    log = _log(_new_format_signals())
    run = Run.whole(log)
    run.metric('acceptance_rate', 'Left')
    run.metric('fps_mean', 'Left')
    assert len([k for k in run.cache if k[0] == '_va_metrics']) == 1
