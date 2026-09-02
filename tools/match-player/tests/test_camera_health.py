"""Spec-builder tests, driven by synthetic signal dicts shaped like the parser's output
so they run in milliseconds and don't depend on a checked-in log."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401  (side effect: puts vision_analyzer on sys.path)

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
    assert [p.id for p in spec.panels] == ['field', 'readout', 'trend-Left', 'trend-Right']
    assert spec.layout == [['field', 'readout'], ['trend-Left'], ['trend-Right']]


def test_factor_tracks_are_hidden_by_default_but_the_score_is_not():
    spec, _ = camera_health.build(_full_log())
    assert spec.track('health/Left/score').hidden is False
    assert spec.track('health/Left/stillness').hidden is True


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
