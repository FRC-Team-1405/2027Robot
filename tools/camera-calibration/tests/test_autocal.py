"""Synthetic tests for camera_calibration.autocal: simulate the calibration routine with a known
camera mount, add realistic noise, and check the solver gets the mount back.

Run from tools/camera-calibration:   python -m pytest tests -q
"""
import math

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from camera_calibration.autocal import cross_camera_agreement, planar_matrix, solve
from camera_calibration.solver import matrix_to_params, params_to_matrix

TAG = np.array([0.0, 0.0, 1.124])          # tag pair centre in the field frame; the tag faces +x
TRUE_LEFT = dict(x_m=0.056, y_m=0.277, z_m=0.73, roll_deg=0.0, pitch_deg=-25.0, yaw_deg=-10.0)
TRUE_RIGHT = dict(x_m=0.056, y_m=-0.277, z_m=0.73, roll_deg=0.0, pitch_deg=-25.0, yaw_deg=10.0)


def mount(d):
    return params_to_matrix(d['x_m'], d['y_m'], d['z_m'], d['roll_deg'], d['pitch_deg'], d['yaw_deg'])


def routine(spin=True, drive=True):
    """(duration_s, vx, vy, omega_deg_s) segments, robot-centric: hold, sweep, forward/back, strafe."""
    seg = [(2.0, 0, 0, 0)]
    if spin:
        seg += [(1.25, 0, 0, 20), (2.5, 0, 0, -20), (1.25, 0, 0, 20)]
    if drive:
        seg += [(1.5, 0.4, 0, 0), (1.5, -0.4, 0, 0),
                (1.5, 0, 0.4, 0), (3.0, 0, -0.4, 0), (1.5, 0, 0.4, 0)]
    seg += [(1.0, 0, 0, 0)]
    return seg


def simulate(segments, true_mounts, start=(2.5, 0.0, math.pi), dt=0.01, seed=0,
             pos_noise=0.015, rot_noise_deg=0.7, label_delay=0.03, fov_deg=35.0, field_shift=None,
             odo_scale_err=1.0):
    """Return per-camera observations plus the odometry series. Odometry is in its own frame."""
    rng = np.random.default_rng(seed)
    x, y, yaw = start
    ts, truth = [0.0], [(x, y, yaw)]
    t = 0.0
    for dur, vx, vy, om in segments:
        for _ in range(int(round(dur / dt))):
            c, s = math.cos(yaw), math.sin(yaw)
            x += (c * vx - s * vy) * dt
            y += (s * vx + c * vy) * dt
            yaw += math.radians(om) * dt
            t += dt
            ts.append(t)
            truth.append((x, y, yaw))
    ts = np.array(ts)
    truth = np.array(truth)

    # odometry frame: starts at (0, 0, 0) at the start pose, with tiny gyro/wheel noise
    d0 = planar_matrix(*truth[0])
    odo = np.empty_like(truth)
    for i, (px, py, pyaw) in enumerate(truth):
        rel = np.linalg.inv(d0) @ planar_matrix(px, py, pyaw)
        odo[i] = (rel[0, 3], rel[1, 3], math.atan2(rel[1, 0], rel[0, 0]))
    odo[:, :2] *= odo_scale_err            # e.g. a wheel radius that is a few percent off
    odo[:, 2] += rng.normal(0, math.radians(0.03), len(odo))
    odo[:, :2] += rng.normal(0, 0.002, (len(odo), 2))

    cams = {}
    for name, tm in true_mounts.items():
        T_rc = mount(tm)
        t_obs, obs = [], []
        for k in range(0, len(ts), 1):               # camera at 100 Hz
            Tc = planar_matrix(*truth[k]) @ T_rc
            fwd = Tc[:3, 0]
            to_tag = TAG - Tc[:3, 3]
            ang = math.degrees(math.acos(np.clip(fwd @ to_tag / np.linalg.norm(to_tag), -1, 1)))
            # horizontal bearing off the camera axis (the real limit is the horizontal FOV)
            bearing = math.degrees(abs(math.atan2(to_tag[1], to_tag[0]) - math.atan2(fwd[1], fwd[0])))
            bearing = min(bearing, 360 - bearing)
            if bearing > fov_deg or ang > 60 or np.linalg.norm(to_tag) > 5:
                continue
            Tn = Tc.copy()
            Tn[:3, 3] += rng.normal(0, pos_noise, 3)
            Tn[:3, :3] = Tn[:3, :3] @ Rotation.from_rotvec(rng.normal(0, math.radians(rot_noise_deg), 3)).as_matrix()
            if field_shift is not None:
                Tn = field_shift @ Tn
            t_obs.append(ts[k] + label_delay)
            obs.append(Tn)
        cams[name] = (np.array(t_obs), np.array(obs))
    return ts, odo, cams


def err(res, true):
    p = res.params
    return dict(
        x=abs(p['x_m'] - true['x_m']) * 1000, y=abs(p['y_m'] - true['y_m']) * 1000,
        z=abs(p['z_m'] - true['z_m']) * 1000,
        roll=abs(p['roll_deg'] - true['roll_deg']), pitch=abs(p['pitch_deg'] - true['pitch_deg']),
        yaw=abs(p['yaw_deg'] - true['yaw_deg']),
    )


def wrong_guess(true):
    """Start from a deliberately wrong mount (a few cm and degrees off), like a hand-measured one."""
    g = dict(true)
    g['x_m'] += 0.04
    g['y_m'] -= 0.05
    g['z_m'] += 0.03
    g['pitch_deg'] += 3.0
    g['yaw_deg'] -= 4.0
    return mount(g)


@pytest.mark.parametrize('seed', [0, 1, 2])
def test_recovers_mount_full_routine(seed):
    ts, odo, cams = simulate(routine(), {'Left': TRUE_LEFT}, seed=seed)
    t_obs, obs = cams['Left']
    assert len(t_obs) > 300
    res = solve(t_obs, obs, ts, odo, wrong_guess(TRUE_LEFT), 'Left')
    e = err(res, TRUE_LEFT)
    assert e['x'] < 15 and e['y'] < 15 and e['z'] < 20, e
    assert e['roll'] < 1.0 and e['pitch'] < 1.0 and e['yaw'] < 1.0, e
    # the clock offset was injected as +30 ms label delay, so tau should come out near -30 ms
    assert res.tau_s == pytest.approx(-0.03, abs=0.015)
    assert not res.warnings, res.warnings


def test_right_camera_and_agreement_after_calibration():
    # low frame noise here so the comparison shows mount error, not single-frame jitter
    ts, odo, cams = simulate(routine(), {'Left': TRUE_LEFT, 'Right': TRUE_RIGHT}, seed=3,
                             pos_noise=0.003, rot_noise_deg=0.15)
    out = {}
    for name, true in (('Left', TRUE_LEFT), ('Right', TRUE_RIGHT)):
        t_obs, obs = cams[name]
        out[name] = solve(t_obs, obs, ts, odo, wrong_guess(true), name)
        e = err(out[name], true)
        assert e['x'] < 15 and e['y'] < 15 and e['yaw'] < 1.0, (name, e)
    tl, ol = cams['Left']
    tr, orr = cams['Right']
    bad = cross_camera_agreement(tl, ol, wrong_guess(TRUE_LEFT), tr, orr, wrong_guess(TRUE_RIGHT))
    good = cross_camera_agreement(tl, ol, out['Left'].T_rc, tr, orr, out['Right'].T_rc)
    assert good['n'] > 100
    assert good['pos_median_mm'] < 0.5 * bad['pos_median_mm']
    assert good['pos_median_mm'] < 10


def test_tag_placement_error_cancels():
    """Moving/turning the whole tag pair rigidly (a student mounted it a bit off) must not change the mount."""
    shift = planar_matrix(0.07, -0.05, math.radians(2.5))
    ts, odo, cams = simulate(routine(), {'Left': TRUE_LEFT}, seed=4, field_shift=shift)
    t_obs, obs = cams['Left']
    res = solve(t_obs, obs, ts, odo, wrong_guess(TRUE_LEFT), 'Left')
    e = err(res, TRUE_LEFT)
    assert e['x'] < 15 and e['y'] < 15 and e['yaw'] < 1.0, e


def test_spin_only_is_flagged():
    ts, odo, cams = simulate(routine(spin=True, drive=False), {'Left': TRUE_LEFT}, seed=5)
    t_obs, obs = cams['Left']
    res = solve(t_obs, obs, ts, odo, wrong_guess(TRUE_LEFT), 'Left')
    assert any('drove' in w or 'yaw' in w for w in res.warnings), res.warnings


def test_too_few_samples_raises():
    ts, odo, cams = simulate(routine(), {'Left': TRUE_LEFT}, seed=6)
    t_obs, obs = cams['Left']
    with pytest.raises(ValueError):
        solve(t_obs[:10], obs[:10], ts, odo, wrong_guess(TRUE_LEFT))


def _pose3d_dict(T):
    q = Rotation.from_matrix(T[:3, :3]).as_quat()  # x y z w
    return {'x': T[0, 3], 'y': T[1, 3], 'z': T[2, 3], 'qw': q[3], 'qx': q[0], 'qy': q[1], 'qz': q[2]}


def test_log_adapter_roundtrip():
    """Build a fake parsed log from a simulated run and solve it through autocal_io."""
    from camera_calibration.autocal_io import calibration_window, extract_run, list_cameras
    ts, odo, cams = simulate(routine(), {'Left': TRUE_LEFT}, seed=7)
    t_obs, obs = cams['Left']
    guess = wrong_guess(TRUE_LEFT)
    # what PhotonVision would have logged: robot pose estimate computed with the *configured* mount.
    # Vision timestamps in the log are capture times; the record time is ~25 ms later.
    sig = {'Vision/Left/rawEstimatedPoses': [], 'Vision/Left/rawTimestampsSec': [],
           'Vision/Left/rawTagCountsPerResult': [], 'Vision/Left/rawTagIdsFlat': []}
    t_end = ts[-1]
    for t, T in zip(t_obs, obs):
        rec = t + 0.025
        sig['Vision/Left/rawEstimatedPoses'].append((rec, [_pose3d_dict(T @ np.linalg.inv(guess))]))
        sig['Vision/Left/rawTimestampsSec'].append((rec, [t]))
        sig['Vision/Left/rawTagCountsPerResult'].append((rec, [2]))
        sig['Vision/Left/rawTagIdsFlat'].append((rec, [9, 10]))
    sig['Drivetrain/Pose'] = [(float(t), [{'x': x, 'y': y, 'rot': th}]) for t, (x, y, th) in zip(ts, odo)]
    sig['Calibration/Phase'] = [(0.0, 'Idle'), (0.5, 'Hold'), (float(t_end) + 0.4, 'Done')]
    sig['Calibration/VisionCorrectionsOff'] = [(0.0, True)]

    assert list_cameras(sig) == ['Left']
    assert calibration_window(sig) == (0.5, pytest.approx(float(t_end) + 0.4))
    run = extract_run(sig, 'Left', guess, tag_ids={9, 10})
    assert run['info']['clock'] == 'rawTimestampsSec' and not run['notes']
    res = solve(run['t_obs'], run['obs_T'], run['t_odo'], run['odo'], guess, 'Left')
    e = err(res, TRUE_LEFT)
    assert e['x'] < 15 and e['y'] < 15 and e['yaw'] < 1.0, e
    # a result that includes an uncovered tag (e.g. 11) is dropped when filtering to the pair
    sig['Vision/Left/rawTagIdsFlat'][100] = (sig['Vision/Left/rawTagIdsFlat'][100][0], [9, 11])
    run2 = extract_run(sig, 'Left', guess, tag_ids={9, 10})
    assert run2['info']['results_dropped_by_tag_filter'] == 1


def test_tag_height_correction():
    """A tag mounted 2 cm lower than the layout says puts every camera height 2 cm high; the correction fixes it."""
    from camera_calibration.autocal import with_tag_height_correction
    raised = np.eye(4)
    raised[2, 3] = 0.02          # layout is 2 cm higher than the real tag
    ts, odo, cams = simulate(routine(), {'Left': TRUE_LEFT}, seed=8, field_shift=raised)
    t_obs, obs = cams['Left']
    res = solve(t_obs, obs, ts, odo, wrong_guess(TRUE_LEFT), 'Left')
    assert res.params['z_m'] - TRUE_LEFT['z_m'] == pytest.approx(0.02, abs=0.008)
    fixed = with_tag_height_correction(res, layout_z_m=1.124, measured_z_m=1.104, camera_name='Left')
    assert abs(fixed.params['z_m'] - TRUE_LEFT['z_m']) < 0.008
    assert 'Units.inchesToMeters' in fixed.java_snippet


def _spans(segments):
    names = ['Hold', 'SweepCCW', 'SweepCW', 'SweepBack', 'DriveForward', 'DriveBack', 'StrafeLeft',
             'StrafeRight', 'StrafeCenter', 'HoldEnd']
    out, t = [], 0.0
    for n, (dur, *_rest) in zip(names, segments):
        out.append((n, t, t + dur))
        t += dur
    return out


def test_wheel_distance_error_is_fitted_and_drive_check_shows_it():
    """Odometry that over-reports distance by 12% (wheel radius wrong): the fit absorbs it (not pinned at a
    limit) and the straight-drive check reports camera/wheels ~ 0.89."""
    from camera_calibration.autocal_io import drive_check
    segs = routine()
    ts, odo, cams = simulate(segs, {'Left': TRUE_LEFT}, seed=9, odo_scale_err=1.12)
    t_obs, obs = cams['Left']
    res = solve(t_obs, obs, ts, odo, wrong_guess(TRUE_LEFT), 'Left')
    assert res.odo_scale == pytest.approx(1 / 1.12, abs=0.03)
    e = err(res, TRUE_LEFT)
    assert e['x'] < 20 and e['y'] < 20 and e['yaw'] < 1.5, e
    rows = drive_check(_spans(segs), t_obs, obs, ts, odo)
    assert [r['phase'] for r in rows] == ['DriveForward', 'DriveBack', 'StrafeLeft', 'StrafeRight', 'StrafeCenter']
    for r in rows:
        assert r['ratio'] == pytest.approx(1 / 1.12, abs=0.08), r
    # the direction offset is the same for every drive (it is the odometry-to-field rotation)
    assert all(abs(r['angle_dev_deg']) < 4 for r in rows), [r['angle_dev_deg'] for r in rows]


def test_standstill_stats_noise_and_closure():
    from camera_calibration.autocal_io import standstill_stats
    segs = routine()
    ts, odo, cams = simulate(segs, {'Left': TRUE_LEFT}, seed=12, pos_noise=0.015, rot_noise_deg=0.7)
    t_obs, obs = cams['Left']
    st_ = standstill_stats(_spans(segs), t_obs, obs, ts, odo)
    nz, cl = st_['noise'], st_['closure']
    assert 8 < nz['x_mm'] < 25 and 8 < nz['y_mm'] < 25, nz          # the 15 mm we injected (per axis)
    assert 0.3 < nz['rot_deg'] < 2.0, nz
    assert cl['wheels_mm'] < 15 and cl['vision_mm'] < 15, cl       # the routine returns to its start
