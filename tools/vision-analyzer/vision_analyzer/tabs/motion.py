"""Motion tab: acceptance rate bucketed by robot motion state."""

LABEL = "Motion"

_MIN_SAMPLES = 5  # hide velocity-curve bins with fewer raw observations than this


def render(ctx: dict) -> None:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
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

    if any(m.get('velocity_curve') for m in metrics):
        st.subheader('Acceptance vs. Robot Speed')
        st.caption(
            'Each point is a 0.25 m/s bin of linear speed. '
            f'Bins with fewer than {_MIN_SAMPLES} raw observations are hidden.'
        )
        fig2 = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            subplot_titles=['Acceptance Rate (%)', 'Accepted Count'],
            vertical_spacing=0.12,
        )
        for m in metrics:
            vc = m.get('velocity_curve', {})
            if not vc:
                continue
            color = _cam_color(m['camera'])
            vels     = vc['velocities']
            rates    = vc['acceptance_rates']
            accepted = vc['accepted_counts']
            raw      = vc['raw_counts']

            r_vels, r_rates = [], []
            c_vels, c_counts = [], []
            for v, rate, acc, n in zip(vels, rates, accepted, raw):
                if n >= _MIN_SAMPLES:
                    r_vels.append(v)
                    r_rates.append(rate)
                    c_vels.append(v)
                    c_counts.append(acc)

            fig2.add_trace(go.Scatter(
                x=r_vels, y=r_rates,
                mode='lines+markers', name=m['camera'],
                line=dict(color=color, width=2),
                marker=dict(size=5, color=color),
                legendgroup=m['camera'],
            ), row=1, col=1)
            fig2.add_trace(go.Scatter(
                x=c_vels, y=c_counts,
                mode='lines+markers', name=m['camera'],
                line=dict(color=color, width=2),
                marker=dict(size=5, color=color),
                legendgroup=m['camera'], showlegend=False,
            ), row=2, col=1)

        fig2.add_hline(y=80, line_dash='dot', line_color='#27ae60', line_width=1,
                       row=1, col=1)
        fig2.update_xaxes(title_text='Linear speed (m/s)', row=2, col=1)
        fig2.update_yaxes(title_text='Acceptance rate (%)', range=[0, 105], row=1, col=1)
        fig2.update_yaxes(title_text='Accepted count', row=2, col=1)
        fig2.update_layout(
            template='plotly_dark', height=520,
            margin=dict(l=40, r=10, t=40, b=40),
        )
        st.plotly_chart(fig2, width='stretch')
