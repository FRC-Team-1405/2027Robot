"""SE(3) math for camera transform calibration."""
import datetime
import math
import statistics

import numpy as np
from scipy.spatial.transform import Rotation


# ─── SE(3) primitives ─────────────────────────────────────────────────────────

def pose3d_to_matrix(p: dict) -> np.ndarray:
    """Convert Pose3d dict {x,y,z,qw,qx,qy,qz} to 4×4 SE(3) matrix."""
    r = Rotation.from_quat([p['qx'], p['qy'], p['qz'], p['qw']])  # scipy: XYZW
    T = np.eye(4)
    T[:3, :3] = r.as_matrix()
    T[:3, 3] = [p['x'], p['y'], p['z']]
    return T


def params_to_matrix(x_m: float, y_m: float, z_m: float,
                     roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
    """Build 4×4 SE(3) from translation (meters) + roll-pitch-yaw (degrees, XYZ extrinsic)."""
    r = Rotation.from_euler('xyz', [roll_deg, pitch_deg, yaw_deg], degrees=True)
    T = np.eye(4)
    T[:3, :3] = r.as_matrix()
    T[:3, 3] = [x_m, y_m, z_m]
    return T


def matrix_to_params(T: np.ndarray) -> dict:
    """Extract x_m/y_m/z_m/roll_deg/pitch_deg/yaw_deg + inch equivalents."""
    r = Rotation.from_matrix(T[:3, :3])
    rpy = r.as_euler('xyz', degrees=True)
    x_m, y_m, z_m = float(T[0, 3]), float(T[1, 3]), float(T[2, 3])
    return {
        'x_m': x_m,        'y_m': y_m,        'z_m': z_m,
        'roll_deg':  float(rpy[0]),
        'pitch_deg': float(rpy[1]),
        'yaw_deg':   float(rpy[2]),
        'x_in': x_m / 0.0254,
        'y_in': y_m / 0.0254,
        'z_in': z_m / 0.0254,
    }


def average_se3(matrices: list[np.ndarray]) -> np.ndarray:
    """Average SE(3) matrices: translation mean + quaternion mean."""
    translations = np.array([m[:3, 3] for m in matrices])
    rots = Rotation.from_matrix([m[:3, :3] for m in matrices])
    T = np.eye(4)
    T[:3, :3] = rots.mean().as_matrix()
    T[:3, 3] = translations.mean(axis=0)
    return T


def residual(estimate: np.ndarray, mean: np.ndarray) -> tuple[float, float]:
    """(translation_mm, rotation_deg) of estimate vs. mean."""
    diff = np.linalg.inv(mean) @ estimate
    t_mm = float(np.linalg.norm(diff[:3, 3]) * 1000.0)
    r_deg = math.degrees(Rotation.from_matrix(diff[:3, :3]).magnitude())
    return t_mm, r_deg


# ─── Calibration core ─────────────────────────────────────────────────────────

def recover_camera_pose(robot_pose_est: np.ndarray, T_rc: np.ndarray) -> np.ndarray:
    """Recover camera world pose from logged robot estimate.

    PhotonVision computes camera_pose_world from raw pixel data, then:
        robot_pose_est = camera_pose_world @ inv(T_rc)

    Inverting:
        camera_pose_world = robot_pose_est @ T_rc

    The T_rc factors cancel exactly when recovering, so this reconstruction
    is exact regardless of how wrong the current T_rc is.
    """
    return robot_pose_est @ T_rc


def estimate_one_T_rc(camera_pose_world: np.ndarray, robot_pose_true: np.ndarray) -> np.ndarray:
    """Estimate T_rc from one (camera_pose_world, true_robot_pose) pair.

    Derivation:
        camera_pose_world = robot_pose_true @ T_rc_true
        T_rc_true = inv(robot_pose_true) @ camera_pose_world
    """
    return np.linalg.inv(robot_pose_true) @ camera_pose_world


def run_calibration(
    windows_data: list[dict],
    T_rc_current: np.ndarray,
    camera_name: str = '',
) -> dict:
    """Run the full calibration solver.

    Parameters
    ----------
    windows_data : list of dicts, each:
        {
            'label':           str,
            'poses':           list of Pose3d dicts from rawEstimatedPoses,
            'robot_pose_true': 4×4 np.ndarray in field frame,
        }
    T_rc_current : 4×4 np.ndarray  (currently configured robot-to-camera)
    camera_name  : str  (for the Java snippet header)

    Returns
    -------
    dict with:
        T_rc_calibrated   : 4×4 np.ndarray
        params            : {x_m, y_m, z_m, roll_deg, pitch_deg, yaw_deg, x_in, y_in, z_in}
        window_residuals  : list of {label, trans_mm, rot_deg, n_frames}
        stddev_trans_mm   : float
        stddev_rot_deg    : float
        java_snippet      : str
        n_total_frames    : int
    """
    # Per-window averaged T_rc estimates
    window_avgs: list[dict] = []

    for wd in windows_data:
        poses = wd['poses']
        T_robot_true = wd['robot_pose_true']
        estimates: list[np.ndarray] = []

        for p in poses:
            T_robot_est = pose3d_to_matrix(p)
            T_cam_world = recover_camera_pose(T_robot_est, T_rc_current)
            estimates.append(estimate_one_T_rc(T_cam_world, T_robot_true))

        if estimates:
            window_avgs.append({
                'label':    wd['label'],
                'T_rc':     average_se3(estimates),
                'n_frames': len(estimates),
            })

    if not window_avgs:
        raise ValueError('No valid frames found in any window.')

    T_rc_cal = average_se3([w['T_rc'] for w in window_avgs])

    window_residuals: list[dict] = []
    trans_list: list[float] = []
    rot_list:   list[float] = []
    for w in window_avgs:
        t_mm, r_deg = residual(w['T_rc'], T_rc_cal)
        window_residuals.append({
            'label': w['label'], 'trans_mm': t_mm, 'rot_deg': r_deg, 'n_frames': w['n_frames'],
        })
        trans_list.append(t_mm)
        rot_list.append(r_deg)

    std_t = statistics.stdev(trans_list) if len(trans_list) > 1 else 0.0
    std_r = statistics.stdev(rot_list)   if len(rot_list)   > 1 else 0.0

    params = matrix_to_params(T_rc_cal)
    n_total = sum(w['n_frames'] for w in window_avgs)

    return {
        'T_rc_calibrated':  T_rc_cal,
        'params':           params,
        'window_residuals': window_residuals,
        'stddev_trans_mm':  std_t,
        'stddev_rot_deg':   std_r,
        'java_snippet':     _java_snippet(params, camera_name),
        'n_total_frames':   n_total,
    }


def _java_snippet(params: dict, camera_name: str) -> str:
    d = datetime.date.today().isoformat()
    xi, yi, zi = params['x_in'], params['y_in'], params['z_in']
    roll  = params['roll_deg']
    pitch = params['pitch_deg']
    yaw   = params['yaw_deg']
    return (
        f'// {camera_name} — calibrated {d}\n'
        f'new Transform3d(\n'
        f'    new Translation3d(\n'
        f'        Units.inchesToMeters({xi:.3f}),\n'
        f'        Units.inchesToMeters({yi:.3f}),\n'
        f'        Units.inchesToMeters({zi:.3f})),\n'
        f'    new Rotation3d(\n'
        f'        Math.toRadians({roll:.3f}),\n'
        f'        Math.toRadians({pitch:.3f}),\n'
        f'        Math.toRadians({yaw:.3f})))'
    )
