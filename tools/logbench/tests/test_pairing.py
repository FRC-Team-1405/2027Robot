"""pairing.py: pure wall-clock pairing of RIO logs to Pi vision sessions. No filesystem,
no network -- synthetic RioLogInfo/PiSessionInfo lists only."""
import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401  (side effect: sys.path bridges)

from pairing import PiSessionInfo, RioLogInfo, suggest_pairings

_T0 = dt.datetime(2026, 1, 15, 14, 30, 0)


def _rio(name='FRC_20260115_143000.wpilog', minutes_after_t0=0, duration_sec=150.0, wall_clock=True):
    return RioLogInfo(
        name=name,
        wall_clock=(_T0 + dt.timedelta(minutes=minutes_after_t0)) if wall_clock else None,
        duration_sec=duration_sec,
    )


def _pi(camera='Left', name='boot0001-20260115-143010', minutes_after_t0=0, seconds_after_t0=10, wall_clock=True):
    return PiSessionInfo(
        camera=camera,
        name=name,
        wall_clock=(_T0 + dt.timedelta(minutes=minutes_after_t0, seconds=seconds_after_t0)) if wall_clock else None,
    )


def test_matches_a_pi_session_that_starts_shortly_after_the_rio_log():
    rio = _rio()
    pi = _pi(seconds_after_t0=10)  # well inside [start-60s, start+150+60s]

    [pairing] = suggest_pairings([rio], [pi])
    assert pairing.rio_log == rio.name
    assert [s.name for s in pairing.pi_sessions] == [pi.name]
    assert pairing.confidence == 'high'


def test_unparseable_rio_wall_clock_is_never_matched():
    rio = _rio(name='FRC_TBD_000001.wpilog', wall_clock=False)
    pi = _pi(seconds_after_t0=10)

    [pairing] = suggest_pairings([rio], [pi])
    assert pairing.pi_sessions == []
    assert pairing.confidence == 'none'
    assert 'FRC_TBD' in pairing.reason or 'never DS-renamed' in pairing.reason


def test_a_pi_session_far_outside_the_window_is_not_matched():
    rio = _rio(duration_sec=150.0)
    pi = _pi(minutes_after_t0=30)  # 30 minutes later -- nowhere near the window

    [pairing] = suggest_pairings([rio], [pi])
    assert pairing.pi_sessions == []
    assert pairing.confidence == 'none'


def test_matches_one_session_per_camera():
    rio = _rio()
    left = _pi(camera='Left', name='boot0001-left', seconds_after_t0=5)
    right = _pi(camera='Right', name='boot0001-right', seconds_after_t0=8)

    [pairing] = suggest_pairings([rio], [left, right])
    matched_names = {s.name for s in pairing.pi_sessions}
    assert matched_names == {'boot0001-left', 'boot0001-right'}


def test_a_pi_session_with_no_wall_clock_is_ignored():
    rio = _rio()
    pi = _pi(wall_clock=False)

    [pairing] = suggest_pairings([rio], [pi])
    assert pairing.pi_sessions == []
    assert pairing.confidence == 'none'


def test_a_session_near_the_window_edge_gets_low_confidence():
    rio = _rio(duration_sec=150.0)
    # Window is [start - 60s, start + 150 + 60s] = [-60, 210]s relative to start.
    # Put the session at 205s in -- inside, but only 5s from the far edge.
    pi = _pi(seconds_after_t0=205)

    [pairing] = suggest_pairings([rio], [pi])
    assert [s.name for s in pairing.pi_sessions] == [pi.name]
    assert pairing.confidence == 'low'


def test_earlier_rio_log_claims_a_session_two_logs_could_both_match():
    early = _rio(name='early.wpilog', minutes_after_t0=0, duration_sec=60.0)
    late = _rio(name='late.wpilog', minutes_after_t0=1, duration_sec=60.0)
    # A session right between the two -- both logs' windows could plausibly cover it.
    shared = _pi(name='shared-session', minutes_after_t0=0, seconds_after_t0=30)

    early_pairing, late_pairing = suggest_pairings([early, late], [shared])
    assert [s.name for s in early_pairing.pi_sessions] == ['shared-session']
    assert late_pairing.pi_sessions == []


def test_output_order_matches_input_rio_logs_order_not_sorted_order():
    later = _rio(name='later.wpilog', minutes_after_t0=5)
    earlier = _rio(name='earlier.wpilog', minutes_after_t0=0)
    pi = _pi(seconds_after_t0=10)

    results = suggest_pairings([later, earlier], [pi])
    assert [p.rio_log for p in results] == ['later.wpilog', 'earlier.wpilog']


def test_empty_inputs_yield_empty_output():
    assert suggest_pairings([], []) == []


def test_no_pi_sessions_at_all_still_returns_one_pairing_per_rio_log():
    rio = _rio()
    [pairing] = suggest_pairings([rio], [])
    assert pairing.rio_log == rio.name
    assert pairing.pi_sessions == []
    assert pairing.confidence == 'none'
