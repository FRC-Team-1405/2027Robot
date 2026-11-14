"""The tool starts out matching the robot code, and the Quick tab works with the log's own camera names."""
import numpy as np
from streamlit.testing.v1 import AppTest

from camera_calibration.robot_defaults import mount_for, parse_vision_constants
from tests.test_autocal import (TRUE_LEFT, TRUE_RIGHT, _pose3d_dict, routine, simulate,
                                wrong_guess)

JAVA = '''
new CameraConfig("AlphaCam", 1.0,
    new Transform3d(new Translation3d(Units.inchesToMeters(2.5), Units.inchesToMeters(-9.0),
        Units.inchesToMeters(30.0)), new Rotation3d(0, Math.toRadians(-20), Math.toRadians(12.5))),
    new CameraIntrinsics(800.0, 600.0, 1, 1, 1, 1, new double[] { 0 })),
new CameraConfig("BetaCam", 1.0,
    new Transform3d(new Translation3d(Units.inchesToMeters(1), Units.inchesToMeters(8),
        Units.inchesToMeters(25)), new Rotation3d(Math.toRadians(1.5), 0.0, Math.toRadians(-3))),
    new CameraIntrinsics(800.0, 600.0, 1, 1, 1, 1, new double[] { 0 }))
'''


def test_parse_vision_constants():
    d = parse_vision_constants(JAVA)
    assert d['AlphaCam'] == {'x_in': 2.5, 'y_in': -9.0, 'z_in': 30.0,
                             'roll_deg': 0.0, 'pitch_deg': -20.0, 'yaw_deg': 12.5}
    assert d['BetaCam']['roll_deg'] == 1.5 and d['BetaCam']['yaw_deg'] == -3.0


def test_real_vision_constants_has_both_cameras():
    from camera_calibration.robot_defaults import camera_defaults
    d, src = camera_defaults()
    assert 'current robot code' in src and {'LeftCam', 'RightCam'} <= set(d)


def test_mount_for_name_variants():
    d = {'LeftCam': {'y_in': 1}, 'RightCam': {'y_in': 2}}
    assert mount_for('LeftCam', d)['y_in'] == 1
    assert mount_for('leftcam', d)['y_in'] == 1
    assert mount_for('Right', d)['y_in'] == 2
    assert mount_for('Mystery', d)['y_in'] == 1       # falls back to the first, never crashes


def _fake_log():
    ts, odo, cams = simulate(routine(), {'LeftCam': TRUE_LEFT, 'RightCam': TRUE_RIGHT}, seed=11)
    sig = {'Drivetrain/Pose': [(float(t), [{'x': x, 'y': y, 'rot': th}]) for t, (x, y, th) in zip(ts, odo)],
           'Calibration/Phase': [(0.0, 'Idle'), (0.2, 'Hold'), (float(ts[-1]) + 0.3, 'Done')],
           'Calibration/VisionCorrectionsOff': [(0.0, True)]}
    from camera_calibration.robot_defaults import camera_defaults
    from camera_calibration.solver import params_to_matrix
    defaults, _ = camera_defaults()
    for name in ('LeftCam', 'RightCam'):
        m = defaults[name]
        T_cur = params_to_matrix(m['x_in'] * 0.0254, m['y_in'] * 0.0254, m['z_in'] * 0.0254,
                                 m['roll_deg'], m['pitch_deg'], m['yaw_deg'])
        t_obs, obs = cams[name]
        for key in ('rawEstimatedPoses', 'rawTimestampsSec', 'rawTagCountsPerResult', 'rawTagIdsFlat'):
            sig[f'Vision/{name}/{key}'] = []
        for t, T in zip(t_obs, obs):
            rec = t + 0.025
            sig[f'Vision/{name}/rawEstimatedPoses'].append((rec, [_pose3d_dict(T @ np.linalg.inv(T_cur))]))
            sig[f'Vision/{name}/rawTimestampsSec'].append((rec, [t]))
            sig[f'Vision/{name}/rawTagCountsPerResult'].append((rec, [2]))
            sig[f'Vision/{name}/rawTagIdsFlat'].append((rec, [9, 10]))
    return sig


def test_quick_tab_with_log_camera_names():
    """Cameras named LeftCam / RightCam in the log; the tab needs no sidebar camera and starts from the code's mounts."""
    sig = _fake_log()

    def script():
        import streamlit as st
        from camera_calibration.tabs import auto_tab
        auto_tab.render({'signals': st.session_state['_sig']})

    at = AppTest.from_function(script)
    at.session_state['_sig'] = sig
    at.run(timeout=120)
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    assert at.selectbox[0].options == ['LeftCam', 'RightCam']
    # mounts prefilled from the robot code
    assert at.number_input(key='aq_y_LeftCam').value == 10.91
    # solve both cameras: the second solve also shows the agreement table
    for cam in ('LeftCam', 'RightCam'):
        at.selectbox[0].select(cam).run(timeout=120)
        btn = [b for b in at.button if b.label.startswith('Solve')][0]
        btn.click().run(timeout=120)
        assert not at.exception, [e.value for e in at.exception]
        assert not at.error, [e.value for e in at.error]
    md = ' '.join(m.value for m in at.markdown)
    assert 'Do the two cameras agree?' in md
