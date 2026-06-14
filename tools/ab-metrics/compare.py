#!/usr/bin/env python3
"""
Vision A/B Metrics Comparison Script

Reads two wpilog files (control = baseline, treatment = one switch ON) and
prints a side-by-side statistics table. Zero external dependencies.

Usage:
    python3 compare.py --control baseline.wpilog --treatment smooth_theta.wpilog
    python3 compare.py --control baseline.wpilog --treatment boundary.wpilog \\
                       --switch VISION_FIELD_BOUNDARY_REJECTION
    python3 compare.py --control baseline.wpilog --treatment smooth_theta.wpilog \\
                       --output results/smooth_theta.csv
    python3 compare.py --control baseline.wpilog --treatment smooth_theta.wpilog \\
                       --cameras Left,Right --stationary-speed 0.05
"""

import argparse
import csv
import math
import pathlib
import struct
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


# ─── WPILog Binary Parser (self-contained copy from analyze.py) ───────────────

POSE2D_SIZE = 24
POSE3D_SIZE = 56


def parse_wpilog(path: str) -> Dict[str, List[Tuple[float, Any]]]:
    raw = pathlib.Path(path).read_bytes()
    pos = 0
    if len(raw) < 12 or raw[0:6] != b'WPILOG':
        raise ValueError(f"Not a WPILog file: {path}")
    extra_len = struct.unpack_from('<I', raw, 8)[0]
    pos = 12 + extra_len

    entries: Dict[int, Dict[str, str]] = {}
    signals: Dict[str, List[Tuple[float, Any]]] = defaultdict(list)

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
            _handle_control(payload, entries)
        else:
            entry = entries.get(entry_id)
            if entry is None:
                continue
            value = _decode(payload, entry['type'])
            if value is not None:
                signals[entry['name']].append((ts_sec, value))

    return dict(signals)


def _handle_control(payload: bytes, entries: Dict) -> None:
    if not payload or payload[0] != 0:
        return
    pos = 1
    if pos + 4 > len(payload):
        return
    new_id = struct.unpack_from('<I', payload, pos)[0]; pos += 4
    name,     pos = _lp_str(payload, pos)
    type_str, pos = _lp_str(payload, pos)
    entries[new_id] = {'name': name.lstrip('/'), 'type': type_str}


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


# ─── Statistics Helpers ───────────────────────────────────────────────────────

def stdev(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    n = len(values)
    mean = sum(values) / n
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))


def mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def delta_pct(control: float, treatment: float) -> str:
    if control == 0:
        return "—"
    d = (treatment - control) / abs(control) * 100
    sign = "+" if d > 0 else ""
    return f"{sign}{d:.1f}%"


def verdict(control: float, treatment: float, lower_is_better: bool = True) -> str:
    if control == 0:
        return "—"
    ratio = treatment / control
    if lower_is_better:
        if ratio < 0.9:
            return "✓ improved"
        elif ratio > 1.1:
            return "✗ REGRESSED"
        else:
            return "  neutral"
    else:
        if ratio > 1.1:
            return "✓ improved"
        elif ratio < 0.9:
            return "✗ REGRESSED"
        else:
            return "  neutral"


# ─── Metric Extraction ────────────────────────────────────────────────────────

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
    entries = signals.get(key, [])
    return [v for _, v in entries if isinstance(v, (int, float))]


def get_last_counter(signals: Dict, key: str) -> int:
    entries = signals.get(key, [])
    if not entries:
        return 0
    return int(entries[-1][1])


def extract_pose_components(signals: Dict, camera: str) -> Tuple[List[float], List[float], List[float]]:
    """Return (xs, ys, rots_deg) of accepted poses for a camera."""
    accepted = signals.get(f'Vision/{camera}/AcceptedPoses', [])
    xs, ys, rots = [], [], []
    for _, pose_list in accepted:
        if not isinstance(pose_list, list):
            continue
        for p in pose_list:
            if isinstance(p, dict):
                xs.append(p.get('x', p.get('x', 0)))
                ys.append(p.get('y', 0))
                rot_rad = p.get('rot', 0)
                # Pose3d: extract yaw from quaternion if present
                if 'qw' in p:
                    qw, qx, qy, qz = p['qw'], p['qx'], p['qy'], p['qz']
                    yaw = math.atan2(2*(qw*qz + qx*qy), 1 - 2*(qy*qy + qz*qz))
                    rot_rad = yaw
                rots.append(math.degrees(rot_rad))
    return xs, ys, rots


def stationary_mask(signals: Dict, max_speed: float) -> Optional[List[float]]:
    """Return timestamps where robot speed < max_speed, or None if no speed data."""
    speed_keys = [
        'Drivetrain/Speeds/vxMetersPerSecond',
        'Drive/ChassisSpeeds/vx',
        'SwerveDrivetrain/ChassisSpeeds/vx',
    ]
    for k in speed_keys:
        if k in signals:
            return [t for t, v in signals[k] if isinstance(v, (int, float)) and abs(v) < max_speed]
    return None


def count_threshold_events(values: List[float], threshold: float) -> int:
    return sum(1 for v in values if v > threshold)


def events_per_minute(signals: Dict, key: str, threshold: float) -> float:
    values = get_scalar_values(signals, key)
    if not values:
        return 0.0
    entries = signals[key]
    if len(entries) < 2:
        return 0.0
    duration_s = entries[-1][0] - entries[0][0]
    if duration_s < 1:
        return 0.0
    count = count_threshold_events(values, threshold)
    return count / duration_s * 60


# ─── Metrics Computation ──────────────────────────────────────────────────────

class RunMetrics:
    def __init__(self, path: str, cameras: List[str], stationary_speed: float):
        self.path = path
        self.name = pathlib.Path(path).name
        signals = parse_wpilog(path)

        if not cameras:
            cameras = discover_cameras(signals)
        self.cameras = cameras

        # Duration
        all_ts = [t for entries in signals.values() for t, _ in entries]
        self.duration_s = (max(all_ts) - min(all_ts)) if len(all_ts) > 1 else 0

        # Per-camera pose stats
        self.cam_accepted: Dict[str, int] = {}
        self.cam_sigma_x:  Dict[str, float] = {}
        self.cam_sigma_y:  Dict[str, float] = {}
        self.cam_sigma_th: Dict[str, float] = {}
        self.cam_rejected_velocity:  Dict[str, int] = {}
        self.cam_rejected_boundary:  Dict[str, int] = {}
        self.cam_rejected_ambiguity: Dict[str, int] = {}

        all_xs, all_ys, all_ths = [], [], []
        total_accepted = 0

        for cam in cameras:
            xs, ys, ths = extract_pose_components(signals, cam)
            self.cam_accepted[cam]  = len(xs)
            self.cam_sigma_x[cam]   = stdev(xs)
            self.cam_sigma_y[cam]   = stdev(ys)
            self.cam_sigma_th[cam]  = stdev(ths)
            self.cam_rejected_velocity[cam]  = get_last_counter(signals, f'Vision/{cam}/RejectedVelocity')
            self.cam_rejected_boundary[cam]  = get_last_counter(signals, f'Vision/{cam}/RejectedBoundary')
            self.cam_rejected_ambiguity[cam] = get_last_counter(signals, f'Vision/{cam}/RejectedAmbiguity')
            all_xs.extend(xs); all_ys.extend(ys); all_ths.extend(ths)
            total_accepted += len(xs)

        self.total_accepted = total_accepted
        self.sigma_x  = stdev(all_xs)
        self.sigma_y  = stdev(all_ys)
        self.sigma_th = stdev(all_ths)

        # Acceptance rate (poses/second)
        self.acceptance_rate = total_accepted / self.duration_s if self.duration_s > 0 else 0

        # Correction magnitude events
        self.correction_epm_1m  = events_per_minute(signals, 'Vision/CorrectionMagnitude', 1.0)
        self.correction_epm_05m = events_per_minute(signals, 'Vision/CorrectionMagnitude', 0.5)

        # Mean stddev values logged
        xy_vals = get_scalar_values(signals, 'Vision/XYStddev')
        th_vals = get_scalar_values(signals, 'Vision/ThetaStddev')
        self.mean_xy_stddev = mean(xy_vals)
        self.mean_th_stddev = mean(th_vals)

        # Total rejections (all cameras combined)
        self.total_rej_velocity  = sum(self.cam_rejected_velocity.values())
        self.total_rej_boundary  = sum(self.cam_rejected_boundary.values())
        self.total_rej_ambiguity = sum(self.cam_rejected_ambiguity.values())

        # Camera connection
        self.cam_connected: Dict[str, bool] = {}
        for cam in cameras:
            connected = signals.get(f'Vision/{cam}/isConnected', [])
            if connected:
                self.cam_connected[cam] = bool(connected[-1][1])
            else:
                connected_alt = signals.get(f'Vision/{cam}/connected', [])
                self.cam_connected[cam] = bool(connected_alt[-1][1]) if connected_alt else None


# ─── Report Rendering ─────────────────────────────────────────────────────────

def fmt(v: float, decimals: int = 3, unit: str = '') -> str:
    return f"{v:.{decimals}f}{unit}"


def print_report(ctrl: RunMetrics, trt: RunMetrics, switch_name: Optional[str]) -> List[Dict]:
    width = 74
    hdr = f"A/B Comparison: {switch_name}" if switch_name else "Vision A/B Comparison"
    print()
    print(hdr)
    print('═' * width)

    cam_ctrl = ', '.join(f"{c}: {ctrl.cam_accepted.get(c, 0)}" for c in ctrl.cameras)
    cam_trt  = ', '.join(f"{c}: {trt.cam_accepted.get(c, 0)}"  for c in trt.cameras)
    print(f"Control:   {ctrl.name:<35} ({ctrl.total_accepted} samples — {cam_ctrl})")
    print(f"Treatment: {trt.name:<35} ({trt.total_accepted} samples — {cam_trt})")
    print(f"Duration:  control {ctrl.duration_s:.0f}s, treatment {trt.duration_s:.0f}s")
    print()

    col_w = [38, 11, 11, 9, 15]
    header = f"{'Metric':<{col_w[0]}} {'Control':>{col_w[1]}} {'Treatment':>{col_w[2]}} {'Delta':>{col_w[3]}} {'Verdict'}"
    sep    = '─' * width
    print(header)
    print(sep)

    rows = []

    def row(label: str, c_val: float, t_val: float, fmt_fn, lower_is_better=True, unit=''):
        c_s = fmt_fn(c_val)
        t_s = fmt_fn(t_val)
        d_s = delta_pct(c_val, t_val)
        v_s = verdict(c_val, t_val, lower_is_better)
        print(f"{label:<{col_w[0]}} {c_s:>{col_w[1]}} {t_s:>{col_w[2]}} {d_s:>{col_w[3]}} {v_s}")
        rows.append({'metric': label, 'control': c_val, 'treatment': t_val,
                     'delta_pct': d_s, 'verdict': v_s.strip()})

    row("σX all positions",       ctrl.sigma_x,  trt.sigma_x,  lambda v: fmt(v, 4, ' m'))
    row("σY all positions",       ctrl.sigma_y,  trt.sigma_y,  lambda v: fmt(v, 4, ' m'))
    row("σθ all positions",       ctrl.sigma_th, trt.sigma_th, lambda v: fmt(v, 3, '°'))
    print(sep)
    row("Acceptance rate",        ctrl.acceptance_rate, trt.acceptance_rate,
        lambda v: fmt(v, 2, '/s'), lower_is_better=False)
    print(sep)
    row("CorrectionMagnitude >1m (epm)", ctrl.correction_epm_1m,  trt.correction_epm_1m,
        lambda v: fmt(v, 2, '/min'))
    row("CorrectionMagnitude >0.5m (epm)", ctrl.correction_epm_05m, trt.correction_epm_05m,
        lambda v: fmt(v, 2, '/min'))
    print(sep)
    row("Velocity rejections",    ctrl.total_rej_velocity,  trt.total_rej_velocity,
        lambda v: f"{int(v)}")
    row("Boundary rejections",    ctrl.total_rej_boundary,  trt.total_rej_boundary,
        lambda v: f"{int(v)}")
    row("Ambiguity rejections",   ctrl.total_rej_ambiguity, trt.total_rej_ambiguity,
        lambda v: f"{int(v)}")
    print(sep)
    row("Mean XY stddev logged",  ctrl.mean_xy_stddev, trt.mean_xy_stddev,
        lambda v: fmt(v, 4))
    row("Mean θ stddev logged",   ctrl.mean_th_stddev, trt.mean_th_stddev,
        lambda v: fmt(v, 1))
    print()

    # Per-camera breakdown
    all_cams = sorted(set(ctrl.cameras) | set(trt.cameras))
    if all_cams:
        print("Per-camera breakdown:")
        print(sep)
        for cam in all_cams:
            cx = ctrl.cam_sigma_x.get(cam, 0)
            tx = trt.cam_sigma_x.get(cam, 0)
            cy = ctrl.cam_sigma_y.get(cam, 0)
            ty = trt.cam_sigma_y.get(cam, 0)
            cth = ctrl.cam_sigma_th.get(cam, 0)
            tth = trt.cam_sigma_th.get(cam, 0)
            ca  = ctrl.cam_accepted.get(cam, 0)
            ta  = trt.cam_accepted.get(cam, 0)
            print(f"  {cam}  accepted ctrl/trt: {ca}/{ta}  "
                  f"σX {cx:.4f}→{tx:.4f}  σY {cy:.4f}→{ty:.4f}  σθ {cth:.2f}→{tth:.2f}°")
        print()

    return rows


def write_csv(rows: List[Dict], path: str) -> None:
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['metric', 'control', 'treatment', 'delta_pct', 'verdict'])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Results written to: {path}")


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description='Compare two wpilog files for vision A/B testing.')
    parser.add_argument('--control',   required=True, help='Baseline wpilog (all switches OFF)')
    parser.add_argument('--treatment', required=True, help='Treatment wpilog (one switch ON)')
    parser.add_argument('--switch',    default=None,
                        help='Name of the switch under test (for display)')
    parser.add_argument('--cameras',   default='',
                        help='Comma-separated camera names (auto-detected if omitted)')
    parser.add_argument('--stationary-speed', type=float, default=0.05,
                        help='Max m/s to consider robot stationary (default: 0.05)')
    parser.add_argument('--output',    default=None,
                        help='Write CSV results to this path')
    args = parser.parse_args()

    cameras = [c.strip() for c in args.cameras.split(',') if c.strip()]

    try:
        ctrl = RunMetrics(args.control,   cameras, args.stationary_speed)
        trt  = RunMetrics(args.treatment, cameras, args.stationary_speed)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    rows = print_report(ctrl, trt, args.switch)

    if args.output:
        write_csv(rows, args.output)


if __name__ == '__main__':
    main()
