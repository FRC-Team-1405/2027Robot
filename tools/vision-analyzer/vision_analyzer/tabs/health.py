"""Health tab: FPS timeline, connection status, and latency distribution."""

LABEL = "Health"


def render(ctx: dict) -> None:
    import plotly.graph_objects as go
    import streamlit as st

    from ..metrics import _downsample, _histogram_data
    from ..constants import _cam_color

    metrics = ctx['metrics']

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
        st.plotly_chart(fig, width='stretch')

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
        st.plotly_chart(fig, width='stretch')

    if any(m.get('stddev_ts') for m in metrics):
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
                    fig.add_trace(go.Scatter(x=ts, y=vs, name=f'{m["camera"]} X', mode='lines',
                                              line=dict(color=_cam_color(m['camera']), width=1.5)))
                    ts, vs = _downsample(m['stddev_ts'], [v * 1000.0 for v in m['stddev_y_m']])
                    fig.add_trace(go.Scatter(x=ts, y=vs, name=f'{m["camera"]} Y', mode='lines',
                                              line=dict(color=_cam_color(m['camera']), width=1.5,
                                                         dash='dot')))
            fig.update_layout(template='plotly_dark', height=280,
                               xaxis_title='Time (s)', yaxis_title='Translation stddev (mm)',
                               margin=dict(l=40, r=10, t=20, b=40))
            st.plotly_chart(fig, width='stretch')

        with col_r:
            fig = go.Figure()
            for m in metrics:
                if m.get('stddev_ts'):
                    ts, vs = _downsample(m['stddev_ts'], m['stddev_theta_deg'])
                    fig.add_trace(go.Scatter(x=ts, y=vs, name=m['camera'], mode='lines',
                                              line=dict(color=_cam_color(m['camera']), width=1.5)))
            fig.update_layout(template='plotly_dark', height=280,
                               xaxis_title='Time (s)', yaxis_title='Rotation stddev (deg)',
                               margin=dict(l=40, r=10, t=20, b=40))
            st.plotly_chart(fig, width='stretch')

    if any(m.get('stddev_1s_ts') for m in metrics):
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
                    ts, vs = _downsample(m['stddev_1s_ts'], [v * 1000.0 for v in m['stddev_1s_x_m']])
                    fig.add_trace(go.Scatter(x=ts, y=vs, name=f'{m["camera"]} X', mode='lines',
                                              line=dict(color=_cam_color(m['camera']), width=1.5)))
                    ts, vs = _downsample(m['stddev_1s_ts'], [v * 1000.0 for v in m['stddev_1s_y_m']])
                    fig.add_trace(go.Scatter(x=ts, y=vs, name=f'{m["camera"]} Y', mode='lines',
                                              line=dict(color=_cam_color(m['camera']), width=1.5,
                                                         dash='dot')))
            fig.update_layout(template='plotly_dark', height=280,
                               xaxis_title='Time (s)', yaxis_title='Translation stddev (mm)',
                               margin=dict(l=40, r=10, t=20, b=40))
            st.plotly_chart(fig, width='stretch')

        with col_r:
            fig = go.Figure()
            for m in metrics:
                if m.get('stddev_1s_ts'):
                    ts, vs = _downsample(m['stddev_1s_ts'], m['stddev_1s_theta_deg'])
                    fig.add_trace(go.Scatter(x=ts, y=vs, name=m['camera'], mode='lines',
                                              line=dict(color=_cam_color(m['camera']), width=1.5)))
            fig.update_layout(template='plotly_dark', height=280,
                               xaxis_title='Time (s)', yaxis_title='Rotation stddev (deg)',
                               margin=dict(l=40, r=10, t=20, b=40))
            st.plotly_chart(fig, width='stretch')

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
        st.plotly_chart(fig, width='stretch')
