#!/usr/bin/env python3
"""
Vision Log Analyzer — interactive Streamlit dashboard from a WPILib .wpilog file.

Dependencies: streamlit plotly   (pip install streamlit plotly)

Usage:
    streamlit run analyze.py                    # browser opens; pick log in sidebar
    python analyze.py --probe path/to/log.wpilog  # dump all signal names/types, exit
    python analyze.py path/to/log.wpilog          # (legacy) write _vision_dashboard.html
"""

import argparse
import bisect
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

REEF_TAG_IDS = frozenset({6, 7, 8, 9, 10, 11, 17, 18, 19, 20, 21, 22})

POSE2D_SIZE = 24   # double x, double y, double rotation_radians
POSE3D_SIZE = 56   # double x,y,z, double qw,qx,qy,qz


# ─── WPILog Binary Parser ─────────────────────────────────────────────────────

def parse_wpilog(path: str) -> Dict[str, List[Tuple[float, Any]]]:
    """
    Parse a WPILib DataLog (.wpilog) file.

    Returns a dict mapping signal name -> list of (timestamp_seconds, value) tuples.
    Values are decoded based on the type string registered in the log:
      boolean        -> bool
      int64          -> int
      double         -> float
      double[]       -> list[float]
      int64[]        -> list[int]
      boolean[]      -> list[bool]
      struct:Pose2d  -> list[dict] with keys x, y, rot
      struct[]:Pose2d -> list[dict] with keys x, y, rot   (0 or more per record)
      struct:Pose3d  -> list[dict] with keys x, y, z, qw, qx, qy, qz
      struct[]:Pose3d -> list[dict] (0 or more per record)
    Unknown types are silently skipped.
    """
    raw = pathlib.Path(path).read_bytes()
    pos = 0

    if len(raw) < 12 or raw[0:6] != b'WPILOG':
        raise ValueError(f"Not a WPILog file (bad magic): {path}")
    extra_len = struct.unpack_from('<I', raw, 8)[0]
    pos = 12 + extra_len

    entries: Dict[int, Dict[str, str]] = {}
    signals: Dict[str, List[Tuple[float, Any]]] = defaultdict(list)

    while pos < len(raw):
        if pos >= len(raw):
            break
        bitfield = raw[pos]
        pos += 1

        eid_sz   = (bitfield & 0x3) + 1
        psz_sz   = ((bitfield >> 2) & 0x3) + 1
        tsz      = ((bitfield >> 4) & 0xF) + 1

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
    if ctrl != 0:
        return
    pos = 1
    if pos + 4 > len(payload):
        return
    new_id = struct.unpack_from('<I', payload, pos)[0]
    pos += 4
    name,     pos = _lp_str(payload, pos)
    type_str, pos = _lp_str(payload, pos)
    entries[new_id] = {'name': name.lstrip('/'), 'type': type_str}


def _lp_str(data: bytes, pos: int) -> Tuple[str, int]:
    if pos + 4 > len(data):
        return '', pos
    length = struct.unpack_from('<I', data, pos)[0]
    pos += 4
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


# ─── Signal Discovery ─────────────────────────────────────────────────────────

def discover_cameras(signals: Dict) -> List[str]:
    cameras = []
    for key in signals:
        parts = key.split('/')
        if len(parts) >= 3 and parts[0] == 'Vision' and parts[2].lower() == 'connected':
            cam = parts[1]
            if cam not in cameras:
                cameras.append(cam)
    return sorted(cameras)


def detect_format(signals: Dict, camera: str) -> str:
    prefix = f'Vision/{camera}/'
    return 'new' if (
        f'{prefix}rawEstimatedPoses' in signals
        or f'{prefix}RawEstimatedPoses' in signals
        or f'RealOutputs/{prefix}RawEstimatedPoses' in signals
    ) else 'old'


def find_drivetrain_speeds(signals: Dict) -> Tuple[Optional[str], Optional[str]]:
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

    def fuzzy(candidates):
        for c in candidates:
            if c in signals:
                return c
        for key in signals:
            kl = key.lower()
            if 'vxmeters' in kl or ('speed' in kl and 'vx' in kl):
                return key
        return None

    linear_key = fuzzy(candidates_linear)

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

def build_timeline(signal: List[Tuple[float, Any]], start_t: float) -> Tuple[List[float], List[Any]]:
    ts = [t - start_t for t, _ in signal]
    vs = [v for _, v in signal]
    return ts, vs


def nearest_value(signal: List[Tuple[float, Any]], target_t: float,
                  _ts_cache: Dict = {}) -> Optional[Any]:
    """Return value at the timestamp closest to target_t. O(log n) via bisect with cache."""
    if not signal:
        return None
    key = id(signal)
    if key not in _ts_cache:
        _ts_cache[key] = [r[0] for r in signal]
    ts = _ts_cache[key]
    idx = bisect.bisect_left(ts, target_t)
    if idx == 0:
        best = signal[0]
    elif idx >= len(signal):
        best = signal[-1]
    else:
        lo, hi = signal[idx - 1], signal[idx]
        best = lo if abs(lo[0] - target_t) <= abs(hi[0] - target_t) else hi
    if abs(best[0] - target_t) > 1.0:
        return None
    return best[1]


def _histogram_data(values: List[float], nbins: int = 30) -> Tuple[List[float], List[int]]:
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
    """O(n) rolling mean using a two-pointer sliding window."""
    if not ts:
        return [], []
    out_ts, out_vs = [], []
    running_sum = 0.0
    lo = 0
    for hi in range(len(ts)):
        running_sum += vs[hi]
        while ts[hi] - ts[lo] > window:
            running_sum -= vs[lo]
            lo += 1
        out_ts.append(ts[hi])
        out_vs.append(running_sum / (hi - lo + 1))
    return out_ts, out_vs


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
    Compute all per-camera metrics. Returns a dict ready for the dashboard.
    Works with both old (pre-refactoring) and new (post-refactoring) signal formats.
    """
    prefix = f'Vision/{camera}/'

    def sig(name):
        result = signals.get(prefix + name)
        if result is None and name:
            pascal = name[0].upper() + name[1:]
            result = signals.get(prefix + pascal)
        if result is None and name:
            # AdvantageKit @AutoLogOutput fields land under RealOutputs/
            result = signals.get('RealOutputs/' + prefix + name)
        if result is None and name:
            pascal = name[0].upper() + name[1:]
            result = signals.get('RealOutputs/' + prefix + pascal)
        return result if result is not None else []

    m: Dict[str, Any] = {'camera': camera, 'format': fmt}

    # FPS timeline
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

    # Connection timeline
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

    if fmt == 'old':
        rej_vel_sig  = sig('rejectionCountVelocity')
        rej_bnd_sig  = sig('rejectionCountBoundary')
        poses_sig    = sig('estimatedPoses')
        dists_sig    = sig('estimateAvgDistancesMeters')
        weights_sig  = sig('estimateWeightScalars')
        ts_est_sig   = sig('estimateTimestampsSec')
        tags_sig     = sig('visibleTagIds')

        acc_ts, acc_counts, rej_v_counts, rej_b_counts = [], [], [], []
        all_distances, all_weights = [], []
        tag_freq: Dict[int, int] = defaultdict(int)
        path_x, path_y = [], []

        for t, poses in poses_sig:
            accepted = len(poses)
            rej_v = nearest_value(rej_vel_sig, t) or 0
            rej_b = nearest_value(rej_bnd_sig, t) or 0
            acc_ts.append(t - start_t)
            acc_counts.append(accepted)
            rej_v_counts.append(rej_v)
            rej_b_counts.append(rej_b)
            if accepted > 0:
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

        m['acc_ts']          = acc_ts
        m['acc_counts']      = acc_counts
        m['rej_v_counts']    = rej_v_counts
        m['rej_b_counts']    = rej_b_counts
        m['total_accepted']  = total_accepted
        m['total_rejected']  = total_rejected
        m['total_results']   = total_results
        m['acceptance_rate'] = 100.0 * total_accepted / total_results if total_results else 0.0
        m['rej_velocity_pct'] = 100.0 * sum(rej_v_counts) / total_results if total_results else 0.0
        m['rej_boundary_pct'] = 100.0 * sum(rej_b_counts) / total_results if total_results else 0.0
        m['distances']  = all_distances
        m['weights']    = all_weights
        m['tag_freq']   = {int(k): v for k, v in tag_freq.items()}
        m['path_x']     = path_x
        m['path_y']     = path_y

        latencies = []
        for (ts_loop, poses), (_, ts_est) in zip(poses_sig, ts_est_sig):
            for est_ts in ts_est:
                lat = ts_loop - est_ts
                if 0.0 < lat < 2.0:
                    latencies.append(lat * 1000.0)
        m['latencies_ms']    = latencies
        m['latency_mean_ms'] = sum(latencies) / len(latencies) if latencies else 0.0

    else:  # fmt == 'new'
        raw_poses_sig = sig('rawEstimatedPoses')
        amb_sig       = sig('rawAmbiguities')
        area_sig      = sig('rawSumTagAreas')
        px_sig        = sig('rawAvgNormalizedPixelOffsets')
        ar_sig        = sig('rawAvgAspectRatioDevs')
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
        tag_freq = defaultdict(int)
        path_x, path_y = [], []
        latencies = []

        for t, raw_poses in raw_poses_sig:
            rej_b     = nearest_value(rej_bnd_sig,   t) or 0
            rej_v     = nearest_value(rej_vel_sig,   t) or 0
            rej_a     = nearest_value(rej_amb_sig,   t) or 0
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

            raw_ts = nearest_value(raw_ts_sig, t) or []
            for est_ts in raw_ts:
                lat = t - est_ts
                if 0.0 < lat < 2.0:
                    latencies.append(lat * 1000.0)

        multi_tag_count  = 0
        single_tag_count = 0
        for _, ambs in amb_sig:
            for a in ambs:
                if a < 0:
                    multi_tag_count += 1
                else:
                    single_tag_count += 1
                    ambiguities.append(a)
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

        m['acc_ts']            = acc_ts
        m['acc_counts']        = acc_counts
        m['rej_v_counts']      = rej_v_counts
        m['rej_b_counts']      = rej_b_counts
        m['rej_a_counts']      = rej_a_counts
        m['raw_counts']        = raw_counts
        m['total_accepted']    = total_accepted
        m['total_raw']         = total_raw
        m['total_results']     = total_raw
        m['acceptance_rate']    = 100.0 * total_accepted / total_raw if total_raw else 0.0
        m['rej_velocity_pct']  = 100.0 * sum(rej_v_counts) / total_raw if total_raw else 0.0
        m['rej_boundary_pct']  = 100.0 * sum(rej_b_counts) / total_raw if total_raw else 0.0
        m['rej_ambiguity_pct'] = 100.0 * sum(rej_a_counts) / total_raw if total_raw else 0.0
        m['multi_tag_count']   = multi_tag_count
        m['single_tag_count']  = single_tag_count
        m['z_heights']         = z_heights
        m['ambiguities']       = ambiguities
        m['distances']         = all_distances
        m['areas']             = areas
        m['px_offsets']        = px_offsets
        m['aspect_ratios']     = aspect_ratios
        m['tag_freq']          = {int(k): v for k, v in tag_freq.items()}
        m['path_x']            = path_x
        m['path_y']            = path_y
        m['latencies_ms']      = latencies
        m['latency_mean_ms']   = sum(latencies) / len(latencies) if latencies else 0.0

    # Velocity-correlated quality
    if linear_sig and omega_sig and acc_ts:
        buckets: Dict[str, List[float]] = {'stationary': [], 'slow': [], 'rotating': [], 'fast': []}
        for i, t_rel in enumerate(acc_ts):
            t_abs     = t_rel + start_t
            lin_v     = nearest_value(linear_sig, t_abs)
            omega_v   = nearest_value(omega_sig,  t_abs)
            if lin_v is None or omega_v is None:
                continue
            lin_abs   = abs(lin_v)
            omega_abs = abs(omega_v)
            raw_n = m.get('raw_counts', [
                m.get('acc_counts', [0])[i]
                + m.get('rej_v_counts', [0])[i]
                + m.get('rej_b_counts', [0])[i]
            ])[i]
            if raw_n > 0:
                accepted_n = acc_counts[i]
                if lin_abs < 0.20 and omega_abs < 0.30:
                    bucket = 'stationary'
                elif omega_abs >= 1.50:
                    bucket = 'rotating'
                elif lin_abs > 2.00 or omega_abs > 4.00:
                    bucket = 'fast'
                else:
                    bucket = 'slow'
                buckets[bucket].append(accepted_n / raw_n)

        m['velocity_buckets'] = {
            k: {'count': len(v), 'acceptance_rate': 100.0 * sum(v) / len(v) if v else 0.0}
            for k, v in buckets.items()
        }
        m['stationary_quality'] = m['velocity_buckets']['stationary']['acceptance_rate']
    else:
        m['velocity_buckets']   = {}
        m['stationary_quality'] = None

    return m


# ─── Dashboard Helpers ────────────────────────────────────────────────────────

_COLORS = {
    'Left':  {'primary': '#4FC3F7', 'secondary': '#0288D1'},
    'Right': {'primary': '#AED581', 'secondary': '#558B2F'},
}
_DEFAULT_COLOR = {'primary': '#FFB74D', 'secondary': '#E65100'}


def _cam_color(camera: str, role: str = 'primary') -> str:
    return _COLORS.get(camera, _DEFAULT_COLOR)[role]


def _downsample(ts: List, vs: List, max_pts: int = 2000) -> Tuple[List, List]:
    if len(ts) <= max_pts:
        return ts, vs
    stride = max(1, len(ts) // max_pts)
    return ts[::stride], vs[::stride]


def _field_fig(metrics: List[Dict]) -> Any:
    """Build the field coverage Plotly figure (no Streamlit dependency)."""
    import plotly.graph_objects as go

    combined_tag_freq: Dict[int, int] = defaultdict(int)
    for m in metrics:
        for tag_id, cnt in m['tag_freq'].items():
            combined_tag_freq[tag_id] += cnt

    tag_ids    = list(APRILTAG_POSITIONS.keys())
    seen_ids   = [t for t in tag_ids if combined_tag_freq.get(t, 0) > 0]
    unseen_ids = [t for t in tag_ids if combined_tag_freq.get(t, 0) == 0]
    max_freq   = max((combined_tag_freq[t] for t in seen_ids), default=1)

    def log_norm(count: int) -> float:
        return math.log1p(count) / math.log1p(max_freq) if max_freq > 0 else 0.0

    fig = go.Figure()

    # Field boundary
    fig.add_trace(go.Scatter(
        x=[0, FIELD_LENGTH, FIELD_LENGTH, 0, 0],
        y=[0, 0, FIELD_WIDTH, FIELD_WIDTH, 0],
        mode='lines', line=dict(color='#555', width=1),
        showlegend=False, hoverinfo='skip',
    ))

    # Never-seen tags (fixed red)
    if unseen_ids:
        fig.add_trace(go.Scatter(
            x=[APRILTAG_POSITIONS[t][0] for t in unseen_ids],
            y=[APRILTAG_POSITIONS[t][1] for t in unseen_ids],
            text=[
                f'Tag {t}<br>Never seen' + ('<br>REEF' if t in REEF_TAG_IDS else '')
                for t in unseen_ids
            ],
            mode='markers+text', textposition='top center',
            textfont=dict(size=8),
            marker=dict(size=14, color='#c0392b', line=dict(color='white', width=1)),
            name='Never seen',
            hovertemplate='%{text}<extra></extra>',
        ))

    # Seen tags — log-normalized orange->green gradient
    if seen_ids:
        fig.add_trace(go.Scatter(
            x=[APRILTAG_POSITIONS[t][0] for t in seen_ids],
            y=[APRILTAG_POSITIONS[t][1] for t in seen_ids],
            text=[
                f'Tag {t}<br>Seen {combined_tag_freq[t]}x'
                + ('<br>REEF' if t in REEF_TAG_IDS else '')
                for t in seen_ids
            ],
            mode='markers+text', textposition='top center',
            textfont=dict(size=8),
            marker=dict(
                size=14,
                color=[log_norm(combined_tag_freq[t]) for t in seen_ids],
                colorscale=[[0, '#f39c12'], [1.0, '#27ae60']],
                cmin=0, cmax=1,
                colorbar=dict(
                    title='Relative freq<br>(log scale)', len=0.4,
                    tickvals=[0, 0.5, 1.0], ticktext=['rarely', '~mid', 'most'],
                ),
                line=dict(color='white', width=1),
            ),
            name='AprilTags',
            hovertemplate='%{text}<extra></extra>',
        ))

    # Robot paths per camera
    for m in metrics:
        cam = m['camera']
        if m['path_x']:
            fig.add_trace(go.Scatter(
                x=m['path_x'], y=m['path_y'],
                name=f'{cam} path', mode='markers',
                marker=dict(size=3, color=_cam_color(cam), opacity=0.4),
            ))

    fig.update_layout(
        template='plotly_dark',
        xaxis=dict(title='X (m)', range=[0, FIELD_LENGTH]),
        yaxis=dict(title='Y (m)', range=[0, FIELD_WIDTH]),
        height=460,
        margin=dict(l=40, r=20, t=20, b=40),
    )
    return fig


# ─── Streamlit Dashboard ──────────────────────────────────────────────────────

def _filter_signals_by_time(signals: Dict, t_lo: float, t_hi: float) -> Dict:
    """Return signals containing only samples within [t_lo, t_hi]."""
    return {
        name: [(t, v) for t, v in samples if t_lo <= t <= t_hi]
        for name, samples in signals.items()
    }


def _compute_mode_spans(
    signals: Dict, start_t: float
) -> List[Tuple[float, float, str]]:
    """
    Return [(rel_start, rel_end, mode), ...] where mode is 'disabled', 'auto', or 'teleop'.
    Times are seconds relative to start_t.
    """
    enabled_sig = signals.get('DriverStation/Enabled', [])
    auto_sig    = signals.get('DriverStation/Autonomous', [])

    if not enabled_sig:
        return []

    auto_by_time   = {t: v for t, v in auto_sig}
    auto_ts_sorted = sorted(auto_by_time.keys())

    def get_auto(t: float) -> bool:
        if not auto_ts_sorted:
            return False
        idx = bisect.bisect_right(auto_ts_sorted, t) - 1
        return bool(auto_by_time[auto_ts_sorted[max(0, idx)]])

    spans: List[Tuple[float, float, str]] = []
    current_mode: Optional[str] = None
    span_start:   Optional[float] = None

    for t, enabled in enabled_sig:
        auto = get_auto(t)
        if enabled and auto:
            mode = 'auto'
        elif enabled:
            mode = 'teleop'
        else:
            mode = 'disabled'

        if mode != current_mode:
            if current_mode is not None and span_start is not None:
                spans.append((span_start - start_t, t - start_t, current_mode))
            current_mode = mode
            span_start   = t

    if current_mode is not None and span_start is not None:
        spans.append((span_start - start_t, enabled_sig[-1][0] - start_t, current_mode))

    return spans


def _mode_timeline_fig(
    mode_spans: List[Tuple[float, float, str]],
    duration:   float,
    sel_lo:     float,
    sel_hi:     float,
) -> Any:
    """Compact Plotly timeline: robot mode color bands + selected window overlay."""
    import plotly.graph_objects as go

    MODE_COLORS = {
        'auto':     'rgba(39, 174, 96, 0.62)',
        'teleop':   'rgba(41, 128, 185, 0.62)',
        'disabled': 'rgba(110, 110, 110, 0.50)',
    }

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=[0, duration], y=[0.5, 0.5],
        mode='markers', marker=dict(opacity=0),
        showlegend=False, hoverinfo='skip',
    ))

    for span_start, span_end, mode in mode_spans:
        fig.add_shape(
            type='rect',
            x0=span_start, x1=span_end,
            y0=0, y1=1, yref='paper',
            fillcolor=MODE_COLORS.get(mode, 'rgba(80,80,80,0.3)'),
            line_width=0,
        )
        span_dur = span_end - span_start
        if span_dur > max(duration * 0.06, 3):
            fig.add_annotation(
                x=(span_start + span_end) / 2, y=0.5, yref='paper',
                text=mode.capitalize(), showarrow=False,
                font=dict(color='white', size=10), opacity=0.9,
            )

    # Selected window overlay
    fig.add_shape(
        type='rect',
        x0=sel_lo, x1=sel_hi,
        y0=0, y1=1, yref='paper',
        fillcolor='rgba(255, 255, 255, 0.10)',
        line=dict(color='rgba(255,255,255,0.80)', width=1.5, dash='dot'),
    )

    fig.update_layout(
        template='plotly_dark',
        height=88,
        showlegend=False,
        xaxis=dict(range=[0, duration], title='Time (s from log start)',
                   showgrid=False, zeroline=False),
        yaxis=dict(visible=False, range=[0, 1]),
        margin=dict(l=40, r=10, t=4, b=30),
        plot_bgcolor='#111827',
        paper_bgcolor='#111827',
    )
    return fig


def _running_under_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False


def _load_log(path: str) -> Tuple[List[Dict], float, Dict, List[str]]:
    """Parse a wpilog and compute metrics for all cameras. Returns (metrics, duration, meta, cameras)."""
    signals = parse_wpilog(path)
    cameras = discover_cameras(signals)
    all_ts  = [t for sig in signals.values() for t, _ in sig]
    start_t = min(all_ts) if all_ts else 0.0
    end_t   = max(all_ts) if all_ts else 0.0

    meta: Dict[str, str] = {}
    for key in ('RealMetadata/ProjectName', 'RealMetadata/GitHash', 'RealMetadata/RuntimeType'):
        if key in signals and signals[key]:
            meta[key.split('/')[-1]] = str(signals[key][-1][1])

    lin_key, omega_key = find_drivetrain_speeds(signals)
    linear_sig = signals[lin_key] if lin_key else None
    omega_sig  = signals[omega_key] if omega_key else None

    all_metrics = []
    for cam in cameras:
        fmt = detect_format(signals, cam)
        m = compute_camera_metrics(signals, cam, fmt, start_t, end_t, linear_sig, omega_sig)
        all_metrics.append(m)

    return all_metrics, end_t - start_t, meta, cameras


def _streamlit_app() -> None:
    import plotly.graph_objects as go
    import streamlit as st

    st.set_page_config(
        page_title='Vision Dashboard',
        page_icon='📡',
        layout='wide',
        initial_sidebar_state='expanded',
    )
    st.title('Vision Log Dashboard')

    with st.sidebar:
        st.header('Log File')
        log_path = st.text_input(
            'Path to .wpilog',
            placeholder='logs/offseason/6-13-26/akit_26-06-13_17-05-06.wpilog',
        )

    if not log_path:
        st.info('Enter a path to a `.wpilog` file in the sidebar to begin.')
        return

    p = pathlib.Path(log_path)
    if not p.exists():
        st.error(f'File not found: `{log_path}`')
        return

    # ── Stage 1: parse signals (cached by path + mtime) ──────────────────────
    @st.cache_data(show_spinner='Scanning log...')
    def _scan_signals(path: str, mtime: float) -> Dict:
        return parse_wpilog(path)

    try:
        signals = _scan_signals(str(p), p.stat().st_mtime)
    except Exception as exc:
        st.error(f'Failed to parse log: {exc}')
        st.exception(exc)
        return

    all_ts   = [t for sig in signals.values() for t, _ in sig]
    start_t  = min(all_ts) if all_ts else 0.0
    duration = (max(all_ts) if all_ts else 0.0) - start_t

    # Reset session state when the log file changes
    if st.session_state.get('_log_path') != str(p):
        st.session_state['_log_path']        = str(p)
        st.session_state['_range']           = (0.0, float(duration))
        st.session_state['_range_committed'] = None

    # ── Time range selector ───────────────────────────────────────────────────
    mode_spans = _compute_mode_spans(signals, start_t)

    committed = st.session_state.get('_range_committed')
    with st.expander('**Time Range**', expanded=(committed is None)):
        st.caption(
            ':gray[■ Disabled]   '
            ':blue[■ Teleop]   '
            ':green[■ Autonomous]'
        )

        sel: Tuple[float, float] = st.slider(
            'Select window (seconds from log start)',
            min_value=0.0,
            max_value=float(duration),
            value=st.session_state['_range'],
            step=0.5,
            key='_time_slider',
        )
        st.session_state['_range'] = sel

        st.plotly_chart(
            _mode_timeline_fig(mode_spans, duration, sel[0], sel[1]),
            use_container_width=True,
            config={'displayModeBar': False},
            key='_mode_fig',
        )

        col_info, col_btn = st.columns([5, 1])
        with col_info:
            st.caption(
                f'Selected: **{sel[0]:.1f} s** to **{sel[1]:.1f} s** '
                f'({sel[1] - sel[0]:.1f} s of {duration:.1f} s total)'
            )
        with col_btn:
            if st.button('Analyze', type='primary', use_container_width=True):
                st.session_state['_range_committed'] = sel
                committed = sel

    if committed is None:
        st.info('Adjust the time range above and click **Analyze** to load the dashboard.')
        return

    t_lo = start_t + committed[0]
    t_hi = start_t + committed[1]

    # ── Stage 2: compute metrics for the committed window (cached) ────────────
    @st.cache_data(show_spinner='Analyzing...')
    def _compute_metrics(path: str, mtime: float, t_lo_k: float, t_hi_k: float):
        sig      = _scan_signals(path, mtime)          # instant — already cached
        filtered = _filter_signals_by_time(sig, t_lo_k, t_hi_k)
        cameras  = discover_cameras(filtered)

        ft_list  = [t for s in filtered.values() for t, _ in s]
        f_start  = min(ft_list) if ft_list else t_lo_k
        f_end    = max(ft_list) if ft_list else t_hi_k

        meta: Dict[str, str] = {}
        for key in ('RealMetadata/ProjectName', 'RealMetadata/GitHash', 'RealMetadata/RuntimeType'):
            if key in filtered and filtered[key]:
                meta[key.split('/')[-1]] = str(filtered[key][-1][1])

        lin_key, omega_key = find_drivetrain_speeds(filtered)
        linear_sig = filtered[lin_key]   if lin_key   else None
        omega_sig  = filtered[omega_key] if omega_key else None

        all_m = []
        for cam in cameras:
            fmt = detect_format(filtered, cam)
            m   = compute_camera_metrics(filtered, cam, fmt, f_start, f_end, linear_sig, omega_sig)
            all_m.append(m)

        return all_m, meta, cameras

    try:
        all_metrics, meta, cameras = _compute_metrics(
            str(p), p.stat().st_mtime,
            round(t_lo, 1), round(t_hi, 1),
        )
    except Exception as exc:
        st.error(f'Failed to compute metrics: {exc}')
        st.exception(exc)
        return

    if not all_metrics:
        st.warning('No vision cameras found in this log (no `Vision/<name>/connected` signal).')
        return

    fmt = all_metrics[0]['format']

    # Camera filter + info in sidebar
    with st.sidebar:
        selected = st.multiselect('Cameras', cameras, default=cameras)
        st.caption(f'Window: {committed[0]:.0f} s – {committed[1]:.0f} s '
                   f'({committed[1] - committed[0]:.0f} s)')
        st.caption(f'Format: {"new (raw pre-filter)" if fmt == "new" else "old (post-filter)"}')
        if meta.get('ProjectName'):
            st.caption(f'{meta["ProjectName"]} @ {meta.get("GitHash", "")[:7]}')

    metrics = [m for m in all_metrics if m['camera'] in selected]
    if not metrics:
        st.warning('No cameras selected.')
        return

    st.caption(
        f'`{p.name}`  ·  '
        f'{committed[0]:.0f} s – {committed[1]:.0f} s  ·  '
        f'cameras: {", ".join(cameras)}'
    )

    def pct(v: Optional[float]) -> str:
        return f'{v:.1f}%' if v is not None else '-'

    def ms_fmt(v: float) -> str:
        return f'{v:.0f} ms' if v else '-'

    # Tab layout
    tabs = st.tabs(['Summary', 'Health', 'Acceptance', 'Geometry', 'Field', 'Motion'])
    t_sum, t_health, t_accept, t_geo, t_field, t_motion = tabs

    # ── Summary ───────────────────────────────────────────────────────────────
    with t_sum:
        sq_vals = [m.get('stationary_quality') for m in metrics]
        if any(v is not None for v in sq_vals):
            cols = st.columns(len(metrics))
            for col, m, sq in zip(cols, metrics, sq_vals):
                if sq is not None:
                    col.metric(
                        f'{m["camera"]} stationary quality', pct(sq),
                        delta='good' if sq > 70 else 'low',
                        delta_color='normal' if sq > 70 else 'inverse',
                    )

        rows: Dict[str, List[str]] = {
            'Acceptance rate':     [pct(m['acceptance_rate']) for m in metrics],
            'FPS (mean)':          [f'{m["fps_mean"]:.1f}' for m in metrics],
            'FPS (min)':           [f'{m["fps_min"]:.1f}' for m in metrics],
            'Connection uptime':   [pct(m['conn_uptime_pct']) for m in metrics],
            'Mean result latency': [ms_fmt(m['latency_mean_ms']) for m in metrics],
            'Rejected (velocity)': [pct(m.get('rej_velocity_pct')) for m in metrics],
            'Rejected (boundary)': [pct(m.get('rej_boundary_pct')) for m in metrics],
        }
        if fmt == 'new':
            rows['Rejected (ambiguity)'] = [pct(m.get('rej_ambiguity_pct')) for m in metrics]
        if any(v is not None for v in sq_vals):
            rows['Stationary quality'] = [pct(m.get('stationary_quality')) for m in metrics]

        table_data: Dict[str, List] = {'Metric': list(rows.keys())}
        for cam_idx, m in enumerate(metrics):
            table_data[m['camera']] = [rows[metric][cam_idx] for metric in rows]
        st.table(table_data)

    # ── Health ────────────────────────────────────────────────────────────────
    with t_health:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader('FPS Over Time')
            fig = go.Figure()
            for m in metrics:
                ts, vs = _downsample(m['fps_ts'], m['fps_values'])
                fig.add_trace(go.Scatter(x=ts, y=vs, name=m['camera'], mode='lines',
                                          line=dict(color=_cam_color(m['camera']), width=1.5)))
            fig.update_layout(template='plotly_dark', height=280,
                               xaxis_title='Time (s)', yaxis_title='FPS',
                               margin=dict(l=40, r=10, t=20, b=40))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader('Connection Status')
            fig = go.Figure()
            for m in metrics:
                ts, vs = _downsample(m['conn_ts'], m['conn_values'])
                fig.add_trace(go.Scatter(x=ts, y=vs, name=m['camera'], mode='lines',
                                          line=dict(color=_cam_color(m['camera']), width=1.5,
                                                    shape='hv')))
            fig.update_layout(template='plotly_dark', height=280,
                               xaxis_title='Time (s)',
                               yaxis=dict(title='Connected', tickvals=[0, 1],
                                          ticktext=['No', 'Yes'], range=[-0.1, 1.4]),
                               margin=dict(l=40, r=10, t=20, b=40))
            st.plotly_chart(fig, use_container_width=True)

        if any(m['latencies_ms'] for m in metrics):
            st.subheader('Result Latency Distribution')
            fig = go.Figure()
            for m in metrics:
                if m['latencies_ms']:
                    centers, counts = _histogram_data(m['latencies_ms'])
                    fig.add_trace(go.Bar(x=centers, y=counts, name=m['camera'], opacity=0.7,
                                          marker_color=_cam_color(m['camera'])))
            fig.update_layout(template='plotly_dark', barmode='overlay', height=260,
                               xaxis_title='Latency (ms)', yaxis_title='Samples',
                               margin=dict(l=40, r=10, t=20, b=40))
            st.plotly_chart(fig, use_container_width=True)

    # ── Acceptance ────────────────────────────────────────────────────────────
    with t_accept:
        st.subheader('Acceptance Rate Over Time (3 s rolling)')
        st.caption('Per-loop acceptance rate smoothed over a 3-second window. '
                   'Drops indicate the filter rejecting more estimates.')
        fig = go.Figure()
        for m in metrics:
            ts = m['acc_ts']
            has_raw = 'raw_counts' in m
            totals = m['raw_counts'] if has_raw else [
                a + b + c for a, b, c in zip(
                    m['acc_counts'], m['rej_v_counts'],
                    m.get('rej_b_counts', [0] * len(m['acc_counts'])),
                )
            ]
            rates = [100.0 * a / t if t > 0 else 0.0 for a, t in zip(m['acc_counts'], totals)]
            rts, rvs = _rolling_mean(ts, rates, window=3.0)
            rts, rvs = _downsample(rts, rvs)
            fig.add_trace(go.Scatter(x=rts, y=rvs, name=m['camera'], mode='lines',
                                      line=dict(color=_cam_color(m['camera']), width=2)))
        fig.update_layout(template='plotly_dark', height=320,
                           xaxis_title='Time (s)',
                           yaxis=dict(title='Acceptance rate (%)', range=[0, 105]),
                           margin=dict(l=40, r=10, t=20, b=40))
        st.plotly_chart(fig, use_container_width=True)

        st.subheader('Rejection Breakdown (% of all raw results)')
        st.caption('Each bar shows what fraction of ALL raw results were rejected for that reason. '
                   'Velocity rejections at low speed or boundary rejections at rest indicate '
                   'calibration issues. Ambiguity rejections = single-tag near threshold (0.2).')
        fig = go.Figure()
        cam_names = [m['camera'] for m in metrics]
        fig.add_trace(go.Bar(x=cam_names, y=[m.get('rej_velocity_pct', 0) for m in metrics],
                              name='Velocity', marker_color='#E74C3C'))
        fig.add_trace(go.Bar(x=cam_names, y=[m.get('rej_boundary_pct', 0) for m in metrics],
                              name='Boundary', marker_color='#F39C12'))
        if fmt == 'new':
            fig.add_trace(go.Bar(x=cam_names, y=[m.get('rej_ambiguity_pct', 0) for m in metrics],
                                  name='Ambiguity', marker_color='#9B59B6'))
        fig.update_layout(template='plotly_dark', barmode='stack', height=280,
                           yaxis_title='% of all raw results',
                           margin=dict(l=40, r=10, t=20, b=40))
        st.plotly_chart(fig, use_container_width=True)

    # ── Geometry ──────────────────────────────────────────────────────────────
    with t_geo:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader('Distance Distribution')
            label = 'All raw estimates (pre-filter)' if fmt == 'new' else 'Accepted estimates only'
            st.caption(f'{label}. Close range = higher quality estimates.')
            fig = go.Figure()
            for m in metrics:
                centers, counts = _histogram_data(m['distances'])
                if centers:
                    fig.add_trace(go.Bar(x=centers, y=counts, name=m['camera'], opacity=0.7,
                                          marker_color=_cam_color(m['camera'])))
            fig.update_layout(template='plotly_dark', barmode='overlay', height=280,
                               xaxis_title='Avg distance (m)', yaxis_title='Samples',
                               margin=dict(l=40, r=10, t=20, b=40))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            if fmt == 'new':
                st.subheader('Tag Area Distribution')
                st.caption('Higher area = larger/closer tags, more reliable.')
                fig = go.Figure()
                for m in metrics:
                    centers, counts = _histogram_data(m.get('areas', []))
                    if centers:
                        fig.add_trace(go.Bar(x=centers, y=counts, name=m['camera'], opacity=0.7,
                                              marker_color=_cam_color(m['camera'])))
                fig.update_layout(template='plotly_dark', barmode='overlay', height=280,
                                   xaxis_title='Sum tag area', yaxis_title='Samples',
                                   margin=dict(l=40, r=10, t=20, b=40))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.subheader('Weight / Trust Distribution')
                st.caption('Higher weight = more influence on pose estimator.')
                fig = go.Figure()
                for m in metrics:
                    centers, counts = _histogram_data(m.get('weights', []))
                    if centers:
                        fig.add_trace(go.Bar(x=centers, y=counts, name=m['camera'], opacity=0.7,
                                              marker_color=_cam_color(m['camera'])))
                fig.update_layout(template='plotly_dark', barmode='overlay', height=280,
                                   xaxis=dict(title='Weight scalar', range=[0, 1.05]),
                                   yaxis_title='Samples',
                                   margin=dict(l=40, r=10, t=20, b=40))
                st.plotly_chart(fig, use_container_width=True)

        if fmt == 'new':
            col3, col4 = st.columns(2)

            with col3:
                st.subheader('Z-Height Distribution')
                st.caption('Should peak at 0. Non-zero mean indicates a calibration error '
                            '(height or pitch angle wrong in VisionConstants).')
                fig = go.Figure()
                for m in metrics:
                    centers, counts = _histogram_data(m.get('z_heights', []), nbins=40)
                    if centers:
                        fig.add_trace(go.Bar(x=centers, y=counts, name=m['camera'], opacity=0.7,
                                              marker_color=_cam_color(m['camera'])))
                fig.add_vline(x=0, line_dash='dot', line_color='white', line_width=1)
                fig.update_layout(template='plotly_dark', barmode='overlay', height=280,
                                   xaxis_title='Z height (m)', yaxis_title='Samples',
                                   margin=dict(l=40, r=10, t=20, b=40))
                st.plotly_chart(fig, use_container_width=True)

            with col4:
                st.subheader('Ambiguity Distribution (Single-Tag Only)')
                st.caption('Multi-tag results are excluded (they report -1 and have no ambiguity). '
                            'Rejection threshold at 0.2 — mass near there = operating near limit.')
                fig = go.Figure()
                for m in metrics:
                    centers, counts = _histogram_data(m.get('ambiguities', []), nbins=20)
                    if centers:
                        fig.add_trace(go.Bar(x=centers, y=counts, name=m['camera'], opacity=0.7,
                                              marker_color=_cam_color(m['camera'])))
                fig.add_vline(x=0.2, line_dash='dash', line_color='#F39C12', line_width=1,
                               annotation_text='reject', annotation_position='top right')
                fig.update_layout(template='plotly_dark', barmode='overlay', height=280,
                                   xaxis_title='Ambiguity', yaxis_title='Samples',
                                   margin=dict(l=40, r=10, t=20, b=40))
                st.plotly_chart(fig, use_container_width=True)

            # Single-tag vs multi-tag breakdown
            has_tag_type_data = any(
                m.get('multi_tag_count', 0) + m.get('single_tag_count', 0) > 0
                for m in metrics
            )
            if has_tag_type_data:
                st.subheader('Single-Tag vs Multi-Tag Results')
                st.caption(
                    'Multi-tag (2+ AprilTags in one estimate) is more reliable: no pose ambiguity, '
                    'better geometry. A high single-tag fraction at short range suggests tags are '
                    'being partially occluded or the camera FOV only sees one tag at a time.'
                )
                col5, col6 = st.columns(2)

                with col5:
                    fig = go.Figure()
                    cam_names = [m['camera'] for m in metrics]
                    fig.add_trace(go.Bar(
                        x=cam_names,
                        y=[m.get('multi_tag_count', 0) for m in metrics],
                        name='Multi-tag', marker_color='#27ae60',
                    ))
                    fig.add_trace(go.Bar(
                        x=cam_names,
                        y=[m.get('single_tag_count', 0) for m in metrics],
                        name='Single-tag', marker_color='#3498db',
                    ))
                    fig.update_layout(
                        template='plotly_dark', barmode='stack', height=280,
                        yaxis_title='Result count',
                        margin=dict(l=40, r=10, t=20, b=40),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                with col6:
                    # Multi-tag rate as a percentage
                    fig = go.Figure()
                    for m in metrics:
                        total = m.get('multi_tag_count', 0) + m.get('single_tag_count', 0)
                        multi_pct = 100.0 * m.get('multi_tag_count', 0) / total if total else 0.0
                        fig.add_trace(go.Bar(
                            x=[m['camera']], y=[multi_pct],
                            name=m['camera'], marker_color=_cam_color(m['camera']),
                        ))
                    fig.add_hline(y=50, line_dash='dot', line_color='white', line_width=1,
                                   annotation_text='50%', annotation_position='top right')
                    fig.update_layout(
                        template='plotly_dark', height=280,
                        yaxis=dict(title='Multi-tag rate (%)', range=[0, 105]),
                        margin=dict(l=40, r=10, t=20, b=40),
                    )
                    st.plotly_chart(fig, use_container_width=True)

    # ── Field ─────────────────────────────────────────────────────────────────
    with t_field:
        st.caption('Tags: red = never seen, orange -> green = detection frequency (log scale). '
                   'Dots = robot positions where vision accepted an estimate.')
        st.plotly_chart(_field_fig(metrics), use_container_width=True)

    # ── Motion ────────────────────────────────────────────────────────────────
    with t_motion:
        if any(m.get('velocity_buckets') for m in metrics):
            st.subheader('Acceptance Rate by Robot Motion State')
            st.caption('Stationary quality removes motion as a confounder. '
                       'Low stationary score points to a camera-intrinsic problem.')
            bucket_names  = ['stationary', 'slow', 'rotating', 'fast']
            bucket_labels = ['Stationary', 'Slow translate', 'Rotating', 'Full speed']
            fig = go.Figure()
            for m in metrics:
                bkts = m.get('velocity_buckets', {})
                fig.add_trace(go.Bar(
                    x=bucket_labels,
                    y=[bkts.get(b, {}).get('acceptance_rate', 0) for b in bucket_names],
                    name=m['camera'], opacity=0.85,
                    marker_color=_cam_color(m['camera']),
                ))
            fig.add_hline(y=80, line_dash='dot', line_color='#27ae60', line_width=1,
                           annotation_text='80% target', annotation_position='top right')
            fig.update_layout(template='plotly_dark', barmode='group', height=320,
                               yaxis=dict(title='Acceptance rate (%)', range=[0, 105]),
                               margin=dict(l=40, r=10, t=20, b=40))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info('Drivetrain speed signals not found in this log — '
                    'motion bucketing unavailable.')


# ─── CLI (legacy / probe mode) ────────────────────────────────────────────────

def probe_signals(path: str) -> None:
    signals = parse_wpilog(path)
    print(f"\n{'-' * 60}")
    print(f"Signals in {pathlib.Path(path).name}  ({len(signals)} entries)")
    print('-' * 60)
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


def _cli_main() -> None:
    parser = argparse.ArgumentParser(
        description='Vision Log Analyzer. Run with `streamlit run analyze.py` for the dashboard.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('paths', nargs='*', help='.wpilog file(s) or a directory')
    parser.add_argument('--output', '-o', metavar='DIR',
                        help='Output directory for HTML reports (legacy mode)')
    parser.add_argument('--probe', action='store_true',
                        help='Dump all signal names and types, then exit')
    args = parser.parse_args()

    if not args.paths:
        print('Usage: streamlit run analyze.py   (dashboard)')
        print('       python analyze.py --probe log.wpilog  (signal dump)')
        sys.exit(0)

    log_files: List[str] = []
    for p in args.paths:
        pp = pathlib.Path(p)
        if pp.is_dir():
            log_files.extend(str(f) for f in sorted(pp.glob('*.wpilog')))
        elif pp.suffix == '.wpilog':
            log_files.append(str(pp))
        else:
            print(f'Warning: {p} is not a .wpilog file or directory, skipping.',
                  file=sys.stderr)

    if not log_files:
        print('No .wpilog files found.', file=sys.stderr)
        sys.exit(1)

    if args.probe:
        for lf in log_files:
            probe_signals(lf)
        return

    # Legacy: write an HTML dashboard for backward compatibility
    for lf in log_files:
        try:
            print(f'Reading {lf} ...', end=' ', flush=True)
            all_metrics, duration, meta, cameras = _load_log(lf)
            print(f'{len(cameras)} cameras.')
            if not all_metrics:
                print('  No vision cameras found. Skipping.')
                continue
            for m in all_metrics:
                sq = m.get('stationary_quality')
                sq_str = f'{sq:.0f}%' if sq is not None else 'n/a'
                print(f'  {m["camera"]}: format={m["format"]}  '
                      f'acceptance={m["acceptance_rate"]:.0f}%  '
                      f'stationary_quality={sq_str}')
            # Generate a minimal HTML placeholder pointing to the Streamlit app
            out_dir  = pathlib.Path(args.output) if args.output else pathlib.Path(lf).parent
            out_dir.mkdir(parents=True, exist_ok=True)
            stem     = pathlib.Path(lf).stem
            out_path = out_dir / f'{stem}_vision_dashboard.html'
            _write_legacy_html(all_metrics, duration, meta, pathlib.Path(lf).name, out_path)
            print(f'  -> {out_path}')
        except Exception as e:
            print(f'Error processing {lf}: {e}', file=sys.stderr)
            import traceback; traceback.print_exc()


def _write_legacy_html(
    all_metrics: List[Dict],
    duration: float,
    meta: Dict,
    log_name: str,
    out_path: pathlib.Path,
) -> None:
    """Write a lightweight HTML that embeds the summary table and links to streamlit."""
    import json as _json

    cameras = [m['camera'] for m in all_metrics]
    fmt = all_metrics[0]['format'] if all_metrics else 'old'

    def pct(v):
        return f'{v:.1f}%' if v is not None else '-'

    rows = [
        ('Acceptance rate',     [pct(m['acceptance_rate']) for m in all_metrics]),
        ('FPS (mean)',          [f'{m["fps_mean"]:.1f}' for m in all_metrics]),
        ('Connection uptime',   [pct(m['conn_uptime_pct']) for m in all_metrics]),
        ('Mean result latency', [f'{m["latency_mean_ms"]:.0f} ms' if m["latency_mean_ms"] else '-'
                                 for m in all_metrics]),
        ('Rejected (velocity)', [pct(m.get('rej_velocity_pct')) for m in all_metrics]),
        ('Rejected (boundary)', [pct(m.get('rej_boundary_pct')) for m in all_metrics]),
    ]
    if fmt == 'new':
        rows.append(('Rejected (ambiguity)', [pct(m.get('rej_ambiguity_pct')) for m in all_metrics]))

    thead = '<tr><th>Metric</th>' + ''.join(f'<th>{c}</th>' for c in cameras) + '</tr>'
    tbody = ''.join(
        '<tr><td>' + row[0] + '</td>' + ''.join(f'<td>{v}</td>' for v in row[1]) + '</tr>'
        for row in rows
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Vision Dashboard - {log_name}</title>
<style>
body{{background:#0f0f1a;color:#e0e0e0;font-family:system-ui,sans-serif;padding:20px}}
h1{{color:#90caf9}}
.note{{color:#aaa;font-size:0.9em;margin:10px 0 20px}}
table{{border-collapse:collapse;width:100%}}
th{{background:#16213e;color:#90caf9;padding:8px 12px;text-align:left}}
td{{padding:6px 12px;border-bottom:1px solid #2a2a4a}}
</style></head>
<body>
<h1>Vision Dashboard - {log_name}</h1>
<p class="note">{duration:.0f} s &nbsp;|&nbsp; cameras: {', '.join(cameras)}
&nbsp;|&nbsp; format: {'new (raw pre-filter)' if fmt == 'new' else 'old (post-filter)'}
{'&nbsp;|&nbsp;' + meta.get('ProjectName','') + ' @ ' + meta.get('GitHash','')[:7]
 if meta.get('ProjectName') else ''}</p>
<p class="note">For the full interactive dashboard run:
<code>streamlit run tools/vision-analyzer/analyze.py</code></p>
<table><thead>{thead}</thead><tbody>{tbody}</tbody></table>
</body></html>"""
    out_path.write_text(html, encoding='utf-8')


# ─── Entry point ──────────────────────────────────────────────────────────────

if _running_under_streamlit():
    _streamlit_app()
elif __name__ == '__main__':
    _cli_main()
