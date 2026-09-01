#!/usr/bin/env python3
"""
Vision A/B Metrics Comparison Script v2

Reads two wpilog files (control = baseline robot log, treatment = replay with FS ON)
and prints a side-by-side statistics table.  Zero external dependencies.

Key differences from v1:
- Correctly handles AKit prefix hierarchy:
    Real robot logs:  RealOutputs/ (vision filter outputs)
    Replay logs:      ReplayOutputs/ (replay filter outputs, preferred over RealOutputs/)
  v1 stripped RealOutputs/ but not ReplayOutputs/, so treatment metrics were silently
  read from the re-embedded original data instead of the replay outputs.
- Rejection counters are summed across all loop cycles (they are per-loop 0/1 events,
  not cumulative totals; reading only the last value always gives 0).
- Total accepted pose count is derived from array sizes, not entry count.
- ASCII-only output (Windows cp1252 compatibility).
- Adds a DATA COVERAGE section so you know which metrics are actually present.

Usage:
    python3 compare_v2.py --control baseline.wpilog --treatment replay_fson.wpilog
    python3 compare_v2.py --control baseline.wpilog --treatment replay_fson.wpilog \\
                          --switch "BOUNDARY+AMBIGUITY+SMOOTH_THETA+DISTANCE_STDDEV"
    python3 compare_v2.py --control baseline.wpilog --treatment replay_fson.wpilog \\
                          --output results/all_switches.csv

IMPORTANT -- metrics that require Logger.recordOutput() to be replayable:
  CorrectionMagnitude, XYStddev, ThetaStddev are currently logged via
  SmartDashboard.putNumber() in RobotContainer.correctOdometry(), which writes to NT
  but NOT into the AKit WPILog.  Until that is changed to Logger.recordOutput(),
  those metrics will always show N/A and the stddev feature switches cannot be
  evaluated from replay logs.
"""

import argparse
import csv
import math
import pathlib
import struct
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# WPILog parser
# ---------------------------------------------------------------------------

POSE2D_SIZE = 24
POSE3D_SIZE = 56


def parse_wpilog(path: str, prefer_replay: bool = False) -> Tuple[Dict, bool]:
    """
    Parse a WPILog file.  Returns (signals, is_replay).

    signals keys are stripped of the AKit prefix:
      - For real robot logs:  RealOutputs/ and RealInputs/ are stripped.
      - For replay logs:      ReplayOutputs/ and ReplayInputs/ entries are preferred
        and override RealOutputs/ entries so the replay filter results win.

    Vision inputs (from Logger.processInputs) come from RealInputs/ in both log
    types (the raw camera data is always the ground truth from the original run).
    """
    raw = pathlib.Path(path).read_bytes()
    pos = 0
    if len(raw) < 12 or raw[0:6] != b'WPILOG':
        raise ValueError(f"Not a WPILog file: {path}")
    extra_len = struct.unpack_from('<I', raw, 8)[0]
    pos = 12 + extra_len

    entry_meta: Dict[int, Tuple[str, str]] = {}  # id -> (name, type)
    raw_signals: Dict[str, List[Tuple[float, Any]]] = defaultdict(list)

    while pos < len(raw):
        bitfield = raw[pos]; pos += 1
        eid_sz = (bitfield & 0x3) + 1
        psz_sz = ((bitfield >> 2) & 0x3) + 1
        tsz    = ((bitfield >> 4) & 0xF) + 1
        if pos + eid_sz + psz_sz + tsz > len(raw):
            break
        entry_id     = int.from_bytes(raw[pos:pos + eid_sz], 'little'); pos += eid_sz
        payload_size = int.from_bytes(raw[pos:pos + psz_sz], 'little'); pos += psz_sz
        ts_us        = int.from_bytes(raw[pos:pos + tsz],    'little'); pos += tsz
        ts_sec       = ts_us / 1_000_000.0
        if pos + payload_size > len(raw):
            break
        payload = raw[pos:pos + payload_size]; pos += payload_size

        if entry_id == 0:
            _handle_control(payload, entry_meta)
        else:
            meta = entry_meta.get(entry_id)
            if meta is None:
                continue
            value = _decode(payload, meta[1])
            if value is not None:
                raw_signals[meta[0]].append((ts_sec, value))

    is_replay = any(k.startswith('ReplayOutputs/') for k in raw_signals)

    REAL_OUT   = 'RealOutputs/'
    REAL_IN    = 'RealInputs/'
    REPLAY_OUT = 'ReplayOutputs/'
    REPLAY_IN  = 'ReplayInputs/'
    ALL_PREFIXES = (REAL_OUT, REAL_IN, REPLAY_OUT, REPLAY_IN)

    # For replay logs we prefer ReplayOutputs over RealOutputs (which contains
    # the original run's outputs, re-embedded as context for the replayer).
    avoid_prefix = REAL_OUT if (prefer_replay and is_replay) else None

    signals: Dict[str, List[Tuple[float, Any]]] = {}
    preferred: set = set()  # keys already claimed by the preferred prefix

    # First pass: claim keys from preferred prefix
    if prefer_replay and is_replay:
        for raw_key, entries in raw_signals.items():
            if raw_key.startswith(REPLAY_OUT) or raw_key.startswith(REPLAY_IN):
                stripped = _strip_prefix(raw_key, ALL_PREFIXES)
                signals[stripped] = entries
                preferred.add(stripped)

    # Second pass: fill remaining keys (skip avoided prefix and already-claimed keys)
    for raw_key, entries in raw_signals.items():
        if avoid_prefix and raw_key.startswith(avoid_prefix):
            continue
        if raw_key.startswith(REPLAY_OUT) or raw_key.startswith(REPLAY_IN):
            continue  # already handled above
        stripped = _strip_prefix(raw_key, ALL_PREFIXES)
        if stripped not in signals:
            signals[stripped] = entries

    return signals, is_replay


def _strip_prefix(key: str, prefixes: tuple) -> str:
    k = key.lstrip('/')
    for pfx in prefixes:
        if k.startswith(pfx):
            return k[len(pfx):]
    return k


def _handle_control(payload: bytes, entry_meta: Dict) -> None:
    if not payload or payload[0] != 0:
        return
    pos = 1
    if pos + 4 > len(payload):
        return
    new_id = struct.unpack_from('<I', payload, pos)[0]; pos += 4
    name, pos     = _lp_str(payload, pos)
    type_str, pos = _lp_str(payload, pos)
    entry_meta[new_id] = (name.lstrip('/'), type_str)


def _lp_str(data: bytes, pos: int) -> Tuple[str, int]:
    if pos + 4 > len(data):
        return '', pos
    length = struct.unpack_from('<I', data, pos)[0]; pos += 4
    s = data[pos:pos + length].decode('utf-8', errors='replace')
    return s, pos + length


def _decode(payload: bytes, typ: str) -> Any:
    try:
        t = typ.lower()
        if t == 'boolean':
            return bool(payload[0]) if payload else None
        if t in ('int64', 'integer', 'int'):
            return struct.unpack_from('<q', payload)[0] if len(payload) >= 8 else None
        if t == 'double':
            return struct.unpack_from('<d', payload)[0] if len(payload) >= 8 else None
        if t == 'float':
            return struct.unpack_from('<f', payload)[0] if len(payload) >= 4 else None
        if t in ('string', 'json'):
            return payload.decode('utf-8', errors='replace')
        if t == 'double[]':
            count = len(payload) // 8
            return list(struct.unpack_from(f'<{count}d', payload)) if count else []
        if t in ('int64[]', 'integer[]', 'int[]'):
            count = len(payload) // 8
            return list(struct.unpack_from(f'<{count}q', payload)) if count else []
        if t == 'float[]':
            count = len(payload) // 4
            return list(struct.unpack_from(f'<{count}f', payload)) if count else []
        if t == 'boolean[]':
            return [bool(b) for b in payload]
        if 'pose2d' in t:
            n = len(payload) // POSE2D_SIZE
            poses = []
            for i in range(n):
                x, y, r = struct.unpack_from('<3d', payload, i * POSE2D_SIZE)
                poses.append({'x': x, 'y': y, 'rot': r})
            return poses
        if 'pose3d' in t:
            n = len(payload) // POSE3D_SIZE
            poses = []
            for i in range(n):
                vals = struct.unpack_from('<7d', payload, i * POSE3D_SIZE)
                poses.append({'x': vals[0], 'y': vals[1], 'z': vals[2],
                              'qw': vals[3], 'qx': vals[4], 'qy': vals[5], 'qz': vals[6]})
            return poses
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------

def stdev(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    n = len(values)
    mean_v = sum(values) / n
    return math.sqrt(sum((v - mean_v) ** 2 for v in values) / (n - 1))


def mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def delta_pct(control: float, treatment: float) -> str:
    if control == 0:
        return "--"
    d = (treatment - control) / abs(control) * 100
    sign = "+" if d > 0 else ""
    return f"{sign}{d:.1f}%"


def verdict(control: float, treatment: float, lower_is_better: bool = True) -> str:
    if control == 0 or treatment == 0:
        return "--"
    ratio = treatment / control
    if lower_is_better:
        if ratio < 0.9:   return "improved"
        elif ratio > 1.1: return "REGRESSED"
        else:             return "neutral"
    else:
        if ratio > 1.1:   return "improved"
        elif ratio < 0.9: return "REGRESSED"
        else:             return "neutral"


# ---------------------------------------------------------------------------
# Metric extraction
# ---------------------------------------------------------------------------

def discover_cameras(signals: Dict) -> List[str]:
    cameras = []
    for key in signals:
        parts = key.split('/')
        if len(parts) >= 3 and parts[0] == 'Vision' and 'connected' in parts[2].lower():
            cam = parts[1]
            if cam not in cameras:
                cameras.append(cam)
    return sorted(cameras)


def get_scalar_values(signals: Dict, key: str) -> List[float]:
    return [v for _, v in signals.get(key, []) if isinstance(v, (int, float))]


def sum_int_events(signals: Dict, key: str) -> int:
    """
    Sum all per-loop integer values for a key.

    Rejection counters (RejectedBoundary, RejectedVelocity, RejectedAmbiguity) are
    logged as per-loop values: 0 most loops, 1 (or more) when a rejection occurs.
    They are NOT monotonically increasing.  Summing gives the true total event count.
    """
    total = 0
    for _, v in signals.get(key, []):
        if isinstance(v, int):
            total += v
        elif isinstance(v, float):
            total += int(v)
    return total


def total_pose_count(signals: Dict, key: str) -> int:
    total = 0
    for _, poses in signals.get(key, []):
        if isinstance(poses, list):
            total += len(poses)
    return total


def extract_pose_xy(signals: Dict, key: str) -> Tuple[List[float], List[float], List[float]]:
    xs, ys, rots = [], [], []
    for _, poses in signals.get(key, []):
        if not isinstance(poses, list):
            continue
        for p in poses:
            if not isinstance(p, dict):
                continue
            xs.append(p.get('x', 0))
            ys.append(p.get('y', 0))
            if 'qw' in p:
                qw, qx, qy, qz = p['qw'], p['qx'], p['qy'], p['qz']
                yaw = math.atan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))
                rots.append(math.degrees(yaw))
            else:
                rots.append(math.degrees(p.get('rot', 0)))
    return xs, ys, rots


def events_per_minute(signals: Dict, key: str, threshold: float, duration_s: float) -> float:
    values = get_scalar_values(signals, key)
    if not values or duration_s < 1:
        return 0.0
    count = sum(1 for v in values if v > threshold)
    return count / duration_s * 60


def has_data(signals: Dict, key: str) -> bool:
    return bool(signals.get(key))


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------

class RunMetrics:
    def __init__(self, path: str, is_replay: bool, signals: Dict,
                 cameras: List[str], stationary_speed: float):
        self.path = path
        self.name = pathlib.Path(path).name
        self.is_replay = is_replay
        self.signals = signals

        if not cameras:
            cameras = discover_cameras(signals)
        self.cameras = cameras

        all_ts = [t for entries in signals.values() for t, _ in entries]
        self.duration_s = (max(all_ts) - min(all_ts)) if len(all_ts) > 1 else 0

        self.cam_total_poses:      Dict[str, int]   = {}
        self.cam_sigma_x:          Dict[str, float] = {}
        self.cam_sigma_y:          Dict[str, float] = {}
        self.cam_sigma_th:         Dict[str, float] = {}
        self.cam_rej_boundary:     Dict[str, int]   = {}
        self.cam_rej_velocity:     Dict[str, int]   = {}
        self.cam_rej_ambiguity:    Dict[str, int]   = {}
        self.cam_acceptance_rate_pct: Dict[str, Optional[float]] = {}

        all_xs, all_ys, all_ths = [], [], []
        total_poses = 0

        for cam in cameras:
            xs, ys, ths = extract_pose_xy(signals, f'Vision/{cam}/AcceptedPoses')
            n = total_pose_count(signals, f'Vision/{cam}/AcceptedPoses')
            self.cam_total_poses[cam]   = n
            self.cam_sigma_x[cam]       = stdev(xs)
            self.cam_sigma_y[cam]       = stdev(ys)
            self.cam_sigma_th[cam]      = stdev(ths)
            self.cam_rej_boundary[cam]  = sum_int_events(signals, f'Vision/{cam}/RejectedBoundary')
            self.cam_rej_velocity[cam]  = sum_int_events(signals, f'Vision/{cam}/RejectedVelocity')
            self.cam_rej_ambiguity[cam] = sum_int_events(signals, f'Vision/{cam}/RejectedAmbiguity')
            pct_vals = get_scalar_values(signals, f'Vision/{cam}/AcceptanceRatePercent')
            self.cam_acceptance_rate_pct[cam] = mean(pct_vals) if pct_vals else None
            all_xs.extend(xs); all_ys.extend(ys); all_ths.extend(ths)
            total_poses += n

        self.total_poses  = total_poses
        self.sigma_x      = stdev(all_xs)
        self.sigma_y      = stdev(all_ys)
        self.sigma_th     = stdev(all_ths)
        self.acceptance_rate = total_poses / self.duration_s if self.duration_s > 0 else 0

        self.total_rej_boundary  = sum(self.cam_rej_boundary.values())
        self.total_rej_velocity  = sum(self.cam_rej_velocity.values())
        self.total_rej_ambiguity = sum(self.cam_rej_ambiguity.values())

        # Stddev values logged via Logger.recordOutput (only present if code was fixed)
        xy_vals = get_scalar_values(signals, 'Vision/XYStddev')
        th_vals = get_scalar_values(signals, 'Vision/ThetaStddev')
        cm_vals = get_scalar_values(signals, 'Vision/CorrectionMagnitude')
        self.mean_xy_stddev        = mean(xy_vals)   if xy_vals else None
        self.mean_th_stddev        = mean(th_vals)   if th_vals else None
        self.correction_epm_1m     = events_per_minute(signals, 'Vision/CorrectionMagnitude',
                                                        1.0, self.duration_s)
        self.correction_epm_05m    = events_per_minute(signals, 'Vision/CorrectionMagnitude',
                                                        0.5, self.duration_s)
        self.has_stddev_data       = bool(xy_vals)
        self.has_correction_data   = bool(cm_vals)


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

W = 78
SEP = '-' * W
DBL = '=' * W

def _fmt_val(v: Optional[float], decimals: int = 3, unit: str = '') -> str:
    if v is None:
        return 'N/A'
    return f"{v:.{decimals}f}{unit}"


def print_report(ctrl: RunMetrics, trt: RunMetrics, switch_name: Optional[str]) -> List[Dict]:
    title = f"Vision A/B Comparison: {switch_name}" if switch_name else "Vision A/B Comparison"
    print()
    print(title)
    print(DBL)

    src_ctrl = 'replay->ReplayOutputs' if ctrl.is_replay else 'robot->RealOutputs'
    src_trt  = 'replay->ReplayOutputs' if trt.is_replay  else 'robot->RealOutputs'

    ctrl_cam = ', '.join(f"{c}: {ctrl.cam_total_poses.get(c,0)}" for c in ctrl.cameras)
    trt_cam  = ', '.join(f"{c}: {trt.cam_total_poses.get(c,0)}"  for c in trt.cameras)
    print(f"Control:   {ctrl.name:<38} [{src_ctrl}]")
    print(f"           {ctrl.total_poses} total accepted poses  ({ctrl_cam})")
    print(f"Treatment: {trt.name:<38} [{src_trt}]")
    print(f"           {trt.total_poses} total accepted poses  ({trt_cam})")
    print(f"Duration:  control {ctrl.duration_s:.0f}s  treatment {trt.duration_s:.0f}s")
    print()

    C1, C2, C3, C4 = 40, 12, 12, 10
    hdr = f"{'Metric':<{C1}} {'Control':>{C2}} {'Treatment':>{C3}} {'Delta':>{C4}}  Verdict"
    print(hdr)
    print(SEP)

    rows = []

    def row(label, c_val, t_val, fmt_fn=None, lower_better=True, na=False):
        if fmt_fn is None:
            fmt_fn = lambda v: _fmt_val(v)
        c_s = 'N/A' if na or c_val is None else fmt_fn(c_val)
        t_s = 'N/A' if na or t_val is None else fmt_fn(t_val)
        if na or c_val is None or t_val is None:
            d_s, v_s = '--', '--'
        else:
            d_s = delta_pct(c_val, t_val)
            v_s = verdict(c_val, t_val, lower_better)
        print(f"{label:<{C1}} {c_s:>{C2}} {t_s:>{C3}} {d_s:>{C4}}  {v_s}")
        rows.append({'metric': label, 'control': c_val, 'treatment': t_val,
                     'delta_pct': d_s, 'verdict': v_s})

    # --- Pose spread (spatial consistency of accepted estimates) ---
    print(f"{'-- Pose spread (sigma of accepted positions) --'}")
    row("sigma-X all cameras",  ctrl.sigma_x,  trt.sigma_x,
        lambda v: f"{v:.4f} m")
    row("sigma-Y all cameras",  ctrl.sigma_y,  trt.sigma_y,
        lambda v: f"{v:.4f} m")
    row("sigma-theta all cams", ctrl.sigma_th, trt.sigma_th,
        lambda v: f"{v:.3f} deg")
    print(SEP)

    # --- Acceptance ---
    print(f"{'-- Acceptance rate --'}")
    row("Total poses accepted",
        float(ctrl.total_poses), float(trt.total_poses),
        lambda v: f"{int(v)}", lower_better=False)
    row("Poses per second",
        ctrl.acceptance_rate, trt.acceptance_rate,
        lambda v: f"{v:.2f}/s", lower_better=False)
    print(SEP)

    # --- Rejection events (summed per-loop values) ---
    print(f"{'-- Rejection events (sum across all loop cycles) --'}")
    row("Boundary rejections",  ctrl.total_rej_boundary,  trt.total_rej_boundary,
        lambda v: str(int(v)), lower_better=True)
    row("Velocity rejections",  ctrl.total_rej_velocity,  trt.total_rej_velocity,
        lambda v: str(int(v)), lower_better=True)
    row("Ambiguity rejections", ctrl.total_rej_ambiguity, trt.total_rej_ambiguity,
        lambda v: str(int(v)), lower_better=True)
    print(SEP)

    # --- Stddev / correction (requires Logger.recordOutput in RobotContainer) ---
    stddev_na = not (ctrl.has_stddev_data or trt.has_stddev_data)
    corr_na   = not (ctrl.has_correction_data or trt.has_correction_data)
    print(f"{'-- Stddev & correction (require Logger.recordOutput fix) --'}")
    row("Mean XY stddev",       ctrl.mean_xy_stddev, trt.mean_xy_stddev,
        lambda v: f"{v:.4f}", na=stddev_na)
    row("Mean theta stddev",    ctrl.mean_th_stddev, trt.mean_th_stddev,
        lambda v: f"{v:.2f} rad", na=stddev_na)
    row("Corrections >1 m/min", ctrl.correction_epm_1m,  trt.correction_epm_1m,
        lambda v: f"{v:.2f}", na=corr_na)
    row("Corrections >0.5m/min",ctrl.correction_epm_05m, trt.correction_epm_05m,
        lambda v: f"{v:.2f}", na=corr_na)
    print(SEP)
    print()

    # --- Per-camera breakdown ---
    all_cams = sorted(set(ctrl.cameras) | set(trt.cameras))
    if all_cams:
        print("Per-camera breakdown:")
        print(SEP)
        for cam in all_cams:
            cp = ctrl.cam_total_poses.get(cam, 0)
            tp = trt.cam_total_poses.get(cam, 0)
            cx = ctrl.cam_sigma_x.get(cam, 0)
            tx = trt.cam_sigma_x.get(cam, 0)
            cy = ctrl.cam_sigma_y.get(cam, 0)
            ty = trt.cam_sigma_y.get(cam, 0)
            cth= ctrl.cam_sigma_th.get(cam, 0)
            tth= trt.cam_sigma_th.get(cam, 0)
            cbnd = ctrl.cam_rej_boundary.get(cam, 0)
            tbnd = trt.cam_rej_boundary.get(cam, 0)
            cvel = ctrl.cam_rej_velocity.get(cam, 0)
            tvel = trt.cam_rej_velocity.get(cam, 0)
            camb = ctrl.cam_rej_ambiguity.get(cam, 0)
            tamb = trt.cam_rej_ambiguity.get(cam, 0)
            cpct = ctrl.cam_acceptance_rate_pct.get(cam)
            tpct = trt.cam_acceptance_rate_pct.get(cam)
            pct_str = (f"  accept-rate: ctrl={_fmt_val(cpct,1,'%')} trt={_fmt_val(tpct,1,'%')}"
                       if (cpct is not None or tpct is not None) else "")
            print(f"  {cam}:")
            print(f"    poses ctrl={cp}  trt={tp}  delta={tp-cp}")
            print(f"    sigma-X {cx:.4f}->{tx:.4f}  sigma-Y {cy:.4f}->{ty:.4f}  sigma-th {cth:.2f}->{tth:.2f} deg")
            print(f"    boundary ctrl={cbnd}  trt={tbnd}   velocity ctrl={cvel}  trt={tvel}   ambiguity ctrl={camb}  trt={tamb}{pct_str}")
        print()

    # --- Data coverage note ---
    _print_coverage(ctrl, trt)

    return rows


def _print_coverage(ctrl: RunMetrics, trt: RunMetrics) -> None:
    print("Data coverage:")
    print(SEP)

    def yesno(cond): return "YES" if cond else "no "

    checks = [
        ("AcceptedPoses (filter acceptance)",
         has_data(ctrl.signals, 'Vision/Left/AcceptedPoses') or
         has_data(ctrl.signals, 'Vision/Right/AcceptedPoses'),
         has_data(trt.signals,  'Vision/Left/AcceptedPoses') or
         has_data(trt.signals,  'Vision/Right/AcceptedPoses')),
        ("RejectedBoundary (per-loop events summed)",
         has_data(ctrl.signals, 'Vision/Left/RejectedBoundary'),
         has_data(trt.signals,  'Vision/Left/RejectedBoundary')),
        ("RejectedVelocity (per-loop events summed)",
         has_data(ctrl.signals, 'Vision/Left/RejectedVelocity'),
         has_data(trt.signals,  'Vision/Left/RejectedVelocity')),
        ("RejectedAmbiguity (per-loop events summed)",
         has_data(ctrl.signals, 'Vision/Left/RejectedAmbiguity'),
         has_data(trt.signals,  'Vision/Left/RejectedAmbiguity')),
        ("AcceptanceRatePercent (new metric, may be absent in control)",
         has_data(ctrl.signals, 'Vision/Left/AcceptanceRatePercent'),
         has_data(trt.signals,  'Vision/Left/AcceptanceRatePercent')),
        ("XYStddev (needs Logger.recordOutput fix in RobotContainer)",
         ctrl.has_stddev_data, trt.has_stddev_data),
        ("ThetaStddev (needs Logger.recordOutput fix in RobotContainer)",
         has_data(ctrl.signals, 'Vision/ThetaStddev'),
         has_data(trt.signals,  'Vision/ThetaStddev')),
        ("CorrectionMagnitude (needs Logger.recordOutput fix in RobotContainer)",
         ctrl.has_correction_data, trt.has_correction_data),
    ]

    for label, in_ctrl, in_trt in checks:
        measurable = "measurable" if (in_ctrl and in_trt) else \
                     "ctrl-only"  if in_ctrl else \
                     "trt-only"   if in_trt  else "MISSING in both"
        print(f"  ctrl={yesno(in_ctrl)}  trt={yesno(in_trt)}  [{measurable:16s}]  {label}")

    print()
    if not (ctrl.has_stddev_data and trt.has_stddev_data):
        print("  ACTION NEEDED: VISION_SMOOTH_THETA_STDDEV and VISION_DISTANCE_BASED_STDDEV")
        print("  change the stddev values passed to addVisionMeasurement() in")
        print("  RobotContainer.correctOdometry().  Those values are currently published via")
        print("  SmartDashboard.putNumber() which does NOT write into the AKit WPILog.")
        print("  Change them to Logger.recordOutput() so replay diffs are captured.")
        print("  Example fix in RobotContainer.java:")
        print('    Logger.recordOutput("Vision/XYStddev", xyStddev);')
        print('    Logger.recordOutput("Vision/ThetaStddev", thetaStddev);')
        print('    Logger.recordOutput("Vision/CorrectionMagnitude", correctionMag);')
        print()
    print(SEP)


def write_csv(rows: List[Dict], path: str) -> None:
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['metric', 'control', 'treatment', 'delta_pct', 'verdict'])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Results written to: {path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description='Compare two wpilog files for vision A/B testing (v2).')
    parser.add_argument('--control',   required=True, help='Baseline wpilog (robot run, all switches OFF)')
    parser.add_argument('--treatment', required=True, help='Treatment wpilog (replay with switches ON)')
    parser.add_argument('--switch',    default=None,  help='Switch(es) under test (display only)')
    parser.add_argument('--cameras',   default='',    help='Comma-separated camera names (auto-detected)')
    parser.add_argument('--stationary-speed', type=float, default=0.05,
                        help='Max m/s for stationary filter (currently unused, reserved)')
    parser.add_argument('--output',    default=None,  help='Write CSV results to this path')
    args = parser.parse_args()

    cameras = [c.strip() for c in args.cameras.split(',') if c.strip()]

    try:
        ctrl_sig, ctrl_replay = parse_wpilog(args.control,   prefer_replay=False)
        trt_sig,  trt_replay  = parse_wpilog(args.treatment, prefer_replay=True)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    ctrl = RunMetrics(args.control,   ctrl_replay, ctrl_sig, list(cameras), args.stationary_speed)
    trt  = RunMetrics(args.treatment, trt_replay,  trt_sig,  list(cameras), args.stationary_speed)

    rows = print_report(ctrl, trt, args.switch)

    if args.output:
        write_csv(rows, args.output)


if __name__ == '__main__':
    main()
