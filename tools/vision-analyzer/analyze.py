#!/usr/bin/env python3
"""
Vision Log Analyzer — generate an interactive HTML dashboard from a WPILib .wpilog file.

Zero external dependencies: uses Python standard library only.
Charts are rendered by Plotly.js loaded from CDN (internet required to open the HTML).

Usage:
    python3 analyze.py path/to/FRC_20260609_123456.wpilog
    python3 analyze.py logs/off-season/               # all .wpilog files in directory
    python3 analyze.py log1.wpilog log2.wpilog --output /tmp/reports
    python3 analyze.py --probe path/to/log.wpilog     # dump all signal names/types, exit
"""

import argparse
import json
import math
import pathlib
import struct
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


# ─── Field and Tag Constants ───────────────────────────────────────────────────

FIELD_LENGTH = 16.541   # meters, 2026 Reefscape rebuilt-welded
FIELD_WIDTH  = 8.069

# Exact positions from src/main/deploy/2026-rebuilt-welded.json
APRILTAG_POSITIONS: Dict[int, Tuple[float, float]] = {
    1:  (11.878, 7.425),   2:  (11.915, 4.638),   3:  (11.312, 4.390),
    4:  (11.312, 4.035),   5:  (11.915, 3.431),   6:  (11.878, 0.644),
    7:  (11.953, 0.644),   8:  (12.271, 3.431),   9:  (12.519, 3.679),
    10: (12.519, 4.035),   11: (12.271, 4.638),   12: (11.953, 7.425),
    13: (16.533, 7.403),   14: (16.533, 6.972),   15: (16.533, 4.324),
    16: (16.533, 3.892),   17: (4.663,  0.644),   18: (4.626,  3.431),
    19: (5.229,  3.679),   20: (5.229,  4.035),   21: (4.626,  4.638),
    22: (4.663,  7.425),   23: (4.588,  7.425),   24: (4.270,  4.638),
    25: (4.022,  4.390),   26: (4.022,  4.035),   27: (4.270,  3.431),
    28: (4.588,  0.644),   29: (0.008,  0.666),   30: (0.008,  1.098),
    31: (0.008,  3.746),   32: (0.008,  4.178),
}

# Tags in the reef scoring zone (trust = 1.0 in TAG_RANKINGS)
REEF_TAG_IDS = frozenset({6, 7, 8, 9, 10, 11, 17, 18, 19, 20, 21, 22})

# Struct sizes (bytes) — WPILib standard, stable across seasons
POSE2D_SIZE = 24   # double x, double y, double rotation_radians
POSE3D_SIZE = 56   # double x,y,z, double qw,qx,qy,qz


# ─── WPILog Binary Parser ─────────────────────────────────────────────────────

def parse_wpilog(path: str) -> Dict[str, List[Tuple[float, Any]]]:
    """
    Parse a WPILib DataLog (.wpilog) file.

    Returns a dict mapping signal name → list of (timestamp_seconds, value) tuples.
    Values are decoded based on the type string registered in the log:
      boolean        → bool
      int64          → int
      double         → float
      double[]       → list[float]
      int64[]        → list[int]
      boolean[]      → list[bool]
      struct:Pose2d  → list[dict] with keys x, y, rot
      struct[]:Pose2d → list[dict] with keys x, y, rot   (0 or more per record)
      struct:Pose3d  → list[dict] with keys x, y, z, qw, qx, qy, qz
      struct[]:Pose3d → list[dict] (0 or more per record)
    Unknown types are silently skipped.
    """
    raw = pathlib.Path(path).read_bytes()
    pos = 0

    # ── Header ──────────────────────────────────────────────────────────────
    if len(raw) < 13 or raw[0:6] != b'WPILOG':
        raise ValueError(f"Not a WPILog file (bad magic): {path}")
    # raw[6]   = 0x00 null
    # raw[7:9] = version (uint16 LE)
    # raw[9:13]= extra_header_size (uint32 LE)
    extra_len = struct.unpack_from('<I', raw, 9)[0]
    pos = 13 + extra_len

    # ── Entry registry: id → {name, type} ───────────────────────────────────
    entries: Dict[int, Dict[str, str]] = {}

    # ── Result accumulator ───────────────────────────────────────────────────
    signals: Dict[str, List[Tuple[float, Any]]] = defaultdict(list)

    while pos < len(raw):
        if pos >= len(raw):
            break
        bitfield = raw[pos]
        pos += 1

        # Decode field widths
        # bits 1:0 → entry_id size  (0→1B, 1→2B, 2→4B)
        # bits 3:2 → payload size   (0→1B, 1→2B, 2→4B)
        # bits 5:4 → timestamp size (0→4B, 1→5B, 2→6B, 3→8B)
        eid_sz   = (1, 2, 4, 4)[ bitfield       & 0x3]
        psz_sz   = (1, 2, 4, 4)[(bitfield >> 2) & 0x3]
        tsz      = (4, 5, 6, 8)[(bitfield >> 4) & 0x3]

        needed = eid_sz + psz_sz + tsz
        if pos + needed > len(raw):
            break

        entry_id     = int.from_bytes(raw[pos:pos + eid_sz], 'little')
        pos         += eid_sz
        payload_size = int.from_bytes(raw[pos:pos + psz_sz], 'little')
        pos         += psz_sz
        ts_us        = int.from_bytes(raw[pos:pos + tsz],    'little')
        pos         += tsz
        ts_sec       = ts_us / 1_000_000.0

        if pos + payload_size > len(raw):
            break
        payload = raw[pos:pos + payload_size]
        pos    += payload_size

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
    if not payload:
        return
    ctrl = payload[0]
    if ctrl != 0:          # only handle kStart; ignore kFinish, kSetMetadata
        return
    pos = 1
    if pos + 4 > len(payload):
        return
    new_id = struct.unpack_from('<I', payload, pos)[0]
    pos += 4
    name,     pos = _lp_str(payload, pos)
    type_str, pos = _lp_str(payload, pos)
    entries[new_id] = {'name': name, 'type': type_str}


def _lp_str(data: bytes, pos: int) -> Tuple[str, int]:
    """Read a length-prefixed UTF-8 string."""
    if pos + 4 > len(data):
        return '', pos
    length = struct.unpack_from('<I', data, pos)[0]
    pos += 4
    s = data[pos:pos + length].decode('utf-8', errors='replace')
    return s, pos + length


def _decode(payload: bytes, typ: str) -> Any:
    """Decode a DataLog payload given its type string."""
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


# ─── Signal Discovery ─────────────────────────────────────────────────────────

def discover_cameras(signals: Dict) -> List[str]:
    """Return camera names by scanning for Vision/<name>/connected signals."""
    cameras = []
    for key in signals:
        parts = key.split('/')
        if len(parts) >= 3 and parts[0] == 'Vision' and parts[2] == 'connected':
            cam = parts[1]
            if cam not in cameras:
                cameras.append(cam)
    return sorted(cameras)


def detect_format(signals: Dict, camera: str) -> str:
    """Return 'new' if rawEstimatedPoses is present, else 'old'."""
    return 'new' if f'Vision/{camera}/rawEstimatedPoses' in signals else 'old'


def find_drivetrain_speeds(signals: Dict) -> Tuple[Optional[str], Optional[str]]:
    """
    Try several known signal paths for chassis linear and angular speed.
    Returns (linear_key, angular_key) or (None, None) if not found.
    """
    candidates_linear = [
        'Drivetrain/Speeds/vxMetersPerSecond',
        'Drive/ChassisSpeeds/vx',
        'SwerveDrivetrain/ChassisSpeeds/vx',
        'Swerve/Speeds/vx',
    ]
    candidates_angular = [
        'Drivetrain/Speeds/omegaRadiansPerSecond',
        'Drive/ChassisSpeeds/omega',
        'SwerveDrivetrain/ChassisSpeeds/omega',
        'Swerve/Speeds/omega',
    ]
    # Also do a fuzzy search for keys containing these substrings
    def fuzzy(candidates, signals):
        for c in candidates:
            if c in signals:
                return c
        # Fuzzy fallback
        for key in signals:
            kl = key.lower()
            if 'vxmeters' in kl or ('speed' in kl and 'vx' in kl):
                return key
        return None

    linear_key = fuzzy(candidates_linear, signals)

    omega_key = None
    for c in candidates_angular:
        if c in signals:
            omega_key = c
            break
    if omega_key is None:
        for key in signals:
            kl = key.lower()
            if 'omega' in kl or ('speed' in kl and ('omega' in kl or 'angular' in kl)):
                omega_key = key
                break

    return linear_key, omega_key


# ─── Metric Computation ───────────────────────────────────────────────────────

def ts_list(signal: List[Tuple[float, Any]]) -> List[float]:
    return [t for t, _ in signal]

def val_list(signal: List[Tuple[float, Any]]) -> List[Any]:
    return [v for _, v in signal]


def build_timeline(signal: List[Tuple[float, Any]], start_t: float) -> Tuple[List[float], List[Any]]:
    ts = [t - start_t for t, _ in signal]
    vs = [v for _, v in signal]
    return ts, vs


def nearest_value(signal: List[Tuple[float, Any]], target_t: float) -> Optional[Any]:
    """Return the value at the timestamp closest to target_t."""
    if not signal:
        return None
    best = min(signal, key=lambda r: abs(r[0] - target_t))
    if abs(best[0] - target_t) > 1.0:   # more than 1 s away — no valid sample
        return None
    return best[1]


def compute_camera_metrics(
    signals: Dict,
    camera: str,
    fmt: str,
    start_t: float,
    end_t: float,
    linear_sig: Optional[List],
    omega_sig: Optional[List],
) -> Dict:
    """
    Compute all per-camera metrics. Returns a dict ready for JSON serialisation.
    Works with both old (pre-refactoring) and new (post-refactoring) signal formats.
    """
    prefix = f'Vision/{camera}/'

    def sig(name):
        return signals.get(prefix + name, [])

    m = {'camera': camera, 'format': fmt}

    # ── FPS timeline ────────────────────────────────────────────────────────
    fps_sig = sig('currentFps')
    if fps_sig:
        ts, vs = build_timeline(fps_sig, start_t)
        m['fps_ts']     = ts
        m['fps_values'] = vs
        m['fps_mean']   = sum(vs) / len(vs)
        m['fps_min']    = min(vs)
    else:
        m['fps_ts'] = m['fps_values'] = []
        m['fps_mean'] = m['fps_min'] = 0.0

    # ── Connection timeline ──────────────────────────────────────────────────
    conn_sig = sig('connected')
    if conn_sig:
        conn_ts, conn_vs = build_timeline(conn_sig, start_t)
        m['conn_ts']     = conn_ts
        m['conn_values'] = [1 if v else 0 for v in conn_vs]
        total = len(conn_vs)
        m['conn_uptime_pct'] = 100.0 * sum(1 for v in conn_vs if v) / total if total else 0.0
    else:
        m['conn_ts'] = m['conn_values'] = []
        m['conn_uptime_pct'] = 0.0

    # ── Old-format signals ───────────────────────────────────────────────────
    if fmt == 'old':
        rej_vel_sig  = sig('rejectionCountVelocity')
        rej_bnd_sig  = sig('rejectionCountBoundary')
        poses_sig    = sig('estimatedPoses')
        dists_sig    = sig('estimateAvgDistancesMeters')
        weights_sig  = sig('estimateWeightScalars')
        ts_est_sig   = sig('estimateTimestampsSec')
        tags_sig     = sig('visibleTagIds')

        # Per-loop acceptance and rejection
        acc_ts, acc_counts, rej_v_counts, rej_b_counts = [], [], [], []
        all_distances, all_weights = [], []
        tag_freq: Dict[int, int] = defaultdict(int)
        path_x, path_y = [], []

        # Interleave timestamps from pose signal and rejection signals
        # Build a merged timeline at each pose-signal sample
        for t, poses in poses_sig:
            accepted = len(poses)
            rej_v = nearest_value(rej_vel_sig, t) or 0
            rej_b = nearest_value(rej_bnd_sig, t) or 0
            acc_ts.append(t - start_t)
            acc_counts.append(accepted)
            rej_v_counts.append(rej_v)
            rej_b_counts.append(rej_b)

            if accepted > 0:
                # Average pose for this loop as robot path point
                avg_x = sum(p['x'] for p in poses) / accepted
                avg_y = sum(p['y'] for p in poses) / accepted
                path_x.append(avg_x)
                path_y.append(avg_y)

        for _, dists in dists_sig:
            all_distances.extend(dists)

        for _, wts in weights_sig:
            all_weights.extend(wts)

        for _, tags in tags_sig:
            for tag_id in tags:
                tag_freq[tag_id] += 1

        total_accepted = sum(acc_counts)
        total_rejected = sum(rej_v_counts) + sum(rej_b_counts)
        total_results  = total_accepted + total_rejected

        m['acc_ts']        = acc_ts
        m['acc_counts']    = acc_counts
        m['rej_v_counts']  = rej_v_counts
        m['rej_b_counts']  = rej_b_counts
        m['total_accepted'] = total_accepted
        m['total_rejected'] = total_rejected
        m['total_results']  = total_results
        m['acceptance_rate'] = (
            100.0 * total_accepted / total_results if total_results else 0.0
        )
        m['rej_velocity_pct'] = (
            100.0 * sum(rej_v_counts) / total_rejected if total_rejected else 0.0
        )
        m['rej_boundary_pct'] = (
            100.0 * sum(rej_b_counts) / total_rejected if total_rejected else 0.0
        )
        m['distances']  = all_distances
        m['weights']    = all_weights
        m['tag_freq']   = {int(k): v for k, v in tag_freq.items()}
        m['path_x']     = path_x
        m['path_y']     = path_y

        # Result latency (robot-loop ts minus coprocessor ts)
        latencies = []
        for (ts_loop, poses), (_, ts_est) in zip(poses_sig, ts_est_sig):
            for j, est_ts in enumerate(ts_est):
                lat = ts_loop - est_ts
                if 0.0 < lat < 2.0:
                    latencies.append(lat * 1000.0)   # ms
        m['latencies_ms'] = latencies
        m['latency_mean_ms'] = sum(latencies) / len(latencies) if latencies else 0.0

    # ── New-format signals ────────────────────────────────────────────────────
    else:  # fmt == 'new'
        raw_poses_sig = sig('rawEstimatedPoses')
        amb_sig       = sig('rawAmbiguities')
        area_sig      = sig('rawSumTagAreas')
        px_sig        = sig('rawAvgNormalizedPixelOffsets')
        ar_sig        = sig('rawAvgAspectRatioDevs')
        cnt_sig       = sig('rawTagCountsPerResult')
        tags_sig      = sig('visibleTagIds')
        rej_bnd_sig   = sig('RejectedBoundary')
        rej_vel_sig   = sig('RejectedVelocity')
        rej_amb_sig   = sig('RejectedAmbiguity')
        acc_poses_sig = sig('AcceptedPoses')
        dists_sig     = sig('rawAvgDistancesMeters')
        raw_ts_sig    = sig('rawTimestampsSec')

        acc_ts, acc_counts, rej_v_counts, rej_b_counts, rej_a_counts = [], [], [], [], []
        raw_counts = []
        z_heights, ambiguities, all_distances = [], [], []
        areas, px_offsets, aspect_ratios = [], [], []
        tag_freq: Dict[int, int] = defaultdict(int)
        path_x, path_y = [], []
        latencies = []

        for t, raw_poses in raw_poses_sig:
            rej_b = nearest_value(rej_bnd_sig, t) or 0
            rej_v = nearest_value(rej_vel_sig, t) or 0
            rej_a = nearest_value(rej_amb_sig, t) or 0
            acc_poses = nearest_value(acc_poses_sig, t) or []
            accepted  = len(acc_poses)

            acc_ts.append(t - start_t)
            acc_counts.append(accepted)
            rej_v_counts.append(rej_v)
            rej_b_counts.append(rej_b)
            rej_a_counts.append(rej_a)
            raw_counts.append(len(raw_poses))

            for p in raw_poses:
                z_heights.append(p['z'])

            if accepted > 0:
                avg_x = sum(p['x'] for p in acc_poses) / accepted
                avg_y = sum(p['y'] for p in acc_poses) / accepted
                path_x.append(avg_x)
                path_y.append(avg_y)

            # Raw timestamps for latency
            raw_ts = nearest_value(raw_ts_sig, t) or []
            for est_ts in raw_ts:
                lat = t - est_ts
                if 0.0 < lat < 2.0:
                    latencies.append(lat * 1000.0)

        for _, ambs in amb_sig:
            ambiguities.extend(a for a in ambs if a >= 0)  # skip -1 (multi-tag)

        for _, dists in dists_sig:
            all_distances.extend(dists)

        for _, ars in area_sig:
            areas.extend(ars)

        for _, pxs in px_sig:
            px_offsets.extend(pxs)

        for _, ars in ar_sig:
            aspect_ratios.extend(ars)

        for _, tags in tags_sig:
            for tag_id in tags:
                tag_freq[tag_id] += 1

        total_accepted = sum(acc_counts)
        total_raw      = sum(raw_counts)
        total_rejected = sum(rej_v_counts) + sum(rej_b_counts) + sum(rej_a_counts)

        m['acc_ts']        = acc_ts
        m['acc_counts']    = acc_counts
        m['rej_v_counts']  = rej_v_counts
        m['rej_b_counts']  = rej_b_counts
        m['rej_a_counts']  = rej_a_counts
        m['raw_counts']    = raw_counts
        m['total_accepted'] = total_accepted
        m['total_raw']      = total_raw
        m['total_results']  = total_raw
        m['acceptance_rate'] = (
            100.0 * total_accepted / total_raw if total_raw else 0.0
        )
        m['rej_velocity_pct'] = (
            100.0 * sum(rej_v_counts) / total_rejected if total_rejected else 0.0
        )
        m['rej_boundary_pct'] = (
            100.0 * sum(rej_b_counts) / total_rejected if total_rejected else 0.0
        )
        m['rej_ambiguity_pct'] = (
            100.0 * sum(rej_a_counts) / total_rejected if total_rejected else 0.0
        )
        m['z_heights']     = z_heights
        m['ambiguities']   = ambiguities
        m['distances']     = all_distances
        m['areas']         = areas
        m['px_offsets']    = px_offsets
        m['aspect_ratios'] = aspect_ratios
        m['tag_freq']      = {int(k): v for k, v in tag_freq.items()}
        m['path_x']        = path_x
        m['path_y']        = path_y
        m['latencies_ms']  = latencies
        m['latency_mean_ms'] = sum(latencies) / len(latencies) if latencies else 0.0

    # ── Velocity-correlated quality (requires drivetrain speed signals) ───────
    if linear_sig and omega_sig and acc_ts:
        buckets = {'stationary': [], 'slow': [], 'rotating': [], 'fast': []}

        for i, t_rel in enumerate(acc_ts):
            t_abs = t_rel + start_t
            lin_v   = nearest_value(linear_sig, t_abs)
            omega_v = nearest_value(omega_sig, t_abs)
            if lin_v is None or omega_v is None:
                continue

            lin_abs   = abs(lin_v)
            omega_abs = abs(omega_v)
            raw_n = m.get('raw_counts', [m.get('acc_counts', [0])[i] +
                           m.get('rej_v_counts', [0])[i] + m.get('rej_b_counts', [0])[i]])[i]
            accepted_n = acc_counts[i]

            if lin_abs < 0.20 and omega_abs < 0.30:
                bucket = 'stationary'
            elif omega_abs >= 1.50:
                bucket = 'rotating'
            elif lin_abs > 2.00 or omega_abs > 4.00:
                bucket = 'fast'
            else:
                bucket = 'slow'

            if raw_n > 0:
                buckets[bucket].append(accepted_n / raw_n)

        m['velocity_buckets'] = {
            k: {
                'count': len(v),
                'acceptance_rate': 100.0 * sum(v) / len(v) if v else 0.0,
            }
            for k, v in buckets.items()
        }
        m['stationary_quality'] = m['velocity_buckets']['stationary']['acceptance_rate']
    else:
        m['velocity_buckets'] = {}
        m['stationary_quality'] = None

    return m


# ─── HTML / Plotly Generation ─────────────────────────────────────────────────

_COLORS = {
    'Left':  {'primary': '#4FC3F7', 'secondary': '#0288D1'},
    'Right': {'primary': '#AED581', 'secondary': '#558B2F'},
}

def _cam_color(camera: str, role: str = 'primary') -> str:
    return _COLORS.get(camera, {'primary': '#FFB74D', 'secondary': '#E65100'})[role]


def _histogram_data(values: List[float], nbins: int = 30) -> Tuple[List[float], List[int]]:
    """Simple histogram — returns (bin_centers, counts)."""
    if not values:
        return [], []
    lo, hi = min(values), max(values)
    if lo == hi:
        return [lo], [len(values)]
    step = (hi - lo) / nbins
    counts = [0] * nbins
    centers = [lo + step * (i + 0.5) for i in range(nbins)]
    for v in values:
        idx = min(int((v - lo) / step), nbins - 1)
        counts[idx] += 1
    return centers, counts


def _rolling_mean(ts: List[float], vs: List[float], window: float = 2.0) -> Tuple[List[float], List[float]]:
    """1D rolling mean over a time window (seconds)."""
    out_ts, out_vs = [], []
    for i, (t, v) in enumerate(zip(ts, vs)):
        window_vals = [vj for tj, vj in zip(ts, vs) if t - window <= tj <= t]
        if window_vals:
            out_ts.append(t)
            out_vs.append(sum(window_vals) / len(window_vals))
    return out_ts, out_vs


def _j(v) -> str:
    """Compact JSON serialisation."""
    return json.dumps(v, separators=(',', ':'))


def generate_html(
    all_metrics: List[Dict],
    log_name: str,
    duration_sec: float,
    metadata: Dict,
) -> str:
    cameras = [m['camera'] for m in all_metrics]
    fmt = all_metrics[0]['format'] if all_metrics else 'old'

    # ── Acceptance-rate-over-time chart ─────────────────────────────────────
    acc_rate_traces = []
    for m in all_metrics:
        cam = m['camera']
        ts  = m['acc_ts']
        # Rolling acceptance rate per second
        has_raw = 'raw_counts' in m
        totals = m['raw_counts'] if has_raw else [
            a + b + c
            for a, b, c in zip(
                m['acc_counts'],
                m['rej_v_counts'],
                m.get('rej_b_counts', [0] * len(m['acc_counts'])),
            )
        ]
        rates = [
            100.0 * a / t if t > 0 else 0.0
            for a, t in zip(m['acc_counts'], totals)
        ]
        rts, rvs = _rolling_mean(ts, rates, window=3.0)
        acc_rate_traces.append({
            'x': rts, 'y': rvs,
            'name': cam, 'type': 'scatter', 'mode': 'lines',
            'line': {'color': _cam_color(cam), 'width': 2},
        })

    # ── FPS chart ─────────────────────────────────────────────────────────
    fps_traces = []
    for m in all_metrics:
        cam = m['camera']
        fps_traces.append({
            'x': m['fps_ts'], 'y': m['fps_values'],
            'name': cam, 'type': 'scatter', 'mode': 'lines',
            'line': {'color': _cam_color(cam), 'width': 1.5},
        })

    # ── Field coverage map ─────────────────────────────────────────────────
    # Aggregate tag detections across all cameras
    combined_tag_freq: Dict[int, int] = defaultdict(int)
    for m in all_metrics:
        for tag_id, cnt in m['tag_freq'].items():
            combined_tag_freq[tag_id] += cnt
    max_freq = max(combined_tag_freq.values()) if combined_tag_freq else 1

    tag_x  = [APRILTAG_POSITIONS[t][0] for t in APRILTAG_POSITIONS]
    tag_y  = [APRILTAG_POSITIONS[t][1] for t in APRILTAG_POSITIONS]
    tag_ids = list(APRILTAG_POSITIONS.keys())
    tag_color = [
        combined_tag_freq.get(tid, 0) / max_freq for tid in tag_ids
    ]
    tag_text  = [
        f'Tag {tid}<br>Seen {combined_tag_freq.get(tid, 0)}×'
        + ('<br>REEF' if tid in REEF_TAG_IDS else '')
        for tid in tag_ids
    ]

    field_traces = [
        # Field boundary
        {
            'x': [0, FIELD_LENGTH, FIELD_LENGTH, 0, 0],
            'y': [0, 0, FIELD_WIDTH, FIELD_WIDTH, 0],
            'type': 'scatter', 'mode': 'lines',
            'line': {'color': '#555', 'width': 1},
            'showlegend': False, 'hoverinfo': 'skip',
        },
        # AprilTags — color by detection frequency
        {
            'x': tag_x, 'y': tag_y, 'text': tag_text,
            'type': 'scatter', 'mode': 'markers+text',
            'textposition': 'top center',
            'textfont': {'size': 8, 'color': '#aaa'},
            'marker': {
                'size': 14,
                'color': tag_color,
                'colorscale': [[0, '#c0392b'], [0.4, '#f39c12'], [1.0, '#27ae60']],
                'cmin': 0, 'cmax': 1,
                'colorbar': {
                    'title': 'Detection rate', 'len': 0.4,
                    'tickvals': [0, 0.5, 1.0],
                    'ticktext': ['never', '50%', 'always'],
                },
                'line': {'color': '#fff', 'width': 1},
            },
            'name': 'AprilTags', 'hovertemplate': '%{text}<extra></extra>',
        },
    ]
    # Robot paths
    for m in all_metrics:
        cam = m['camera']
        if m['path_x']:
            field_traces.append({
                'x': m['path_x'], 'y': m['path_y'],
                'name': f'{cam} path', 'type': 'scatter', 'mode': 'markers',
                'marker': {'size': 3, 'color': _cam_color(cam), 'opacity': 0.4},
            })

    # ── Rejection breakdown bars ────────────────────────────────────────────
    rej_bars = []
    labels_vel, labels_bnd, labels_amb = [], [], []
    for m in all_metrics:
        cam = m['camera']
        labels_vel.append(m.get('rej_velocity_pct', 0))
        labels_bnd.append(m.get('rej_boundary_pct', 0))
        labels_amb.append(m.get('rej_ambiguity_pct', 0))
    rej_bars = [
        {'x': cameras, 'y': labels_vel, 'name': 'Velocity', 'type': 'bar',
         'marker': {'color': '#E74C3C'}},
        {'x': cameras, 'y': labels_bnd, 'name': 'Boundary', 'type': 'bar',
         'marker': {'color': '#F39C12'}},
    ]
    if fmt == 'new':
        rej_bars.append(
            {'x': cameras, 'y': labels_amb, 'name': 'Ambiguity', 'type': 'bar',
             'marker': {'color': '#9B59B6'}}
        )

    # ── Distance histograms ─────────────────────────────────────────────────
    dist_traces = []
    for m in all_metrics:
        cam = m['camera']
        centers, counts = _histogram_data(m['distances'])
        dist_traces.append({
            'x': centers, 'y': counts, 'name': cam,
            'type': 'bar', 'opacity': 0.7,
            'marker': {'color': _cam_color(cam)},
        })

    # ── Weight histograms (old format only) ─────────────────────────────────
    weight_traces = []
    if fmt == 'old':
        for m in all_metrics:
            cam = m['camera']
            centers, counts = _histogram_data(m.get('weights', []))
            weight_traces.append({
                'x': centers, 'y': counts, 'name': cam,
                'type': 'bar', 'opacity': 0.7,
                'marker': {'color': _cam_color(cam)},
            })

    # ── Z-height histograms (new format only) ───────────────────────────────
    z_traces = []
    if fmt == 'new':
        for m in all_metrics:
            cam = m['camera']
            centers, counts = _histogram_data(m.get('z_heights', []), nbins=40)
            z_traces.append({
                'x': centers, 'y': counts, 'name': cam,
                'type': 'bar', 'opacity': 0.7,
                'marker': {'color': _cam_color(cam)},
            })

    # ── Ambiguity histograms (new format only) ──────────────────────────────
    amb_traces = []
    if fmt == 'new':
        for m in all_metrics:
            cam = m['camera']
            centers, counts = _histogram_data(m.get('ambiguities', []), nbins=20)
            amb_traces.append({
                'x': centers, 'y': counts, 'name': cam,
                'type': 'bar', 'opacity': 0.7,
                'marker': {'color': _cam_color(cam)},
            })

    # ── Velocity bucket bars (if available) ─────────────────────────────────
    vel_traces = []
    if any(m.get('velocity_buckets') for m in all_metrics):
        bucket_names = ['stationary', 'slow', 'rotating', 'fast']
        bucket_labels = ['Stationary', 'Slow translate', 'Rotating', 'Full speed']
        for m in all_metrics:
            cam = m['camera']
            bkts = m.get('velocity_buckets', {})
            vel_traces.append({
                'x': bucket_labels,
                'y': [bkts.get(b, {}).get('acceptance_rate', 0) for b in bucket_names],
                'name': cam, 'type': 'bar', 'opacity': 0.85,
                'marker': {'color': _cam_color(cam)},
            })

    # ── Summary table rows ───────────────────────────────────────────────────
    def pct(v):
        return f'{v:.1f}%' if v is not None else '—'
    def ms(v):
        return f'{v:.0f} ms' if v else '—'

    table_header = ['Metric'] + cameras
    table_rows = [
        ['Acceptance rate'] + [pct(m['acceptance_rate']) for m in all_metrics],
        ['FPS (mean)'] + [f'{m["fps_mean"]:.1f}' for m in all_metrics],
        ['FPS (min)'] + [f'{m["fps_min"]:.1f}' for m in all_metrics],
        ['Connection uptime'] + [pct(m['conn_uptime_pct']) for m in all_metrics],
        ['Mean result latency'] + [ms(m['latency_mean_ms']) for m in all_metrics],
        ['Rejected (velocity)'] + [pct(m.get('rej_velocity_pct')) for m in all_metrics],
        ['Rejected (boundary)'] + [pct(m.get('rej_boundary_pct')) for m in all_metrics],
    ]
    if fmt == 'new':
        table_rows.append(
            ['Rejected (ambiguity)'] + [pct(m.get('rej_ambiguity_pct')) for m in all_metrics]
        )
    if any(m.get('stationary_quality') is not None for m in all_metrics):
        table_rows.append(
            ['Stationary quality score'] + [
                pct(m.get('stationary_quality')) for m in all_metrics
            ]
        )

    # ── Build the HTML ────────────────────────────────────────────────────────
    def chart_div(div_id: str, traces: list, layout_extra: dict = None, height: int = 340) -> str:
        layout = {
            'paper_bgcolor': '#1a1a2e', 'plot_bgcolor': '#16213e',
            'font': {'color': '#e0e0e0', 'size': 11},
            'legend': {'bgcolor': 'rgba(0,0,0,0)', 'font': {'size': 10}},
            'margin': {'l': 50, 'r': 20, 't': 30, 'b': 40},
            'height': height,
        }
        if layout_extra:
            layout.update(layout_extra)
        return f'''
<div id="{div_id}" style="width:100%;height:{height}px;"></div>
<script>
Plotly.newPlot({_j(div_id)},{_j(traces)},{_j(layout)},{{responsive:true,displayModeBar:false}});
</script>'''

    def section(title: str, content: str) -> str:
        return f'<section class="card"><h2>{title}</h2>{content}</section>'

    def two_col(*divs) -> str:
        return '<div class="two-col">' + ''.join(
            f'<div class="col">{d}</div>' for d in divs
        ) + '</div>'

    grid_layout = {'xaxis': {'gridcolor': '#2a2a4a'}, 'yaxis': {'gridcolor': '#2a2a4a'}}

    # Build table HTML
    thead = '<tr>' + ''.join(f'<th>{h}</th>' for h in table_header) + '</tr>'
    tbody = ''.join(
        '<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>'
        for row in table_rows
    )

    # Stationary quality score callout
    sq_callout = ''
    if any(m.get('stationary_quality') is not None for m in all_metrics):
        sq_items = ''.join(
            f'<div class="sq-item"><div class="sq-label">{m["camera"]}</div>'
            f'<div class="sq-val {"sq-good" if (m.get("stationary_quality") or 0) > 70 else "sq-bad"}">'
            f'{pct(m.get("stationary_quality"))}</div></div>'
            for m in all_metrics
        )
        sq_callout = f'<div class="sq-row">{sq_items}</div>'

    # New-format extra sections
    new_fmt_sections = ''
    if fmt == 'new' and z_traces:
        new_fmt_sections += section('Z-Height Distribution (Calibration)',
            two_col(
                chart_div('ch_z', z_traces, {
                    **grid_layout,
                    'barmode': 'overlay',
                    'xaxis': {'title': 'Z height (m)', 'gridcolor': '#2a2a4a'},
                    'yaxis': {'title': 'Samples', 'gridcolor': '#2a2a4a'},
                    'shapes': [{'type': 'line', 'x0': 0, 'x1': 0, 'y0': 0, 'y1': 1,
                                'yref': 'paper', 'line': {'color': '#fff', 'dash': 'dot', 'width': 1}}],
                }),
                chart_div('ch_amb', amb_traces, {
                    **grid_layout,
                    'barmode': 'overlay',
                    'xaxis': {'title': 'Ambiguity (single-tag)', 'gridcolor': '#2a2a4a'},
                    'yaxis': {'title': 'Samples', 'gridcolor': '#2a2a4a'},
                    'shapes': [{'type': 'line', 'x0': 0.2, 'x1': 0.2, 'y0': 0, 'y1': 1,
                                'yref': 'paper',
                                'line': {'color': '#F39C12', 'dash': 'dash', 'width': 1}}],
                }),
            )
        )

    vel_section = ''
    if vel_traces:
        vel_section = section('Acceptance Rate by Robot Motion State',
            '<p class="note">Stationary quality score is the key metric: removes motion as a confounder. '
            'Low score here points to a camera-intrinsic problem.</p>' +
            chart_div('ch_vel', vel_traces, {
                **grid_layout,
                'barmode': 'group',
                'yaxis': {'title': 'Acceptance rate (%)', 'range': [0, 105], 'gridcolor': '#2a2a4a'},
                'shapes': [{'type': 'line', 'x0': -0.5, 'x1': 3.5, 'y0': 80, 'y1': 80,
                            'line': {'color': '#27ae60', 'dash': 'dot', 'width': 1}}],
            }, height=300)
        )

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Vision Dashboard — {log_name}</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f0f1a; color: #e0e0e0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 16px; }}
  h1 {{ font-size: 1.3rem; font-weight: 600; color: #90caf9; margin-bottom: 4px; }}
  .subtitle {{ font-size: 0.82rem; color: #888; margin-bottom: 16px; }}
  h2 {{ font-size: 0.95rem; font-weight: 600; color: #b0bec5; margin-bottom: 10px; }}
  .card {{ background: #1a1a2e; border: 1px solid #2a2a4a; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  .col {{ min-width: 0; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ background: #16213e; color: #90caf9; padding: 6px 10px; text-align: left; border-bottom: 1px solid #2a2a4a; }}
  td {{ padding: 5px 10px; border-bottom: 1px solid #1e1e3a; }}
  tr:hover td {{ background: #16213e; }}
  .note {{ font-size: 0.78rem; color: #888; margin-bottom: 10px; font-style: italic; }}
  .sq-row {{ display: flex; gap: 20px; margin-bottom: 14px; }}
  .sq-item {{ text-align: center; }}
  .sq-label {{ font-size: 0.78rem; color: #888; margin-bottom: 4px; }}
  .sq-val {{ font-size: 1.6rem; font-weight: 700; }}
  .sq-good {{ color: #27ae60; }}
  .sq-bad  {{ color: #e74c3c; }}
  @media (max-width: 700px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<h1>Vision Log Dashboard</h1>
<div class="subtitle">
  {log_name} &nbsp;·&nbsp; {duration_sec:.0f}s &nbsp;·&nbsp;
  Cameras: {", ".join(cameras)} &nbsp;·&nbsp;
  Format: {"new (raw pre-filter)" if fmt == "new" else "old (post-filter)"}
  {("&nbsp;·&nbsp;" + metadata.get("ProjectName", "") + " @ " + metadata.get("GitHash", "")[:7])
   if metadata.get("ProjectName") else ""}
</div>

{section("Camera Summary",
    sq_callout +
    f'<table><thead>{thead}</thead><tbody>{tbody}</tbody></table>'
)}

{section("Acceptance Rate Over Time (3 s rolling)",
    '<p class="note">Per-loop acceptance rate smoothed over a 3-second window. Drops indicate '
    'the filter is rejecting more estimates — check if correlated with robot motion below.</p>' +
    chart_div('ch_acc', acc_rate_traces, {
        **grid_layout,
        'yaxis': {'title': 'Acceptance rate (%)', 'range': [0, 105], 'gridcolor': '#2a2a4a'},
        'xaxis': {'title': 'Time (s)', 'gridcolor': '#2a2a4a'},
    })
)}

{section("FPS Timeline",
    chart_div('ch_fps', fps_traces, {
        **grid_layout,
        'yaxis': {'title': 'Frames per second', 'gridcolor': '#2a2a4a'},
        'xaxis': {'title': 'Time (s)', 'gridcolor': '#2a2a4a'},
    }, height=260)
)}

{section("Rejection Breakdown (% of rejected results)",
    '<p class="note">Velocity rejections are expected during fast motion. Boundary rejections '
    'at low velocity suggest calibration issues. Ambiguity rejections indicate single-tag '
    'observations with uncertain orientation.</p>' +
    chart_div('ch_rej', rej_bars, {
        **grid_layout,
        'barmode': 'stack',
        'yaxis': {'title': '% of rejected', 'gridcolor': '#2a2a4a'},
    }, height=280)
)}

{section("Field Coverage Map",
    '<p class="note">Tags colored by detection frequency (green=often, red=rarely/never). '
    'Dots show robot positions where vision accepted an estimate.</p>' +
    chart_div('ch_field', field_traces, {
        'paper_bgcolor': '#1a1a2e', 'plot_bgcolor': '#101020',
        'xaxis': {'title': 'X (m)', 'scaleanchor': 'y', 'scaleratio': 1, 'gridcolor': '#2a2a4a'},
        'yaxis': {'title': 'Y (m)', 'gridcolor': '#2a2a4a'},
        'showlegend': True,
        'margin': {'l': 50, 'r': 20, 't': 30, 'b': 40},
    }, height=420)
)}

{two_col(
    section("Distance Distribution (m)",
        '<p class="note">Accepted estimates only. Close range = high quality.</p>' +
        chart_div('ch_dist', dist_traces, {
            **grid_layout,
            'barmode': 'overlay',
            'xaxis': {'title': 'Avg distance (m)', 'gridcolor': '#2a2a4a'},
            'yaxis': {'title': 'Samples', 'gridcolor': '#2a2a4a'},
        }, height=280)
    ),
    section("Weight / Trust Distribution" if fmt == "old" else "Mean Tag Area Distribution",
        ('<p class="note">Higher weight = more influence on pose estimator.</p>' +
         chart_div('ch_wt', weight_traces, {
             **grid_layout,
             'barmode': 'overlay',
             'xaxis': {'title': 'Weight scalar', 'range': [0, 1.05], 'gridcolor': '#2a2a4a'},
             'yaxis': {'title': 'Samples', 'gridcolor': '#2a2a4a'},
         }, height=280)
        ) if fmt == 'old' else
        ('<p class="note">Higher area = larger/closer tags, more reliable.</p>' +
         chart_div('ch_area', [{
             'x': _histogram_data(m.get("areas",[]))[0],
             'y': _histogram_data(m.get("areas",[]))[1],
             'name': m["camera"], 'type': 'bar', 'opacity': 0.7,
             'marker': {'color': _cam_color(m["camera"])},
         } for m in all_metrics], {
             **grid_layout,
             'barmode': 'overlay',
             'xaxis': {'title': 'Sum tag area', 'gridcolor': '#2a2a4a'},
             'yaxis': {'title': 'Samples', 'gridcolor': '#2a2a4a'},
         }, height=280)
        ) if fmt == 'new' else ''
    )
)}

{vel_section}

{new_fmt_sections}

</body>
</html>'''

    return html


# ─── Main ─────────────────────────────────────────────────────────────────────

def probe_signals(path: str) -> None:
    """Print all signal names and types in the log, then exit."""
    signals = parse_wpilog(path)
    print(f"\n{'─' * 60}")
    print(f"Signals in {pathlib.Path(path).name}  ({len(signals)} entries)")
    print('─' * 60)
    # Group by top-level namespace
    by_ns: Dict[str, list] = defaultdict(list)
    for name in sorted(signals):
        ns = name.split('/')[0] if '/' in name else '(root)'
        sample = signals[name]
        typ = type(sample[0][1]).__name__ if sample else '?'
        count = len(sample)
        by_ns[ns].append(f'  {name}  [{typ}, {count} samples]')
    for ns, items in sorted(by_ns.items()):
        print(f'\n[{ns}]')
        for item in items:
            print(item)
    print()


def process_log(log_path: str, output_dir: Optional[str]) -> None:
    print(f"Reading {log_path} …", end=' ', flush=True)
    signals = parse_wpilog(log_path)
    print(f"{len(signals)} signals found.")

    cameras = discover_cameras(signals)
    if not cameras:
        print("  No vision cameras found in this log (no Vision/<name>/connected signal). Skipping.")
        return

    print(f"  Cameras: {cameras}")

    # Log time range from any signal present
    all_ts = [t for sig in signals.values() for t, _ in sig]
    start_t  = min(all_ts) if all_ts else 0.0
    end_t    = max(all_ts) if all_ts else 0.0
    duration = end_t - start_t

    # Metadata
    meta: Dict[str, str] = {}
    for key in ('RealMetadata/ProjectName', 'RealMetadata/GitHash', 'RealMetadata/RuntimeType'):
        if key in signals and signals[key]:
            meta[key.split('/')[-1]] = str(signals[key][-1][1])

    # Drivetrain speeds
    lin_key, omega_key = find_drivetrain_speeds(signals)
    linear_sig = signals[lin_key] if lin_key else None
    omega_sig  = signals[omega_key] if omega_key else None
    if lin_key:
        print(f"  Drivetrain: {lin_key} / {omega_key}")
    else:
        print("  Drivetrain speed signals not found — velocity correlation skipped.")

    all_metrics = []
    for cam in cameras:
        fmt = detect_format(signals, cam)
        print(f"  {cam}: {fmt} format", end=' … ', flush=True)
        m = compute_camera_metrics(
            signals, cam, fmt, start_t, end_t, linear_sig, omega_sig
        )
        all_metrics.append(m)
        sq = m.get('stationary_quality')
        sq_str = f'{sq:.0f}%' if sq is not None else 'n/a'
        print(f"acceptance={m['acceptance_rate']:.0f}%  stationary_quality={sq_str}")

    log_name = pathlib.Path(log_path).name
    html = generate_html(all_metrics, log_name, duration, meta)

    # Output path
    out_dir = pathlib.Path(output_dir) if output_dir else pathlib.Path(log_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = pathlib.Path(log_path).stem
    out_path = out_dir / f'{stem}_vision_dashboard.html'
    out_path.write_text(html, encoding='utf-8')
    print(f"  → {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Vision Log Analyzer — generate an HTML dashboard from a .wpilog file.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('paths', nargs='+', help='.wpilog file(s) or a directory containing them')
    parser.add_argument('--output', '-o', metavar='DIR',
                        help='Directory to write HTML reports (default: same as log file)')
    parser.add_argument('--probe', action='store_true',
                        help='Dump all signal names and types, then exit (no dashboard generated)')
    args = parser.parse_args()

    log_files: List[str] = []
    for p in args.paths:
        pp = pathlib.Path(p)
        if pp.is_dir():
            log_files.extend(str(f) for f in sorted(pp.glob('*.wpilog')))
        elif pp.suffix == '.wpilog':
            log_files.append(str(pp))
        else:
            print(f"Warning: {p} is not a .wpilog file or directory, skipping.", file=sys.stderr)

    if not log_files:
        print("No .wpilog files found.", file=sys.stderr)
        sys.exit(1)

    if args.probe:
        for lf in log_files:
            probe_signals(lf)
        return

    for lf in log_files:
        try:
            process_log(lf, args.output)
        except Exception as e:
            print(f"Error processing {lf}: {e}", file=sys.stderr)
            import traceback; traceback.print_exc()


if __name__ == '__main__':
    main()
