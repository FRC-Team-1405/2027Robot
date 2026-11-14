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
    info = {
        'results_in_window': n_results, 'results_dropped_by_tag_filter': n_tagfilter,
        'samples': int(len(obs)), 'clock': clock, 'window': window,
        'median_latency_ms': float(np.median(lat[good]) * 1000) if good.any() else float('nan'),
    }
    return {'t_obs': t_obs[order], 'obs_T': obs[order], 't_odo': t_odo, 'odo': odo, 'info': info, 'notes': notes}
