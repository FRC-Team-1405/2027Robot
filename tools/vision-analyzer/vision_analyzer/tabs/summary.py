"""Summary tab: key metrics table and stationary quality KPIs."""
from typing import Optional

LABEL = "Summary"


def render(ctx: dict) -> None:
    import streamlit as st

    metrics   = ctx['metrics']
    fmt       = ctx['fmt']

    def pct(v: Optional[float]) -> str:
        return f'{v:.1f}%' if v is not None else '-'

    def ms_fmt(v: float) -> str:
        return f'{v:.0f} ms' if v else '-'

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
