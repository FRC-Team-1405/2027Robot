"""Motion tab: acceptance rate bucketed by robot motion state."""

LABEL = "Motion"

_MIN_SAMPLES = 5  # hide velocity-curve bins with fewer raw observations than this


def render(ctx: dict) -> None:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import streamlit as st

    from ..constants import _cam_color, _cam_color_b

    metrics     = ctx['metrics']
    has_compare = ctx.get('has_compare', False)
    metrics_b   = ctx.get('metrics_b') or []
    b_by_cam    = {m['camera']: m for m in metrics_b}

    bucket_names  = ['stationary', 'slow', 'rotating', 'fast']
    bucket_labels = ['Stationary', 'Slow translate', 'Rotating', 'Full speed']

    # ── Acceptance Rate by Motion State ───────────────────────────────────────
    if any(m.get('velocity_buckets') for m in metrics):
        st.subheader('Acceptance Rate by Robot Motion State')
        st.caption('Stationary quality removes motion as a confounder. '
                   'Low stationary score points to a camera-intrinsic problem.')

        if has_compare:
            col_ab, col_d = st.columns(2)
            with col_ab:
                st.caption('Log A (solid) vs Log B (dashed)')
                fig = go.Figure()
                for m in metrics:
                    bkts = m.get('velocity_buckets', {})
                    fig.add_trace(go.Bar(
                        x=bucket_labels,
                        y=[bkts.get(b, {}).get('acceptance_rate', 0) for b in bucket_names],
                        name=f'{m["camera"]} (A)', opacity=0.85,
                        marker_color=_cam_color(m['camera']),
                    ))
                for m in metrics_b:
                    bkts = m.get('velocity_buckets', {})
                    fig.add_trace(go.Bar(
                        x=bucket_labels,
                        y=[bkts.get(b, {}).get('acceptance_rate', 0) for b in bucket_names],
                        name=f'{m["camera"]} (B)', opacity=0.75,
                        marker_color=_cam_color_b(m['camera']),
                    ))
                fig.add_hline(y=80, line_dash='dot', line_color='#27ae60', line_width=1,
                               annotation_text='80% target', annotation_position='top right')
                fig.update_layout(template='plotly_dark', barmode='group', height=320,
                                   yaxis=dict(title='Acceptance rate (%)', range=[0, 105]),
                                   margin=dict(l=40, r=10, t=20, b=40))
                st.plotly_chart(fig, width='stretch', key='motion_bucket_ab')

            with col_d:
                st.caption('Δ acceptance rate % (B − A)')
                fig_d = go.Figure()
                for m in metrics:
                    mb = b_by_cam.get(m['camera'])
                    if mb is None:
                        continue
                    bkts_a = m.get('velocity_buckets', {})
                    bkts_b = mb.get('velocity_buckets', {})
                    deltas = [
                        bkts_b.get(b, {}).get('acceptance_rate', 0)
                        - bkts_a.get(b, {}).get('acceptance_rate', 0)
                        for b in bucket_names
                    ]
                    colors = ['#27ae60' if d >= 0 else '#E74C3C' for d in deltas]
                    fig_d.add_trace(go.Bar(
                        x=bucket_labels, y=deltas,
                        name=f'Δ {m["camera"]}',
                        marker_color=colors, opacity=0.85,
                    ))
                fig_d.add_hline(y=0, line_color='white', line_width=1, opacity=0.4)
                fig_d.update_layout(template='plotly_dark', barmode='group', height=320,
                                     yaxis=dict(title='Δ acceptance rate (%)'),
                                     margin=dict(l=40, r=10, t=20, b=40))
                st.plotly_chart(fig_d, width='stretch', key='motion_bucket_delta')
        else:
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

    # ── Acceptance vs. Robot Speed ────────────────────────────────────────────
    all_have_vc = any(m.get('velocity_curve') for m in metrics)
    if all_have_vc or (has_compare and any(m.get('velocity_curve') for m in metrics_b)):
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

        def _add_vc_traces(ms, color_fn, suffix='', dash='solid'):
            for m in ms:
                vc = m.get('velocity_curve', {})
                if not vc:
                    continue
                color = color_fn(m['camera'])
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

                lname = f'{m["camera"]}{suffix}'
                fig2.add_trace(go.Scatter(
                    x=r_vels, y=r_rates,
                    mode='lines+markers', name=lname,
                    line=dict(color=color, width=2, dash=dash),
                    marker=dict(size=5, color=color),
                    legendgroup=lname,
                ), row=1, col=1)
                fig2.add_trace(go.Scatter(
                    x=c_vels, y=c_counts,
                    mode='lines+markers', name=lname,
                    line=dict(color=color, width=2, dash=dash),
                    marker=dict(size=5, color=color),
                    legendgroup=lname, showlegend=False,
                ), row=2, col=1)

        _add_vc_traces(metrics, _cam_color, ' (A)', 'solid')
        if has_compare:
            _add_vc_traces(metrics_b, _cam_color_b, ' (B)', 'dash')

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
