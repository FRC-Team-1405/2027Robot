"""Auto-calibration ("spin & drive"): solve a camera's mount from how the robot moved.

The manual method (solver.py) needs the robot's true pose at each stop, which means tape
measurements. This one needs none. While the robot spins and drives in front of an AprilTag
with vision corrections switched off, two things are logged:

  * the camera's pose in the field frame, from vision (the tag pose is known), and
  * the robot's pose from wheel + gyro odometry, which is only good *relatively*: it starts
    wherever it started, in its own frame.

Model. The robot's field pose at time t is  G o odo(t + tau)  where G is an unknown planar
rigid transform (the odometry frame -> the field frame) and tau is an unknown vision-vs-odometry
clock offset. The camera's field pose is that robot pose composed with the unknown mount
T_rc (the thing we want). We fit G, tau and T_rc together to every vision sample by robust
non-linear least squares.

What each motion tells us (this is why the robot does what it does):
  * z, roll, pitch of the camera: read straight off the tag view, because the robot is level
    on the floor (robot z = 0, roll = pitch = 0).
  * camera x, y: the camera swings around the robot's rotation centre when the robot spins.
  * camera yaw: needs an absolute heading reference. Spinning alone can't give one (it only
    fixes yaw relative to an unknown starting heading), but driving straight does: the camera
    moves along the robot's own x / y axes, and where that points in the field frame is the
    heading. That is what breaks the tie between G's rotation and the camera's yaw.

A rigid placement error of the tag(s) cancels: it shifts/rotates every camera pose the same
way and is absorbed by G. What does NOT cancel: tag height, tag tilt, and the spacing between
the tags of a pair.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

from .solver import matrix_to_params, params_to_matrix, _java_snippet

# Vision noise scales used to weight the residuals (they only set relative weights between
# translation and rotation; the robust loss handles outliers).
SIGMA_T_M = 0.02
SIGMA_R_RAD = math.radians(1.5)

PARAM_NAMES = ['theta0', 'tx', 'ty', 'x', 'y', 'z', 'roll', 'pitch', 'yaw']


# --------------------------------------------------------------------------- helpers

def planar_matrix(x: float, y: float, yaw: float) -> np.ndarray:
    """4x4 pose of a robot on the floor (z = 0, level)."""
    c, s = math.cos(yaw), math.sin(yaw)
    T = np.eye(4)
    T[0, 0], T[0, 1], T[1, 0], T[1, 1] = c, -s, s, c
    T[0, 3], T[1, 3] = x, y
    return T


def unwrap_yaw(yaw: np.ndarray) -> np.ndarray:
    return np.unwrap(np.asarray(yaw, dtype=float))


def _interp_odo(t_odo: np.ndarray, odo: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Linear interpolation of an (N, 3) odometry series (x, y, unwrapped yaw) at times t."""
    return np.column_stack([np.interp(t, t_odo, odo[:, i]) for i in range(3)])


def _mount_matrix(p: np.ndarray) -> np.ndarray:
    return params_to_matrix(p[3], p[4], p[5], *np.degrees(p[6:9]))


def _predict_cam(p: np.ndarray, odo_at_t: np.ndarray) -> np.ndarray:
    """(N, 4, 4) predicted camera field poses for parameter vector p (vectorised)."""
    th0, tx, ty = p[0], p[1], p[2]
    c, s = math.cos(th0), math.sin(th0)
    n = len(odo_at_t)
    ox, oy, oth = odo_at_t[:, 0], odo_at_t[:, 1], odo_at_t[:, 2]
    yaw = th0 + oth
    R = np.zeros((n, 4, 4))
    R[:, 0, 0], R[:, 0, 1] = np.cos(yaw), -np.sin(yaw)
    R[:, 1, 0], R[:, 1, 1] = np.sin(yaw), np.cos(yaw)
    R[:, 2, 2] = 1.0
    R[:, 3, 3] = 1.0
    R[:, 0, 3] = c * ox - s * oy + tx
    R[:, 1, 3] = s * ox + c * oy + ty
    return R @ _mount_matrix(p)


def _residuals(p, t_obs, obs_T, t_odo, odo, fit_tau, tau_fixed):
    tau = p[9] if fit_tau else tau_fixed
    pred = _predict_cam(p, _interp_odo(t_odo, odo, t_obs + tau))
    d_t = (obs_T[:, :3, 3] - pred[:, :3, 3]) / SIGMA_T_M
    # rotation error as a rotation vector in the predicted camera's frame
    rel = np.swapaxes(pred[:, :3, :3], 1, 2) @ obs_T[:, :3, :3]
    d_r = Rotation.from_matrix(rel).as_rotvec() / SIGMA_R_RAD
    return np.concatenate([d_t.ravel(), d_r.ravel()])


def _seed_G(obs_T, t_obs, t_odo, odo, T_rc0):
    """Seed G from observations: robot_field_obs = obs @ inv(T_rc0); G = robot_field o inv(odo)."""
    inv_mount = np.linalg.inv(T_rc0)
    odo_at = _interp_odo(t_odo, odo, t_obs)
    ths, txy = [], []
    for T, (ox, oy, oth) in zip(obs_T, odo_at):
        R = T @ inv_mount
        yaw = math.atan2(R[1, 0], R[0, 0])
        th0 = yaw - oth
        c, s = math.cos(th0), math.sin(th0)
        ths.append(th0)
        txy.append((R[0, 3] - (c * ox - s * oy), R[1, 3] - (s * ox + c * oy)))
    th0 = math.atan2(np.mean(np.sin(ths)), np.mean(np.cos(ths)))
    # re-derive translation with the averaged angle so the pair stays consistent
    c, s = math.cos(th0), math.sin(th0)
    tx = np.mean([(T @ inv_mount)[0, 3] - (c * ox - s * oy) for T, (ox, oy, _) in zip(obs_T, odo_at)])
    ty = np.mean([(T @ inv_mount)[1, 3] - (s * ox + c * oy) for T, (ox, oy, _) in zip(obs_T, odo_at)])
    return th0, float(tx), float(ty)


# --------------------------------------------------------------------------- the solver

@dataclass
class AutoResult:
    T_rc: np.ndarray
    params: dict                 # x_m..yaw_deg, x_in.. (as solver.matrix_to_params)
    sigma: dict                  # 1-sigma: x_mm, y_mm, z_mm, roll_deg, pitch_deg, yaw_deg
    tau_s: float                 # fitted vision-minus-odometry clock offset
    rms_t_mm: float              # RMS camera-position residual
    rms_r_deg: float             # RMS camera-rotation residual
    n_samples: int
    n_inliers: int
    split_half: dict             # the same solve on two interleaved halves: how repeatable?
    warnings: list = field(default_factory=list)
    java_snippet: str = ''
    G: tuple = (0.0, 0.0, 0.0)   # odometry frame -> field frame (theta0, tx, ty)


def solve(
    t_obs: np.ndarray,
    obs_T: np.ndarray,
    t_odo: np.ndarray,
    odo: np.ndarray,
    T_rc0: np.ndarray,
    camera_name: str = '',
    fit_time_offset: bool = True,
    _skip_split: bool = False,
) -> AutoResult:
    """Fit the camera mount (and the odometry frame and clock offset) from one logged run.

    t_obs   (N,)      capture time of each vision sample (s, same clock as t_odo)
    obs_T   (N,4,4)   camera pose in the FIELD frame for each sample (recover with
                      solver.recover_camera_pose(robot_pose_est, T_rc_current))
    t_odo   (M,)      odometry timestamps (s), increasing
    odo     (M,3)     odometry x, y, yaw (m, m, rad). Wheel + gyro ONLY: vision corrections
                      must have been off, or this is circular.
    T_rc0   (4,4)     the mount currently configured (the starting guess)
    """
    t_obs = np.asarray(t_obs, float)
    obs_T = np.asarray(obs_T, float)
    t_odo = np.asarray(t_odo, float)
    odo = np.column_stack([odo[:, 0], odo[:, 1], unwrap_yaw(odo[:, 2])])
    if len(t_obs) < 30:
        raise ValueError(f'Only {len(t_obs)} vision samples: too few to solve (need at least ~30, '
                         'ideally hundreds). Is the tag in view of this camera during the run?')

    inside = (t_obs >= t_odo[0]) & (t_obs <= t_odo[-1])
    t_obs, obs_T = t_obs[inside], obs_T[inside]

    th0, tx, ty = _seed_G(obs_T, t_obs, t_odo, odo, T_rc0)
    m = matrix_to_params(T_rc0)
    p0 = [th0, tx, ty, m['x_m'], m['y_m'], m['z_m'],
          math.radians(m['roll_deg']), math.radians(m['pitch_deg']), math.radians(m['yaw_deg'])]
    lo = [-np.inf] * 9
    hi = [np.inf] * 9
    if fit_time_offset:
        p0.append(0.0)
        lo.append(-0.15)
        hi.append(0.15)
    p0 = np.array(p0)

    def run(idx):
        fun = lambda p: _residuals(p, t_obs[idx], obs_T[idx], t_odo, odo, fit_time_offset, 0.0)  # noqa: E731
        return least_squares(fun, p0, bounds=(lo, hi), loss='soft_l1', f_scale=2.0, x_scale='jac')

    all_idx = np.arange(len(t_obs))
    sol = run(all_idx)
    p = sol.x
    T_rc = _mount_matrix(p)

    # fit quality on the full set
    tau = p[9] if fit_time_offset else 0.0
    res = _residuals(p, t_obs, obs_T, t_odo, odo, fit_time_offset, 0.0)
    n = len(t_obs)
    r_t = res[:3 * n].reshape(n, 3) * SIGMA_T_M
    r_r = res[3 * n:].reshape(n, 3) * SIGMA_R_RAD
    err_t = np.linalg.norm(r_t, axis=1)
    keep = err_t < max(3 * np.median(err_t), 0.02)
    rms_t = float(np.sqrt(np.mean(err_t[keep] ** 2))) * 1000.0
    rms_r = float(np.degrees(np.sqrt(np.mean(np.sum(r_r[keep] ** 2, axis=1)))))

    # parameter uncertainty from the Jacobian (optimistic: samples are correlated), scaled by the fit
    J = sol.jac
    n_keep = int(keep.sum())
    dof = max(1, 6 * n_keep - J.shape[1])
    rn_t, rn_r = res[:3 * n].reshape(n, 3), res[3 * n:].reshape(n, 3)
    s2 = float(np.sum(rn_t[keep] ** 2) + np.sum(rn_r[keep] ** 2)) / dof if n_keep else 1.0
    try:
        cov = np.linalg.inv(J.T @ J) * max(s2, 1.0)
        sd = np.sqrt(np.clip(np.diag(cov), 0, None))
    except np.linalg.LinAlgError:
        sd = np.full(J.shape[1], np.inf)
    sigma = {
        'x_mm': float(sd[3] * 1000), 'y_mm': float(sd[4] * 1000), 'z_mm': float(sd[5] * 1000),
        'roll_deg': math.degrees(sd[6]), 'pitch_deg': math.degrees(sd[7]), 'yaw_deg': math.degrees(sd[8]),
    }

    params = matrix_to_params(T_rc)
    out = AutoResult(
        T_rc=T_rc, params=params, sigma=sigma, tau_s=float(tau), rms_t_mm=rms_t, rms_r_deg=rms_r,
        n_samples=n, n_inliers=int(keep.sum()), split_half={}, G=(float(p[0]), float(p[1]), float(p[2])),
        java_snippet=_java_snippet(params, camera_name),
    )

    # repeatability: solve two interleaved halves (1-second blocks alternate) and compare
    if not _skip_split:
        block = np.floor((t_obs - t_obs[0]) / 1.0).astype(int)
        halves = [all_idx[block % 2 == 0], all_idx[block % 2 == 1]]
        if min(len(h) for h in halves) >= 30:
            try:
                sols = [run(h).x for h in halves]
                Ts = [_mount_matrix(s) for s in sols]
                dT = np.linalg.inv(Ts[0]) @ Ts[1]
                dxyz = (Ts[1][:3, 3] - Ts[0][:3, 3]) * 1000.0
                out.split_half = {
                    'dx_mm': float(dxyz[0]), 'dy_mm': float(dxyz[1]), 'dz_mm': float(dxyz[2]),
                    'rot_deg': float(np.degrees(Rotation.from_matrix(dT[:3, :3]).magnitude())),
                }
            except Exception:  # noqa: BLE001 - diagnostics only
                out.split_half = {}

    out.warnings = _warnings(out, sol, odo, t_obs, obs_T, fit_time_offset)
    return out


def _warnings(r: AutoResult, sol, odo, t_obs, obs_T, fit_tau) -> list:
    w = []
    if r.n_inliers < 0.7 * r.n_samples:
        w.append(f'{r.n_samples - r.n_inliers} of {r.n_samples} samples were outliers: check that only '
                 'the tags you intend are visible, and that the log has Drivetrain/Pose with vision '
                 'corrections OFF.')
    # coverage: how much did the robot rotate and translate while the camera saw the tag?
    seen = (t_obs[0], t_obs[-1])
    yaw_span = float(np.degrees(np.ptp(odo[:, 2])))
    path = float(np.sum(np.hypot(np.diff(odo[:, 0]), np.diff(odo[:, 1]))))
    if yaw_span < 20:
        w.append(f'The robot only turned {yaw_span:.0f} degrees: x/y of the camera are poorly '
                 'constrained. Run the full sweep.')
    if path < 0.5:
        w.append(f'The robot only drove {path:.2f} m: the camera yaw is poorly constrained '
                 '(no drive to fix the heading). Run the full routine.')
    for k, lim, unit in (('x_mm', 8, 'mm'), ('y_mm', 8, 'mm'), ('z_mm', 15, 'mm'),
                         ('yaw_deg', 0.6, 'deg'), ('pitch_deg', 0.6, 'deg'), ('roll_deg', 0.6, 'deg')):
        if r.sigma[k] > lim:
            w.append(f'{k} uncertainty is {r.sigma[k]:.2f} {unit} (limit {lim}): '
                     'more data or a better tag view would help.')
    sh = r.split_half
    if sh and (abs(sh['dx_mm']) > 15 or abs(sh['dy_mm']) > 15 or sh['rot_deg'] > 1.0):
        w.append('The two halves of the run disagree by '
                 f'{abs(sh["dx_mm"]):.0f}/{abs(sh["dy_mm"]):.0f} mm and {sh["rot_deg"]:.2f} deg: '
                 'the result is not repeatable. Re-run, or check for odometry slip.')
    if fit_tau and abs(r.tau_s) > 0.1:
        w.append(f'Fitted clock offset is {r.tau_s * 1000:.0f} ms (at the limit): timestamps may be wrong.')
    return w


def with_tag_height_correction(res: AutoResult, layout_z_m: float, measured_z_m: float,
                               camera_name: str = '') -> AutoResult:
    """Correct the camera height for tags mounted at a different height than the field layout says.

    PhotonVision places the camera using the layout's tag height, so if the real tag is lower by dz
    (layout - measured), every camera height comes out dz too high.  The mount's z is the only thing
    this changes. (A rigid sideways/rotation placement error needs no correction: the solver absorbs it.)
    """
    from dataclasses import replace
    dz = layout_z_m - measured_z_m
    T = res.T_rc.copy()
    T[2, 3] -= dz
    params = matrix_to_params(T)
    return replace(res, T_rc=T, params=params, java_snippet=_java_snippet(params, camera_name))


# --------------------------------------------------------------------------- verify

def cross_camera_agreement(
    t_a: np.ndarray, cam_a: np.ndarray, T_rc_a: np.ndarray,
    t_b: np.ndarray, cam_b: np.ndarray, T_rc_b: np.ndarray,
    max_dt: float = 0.02,
) -> dict:
    """How well do two cameras agree about where the robot is, given their mounts?

    cam_a / cam_b are camera field poses ((N,4,4)); each is turned into a robot pose with its
    mount and compared to the nearest-in-time sample from the other camera.
    Returns median / p95 position difference (mm) and heading difference (deg), and the count.
    """
    t_a, t_b = np.asarray(t_a, float), np.asarray(t_b, float)
    if len(t_a) == 0 or len(t_b) == 0:
        return {'n': 0}
    inv_a, inv_b = np.linalg.inv(T_rc_a), np.linalg.inv(T_rc_b)
    j = np.clip(np.searchsorted(t_b, t_a), 1, len(t_b) - 1)
    j = np.where(np.abs(t_b[j - 1] - t_a) < np.abs(t_b[j] - t_a), j - 1, j)
    ok = np.abs(t_b[j] - t_a) <= max_dt
    dpos, dyaw = [], []
    for i in np.flatnonzero(ok):
        ra = cam_a[i] @ inv_a
        rb = cam_b[j[i]] @ inv_b
        dpos.append(np.hypot(*(ra[:2, 3] - rb[:2, 3])) * 1000.0)
        dyaw.append(abs(math.degrees(math.atan2(math.sin(math.atan2(ra[1, 0], ra[0, 0]) - math.atan2(rb[1, 0], rb[0, 0])),
                                                  math.cos(math.atan2(ra[1, 0], ra[0, 0]) - math.atan2(rb[1, 0], rb[0, 0]))))))
    if not dpos:
        return {'n': 0}
    return {
        'n': len(dpos),
        'pos_median_mm': float(np.median(dpos)), 'pos_p95_mm': float(np.percentile(dpos, 95)),
        'yaw_median_deg': float(np.median(dyaw)), 'yaw_p95_deg': float(np.percentile(dyaw, 95)),
    }
