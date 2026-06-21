"""Load AprilTag field poses from WPILib field_calibration.json."""
import json
import pathlib

import numpy as np

_FIELD_JSON = pathlib.Path(__file__).parents[3] / 'src/main/deploy/field_calibration.json'


def load_tag_poses(path: str | pathlib.Path | None = None) -> dict[int, np.ndarray]:
    """Return dict: tag_id -> 4×4 SE(3) matrix (WPILib field frame)."""
    p = pathlib.Path(path) if path else _FIELD_JSON
    data = json.loads(p.read_text())
    result: dict[int, np.ndarray] = {}
    for entry in data['tags']:
        tid = entry['ID']
        t   = entry['pose']['translation']
        q   = entry['pose']['rotation']['quaternion']
        result[tid] = _matrix_from_quat(t['x'], t['y'], t['z'],
                                         q['W'], q['X'], q['Y'], q['Z'])
    return result


def robot_pose_to_field(
    tag_matrix: np.ndarray,
    x_calib_m: float,
    y_calib_m: float,
    tag_height_m: float,
    heading_wpilib_deg: float,
) -> np.ndarray:
    """Convert tag-relative robot measurement to field-frame SE(3) matrix.

    Calibration coordinate frame (tag-local):
      origin  = tag center
      +X axis = tag face direction (outward, toward robot approach area)
      +Y axis = tag's +Y (left when facing the tag from the robot side)
      +Z axis = up

    Parameters
    ----------
    tag_matrix:           field-frame SE(3) of the tag (from field_calibration.json)
    x_calib_m:            perpendicular distance from tag face to robot center
    y_calib_m:            lateral offset, positive = robot's left / tag's +Y
    tag_height_m:         tag center height from floor; robot floor = z=-tag_height in tag frame
    heading_wpilib_deg:   WPILib yaw (180° = facing tag = typical starting point)
    """
    T_robot_tag = _matrix_from_rpy(x_calib_m, y_calib_m, -tag_height_m,
                                    0.0, 0.0, heading_wpilib_deg)
    return tag_matrix @ T_robot_tag


def _matrix_from_quat(x: float, y: float, z: float,
                       qw: float, qx: float, qy: float, qz: float) -> np.ndarray:
    from scipy.spatial.transform import Rotation
    r = Rotation.from_quat([qx, qy, qz, qw])  # scipy uses XYZW
    T = np.eye(4)
    T[:3, :3] = r.as_matrix()
    T[:3, 3] = [x, y, z]
    return T


def _matrix_from_rpy(x: float, y: float, z: float,
                      roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
    from scipy.spatial.transform import Rotation
    r = Rotation.from_euler('xyz', [roll_deg, pitch_deg, yaw_deg], degrees=True)
    T = np.eye(4)
    T[:3, :3] = r.as_matrix()
    T[:3, 3] = [x, y, z]
    return T
