"""Spec-builder tests, driven by synthetic signal dicts shaped like the parser's output
so they run in milliseconds and don't depend on a checked-in log."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401  (side effect: puts vision_analyzer on sys.path)

import bundles
from specs import camera_health


def _pose(x=1.0, y=2.0, rot=0.0):
    return [{'x': x, 'y': y, 'rot': rot}]


def _sig(n=5, value=50.0, t0=10.0):
    return [(t0 + i * 0.02, value) for i in range(n)]


def _full_log(cams=('Left', 'Right')):
    s = {}
    for cam in cams:
        s[f'RealOutputs/Vision/{cam}/Health/ScorePercent'] = _sig()
        s[f'RealOutputs/Vision/{cam}/Health/Reason'] = _sig(value='')
        s[f'RealOutputs/Vision/{cam}/AcceptedPoses'] = [
            (10.0 + i * 0.02, _pose()) for i in range(5)]
        s[f'Vision/{cam}/VisibleTagIds'] = [(10.0 + i * 0.02, [10, 11]) for i in range(5)]
        for _, _, _, suffix in camera_health.FACTORS:
            s[f'RealOutputs/Vision/{cam}/Health/{suffix}'] = _sig()
    return s


def test_discovers_cameras_from_health_keys():
    assert camera_health.discover_cameras(_full_log()) == ['Left', 'Right']


def test_discovers_a_third_camera_without_a_code_change():
    """The 2027 robot may not have exactly two cameras."""
    assert camera_health.discover_cameras(_full_log(('Left', 'Right', 'Rear'))) == \
        ['Left', 'Right', 'Rear']


def test_cross_camera_agreement_is_not_mistaken_for_a_camera():
    s = _full_log()
    s['RealOutputs/Vision/CrossCameraAgreement/ScorePercent'] = _sig()
    assert camera_health.discover_cameras(s) == ['Left', 'Right']


def test_falls_back_to_accepted_poses_on_a_pre_health_log():
    s = {'RealOutputs/Vision/Left/AcceptedPoses': [(10.0, _pose())]}
    assert camera_health.discover_cameras(s) == ['Left']


def test_visible_tag_ids_are_found_despite_the_case_mismatch():
    """The robot logs 'VisibleTagIds'; the old replay tab looked for 'visibleTagIds' and
    therefore always drew zero lit tags. Guard the fix."""
    s = {'Vision/Left/visibleTagIds': [(10.0, [7])],
         'RealOutputs/Vision/Left/Health/ScorePercent': _sig()}
    spec, data = camera_health.build(s)
    assert data['tags/Left'] == [(10.0, [7])]


def test_builds_expected_tracks_and_panels():
    spec, data = camera_health.build(_full_log())
    ids = {t.id for t in spec.tracks}
    for cam in ('Left', 'Right'):
        assert f'health/{cam}/score' in ids
        assert f'pose/{cam}' in ids
        assert f'tags/{cam}' in ids
        for suffix, _, _, _ in camera_health.FACTORS:
            assert f'health/{cam}/{suffix}' in ids
    assert [p.id for p in spec.panels] == ['field', 'readout', 'vision', 'trend-Left', 'trend-Right']
    assert spec.layout == [['field', 'readout'], ['vision'], ['trend-Left'], ['trend-Right']]


def test_score_and_factor_tracks_are_all_visible_by_default():
    spec, _ = camera_health.build(_full_log())
    assert spec.track('health/Left/score').hidden is False
    assert spec.track('health/Left/stillness').hidden is False


def test_time_bounds_span_the_data():
    spec, _ = camera_health.build(_full_log())
    assert spec.t0 == 10.0
    assert spec.t1 == 10.08


def test_warns_when_health_is_missing():
    s = {'RealOutputs/Vision/Left/AcceptedPoses': [(10.0, _pose())]}
    spec, _ = camera_health.build(s)
    assert any('predates the live-health scoring' in w for w in spec.warnings)


def test_warns_when_position_is_missing_entirely():
    s = {'RealOutputs/Vision/Left/Health/ScorePercent': _sig()}
    spec, _ = camera_health.build(s)
    assert any('No position data at all' in w for w in spec.warnings)


def test_warns_about_missing_odometry_when_camera_poses_exist():
    spec, _ = camera_health.build(_full_log())
    assert any('No `Drivetrain/Pose`' in w for w in spec.warnings)
    assert not any('No position data at all' in w for w in spec.warnings)


def test_odometry_track_appears_when_drivetrain_pose_is_logged():
    s = _full_log()
    s['RealOutputs/Drivetrain/Pose'] = [(10.0, _pose(3.0, 4.0, 1.0))]
    spec, data = camera_health.build(s)
    assert spec.track('pose/odometry') is not None
    assert data['pose/odometry'] == [(10.0, {'x': 3.0, 'y': 4.0, 'rot': 1.0})]
    assert not any('No `Drivetrain/Pose`' in w for w in spec.warnings)


def test_accepted_poses_array_takes_the_last_pose_of_the_loop():
    s = {'RealOutputs/Vision/Left/AcceptedPoses': [
        (10.0, [{'x': 1.0, 'y': 1.0, 'rot': 0.0}, {'x': 9.0, 'y': 9.0, 'rot': 0.0}])]}
    _, data = camera_health.build(s)
    assert data['pose/Left'] == [(10.0, {'x': 9.0, 'y': 9.0, 'rot': 0.0})]


def test_empty_log_yields_a_spec_that_says_so():
    spec, data = camera_health.build({})
    assert data == {}
    assert any('nothing to replay' in w for w in spec.warnings)


def test_static_carries_field_geometry_and_thresholds():
    spec, _ = camera_health.build(_full_log())
    assert spec.static['field']['length'] > 16
    assert '7' in spec.static['field']['tags']
    assert spec.static['severity'][0]['min'] == 80


def test_vision_panel_and_layout_row_are_always_present():
    """Even with no log_path (and therefore no vision recording to attach), the panel
    exists so the Streamlit tab / standalone export's layout has a stable slot for it."""
    spec, _ = camera_health.build(_full_log())
    vision_panels = [p for p in spec.panels if p.id == 'vision']
    assert len(vision_panels) == 1
    assert vision_panels[0].type == 'vision'
    assert ['vision'] in spec.layout
    assert 'vision' not in spec.static


def _write_session(vision_dir, camera, boot_name, frame_times):
    session = vision_dir / camera / boot_name
    session.mkdir(parents=True)
    with open(session / 'manifest.jsonl', 'w', encoding='utf-8') as f:
        for i, t in enumerate(frame_times):
            frame = 'frame_%.6f.jpg' % t
            (session / frame).write_bytes(b'\xff\xd8\xff\xd9')  # minimal fake JPEG bytes
            f.write(json.dumps({'frame': frame, 't_sec': t}) + '\n')
    return session


def test_build_without_log_path_does_not_touch_static_vision():
    spec, _ = camera_health.build(_full_log())
    assert 'vision' not in spec.static


def test_build_with_log_path_but_no_vision_recording_is_a_no_op(tmp_path):
    log_path = tmp_path / 'FRC_20260101_120000.wpilog'
    log_path.write_bytes(b'')
    spec, _ = camera_health.build(_full_log(), log_path=log_path, log_root=tmp_path)
    assert 'vision' not in spec.static
    assert spec.warnings == [w for w in spec.warnings if 'Vision preview' not in w]


def test_build_with_log_path_warns_when_ffmpeg_is_missing(tmp_path, monkeypatch):
    log_path = tmp_path / 'FRC_20260101_120000.wpilog'
    log_path.write_bytes(b'')
    vision_dir = bundles.vision_dir_for(log_path)
    _write_session(vision_dir, 'Left', 'boot0001-20260101-120000', [10.0, 10.02, 10.04])

    monkeypatch.setattr(bundles, 'ffmpeg_available', lambda: False)

    signals = _full_log(('Left',))
    spec, _ = camera_health.build(signals, log_path=log_path, log_root=tmp_path)

    assert 'vision' not in spec.static
    assert any('Vision preview for the Left camera could not be built' in w for w in spec.warnings)
    assert any('ffmpeg is not on PATH' in w for w in spec.warnings)


def test_build_with_log_path_skips_a_session_outside_the_log_window(tmp_path, monkeypatch):
    log_path = tmp_path / 'FRC_20260101_120000.wpilog'
    log_path.write_bytes(b'')
    vision_dir = bundles.vision_dir_for(log_path)
    # Session frames are far outside the log's [10.0, 10.08] time bounds from _full_log().
    _write_session(vision_dir, 'Left', 'boot0001-20260101-120000', [500.0, 500.02])

    monkeypatch.setattr(bundles, 'ffmpeg_available', lambda: False)  # would raise if reached

    spec, _ = camera_health.build(_full_log(('Left',)), log_path=log_path, log_root=tmp_path)
    assert 'vision' not in spec.static
