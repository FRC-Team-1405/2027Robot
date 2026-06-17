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
