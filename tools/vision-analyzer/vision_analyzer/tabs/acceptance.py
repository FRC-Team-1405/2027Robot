"""Acceptance tab: rolling acceptance rate over time and rejection breakdown."""

LABEL = "Acceptance"


def render(ctx: dict) -> None:
    import plotly.graph_objects as go
    import streamlit as st

    from ..metrics import _rolling_mean, _downsample
    from ..constants import _cam_color

    metrics = ctx['metrics']
    fmt     = ctx['fmt']

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
    st.plotly_chart(fig, width='stretch')

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
    st.plotly_chart(fig, width='stretch')
