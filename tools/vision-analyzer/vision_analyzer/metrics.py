"""
Metric computation: signal discovery, per-camera metrics, and chart helpers.
No Streamlit dependency; Plotly imports stay inside functions that need them.
"""
import bisect
import math
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from .constants import (
    APRILTAG_POSITIONS,
    FIELD_LENGTH,
    FIELD_WIDTH,
    REEF_TAG_IDS,
    _cam_color,
)

# Module-level cache for nearest_value — must NOT be a default argument
_ts_cache: Dict = {}


# ─── Signal Discovery ──────────────────────────────────────────────────────────

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


# ─── Timeline Helpers ──────────────────────────────────────────────────────────

def build_timeline(signal: List[Tuple[float, Any]], start_t: float) -> Tuple[List[float], List[Any]]:
    ts = [t - start_t for t, _ in signal]
    vs = [v for _, v in signal]
    return ts, vs


def nearest_value(signal: List[Tuple[float, Any]], target_t: float) -> Optional[Any]:
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


# ─── Chart Helpers ─────────────────────────────────────────────────────────────

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


def _bucket_sum(ts: List[float], counts: List[float], bucket: float = 1.0) -> Tuple[List[float], List[float]]:
    """Sum counts into fixed-width time buckets. With bucket=1.0 the result is a
    poses-per-second rate, since each bucket spans exactly one second."""
    if not ts:
        return [], []
    end = ts[-1]
    n_buckets = int(end // bucket) + 1
    sums = [0.0] * n_buckets
    for t, c in zip(ts, counts):
        idx = min(int(t // bucket), n_buckets - 1)
        sums[idx] += c
    bucket_ts = [i * bucket for i in range(n_buckets)]
    return bucket_ts, sums


def _downsample(ts: List, vs: List, max_pts: int = 2000) -> Tuple[List, List]:
    if len(ts) <= max_pts:
        return ts, vs
    stride = max(1, len(ts) // max_pts)
    return ts[::stride], vs[::stride]


# ─── Metric Computation ────────────────────────────────────────────────────────

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

    # Pose stability — rolling stddev of the last N accepted poses (mirrors
    # PhotonVision's "multi-tag pose standard deviation" dashboard panel).
    stddev_x_sig = sig('PoseStdDevXMeters')
    if stddev_x_sig:
        ts, vs_x = build_timeline(stddev_x_sig, start_t)
        _,  vs_y = build_timeline(sig('PoseStdDevYMeters'), start_t)
        _,  vs_t = build_timeline(sig('PoseStdDevThetaDegrees'), start_t)
        m['stddev_ts']        = ts
        m['stddev_x_m']       = vs_x
        m['stddev_y_m']       = vs_y
        m['stddev_theta_deg'] = vs_t
    else:
        m['stddev_ts'] = m['stddev_x_m'] = m['stddev_y_m'] = m['stddev_theta_deg'] = []

    # Same metric, time-bounded (last 1s) instead of count-bounded — reacts faster
    # to motion transitions; kept alongside the 100-sample one for comparison.
    stddev_x_1s_sig = sig('PoseStdDevXMeters1s')
    if stddev_x_1s_sig:
        ts, vs_x = build_timeline(stddev_x_1s_sig, start_t)
        _,  vs_y = build_timeline(sig('PoseStdDevYMeters1s'), start_t)
        _,  vs_t = build_timeline(sig('PoseStdDevThetaDegrees1s'), start_t)
        m['stddev_1s_ts']        = ts
        m['stddev_1s_x_m']       = vs_x
        m['stddev_1s_y_m']       = vs_y
        m['stddev_1s_theta_deg'] = vs_t
    else:
        m['stddev_1s_ts'] = m['stddev_1s_x_m'] = m['stddev_1s_y_m'] = m['stddev_1s_theta_deg'] = []

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
        rej_bnd_poses_sig = sig('RejectedBoundaryPoses')
        rej_vel_poses_sig = sig('RejectedVelocityPoses')
        rej_amb_poses_sig = sig('RejectedAmbiguityPoses')
        dists_sig     = sig('rawAvgDistancesMeters')
        raw_ts_sig    = sig('rawTimestampsSec')

        acc_ts, acc_counts, rej_v_counts, rej_b_counts, rej_a_counts = [], [], [], [], []
        raw_counts = []
        z_heights, ambiguities, all_distances = [], [], []
        areas, px_offsets, aspect_ratios = [], [], []
        tag_freq = defaultdict(int)
        path_x, path_y = [], []
        rej_boundary_path_x, rej_boundary_path_y = [], []
        rej_velocity_path_x, rej_velocity_path_y = [], []
        rej_ambiguity_path_x, rej_ambiguity_path_y = [], []
        latencies = []

        for _, rej_poses in rej_bnd_poses_sig:
            rej_boundary_path_x.extend(p['x'] for p in rej_poses)
            rej_boundary_path_y.extend(p['y'] for p in rej_poses)
        for _, rej_poses in rej_vel_poses_sig:
            rej_velocity_path_x.extend(p['x'] for p in rej_poses)
            rej_velocity_path_y.extend(p['y'] for p in rej_poses)
        for _, rej_poses in rej_amb_poses_sig:
            rej_ambiguity_path_x.extend(p['x'] for p in rej_poses)
            rej_ambiguity_path_y.extend(p['y'] for p in rej_poses)

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
        m['rej_boundary_path_x']  = rej_boundary_path_x
        m['rej_boundary_path_y']  = rej_boundary_path_y
        m['rej_velocity_path_x']  = rej_velocity_path_x
        m['rej_velocity_path_y']  = rej_velocity_path_y
        m['rej_ambiguity_path_x'] = rej_ambiguity_path_x
        m['rej_ambiguity_path_y'] = rej_ambiguity_path_y
        m['latencies_ms']      = latencies
        m['latency_mean_ms']   = sum(latencies) / len(latencies) if latencies else 0.0

    # Velocity-correlated quality
    if linear_sig and omega_sig and acc_ts:
        buckets: Dict[str, List[float]] = {'stationary': [], 'slow': [], 'rotating': [], 'fast': []}
        VEL_BIN_SIZE = 0.25  # m/s
        vel_accepted: Dict[int, int] = defaultdict(int)
        vel_total: Dict[int, int] = defaultdict(int)
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
                bin_idx = int(lin_abs / VEL_BIN_SIZE)
                vel_accepted[bin_idx] += accepted_n
                vel_total[bin_idx] += raw_n

        m['velocity_buckets'] = {
            k: {'count': len(v), 'acceptance_rate': 100.0 * sum(v) / len(v) if v else 0.0}
            for k, v in buckets.items()
        }
        m['stationary_quality'] = m['velocity_buckets']['stationary']['acceptance_rate']

        if vel_total:
            max_bin = max(vel_total.keys())
            m['velocity_curve'] = {
                'velocities':       [(i + 0.5) * VEL_BIN_SIZE for i in range(max_bin + 1)],
                'acceptance_rates': [
                    100.0 * vel_accepted[i] / vel_total[i] if vel_total.get(i, 0) > 0 else None
                    for i in range(max_bin + 1)
                ],
                'accepted_counts':  [vel_accepted.get(i, 0) for i in range(max_bin + 1)],
                'raw_counts':       [vel_total.get(i, 0) for i in range(max_bin + 1)],
            }
        else:
            m['velocity_curve'] = {}
    else:
        m['velocity_buckets']   = {}
        m['stationary_quality'] = None
        m['velocity_curve']     = {}

    return m


# ─── Signal Filtering ──────────────────────────────────────────────────────────

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
    import bisect as _bisect

    enabled_sig = signals.get('DriverStation/Enabled', [])
    auto_sig    = signals.get('DriverStation/Autonomous', [])

    if not enabled_sig:
        return []

    auto_by_time   = {t: v for t, v in auto_sig}
    auto_ts_sorted = sorted(auto_by_time.keys())

    def get_auto(t: float) -> bool:
        if not auto_ts_sorted:
            return False
        idx = _bisect.bisect_right(auto_ts_sorted, t) - 1
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


# ─── Field Figure ──────────────────────────────────────────────────────────────

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

    # Robot paths per camera — accepted poses, plus rejected poses by reason
    # (different marker symbol per reason so they stand out from accepted dots).
    for m in metrics:
        cam = m['camera']
        if m['path_x']:
            fig.add_trace(go.Scatter(
                x=m['path_x'], y=m['path_y'],
                name=f'{cam} accepted', mode='markers',
                marker=dict(size=3, color=_cam_color(cam), opacity=0.4, symbol='circle'),
            ))
        if m.get('rej_boundary_path_x'):
            fig.add_trace(go.Scatter(
                x=m['rej_boundary_path_x'], y=m['rej_boundary_path_y'],
                name=f'{cam} rejected (boundary)', mode='markers',
                marker=dict(size=7, color='#F39C12', opacity=0.7, symbol='x'),
            ))
        if m.get('rej_velocity_path_x'):
            fig.add_trace(go.Scatter(
                x=m['rej_velocity_path_x'], y=m['rej_velocity_path_y'],
                name=f'{cam} rejected (velocity)', mode='markers',
                marker=dict(size=7, color='#E74C3C', opacity=0.7, symbol='triangle-up'),
            ))
        if m.get('rej_ambiguity_path_x'):
            fig.add_trace(go.Scatter(
                x=m['rej_ambiguity_path_x'], y=m['rej_ambiguity_path_y'],
                name=f'{cam} rejected (ambiguity)', mode='markers',
                marker=dict(size=7, color='#9B59B6', opacity=0.7, symbol='diamond'),
            ))

    fig.update_layout(
        template='plotly_dark',
        xaxis=dict(title='X (m)', range=[0, FIELD_LENGTH]),
        yaxis=dict(title='Y (m)', range=[0, FIELD_WIDTH]),
        height=460,
        margin=dict(l=40, r=20, t=20, b=40),
    )
    return fig
