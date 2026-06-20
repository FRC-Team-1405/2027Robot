"""Health tab: FPS timeline, connection status, and latency distribution."""

LABEL = "Health"


def render(ctx: dict) -> None:
    import plotly.graph_objects as go
    import streamlit as st

    from ..metrics import _downsample, _histogram_data, _histogram_data_aligned
    from ..constants import _cam_color, _cam_color_b

    metrics     = ctx['metrics']
    has_compare = ctx.get('has_compare', False)
    metrics_b   = ctx.get('metrics_b') or []
    b_by_cam    = {m['camera']: m for m in metrics_b}

    col1, col2 = st.columns(2)

    with col1:
        st.subheader('FPS Over Time')
        fig = go.Figure()
        for m in metrics:
            ts, vs = _downsample(m['fps_ts'], m['fps_values'])
            fig.add_trace(go.Scatter(
                x=ts, y=vs, name=f'{m["camera"]} (A)' if has_compare else m['camera'],
                mode='lines', line=dict(color=_cam_color(m['camera']), width=1.5),
            ))
        if has_compare:
            for m in metrics_b:
                ts, vs = _downsample(m['fps_ts'], m['fps_values'])
                fig.add_trace(go.Scatter(
                    x=ts, y=vs, name=f'{m["camera"]} (B)', mode='lines',
                    line=dict(color=_cam_color_b(m['camera']), width=1.5, dash='dash'),
                ))
        fig.update_layout(template='plotly_dark', height=280,
                           xaxis_title='Time (s)', yaxis_title='FPS',
                           margin=dict(l=40, r=10, t=20, b=40))
        st.plotly_chart(fig, width='stretch', key='fps_time')

    with col2:
        st.subheader('Connection Status')
        fig = go.Figure()
        for m in metrics:
            ts, vs = _downsample(m['conn_ts'], m['conn_values'])
            fig.add_trace(go.Scatter(
                x=ts, y=vs, name=f'{m["camera"]} (A)' if has_compare else m['camera'],
                mode='lines',
                line=dict(color=_cam_color(m['camera']), width=1.5, shape='hv'),
            ))
        if has_compare:
            for m in metrics_b:
                ts, vs = _downsample(m['conn_ts'], m['conn_values'])
                fig.add_trace(go.Scatter(
                    x=ts, y=vs, name=f'{m["camera"]} (B)', mode='lines',
                    line=dict(color=_cam_color_b(m['camera']), width=1.5,
                               shape='hv', dash='dash'),
                ))
        fig.update_layout(template='plotly_dark', height=280,
                           xaxis_title='Time (s)',
                           yaxis=dict(title='Connected', tickvals=[0, 1],
                                      ticktext=['No', 'Yes'], range=[-0.1, 1.4]),
                           margin=dict(l=40, r=10, t=20, b=40))
        st.plotly_chart(fig, width='stretch', key='conn_status')

    # ── Pose Stability — rolling stddev (100-sample window) ───────────────────
    if any(m.get('stddev_ts') for m in metrics) or (
        has_compare and any(m.get('stddev_ts') for m in metrics_b)
    ):
        st.subheader('Pose Stability — Rolling StdDev (last 100 accepted poses)')
        st.caption(
            'How much consecutive accepted poses disagree with each other — same idea as '
            "PhotonVision's per-camera \"multi-tag pose standard deviation\" panel. Low and "
            'flat = repeatable solves (high precision). Spikes during motion (blur, occlusion, '
            'fewer clean tag corners) are expected; they linger afterward because this is a '
            'rolling window — it takes ~100 good samples to fully flush out the noisy ones.'
        )
        col_t, col_r = st.columns(2)
        with col_t:
            fig = go.Figure()
            for m in metrics:
                if m.get('stddev_ts'):
                    ts, vs = _downsample(m['stddev_ts'], [v * 1000.0 for v in m['stddev_x_m']])
                    fig.add_trace(go.Scatter(
                        x=ts, y=vs,
                        name=f'{m["camera"]} X (A)' if has_compare else f'{m["camera"]} X',
                        mode='lines', line=dict(color=_cam_color(m['camera']), width=1.5),
                    ))
                    ts, vs = _downsample(m['stddev_ts'], [v * 1000.0 for v in m['stddev_y_m']])
                    fig.add_trace(go.Scatter(
                        x=ts, y=vs,
                        name=f'{m["camera"]} Y (A)' if has_compare else f'{m["camera"]} Y',
                        mode='lines',
                        line=dict(color=_cam_color(m['camera']), width=1.5, dash='dot'),
                    ))
            if has_compare:
                for m in metrics_b:
                    if m.get('stddev_ts'):
                        ts, vs = _downsample(m['stddev_ts'],
                                              [v * 1000.0 for v in m['stddev_x_m']])
                        fig.add_trace(go.Scatter(
                            x=ts, y=vs, name=f'{m["camera"]} X (B)', mode='lines',
                            line=dict(color=_cam_color_b(m['camera']), width=1.5, dash='dash'),
                        ))
                        ts, vs = _downsample(m['stddev_ts'],
                                              [v * 1000.0 for v in m['stddev_y_m']])
                        fig.add_trace(go.Scatter(
                            x=ts, y=vs, name=f'{m["camera"]} Y (B)', mode='lines',
                            line=dict(color=_cam_color_b(m['camera']), width=1.5,
                                       dash='dashdot'),
                        ))
            fig.update_layout(template='plotly_dark', height=280,
                               xaxis_title='Time (s)', yaxis_title='Translation stddev (mm)',
                               margin=dict(l=40, r=10, t=20, b=40))
            st.plotly_chart(fig, width='stretch', key='stddev_xy_100')

        with col_r:
            fig = go.Figure()
            for m in metrics:
                if m.get('stddev_ts'):
                    ts, vs = _downsample(m['stddev_ts'], m['stddev_theta_deg'])
                    fig.add_trace(go.Scatter(
                        x=ts, y=vs,
                        name=f'{m["camera"]} (A)' if has_compare else m['camera'],
                        mode='lines', line=dict(color=_cam_color(m['camera']), width=1.5),
                    ))
            if has_compare:
                for m in metrics_b:
                    if m.get('stddev_ts'):
                        ts, vs = _downsample(m['stddev_ts'], m['stddev_theta_deg'])
                        fig.add_trace(go.Scatter(
                            x=ts, y=vs, name=f'{m["camera"]} (B)', mode='lines',
                            line=dict(color=_cam_color_b(m['camera']), width=1.5, dash='dash'),
                        ))
            fig.update_layout(template='plotly_dark', height=280,
                               xaxis_title='Time (s)', yaxis_title='Rotation stddev (deg)',
                               margin=dict(l=40, r=10, t=20, b=40))
            st.plotly_chart(fig, width='stretch', key='stddev_theta_100')

    # ── Pose Stability — rolling stddev (1 s window) ──────────────────────────
    if any(m.get('stddev_1s_ts') for m in metrics) or (
        has_compare and any(m.get('stddev_1s_ts') for m in metrics_b)
    ):
        st.subheader('Pose Stability — Rolling StdDev (last 1 s)')
        st.caption(
            'Same metric as above, but windowed by time instead of sample count — reacts to '
            'motion transitions immediately (no 100-sample flush lag), independent of FPS. '
            'Compare the two charts: if they track closely, the 100-sample window is wide '
            "enough at this camera's frame rate; a big gap between them means the 100-sample "
            'number is smoothing over real, recent changes.'
        )
        col_t, col_r = st.columns(2)
        with col_t:
            fig = go.Figure()
            for m in metrics:
                if m.get('stddev_1s_ts'):
                    ts, vs = _downsample(m['stddev_1s_ts'],
                                          [v * 1000.0 for v in m['stddev_1s_x_m']])
                    fig.add_trace(go.Scatter(
                        x=ts, y=vs,
                        name=f'{m["camera"]} X (A)' if has_compare else f'{m["camera"]} X',
                        mode='lines', line=dict(color=_cam_color(m['camera']), width=1.5),
                    ))
                    ts, vs = _downsample(m['stddev_1s_ts'],
                                          [v * 1000.0 for v in m['stddev_1s_y_m']])
                    fig.add_trace(go.Scatter(
                        x=ts, y=vs,
                        name=f'{m["camera"]} Y (A)' if has_compare else f'{m["camera"]} Y',
                        mode='lines',
                        line=dict(color=_cam_color(m['camera']), width=1.5, dash='dot'),
                    ))
            if has_compare:
                for m in metrics_b:
                    if m.get('stddev_1s_ts'):
                        ts, vs = _downsample(m['stddev_1s_ts'],
                                              [v * 1000.0 for v in m['stddev_1s_x_m']])
                        fig.add_trace(go.Scatter(
                            x=ts, y=vs, name=f'{m["camera"]} X (B)', mode='lines',
                            line=dict(color=_cam_color_b(m['camera']), width=1.5, dash='dash'),
                        ))
                        ts, vs = _downsample(m['stddev_1s_ts'],
                                              [v * 1000.0 for v in m['stddev_1s_y_m']])
                        fig.add_trace(go.Scatter(
                            x=ts, y=vs, name=f'{m["camera"]} Y (B)', mode='lines',
                            line=dict(color=_cam_color_b(m['camera']), width=1.5,
                                       dash='dashdot'),
                        ))
            fig.update_layout(template='plotly_dark', height=280,
                               xaxis_title='Time (s)', yaxis_title='Translation stddev (mm)',
                               margin=dict(l=40, r=10, t=20, b=40))
            st.plotly_chart(fig, width='stretch', key='stddev_xy_1s')

        with col_r:
            fig = go.Figure()
            for m in metrics:
                if m.get('stddev_1s_ts'):
                    ts, vs = _downsample(m['stddev_1s_ts'], m['stddev_1s_theta_deg'])
                    fig.add_trace(go.Scatter(
                        x=ts, y=vs,
                        name=f'{m["camera"]} (A)' if has_compare else m['camera'],
                        mode='lines', line=dict(color=_cam_color(m['camera']), width=1.5),
                    ))
            if has_compare:
                for m in metrics_b:
                    if m.get('stddev_1s_ts'):
                        ts, vs = _downsample(m['stddev_1s_ts'], m['stddev_1s_theta_deg'])
                        fig.add_trace(go.Scatter(
                            x=ts, y=vs, name=f'{m["camera"]} (B)', mode='lines',
                            line=dict(color=_cam_color_b(m['camera']), width=1.5, dash='dash'),
                        ))
            fig.update_layout(template='plotly_dark', height=280,
                               xaxis_title='Time (s)', yaxis_title='Rotation stddev (deg)',
                               margin=dict(l=40, r=10, t=20, b=40))
            st.plotly_chart(fig, width='stretch', key='stddev_theta_1s')

    # ── Latency Distribution ──────────────────────────────────────────────────
    if any(m['latencies_ms'] for m in metrics) or (
        has_compare and any(m['latencies_ms'] for m in metrics_b)
    ):
        st.subheader('Result Latency Distribution')
        if has_compare:
            col_lat, col_lat_d = st.columns(2)
            with col_lat:
                st.caption('Normalized histogram — Log A (solid) vs Log B (dashed color)')
                fig = go.Figure()
                for m in metrics:
                    mb = b_by_cam.get(m['camera'])
                    lats_a = m['latencies_ms']
                    lats_b = mb['latencies_ms'] if mb else []
                    if lats_a or lats_b:
                        centers, pct_a, pct_b = _histogram_data_aligned(lats_a, lats_b)
                        fig.add_trace(go.Bar(x=centers, y=pct_a,
                                              name=f'{m["camera"]} (A)', opacity=0.7,
                                              marker_color=_cam_color(m['camera'])))
                        if mb:
                            fig.add_trace(go.Bar(x=centers, y=pct_b,
                                                  name=f'{m["camera"]} (B)', opacity=0.6,
                                                  marker_color=_cam_color_b(m['camera'])))
                fig.update_layout(template='plotly_dark', barmode='overlay', height=260,
                                   xaxis_title='Latency (ms)', yaxis_title='% of samples',
                                   margin=dict(l=40, r=10, t=20, b=40))
                st.plotly_chart(fig, width='stretch', key='latency_hist')

            with col_lat_d:
                st.caption('Δ latency distribution % (B − A)')
                fig_d = go.Figure()
                for m in metrics:
                    mb = b_by_cam.get(m['camera'])
                    if mb is None:
                        continue
                    lats_a = m['latencies_ms']
                    lats_b = mb['latencies_ms']
                    if not lats_a and not lats_b:
                        continue
                    centers, pct_a, pct_b = _histogram_data_aligned(lats_a, lats_b)
                    deltas = [b - a for a, b in zip(pct_a, pct_b)]
                    colors = ['#27ae60' if d <= 0 else '#E74C3C' for d in deltas]
                    fig_d.add_trace(go.Bar(x=centers, y=deltas,
                                            name=f'Δ {m["camera"]}',
                                            marker_color=colors, opacity=0.8))
                fig_d.add_hline(y=0, line_color='white', line_width=1, opacity=0.4)
                fig_d.update_layout(
                    template='plotly_dark', barmode='overlay', height=260,
                    xaxis_title='Latency (ms)',
                    yaxis_title='Δ % (B − A, green = B faster)',
                    margin=dict(l=40, r=10, t=20, b=40),
                )
                st.plotly_chart(fig_d, width='stretch', key='latency_delta')
        else:
            fig = go.Figure()
            for m in metrics:
                if m['latencies_ms']:
                    centers, counts = _histogram_data(m['latencies_ms'])
                    fig.add_trace(go.Bar(x=centers, y=counts, name=m['camera'], opacity=0.7,
                                          marker_color=_cam_color(m['camera'])))
            fig.update_layout(template='plotly_dark', barmode='overlay', height=260,
                               xaxis_title='Latency (ms)', yaxis_title='Samples',
                               margin=dict(l=40, r=10, t=20, b=40))
            st.plotly_chart(fig, width='stretch')
