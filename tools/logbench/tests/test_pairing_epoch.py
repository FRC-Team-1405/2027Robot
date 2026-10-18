"""Pairing by roboRIO boot clock (epoch), twin logs sharing sessions, and the fall-backs.

Synthetic data modelled on Ruckus 2026: every log was named 20-412 s after its boot (when the Driver
Station synced the roboRIO clock), the akit_* and FRC_* logs of a boot were named ~3 s apart, and the
recorder split a match into many short sessions per camera (up to 14) whose names are the robot's wall
clock at session start. Session epoch = name time - first frame t_sec, correct to a few seconds."""
import datetime as dt
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401

import pytest

import pairing
from pairing import PiSessionInfo, RioLogInfo, select_for_log, session_clock, suggest_pairings

UTC = dt.timezone.utc
BOOT_Q1 = dt.datetime(2026, 10, 17, 12, 30, 0, tzinfo=UTC)        # roboRIO boot (FPGA t=0)


def at(base, seconds):
    return base + dt.timedelta(seconds=seconds)


def stamp(t, fmt):
    return t.strftime(fmt)


def logs_for_boot(boot, sync_delay, event='nyroc1', match='q1', frc_offset=3, **kw):
    """The akit_* and FRC_* logs of one boot, named when the DS synced the clock."""
    akit_t, frc_t = at(boot, sync_delay), at(boot, sync_delay + frc_offset)
    akit = RioLogInfo(name='akit_%s_%s_%s.wpilog' % (stamp(akit_t, '%y-%m-%d_%H-%M-%S'), event, match),
                      wall_clock=akit_t, **kw)
    frc = RioLogInfo(name='FRC_%s_%s_%s.wpilog' % (stamp(frc_t, '%Y%m%d_%H%M%S'), event.upper(), match.upper()),
                     wall_clock=frc_t, **kw)
    return akit, frc


def sessions_for_boot(boot, enables, cameras=('LeftCam', 'RightCam'), epoch_jitter=3.0, seed=0, boot_no=1):
    """One session per enable per camera. `enables` = [(t_first, t_last)] on the robot axis. The name
    time is when the session opened, a moment before its first frame, so the name-derived epoch is
    a little late (up to epoch_jitter seconds)."""
    rng = random.Random(seed)
    out = []
    for cam in cameras:
        for i, (t0, t1) in enumerate(enables):
            lag = rng.uniform(0.0, epoch_jitter)
            name_time = at(boot, t0).replace(microsecond=0)
            t_first = t0 + lag
            out.append(PiSessionInfo(
                camera=cam, name='boot%04d-%s' % (boot_no, stamp(name_time, '%Y%m%d-%H%M%S')),
                wall_clock=name_time, epoch=at(name_time, -t_first), t_first=t_first, t_last=t1))
    return out


def fourteen_pieces(first, total=150.0, n=14):
    """A match the recorder cut into n short sessions (camera/NT flapping)."""
    step = total / n
    return [(first + i * step, first + i * step + step * 0.7) for i in range(n)]


def names(pairing_):
    return sorted((s.camera, s.name) for s in pairing_.pi_sessions)


# ── twins share sessions ─────────────────────────────────────────────────────────────────────

def test_twin_logs_of_one_boot_get_the_same_sessions_by_boot_clock():
    akit, frc = logs_for_boot(BOOT_Q1, sync_delay=240)
    sessions = sessions_for_boot(BOOT_Q1, fourteen_pieces(first=600))
    by_log = {p.rio_log: p for p in suggest_pairings([frc, akit], sessions)}
    assert len(by_log[akit.name].pi_sessions) == len(by_log[frc.name].pi_sessions) == 28
    assert names(by_log[akit.name]) == names(by_log[frc.name])
    assert by_log[akit.name].method == 'inferred' and by_log[akit.name].confidence == 'high'


def test_a_log_with_no_twin_still_gets_its_sessions():
    """Q13 at Ruckus had no akit log at all."""
    [frc] = [logs_for_boot(BOOT_Q1, 120)[1]]
    [p] = suggest_pairings([frc], sessions_for_boot(BOOT_Q1, fourteen_pieces(500)))
    assert len(p.pi_sessions) == 28


def test_logs_for_different_matches_are_not_twins():
    a_akit, _ = logs_for_boot(BOOT_Q1, 240, match='q1')
    _, b_frc = logs_for_boot(at(BOOT_Q1, 0), 240, match='q6')    # same time, other match suffix
    assert not pairing._twins(a_akit, b_frc)


def test_twins_with_conflicting_boot_ids_or_epochs_are_not_paired():
    akit, frc = logs_for_boot(BOOT_Q1, 240, boot_id='a')
    frc.boot_id = 'b'
    assert not pairing._twins(akit, frc)
    akit, frc = logs_for_boot(BOOT_Q1, 240, epoch=BOOT_Q1)
    frc.epoch = at(BOOT_Q1, 120)
    assert not pairing._twins(akit, frc)


# ── a match long after the clock sync still pairs ────────────────────────────────────────────

@pytest.mark.parametrize('match_starts_after_sync', [4 * 60, 11 * 60, 25 * 60, 70 * 60])
def test_a_match_far_after_the_clock_sync_still_pairs(match_starts_after_sync):
    """The old window ended 10 min after the file time, so anything later paired nothing."""
    sync = 240
    akit, frc = logs_for_boot(BOOT_Q1, sync)
    first = sync + match_starts_after_sync
    sessions = sessions_for_boot(BOOT_Q1, fourteen_pieces(first, total=150))
    pairs = {p.rio_log: p for p in suggest_pairings([akit, frc], sessions)}
    assert len(pairs[akit.name].pi_sessions) == 28
    assert len(pairs[frc.name].pi_sessions) == 28


# ── boots do not mix ─────────────────────────────────────────────────────────────────────────

def test_two_boots_minutes_apart_each_get_only_their_own_sessions():
    boot2 = at(BOOT_Q1, 55 * 60)
    a_akit, a_frc = logs_for_boot(BOOT_Q1, 60, match='q1')
    b_akit, b_frc = logs_for_boot(boot2, 400, match='q6')    # DS synced late: 412 s was seen
    s1 = sessions_for_boot(BOOT_Q1, fourteen_pieces(300), boot_no=1)
    s2 = sessions_for_boot(boot2, fourteen_pieces(700, n=5), boot_no=2)
    pairs = {p.rio_log: p for p in suggest_pairings([a_akit, a_frc, b_akit, b_frc], s1 + s2)}
    assert {s.name for s in pairs[a_akit.name].pi_sessions} == {s.name for s in s1}
    assert {s.name for s in pairs[b_frc.name].pi_sessions} == {s.name for s in s2}
    assert len(pairs[b_akit.name].pi_sessions) == 10


def test_a_boot_with_no_recordings_does_not_steal_the_previous_boots_sessions():
    """Boot 2 was named 30 min after boot 1's epoch (outside MAX_SYNC_DELAY), recorded nothing."""
    boot2 = at(BOOT_Q1, 50 * 60)
    a_akit, _ = logs_for_boot(BOOT_Q1, 60)
    b_akit, _ = logs_for_boot(boot2, 60, match='q6')
    sessions = sessions_for_boot(BOOT_Q1, fourteen_pieces(300))
    first, second = suggest_pairings([a_akit, b_akit], sessions)
    assert len(first.pi_sessions) == 28
    assert second.pi_sessions == [] and second.confidence == 'none'


def test_a_late_sync_is_low_confidence_not_ignored():
    akit, _ = logs_for_boot(BOOT_Q1, 15 * 60)
    [p] = suggest_pairings([akit], sessions_for_boot(BOOT_Q1, fourteen_pieces(1000)))
    assert len(p.pi_sessions) == 28 and p.confidence == 'low'


# ── exact: the log's own epoch ───────────────────────────────────────────────────────────────

def test_a_known_log_epoch_picks_the_boot_and_the_overlapping_time_range():
    sessions = sessions_for_boot(BOOT_Q1, fourteen_pieces(600))
    # A second run of robot code in the same boot: same epoch, later t range, own log.
    later = sessions_for_boot(BOOT_Q1, [(5000, 5100), (5200, 5300)], cameras=('LeftCam',), seed=9)
    rio = RioLogInfo('akit_a.wpilog', None, epoch=BOOT_Q1, t_range=(100.0, 900.0))
    got = select_for_log(rio, sessions + later)
    assert len(got.pi_sessions) == 28 and got.method == 'epoch' and got.confidence == 'high'
    rio2 = RioLogInfo('akit_b.wpilog', None, epoch=BOOT_Q1, t_range=(4900.0, 5400.0))
    assert [s.t_first > 4000 for s in select_for_log(rio2, sessions + later).pi_sessions] == [True, True]


def test_epoch_selection_returns_none_when_it_cannot_decide():
    sessions = sessions_for_boot(BOOT_Q1, fourteen_pieces(600))
    assert select_for_log(RioLogInfo('x.wpilog', None), sessions) is None             # log has no epoch
    other_boot = RioLogInfo('x.wpilog', None, epoch=at(BOOT_Q1, 3600), t_range=(0, 1000))
    assert select_for_log(other_boot, sessions) is None                                # nobody shares it


def test_known_epochs_pair_without_any_file_name_clock():
    sessions = sessions_for_boot(BOOT_Q1, fourteen_pieces(600))
    akit = RioLogInfo('akit_tbd.wpilog', None, epoch=BOOT_Q1, t_range=(0, 900))
    [p] = suggest_pairings([akit], sessions)
    assert len(p.pi_sessions) == 28 and p.method == 'epoch'


def test_sessions_a_few_seconds_off_still_share_the_boot():
    """Session epochs agree to 1-3 s; allow for a slow first frame."""
    sessions = sessions_for_boot(BOOT_Q1, fourteen_pieces(600), epoch_jitter=8.0)
    rio = RioLogInfo('akit.wpilog', None, epoch=BOOT_Q1, t_range=(0, 900))
    assert len(select_for_log(rio, sessions).pi_sessions) == 28


# ── fall-backs ───────────────────────────────────────────────────────────────────────────────

def test_sessions_with_no_epoch_fall_back_to_the_file_name_window():
    akit, frc = logs_for_boot(BOOT_Q1, 60)
    bare = [PiSessionInfo('LeftCam', 'boot0001-x', wall_clock=at(BOOT_Q1, 200)),
            PiSessionInfo('RightCam', 'boot0001-y', wall_clock=at(BOOT_Q1, 210))]
    pairs = {p.rio_log: p for p in suggest_pairings([akit, frc], bare)}
    assert len(pairs[akit.name].pi_sessions) == 2 and len(pairs[frc.name].pi_sessions) == 2
    assert pairs[akit.name].method == 'filename'


def test_clockless_sessions_are_added_to_an_epoch_match():
    akit, _ = logs_for_boot(BOOT_Q1, 60)
    good = sessions_for_boot(BOOT_Q1, fourteen_pieces(300, n=2), cameras=('LeftCam',))
    bare = PiSessionInfo('RightCam', 'boot0001-bare', wall_clock=at(BOOT_Q1, 330))
    [p] = suggest_pairings([akit], good + [bare])
    assert {s.name for s in p.pi_sessions} == {s.name for s in good} | {'boot0001-bare'}


def test_a_boot_cluster_with_no_log_named_near_it_falls_back_to_the_window():
    """Epoch known but the DS synced > MAX_SYNC_DELAY after it: the file-name window still tries."""
    akit, _ = logs_for_boot(BOOT_Q1, 40 * 60)
    sessions = sessions_for_boot(BOOT_Q1, [(40 * 60 + 30, 40 * 60 + 90)], cameras=('LeftCam',))
    [p] = suggest_pairings([akit], sessions)
    assert len(p.pi_sessions) == 1 and p.method == 'filename'


# ── reading a session's clock from its manifest rows ─────────────────────────────────────────

def test_session_clock_prefers_the_rows_own_robot_timestamp():
    name_wall = dt.datetime(2026, 10, 17, 12, 35, 4, tzinfo=UTC)
    rows = [{'frame': 'f', 't_sec': 304.7, 'timestamp_utc': '2026-10-17T12:35:04.740Z',
             'timestamp_status': 'synced'}]
    epoch, t_first, t_last = session_clock(rows, rows, name_wall)
    assert t_first == t_last == 304.7
    assert abs((epoch - dt.datetime(2026, 10, 17, 12, 30, 0, tzinfo=UTC)).total_seconds()) < 0.1


def test_session_clock_falls_back_to_the_session_name_and_skips_pi_clock_rows():
    name_wall = dt.datetime(2026, 10, 17, 12, 35, 4, tzinfo=UTC)
    head = [{'frame': 'a', 't_sec': 1.79e9, 'timestamp_status': 'nt_clock_unsynced'},   # Pi wall clock
            {'frame': 'b', 't_sec': 303.0, 'timestamp_status': 'nt_clock_unsynced'}]
    tail = [{'frame': 'z', 't_sec': 340.5}]
    epoch, t_first, t_last = session_clock(head, tail, name_wall)
    assert (t_first, t_last) == (303.0, 340.5)
    assert epoch == name_wall - dt.timedelta(seconds=303.0)


def test_session_clock_of_an_empty_manifest_is_unknown():
    assert session_clock([], [], dt.datetime(2026, 10, 17, tzinfo=UTC)) == (None, None, None)
