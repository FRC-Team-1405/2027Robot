"""Acceptance tab: rolling acceptance rate over time and rejection breakdown."""

LABEL = "Acceptance"


def render(ctx: dict) -> None:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import streamlit as st

    from ..metrics import _rolling_mean, _downsample, _bucket_sum, _delta_series
    from ..constants import _cam_color, _cam_color_b

    metrics     = ctx['metrics']
    fmt         = ctx['fmt']
    has_compare = ctx.get('has_compare', False)
    metrics_b   = ctx.get('metrics_b') or []
    b_by_cam    = {m['camera']: m for m in metrics_b}

    # ── Accepted Poses Per Second ─────────────────────────────────────────────
    st.subheader('Accepted Poses Per Second (1 s buckets)')
    st.caption('Accepted pose count per camera, summed into 1-second buckets — '
               'i.e. accepted poses/sec. Useful for comparing which camera contributes '
               'more accepted measurements over the course of a match.')

    if has_compare:
        fig = go.Figure()
        for m in metrics:
            bts, bvs = _bucket_sum(m['acc_ts'], m['acc_counts'], bucket=1.0)
            fig.add_trace(go.Scatter(
                x=bts, y=bvs, name=f'{m["camera"]} (A)', mode='lines',
                line=dict(color=_cam_color(m['camera']), width=2),
            ))
        for m in metrics_b:
            bts, bvs = _bucket_sum(m['acc_ts'], m['acc_counts'], bucket=1.0)
            fig.add_trace(go.Scatter(
                x=bts, y=bvs, name=f'{m["camera"]} (B)', mode='lines',
                line=dict(color=_cam_color_b(m['camera']), width=2, dash='dash'),
            ))
        fig.update_layout(template='plotly_dark', height=280,
                           xaxis_title='Time (s)',
                           yaxis=dict(title='Accepted poses / sec'),
                           margin=dict(l=40, r=10, t=20, b=40))
        st.plotly_chart(fig, width='stretch', key='acc_poses_compare')

        # Delta sub-chart
        st.caption('**Δ Accepted Poses/sec (B − A)**')
        fig_d = go.Figure()
        for m in metrics:
            mb = b_by_cam.get(m['camera'])
            if mb is None:
                continue
            bts_a, bvs_a = _bucket_sum(m['acc_ts'],  m['acc_counts'],  bucket=1.0)
            bts_b, bvs_b = _bucket_sum(mb['acc_ts'], mb['acc_counts'], bucket=1.0)
            # Align on common bucket times
            a_dict = dict(zip(bts_a, bvs_a))
            b_dict = dict(zip(bts_b, bvs_b))
            common = sorted(set(bts_a) & set(bts_b))
            if common:
                delta_vs = [b_dict[t] - a_dict[t] for t in common]
                colors   = ['#27ae60' if v >= 0 else '#E74C3C' for v in delta_vs]
                fig_d.add_trace(go.Bar(
                    x=common, y=delta_vs, name=f'Δ {m["camera"]}',
                    marker_color=colors, opacity=0.8,
                ))
        fig_d.add_hline(y=0, line_color='white', line_width=1, opacity=0.4)
        fig_d.update_layout(template='plotly_dark', height=200,
                             xaxis_title='Time (s)',
                             yaxis_title='Δ poses / sec',
                             margin=dict(l=40, r=10, t=10, b=40))
        st.plotly_chart(fig_d, width='stretch', key='acc_poses_delta')
    else:
        fig = go.Figure()
        for m in metrics:
            bts, bvs = _bucket_sum(m['acc_ts'], m['acc_counts'], bucket=1.0)
            fig.add_trace(go.Scatter(x=bts, y=bvs, name=m['camera'], mode='lines',
                                      line=dict(color=_cam_color(m['camera']), width=2)))
        fig.update_layout(template='plotly_dark', height=320,
                           xaxis_title='Time (s)',
                           yaxis=dict(title='Accepted poses / sec'),
                           margin=dict(l=40, r=10, t=20, b=40))
        st.plotly_chart(fig, width='stretch')

    # ── Acceptance Rate Over Time ─────────────────────────────────────────────
    st.subheader('Acceptance Rate Over Time (3 s rolling)')
    st.caption('Per-loop acceptance rate smoothed over a 3-second window. '
               'Drops indicate the filter rejecting more estimates.')

    def _compute_rate_series(m):
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
        return _downsample(rts, rvs)

    if has_compare:
        fig = go.Figure()
        for m in metrics:
            rts, rvs = _compute_rate_series(m)
            fig.add_trace(go.Scatter(
                x=rts, y=rvs, name=f'{m["camera"]} (A)', mode='lines',
                line=dict(color=_cam_color(m['camera']), width=2),
            ))
        for m in metrics_b:
            rts, rvs = _compute_rate_series(m)
            fig.add_trace(go.Scatter(
                x=rts, y=rvs, name=f'{m["camera"]} (B)', mode='lines',
                line=dict(color=_cam_color_b(m['camera']), width=2, dash='dash'),
            ))
        fig.update_layout(template='plotly_dark', height=280,
                           xaxis_title='Time (s)',
                           yaxis=dict(title='Acceptance rate (%)', range=[0, 105]),
                           margin=dict(l=40, r=10, t=20, b=40))
        st.plotly_chart(fig, width='stretch', key='acc_rate_compare')

        # Delta
        st.caption('**Δ Acceptance Rate % (B − A), 1 s buckets**')
        fig_d = go.Figure()
        for m in metrics:
            mb = b_by_cam.get(m['camera'])
            if mb is None:
                continue
            ts_a, vs_a = _compute_rate_series(m)
            ts_b, vs_b = _compute_rate_series(mb)
            d_ts, d_vs = _delta_series(list(ts_a), list(vs_a), list(ts_b), list(vs_b), bucket=1.0)
            if d_ts:
                colors = ['#27ae60' if v >= 0 else '#E74C3C' for v in d_vs]
                fig_d.add_trace(go.Bar(
                    x=d_ts, y=d_vs, name=f'Δ {m["camera"]}',
                    marker_color=colors, opacity=0.8,
                ))
        fig_d.add_hline(y=0, line_color='white', line_width=1, opacity=0.4)
        fig_d.update_layout(template='plotly_dark', height=200,
                             xaxis_title='Time (s)',
                             yaxis_title='Δ acceptance (%)',
                             margin=dict(l=40, r=10, t=10, b=40))
        st.plotly_chart(fig_d, width='stretch', key='acc_rate_delta')
    else:
        fig = go.Figure()
        for m in metrics:
            rts, rvs = _compute_rate_series(m)
            fig.add_trace(go.Scatter(x=rts, y=rvs, name=m['camera'], mode='lines',
                                      line=dict(color=_cam_color(m['camera']), width=2)))
        fig.update_layout(template='plotly_dark', height=320,
                           xaxis_title='Time (s)',
                           yaxis=dict(title='Acceptance rate (%)', range=[0, 105]),
                           margin=dict(l=40, r=10, t=20, b=40))
        st.plotly_chart(fig, width='stretch')

    # ── Rejection Breakdown ───────────────────────────────────────────────────
    st.subheader('Rejection Breakdown (% of all raw results)')
    st.caption('Each bar shows what fraction of ALL raw results were rejected for that reason. '
               'Velocity rejections at low speed or boundary rejections at rest indicate '
               'calibration issues. Ambiguity rejections = single-tag near threshold (0.2).')

    if has_compare:
        # Side-by-side grouped bars: Log A vs Log B per rejection type per camera
        col_ab, col_d = st.columns(2)
        with col_ab:
            st.caption('Log A (solid) vs Log B (hatched)')
            fig = go.Figure()
            cam_names_a = [f'{m["camera"]} (A)' for m in metrics]
            cam_names_b = [f'{mb["camera"]} (B)' for mb in metrics_b]
            all_cams = cam_names_a + cam_names_b
            all_ms   = list(metrics) + list(metrics_b)
            all_cols = [_cam_color(m['camera']) for m in metrics] + \
                       [_cam_color_b(m['camera']) for m in metrics_b]

            fig.add_trace(go.Bar(
                x=all_cams,
                y=[m.get('rej_velocity_pct', 0) for m in all_ms],
                name='Velocity', marker_color='#E74C3C',
                opacity=0.9,
            ))
            fig.add_trace(go.Bar(
                x=all_cams,
                y=[m.get('rej_boundary_pct', 0) for m in all_ms],
                name='Boundary', marker_color='#F39C12',
                opacity=0.9,
            ))
            if fmt == 'new':
                fig.add_trace(go.Bar(
                    x=all_cams,
                    y=[m.get('rej_ambiguity_pct', 0) for m in all_ms],
                    name='Ambiguity', marker_color='#9B59B6',
                    opacity=0.9,
                ))
            fig.update_layout(template='plotly_dark', barmode='stack', height=280,
                               yaxis_title='% of all raw results',
                               margin=dict(l=40, r=10, t=20, b=40))
            st.plotly_chart(fig, width='stretch', key='rej_breakdown_ab')

        with col_d:
            st.caption('Δ rejection % (B − A) per camera')
            fig_d = go.Figure()
            rej_types = [('Velocity', 'rej_velocity_pct', '#E74C3C'),
                         ('Boundary', 'rej_boundary_pct', '#F39C12')]
            if fmt == 'new':
                rej_types.append(('Ambiguity', 'rej_ambiguity_pct', '#9B59B6'))

            for label, key, color in rej_types:
                deltas = []
                x_cams = []
                for m in metrics:
                    mb = b_by_cam.get(m['camera'])
                    if mb is not None:
                        deltas.append(mb.get(key, 0) - m.get(key, 0))
                        x_cams.append(m['camera'])
                if deltas:
                    fig_d.add_trace(go.Bar(
                        x=x_cams, y=deltas, name=f'Δ {label}',
                        marker_color=color, opacity=0.85,
                    ))
            fig_d.add_hline(y=0, line_color='white', line_width=1, opacity=0.4)
            fig_d.update_layout(
                template='plotly_dark', barmode='group', height=280,
                yaxis_title='Δ % (B − A)',
                margin=dict(l=40, r=10, t=20, b=40),
            )
            st.plotly_chart(fig_d, width='stretch', key='rej_delta')
    else:
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
