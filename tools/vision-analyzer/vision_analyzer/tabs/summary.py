"""Summary tab: key metrics table and stationary quality KPIs."""
from typing import Any, Dict, List, Optional

LABEL = "Summary"


def _pct(v: Optional[float]) -> str:
    return f'{v:.1f}%' if v is not None else '-'


def _ms(v: float) -> str:
    return f'{v:.0f} ms' if v else '-'


def _delta_pct(a: Optional[float], b: Optional[float]) -> str:
    if a is None or b is None:
        return '-'
    d = b - a
    sign = '+' if d >= 0 else ''
    return f'{sign}{d:.1f}%'


def _delta_val(a: Optional[float], b: Optional[float], fmt: str = '{:+.1f}') -> str:
    if a is None or b is None:
        return '-'
    return fmt.format(b - a)


def render(ctx: dict) -> None:
    import streamlit as st

    metrics     = ctx['metrics']
    fmt         = ctx['fmt']
    has_compare = ctx.get('has_compare', False)
    metrics_b   = ctx.get('metrics_b') or []

    def pct(v: Optional[float]) -> str:
        return _pct(v)

    def ms_fmt(v: float) -> str:
        return _ms(v)

    if not has_compare:
        # ── Single-log mode (original behavior) ───────────────────────────────
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

        rows = {
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

        table_data = {'Metric': list(rows.keys())}
        for cam_idx, m in enumerate(metrics):
            table_data[m['camera']] = [rows[metric][cam_idx] for metric in rows]
        st.table(table_data)
        return

    # ── Comparison mode ───────────────────────────────────────────────────────
    b_by_cam: Dict[str, Dict] = {m['camera']: m for m in metrics_b}

    # Stationary quality KPIs — show A, B, and Δ
    sq_a = [m.get('stationary_quality') for m in metrics]
    sq_b = [b_by_cam.get(m['camera'], {}).get('stationary_quality') for m in metrics]
    if any(v is not None for v in sq_a + sq_b):
        cols = st.columns(len(metrics) * 3)
        col_idx = 0
        for m, sq_a_val, sq_b_val in zip(metrics, sq_a, sq_b):
            cam = m['camera']
            if sq_a_val is not None:
                cols[col_idx].metric(f'{cam} (A)', pct(sq_a_val))
            col_idx += 1
            if sq_b_val is not None:
                cols[col_idx].metric(f'{cam} (B)', pct(sq_b_val))
            col_idx += 1
            if sq_a_val is not None and sq_b_val is not None:
                delta = sq_b_val - sq_a_val
                cols[col_idx].metric(
                    f'Δ {cam}',
                    f'{delta:+.1f}%',
                    delta_color='normal' if delta >= 0 else 'inverse',
                )
            col_idx += 1

    # Build A, B, and Δ tables
    def _build_rows(ms: List[Dict], f: str) -> Dict:
        r: Dict[str, List] = {
            'Acceptance rate':     [pct(m['acceptance_rate']) for m in ms],
            'FPS (mean)':          [f'{m["fps_mean"]:.1f}' for m in ms],
            'FPS (min)':           [f'{m["fps_min"]:.1f}' for m in ms],
            'Connection uptime':   [pct(m['conn_uptime_pct']) for m in ms],
            'Mean result latency': [ms_fmt(m['latency_mean_ms']) for m in ms],
            'Rejected (velocity)': [pct(m.get('rej_velocity_pct')) for m in ms],
            'Rejected (boundary)': [pct(m.get('rej_boundary_pct')) for m in ms],
        }
        if f == 'new':
            r['Rejected (ambiguity)'] = [pct(m.get('rej_ambiguity_pct')) for m in ms]
        r['Stationary quality'] = [pct(m.get('stationary_quality')) for m in ms]
        return r

    rows_a = _build_rows(metrics, fmt)
    # Build B rows for cameras that exist in both logs
    cameras_matched = [m['camera'] for m in metrics if m['camera'] in b_by_cam]
    metrics_matched_b = [b_by_cam[cam] for cam in cameras_matched]
    fmt_b = ctx.get('fmt_b', fmt)
    rows_b = _build_rows(metrics_matched_b, fmt_b) if metrics_matched_b else {}

    # Delta values (numeric diff B - A)
    _DELTA_MAP: Dict[str, Any] = {
        'Acceptance rate':     ('acceptance_rate', _pct, _delta_pct),
        'FPS (mean)':          ('fps_mean', lambda v: f'{v:.1f}', lambda a, b: f'{b-a:+.1f}'),
        'FPS (min)':           ('fps_min',  lambda v: f'{v:.1f}', lambda a, b: f'{b-a:+.1f}'),
        'Connection uptime':   ('conn_uptime_pct', _pct, _delta_pct),
        'Mean result latency': ('latency_mean_ms', _ms, lambda a, b: f'{b-a:+.0f} ms'),
        'Rejected (velocity)': ('rej_velocity_pct', _pct, _delta_pct),
        'Rejected (boundary)': ('rej_boundary_pct', _pct, _delta_pct),
        'Rejected (ambiguity)':('rej_ambiguity_pct', _pct, _delta_pct),
        'Stationary quality':  ('stationary_quality', _pct, _delta_pct),
    }

    metric_names = list(rows_a.keys())

    col_a, col_b, col_d = st.columns(3)
    with col_a:
        st.subheader('Log A')
        table_a = {'Metric': metric_names}
        for m in metrics:
            table_a[m['camera']] = [rows_a[mn][i] for i, mn in enumerate(metric_names)]
        st.table(table_a)

    with col_b:
        st.subheader('Log B')
        if metrics_matched_b:
            table_b = {'Metric': metric_names}
            for cam in cameras_matched:
                mb = b_by_cam[cam]
                col_vals = []
                for mn in metric_names:
                    key, fmt_fn, _ = _DELTA_MAP.get(mn, (None, None, None))
                    if key and hasattr(mb, 'get'):
                        col_vals.append(fmt_fn(mb.get(key)) if fmt_fn and mb.get(key) is not None else '-')
                    else:
                        col_vals.append('-')
                table_b[cam] = col_vals
            st.table(table_b)
        else:
            st.info('No matching cameras between Log A and Log B.')

    with col_d:
        st.subheader('Δ (B − A)')
        if metrics_matched_b:
            table_d = {'Metric': metric_names}
            for ma in metrics:
                cam = ma['camera']
                if cam not in b_by_cam:
                    continue
                mb = b_by_cam[cam]
                col_vals = []
                for mn in metric_names:
                    info = _DELTA_MAP.get(mn)
                    if info:
                        key, _, delta_fn = info
                        a_val = ma.get(key)
                        b_val = mb.get(key)
                        col_vals.append(delta_fn(a_val, b_val))
                    else:
                        col_vals.append('-')
                table_d[cam] = col_vals
            st.table(table_d)
        else:
            st.caption('—')
