"""Motion tab: acceptance rate bucketed by robot motion state."""

LABEL = "Motion"


def render(ctx: dict) -> None:
    import plotly.graph_objects as go
    import streamlit as st

    from ..constants import _cam_color

    metrics = ctx['metrics']

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
        st.plotly_chart(fig, width='stretch')
    else:
        st.info('Drivetrain speed signals not found in this log — '
                'motion bucketing unavailable.')
