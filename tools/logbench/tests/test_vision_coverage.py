"""vision_coverage.py: per-camera share of the enabled time that has a frame, the largest gaps, and the
Health Check rows built from them. Gap shapes come from Ruckus 2026 (a 150 s match, sessions cut by
camera/NT flapping, gaps of 4 s to 140 s shared by every recorder)."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import paths  # noqa: F401

from fastapi.testclient import TestClient

import main
import vision_coverage as vc
from testkit import build_bundle

client = TestClient(main.app)


def frames(lo, hi, hz=3.0):
    n = int((hi - lo) * hz)
    return [lo + i / hz for i in range(n + 1)]


# ── the arithmetic ──────────────────────────────────────────────────────────────────────────

def test_continuous_frames_cover_the_whole_window_with_no_gaps():
    covered, gaps = vc.coverage_of(frames(100, 250), [(100, 250)])
    assert covered == pytest.approx(150, abs=0.01) and gaps == []


def test_no_frames_is_one_gap_the_size_of_the_window():
    covered, gaps = vc.coverage_of([], [(100, 250)])
    assert covered == 0 and gaps == [(100, 250)]


def test_gaps_are_found_inside_the_window_and_listed_largest_first():
    times = frames(100, 120) + frames(135, 190) + frames(250, 250.5)
    covered, gaps = vc.coverage_of(times, [(100, 250)])
    assert [round(b - a) for a, b in gaps] == [59, 14]            # 190.5-249.5, 120.5-134.5
    assert gaps[0][0] == pytest.approx(190.5, abs=0.01)
    assert covered == pytest.approx(77, abs=1.0)


def test_frames_outside_the_enabled_windows_do_not_count_and_short_gaps_are_ignored():
    times = frames(0, 90) + [100.2, 101.0, 103.1, 104.0, 104.5]   # a 2.1 s hole at ~101.5-102.6 is under MIN_GAP
    covered, gaps = vc.coverage_of(times, [(100, 105)])
    assert gaps == []
    assert 3.5 < covered <= 5


def test_two_windows_are_measured_separately():
    times = frames(10, 20) + frames(40, 50)
    covered, gaps = vc.coverage_of(times, [(10, 20), (40, 60)])
    assert covered == pytest.approx(10 + 10, abs=1.0)
    assert [(round(a), round(b)) for a, b in gaps] == [(50, 60)]


# ── the rows ────────────────────────────────────────────────────────────────────────────────

def cam(name, fraction, gaps=(), frames_=100, sessions=3):
    return vc.CameraCoverage(name, frames_, sessions, 150.0, 150.0 * fraction, list(gaps))


def by_id(rows, group, id_):
    [row] = [r for r in rows if r['group'] == group and r['id'] == id_]
    return row


def test_a_good_camera_is_ok_and_a_sparse_one_is_flagged_with_its_biggest_gaps():
    rows = vc.health_rows([cam('LeftCam', 0.946, [(40, 44)]), cam('RightCam', 0.211, [(300, 395), (30, 40)])])
    assert by_id(rows, 'LeftCam', 'vision.recording.coverage')['status'] == 'ok'
    assert by_id(rows, 'LeftCam', 'vision.recording.gap')['status'] == 'ok'
    sparse = by_id(rows, 'RightCam', 'vision.recording.coverage')
    assert sparse['status'] == 'fail' and sparse['display'] == '21%'
    assert '300-395 s (95 s)' in sparse['detail']
    assert by_id(rows, 'RightCam', 'vision.recording.gap')['status'] == 'fail'
    assert by_id(rows, 'RightCam', 'vision.recording.gap')['display'] == '95 s'


def test_the_middle_band_warns():
    rows = vc.health_rows([cam('LeftCam', 0.80, [(40, 55)])])
    assert by_id(rows, 'LeftCam', 'vision.recording.coverage')['status'] == 'warn'
    assert by_id(rows, 'LeftCam', 'vision.recording.gap')['status'] == 'warn'


def test_a_camera_the_robot_logged_but_the_bundle_lacks_is_a_failure():
    rows = vc.health_rows([cam('LeftCam', 1.0)], expected_cameras=['LeftCam', 'RightCam'])
    missing = by_id(rows, 'RightCam', 'vision.recording.coverage')
    assert missing['status'] == 'fail' and 'no recording folder' in missing['detail']


def test_a_log_without_any_vision_recording_gets_no_rows():
    assert vc.health_rows(None, expected_cameras=['LeftCam']) == []


# ── through the API, on testkit bundles ─────────────────────────────────────────────────────

def report_for(tmp_path, monkeypatch, scenario):
    bundle = build_bundle.build_bundle(tmp_path / scenario, scenario, cycle_ms=250)
    monkeypatch.setattr(main, 'LOG_ROOT', bundle.out_dir)
    r = client.get('/api/health/log', params={'path': bundle.log_path.name})
    assert r.status_code == 200, r.text
    rows = [c for s in r.json()['sections'] for g in s['groups'] for sub in g['subjects'] for c in sub['checks']
            if c['id'].startswith('vision.recording')]
    return rows


def test_a_clean_bundle_is_fully_covered(tmp_path, monkeypatch):
    rows = report_for(tmp_path, monkeypatch, 'clean')
    coverage = [r for r in rows if r['id'].endswith('coverage')]
    assert {r['group'] for r in coverage} == {'LeftCam', 'RightCam'}
    assert all(r['status'] == 'ok' and r['value'] > 90 for r in coverage)


def test_nt_flapping_shows_up_as_gaps(tmp_path, monkeypatch):
    rows = report_for(tmp_path, monkeypatch, 'nt-flap')
    clean = {r['group']: r['value'] for r in report_for(tmp_path, monkeypatch, 'clean') if r['id'].endswith('coverage')}
    flap = {r['group']: r for r in rows if r['id'].endswith('coverage')}
    assert all(flap[c]['value'] < clean[c] for c in clean)
    gap = by_id(rows, 'LeftCam', 'vision.recording.gap')
    assert gap['value'] >= 8 and 'largest gaps' in gap['detail']


def test_only_auto_recorded_fails_the_coverage_row(tmp_path, monkeypatch):
    rows = report_for(tmp_path, monkeypatch, 'partial-auto-only')
    assert by_id(rows, 'LeftCam', 'vision.recording.coverage')['status'] == 'fail'


def test_a_missing_camera_folder_is_reported(tmp_path, monkeypatch):
    rows = report_for(tmp_path, monkeypatch, 'one-camera')
    assert by_id(rows, 'RightCam', 'vision.recording.coverage')['display'] == 'none'


def test_a_log_with_no_recording_has_no_vision_recording_section(tmp_path, monkeypatch):
    assert report_for(tmp_path, monkeypatch, 'no-recording') == []
