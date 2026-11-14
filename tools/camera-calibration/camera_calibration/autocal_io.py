"""Read a "Calibrate Cameras" run out of a parsed .wpilog for camera_calibration.autocal.

`signals` is what vision_analyzer.parser.parse_wpilog returns: {key: [(t_seconds, value), ...]}.
Pose3d[] decode to lists of {x, y, z, qw, qx, qy, qz}; Pose2d to {x, y, rot}.

Keys read (written by the robot code):
  Vision/<cam>/rawEstimatedPoses, rawTimestampsSec, rawTagCountsPerResult, rawTagIdsFlat
  Drivetrain/Pose          fused pose; with vision corrections OFF (as in the calibration auto) it
                           is pure wheel + gyro odometry, which is what the solver needs
  Calibration/Phase        string, set by CalibrateCamerasCommand; bounds the analysed window
  Calibration/VisionCorrectionsOff   boolean, true while the command runs
"""
from __future__ import annotations

import numpy as np

from .solver import pose3d_to_matrix, recover_camera_pose

IDLE_PHASES = ('', 'idle', 'done', 'interrupted')


def find_signal(signals: dict, base_key: str):
    """Exact, RealOutputs/-prefixed, then case-insensitive lookup (AdvantageKit key variants)."""
    for prefix in ('', 'RealOutputs/'):
        if prefix + base_key in signals:
            return signals[prefix + base_key]
    target = base_key.lower()
    for k, v in signals.items():
        kl = k.lower()
        if kl == target or kl == 'realoutputs/' + target:
            return v
    return None


def calibration_window(signals: dict) -> tuple[float, float] | None:
    """(start, end) of the calibration routine from Calibration/Phase, or None if it isn't logged."""
    sig = find_signal(signals, 'Calibration/Phase')
    if not sig:
        return None
    start = end = None
    for t, v in sig:
        active = str(v).strip().lower() not in IDLE_PHASES
        if start is None and active:
            start = t
        elif start is not None and not active:
            end = t
            break
    if start is None:
        return None
    return start, end if end is not None else sig[-1][0]


def phase_spans(signals: dict, window=None) -> list[tuple[str, float, float]]:
    """[(phase name, start, end)] in order, from Calibration/Phase (a step function)."""
    sig = find_signal(signals, 'Calibration/Phase')
    if not sig:
        return []
    spans = []
    for i, (t, v) in enumerate(sig):
        name = str(v).strip()
        if name.lower() in IDLE_PHASES:
            continue
        t_end = sig[i + 1][0] if i + 1 < len(sig) else (window[1] if window else t)
        if window and t >= window[1]:
            continue
        spans.append((name, t, t_end))
    return spans


def phase_diagnostics(spans, sample_t, err_t_mm, err_r_deg) -> list[dict]:
    """Per phase: seconds, vision samples, samples per second, and RMS error at the solution.

    A phase whose samples/s is far below the others means the tag left the camera's view.
    A phase with a large error is where the model and the data disagree (odometry slip, a lost
    tag, a bad tag pose).
    """
    sample_t = np.asarray(sample_t, float)
    out = []
    for name, t0, t1 in spans:
        # vision samples are stamped at capture time, slightly before the record time
        m = (sample_t >= t0 - 0.05) & (sample_t < t1 - 0.05)
        n = int(m.sum())
        secs = max(t1 - t0, 1e-9)
        out.append({
            'phase': name, 'seconds': float(secs), 'samples': n, 'rate': n / secs,
            'rms_t_mm': float(np.sqrt(np.mean(np.square(np.asarray(err_t_mm)[m])))) if n else None,
            'rms_r_deg': float(np.sqrt(np.mean(np.square(np.asarray(err_r_deg)[m])))) if n else None,
        })
    return out


def drive_check(spans, t_obs, obs_T, t_odo, odo, edge=(0.1, 0.4)) -> list[dict]:
    """For each straight drive: how far the wheels say the robot moved vs how far the camera saw it move.

    Needs no mount. The robot does not rotate during these phases, so the camera moves exactly as the
    robot does. `ratio` = vision distance / wheel distance: 1.00 means the wheels and the camera agree;
    0.90 means the wheels claim 11% more distance than the camera saw (wheel radius too big, wheels
    slipping, or the camera's range reading 10% short: tag size, spacing, intrinsics).
    `angle_deg` is the direction of the vision displacement minus the wheel displacement in the field
    frame (the odometry-to-field rotation); `angle_dev_deg` is how far each drive is from the typical
    one, which should be near 0 for every drive.
    """
    t_obs = np.asarray(t_obs, float)
    out = []
    for name, t0, t1 in spans:
        if not (name.lower().startswith('drive') or name.lower().startswith('strafe')):
            continue

        def window(lo, hi):
            m = (t_obs >= lo) & (t_obs <= hi)
            if m.sum() < 3:
                return None
            cam = np.asarray(obs_T)[m][:, :2, 3].mean(axis=0)
            o = np.column_stack([np.interp(t_obs[m], t_odo, odo[:, 0]),
                                 np.interp(t_obs[m], t_odo, odo[:, 1])]).mean(axis=0)
            return cam, o

        a = window(t0 + edge[0], t0 + edge[1])
        b = window(t1 - edge[1], t1 - edge[0])
        if a is None or b is None:
            out.append({'phase': name, 'odo_mm': None, 'vision_mm': None, 'ratio': None, 'angle_deg': None, 'angle_dev_deg': None})
            continue
        dv, do = b[0] - a[0], b[1] - a[1]
        lo_, lv = float(np.hypot(*do)), float(np.hypot(*dv))
        ang = float(np.degrees(np.arctan2(dv[1], dv[0]) - np.arctan2(do[1], do[0])))
        ang = (ang + 180.0) % 360.0 - 180.0
        out.append({'phase': name, 'odo_mm': lo_ * 1000, 'vision_mm': lv * 1000,
                    'ratio': lv / lo_ if lo_ > 0.05 else None, 'angle_deg': ang})
    # the raw angle is the odometry-to-field rotation (any value); what matters is how much each drive
    # differs from the typical one
    angs = [d['angle_deg'] for d in out if d.get('angle_deg') is not None]
    if angs:
        ref = float(np.degrees(np.arctan2(np.median(np.sin(np.radians(angs))), np.median(np.cos(np.radians(angs))))))
        for d in out:
            if d.get('angle_deg') is not None:
                d['angle_dev_deg'] = (d['angle_deg'] - ref + 180.0) % 360.0 - 180.0
    return out


def list_cameras(signals: dict) -> list[str]:
    import re
    rx = re.compile(r'^(?:RealOutputs/)?Vision/([^/]+)/rawEstimatedPoses$', re.IGNORECASE)
    return sorted({m.group(1) for k in signals if (m := rx.match(k))})


def list_tag_ids(signals: dict, camera: str, window=None) -> dict[int, int]:
    """{tag id: number of results it appeared in}, so the user can see which tags the camera saw."""
    ids = find_signal(signals, f'Vision/{camera}/rawTagIdsFlat') or []
    seen: dict[int, int] = {}
    for t, flat in ids:
        if window and not (window[0] <= t <= window[1]):
            continue
        for i in flat:
            seen[int(i)] = seen.get(int(i), 0) + 1
    return seen


def extract_run(signals: dict, camera: str, T_rc_current: np.ndarray,
                tag_ids: set[int] | None = None, window: tuple[float, float] | None = None) -> dict:
    """Arrays for autocal.solve, plus notes about what was found.

    Returns {'t_obs','obs_T','t_odo','odo','info': {...}, 'notes': [str]}.
    """
    notes: list[str] = []
    poses_sig = find_signal(signals, f'Vision/{camera}/rawEstimatedPoses')
    if not poses_sig:
        raise ValueError(f'No Vision/{camera}/rawEstimatedPoses in this log.')
    ts_sig = dict(find_signal(signals, f'Vision/{camera}/rawTimestampsSec') or [])
    counts_sig = dict(find_signal(signals, f'Vision/{camera}/rawTagCountsPerResult') or [])
    ids_sig = dict(find_signal(signals, f'Vision/{camera}/rawTagIdsFlat') or [])
    odo_sig = find_signal(signals, 'Drivetrain/Pose')
    if not odo_sig:
        raise ValueError('No Drivetrain/Pose in this log: the solver needs the robot odometry.')

    if window is None:
        window = calibration_window(signals)
        if window is None:
            notes.append('No Calibration/Phase in the log: using the whole log. If this is not a '
                         '"Calibrate Cameras" run, the result will be meaningless.')
    off = find_signal(signals, 'Calibration/VisionCorrectionsOff')
    if off is None:
        notes.append('The log does not show vision corrections being switched off, so Drivetrain/Pose '
                     'may already include them (circular). Use a run of the Calibrate Cameras auto.')

    # --- vision samples --------------------------------------------------------------------
    t_obs, obs, lat = [], [], []
    n_results = n_tagfilter = 0
    for t, poses in poses_sig:
        if window and not (window[0] <= t <= window[1]) or not poses:
            continue
        stamps = ts_sig.get(t) or []
        counts = counts_sig.get(t) or []
        flat = ids_sig.get(t) or []
        offsets = np.cumsum([0] + list(counts)) if len(counts) else None
        for j, pose in enumerate(poses):
            n_results += 1
            if tag_ids is not None and offsets is not None and j < len(counts):
                these = {int(i) for i in flat[offsets[j]:offsets[j + 1]]}
                if not these or not these <= tag_ids:
                    n_tagfilter += 1
                    continue
            T_robot_est = pose3d_to_matrix(pose)
            obs.append(recover_camera_pose(T_robot_est, T_rc_current))
            if j < len(stamps):
                t_obs.append(float(stamps[j]))
                lat.append(t - float(stamps[j]))
            else:
                t_obs.append(float('nan'))
                lat.append(float('nan'))
    t_obs = np.array(t_obs)
    obs = np.array(obs)
    lat = np.array(lat)

    clock = 'rawTimestampsSec'
    good = np.isfinite(lat)
    if not good.any() or not (0.0 <= float(np.median(lat[good])) <= 1.0):
        # capture timestamps aren't on the log's clock: fall back to the record time minus a typical latency
        notes.append('rawTimestampsSec is not on the log clock; using the log record time minus 30 ms.')
        clock = 'record time - 30 ms'
        t_obs = np.array([t for t, poses in poses_sig for _ in poses
                          if not (window and not (window[0] <= t <= window[1]))])
        if tag_ids is not None:
            notes.append('Tag filtering could not be re-aligned after the clock fallback; using all samples.')
        t_obs = t_obs[:len(obs)] - 0.03
    if len(t_obs) != len(obs):
        raise ValueError('Internal mismatch between timestamps and poses.')

    # --- odometry --------------------------------------------------------------------------
    pad = 1.0
    t_odo, odo = [], []
    for t, v in odo_sig:
        if not v:
            continue
        if window and not (window[0] - pad <= t <= window[1] + pad):
            continue
        p = v[-1]
        t_odo.append(t)
        odo.append((p['x'], p['y'], p['rot']))
    t_odo = np.array(t_odo)
    odo = np.array(odo)
    if len(t_odo) < 10:
        raise ValueError('Too few Drivetrain/Pose samples inside the calibration window.')
    order = np.argsort(t_obs)
    spans = phase_spans(signals, window)
    info = {
        'results_in_window': n_results, 'results_dropped_by_tag_filter': n_tagfilter,
        'samples': int(len(obs)), 'clock': clock, 'window': window,
        'median_latency_ms': float(np.median(lat[good]) * 1000) if good.any() else float('nan'),
    }
    return {'t_obs': t_obs[order], 'obs_T': obs[order], 't_odo': t_odo, 'odo': odo, 'info': info,
            'notes': notes, 'spans': spans}
