"""Geometry tab: distance, area/weight, Z-height, ambiguity, and single vs multi-tag."""

LABEL = "Geometry"


def render(ctx: dict) -> None:
    import plotly.graph_objects as go
    import streamlit as st

    from ..metrics import _histogram_data, _histogram_data_aligned
    from ..constants import _cam_color, _cam_color_b

    metrics     = ctx['metrics']
    fmt         = ctx['fmt']
    has_compare = ctx.get('has_compare', False)
    metrics_b   = ctx.get('metrics_b') or []
    b_by_cam    = {m['camera']: m for m in metrics_b}

    def _hist_compare(ax, key_a, key_b=None, nbins=30, title='', xlabel=''):
        """Render overlaid normalized histograms + delta for one geometry quantity."""
        key_b = key_b or key_a
        fig = go.Figure()
        for m in metrics:
            mb = b_by_cam.get(m['camera'])
            vals_a = m.get(key_a, [])
            vals_b = mb.get(key_b, []) if mb else []
            if has_compare and (vals_a or vals_b):
                centers, pct_a, pct_b = _histogram_data_aligned(vals_a, vals_b, nbins=nbins)
                color_a = _cam_color(m['camera'])
                color_b = _cam_color_b(m['camera'])
                fig.add_trace(go.Bar(
                    x=centers, y=pct_a,
                    name=f'{m["camera"]} (A)', opacity=0.7,
                    marker_color=color_a,
                ))
                fig.add_trace(go.Bar(
                    x=centers, y=pct_b,
                    name=f'{m["camera"]} (B)', opacity=0.6,
                    marker_color=color_b,
                    marker=dict(color=color_b, line=dict(color=color_b, width=1)),
                ))
            elif vals_a:
                centers, counts = _histogram_data(vals_a, nbins=nbins)
                if centers:
                    fig.add_trace(go.Bar(x=centers, y=counts, name=m['camera'],
                                          opacity=0.7, marker_color=_cam_color(m['camera'])))
        y_title = '% of samples' if has_compare else 'Samples'
        fig.update_layout(template='plotly_dark', barmode='overlay', height=280,
                           xaxis_title=xlabel, yaxis_title=y_title,
                           margin=dict(l=40, r=10, t=20, b=40))
        ax.plotly_chart(fig, width='stretch')

        if has_compare:
            # Delta histogram
            fig_d = go.Figure()
            for m in metrics:
                mb = b_by_cam.get(m['camera'])
                if mb is None:
                    continue
                vals_a = m.get(key_a, [])
                vals_b = mb.get(key_b, [])
                if not vals_a and not vals_b:
                    continue
                centers, pct_a, pct_b = _histogram_data_aligned(vals_a, vals_b, nbins=nbins)
                deltas = [b - a for a, b in zip(pct_a, pct_b)]
                colors = ['#27ae60' if d >= 0 else '#E74C3C' for d in deltas]
                fig_d.add_trace(go.Bar(
                    x=centers, y=deltas,
                    name=f'Δ {m["camera"]}',
                    marker_color=colors, opacity=0.8,
                ))
            fig_d.add_hline(y=0, line_color='white', line_width=1, opacity=0.4)
            fig_d.update_layout(template='plotly_dark', barmode='overlay', height=200,
                                 xaxis_title=xlabel,
                                 yaxis_title='Δ % (B − A)',
                                 margin=dict(l=40, r=10, t=10, b=40))
            ax.plotly_chart(fig_d, width='stretch')

    col1, col2 = st.columns(2)

    with col1:
        st.subheader('Distance Distribution')
        label = 'All raw estimates (pre-filter)' if fmt == 'new' else 'Accepted estimates only'
        st.caption(f'{label}. Close range = higher quality estimates.')
        _hist_compare(col1, 'distances', xlabel='Avg distance (m)')

    with col2:
        if fmt == 'new':
            st.subheader('Tag Area Distribution')
            st.caption('Higher area = larger/closer tags, more reliable.')
            _hist_compare(col2, 'areas', xlabel='Sum tag area')
        else:
            st.subheader('Weight / Trust Distribution')
            st.caption('Higher weight = more influence on pose estimator.')
            if has_compare:
                fig = go.Figure()
                for m in metrics:
                    mb = b_by_cam.get(m['camera'])
                    vals_a = m.get('weights', [])
                    vals_b = mb.get('weights', []) if mb else []
                    centers, pct_a, pct_b = _histogram_data_aligned(vals_a, vals_b)
                    fig.add_trace(go.Bar(x=centers, y=pct_a,
                                          name=f'{m["camera"]} (A)', opacity=0.7,
                                          marker_color=_cam_color(m['camera'])))
                    if mb:
                        fig.add_trace(go.Bar(x=centers, y=pct_b,
                                              name=f'{m["camera"]} (B)', opacity=0.6,
                                              marker_color=_cam_color_b(m['camera'])))
                fig.update_layout(
                    template='plotly_dark', barmode='overlay', height=280,
                    xaxis=dict(title='Weight scalar', range=[0, 1.05]),
                    yaxis_title='% of samples',
                    margin=dict(l=40, r=10, t=20, b=40),
                )
                col2.plotly_chart(fig, width='stretch')
            else:
                fig = go.Figure()
                for m in metrics:
                    centers, counts = _histogram_data(m.get('weights', []))
                    if centers:
                        fig.add_trace(go.Bar(x=centers, y=counts, name=m['camera'], opacity=0.7,
                                              marker_color=_cam_color(m['camera'])))
                fig.update_layout(template='plotly_dark', barmode='overlay', height=280,
                                   xaxis=dict(title='Weight scalar', range=[0, 1.05]),
                                   yaxis_title='Samples',
                                   margin=dict(l=40, r=10, t=20, b=40))
                col2.plotly_chart(fig, width='stretch')

    if fmt == 'new':
        col3, col4 = st.columns(2)

        with col3:
            st.subheader('Z-Height Distribution')
            st.caption('Should peak at 0. Non-zero mean indicates a calibration error '
                        '(height or pitch angle wrong in VisionConstants).')
            _hist_compare(col3, 'z_heights', nbins=40, xlabel='Z height (m)')
            # Always add the zero-line reference on the main chart
            # (drawn by individual chart above; the function handles both paths)

        with col4:
            st.subheader('Ambiguity Distribution (Single-Tag Only)')
            st.caption('Multi-tag results are excluded (they report -1 and have no ambiguity). '
                        'Rejection threshold at 0.2 — mass near there = operating near limit.')
            _hist_compare(col4, 'ambiguities', nbins=20, xlabel='Ambiguity')

        # Single-tag vs multi-tag breakdown
        has_tag_type_data = any(
            m.get('multi_tag_count', 0) + m.get('single_tag_count', 0) > 0
            for m in metrics
        )
        if has_tag_type_data:
            st.subheader('Single-Tag vs Multi-Tag Results')
            st.caption(
                'Multi-tag (2+ AprilTags in one estimate) is more reliable: no pose ambiguity, '
                'better geometry. A high single-tag fraction at short range suggests tags are '
                'being partially occluded or the camera FOV only sees one tag at a time.'
            )

            if has_compare:
                col5, col6, col7 = st.columns(3)

                with col5:
                    st.caption('Log A')
                    fig = go.Figure()
                    cam_names = [m['camera'] for m in metrics]
                    fig.add_trace(go.Bar(
                        x=cam_names,
                        y=[m.get('multi_tag_count', 0) for m in metrics],
                        name='Multi-tag', marker_color='#27ae60',
                    ))
                    fig.add_trace(go.Bar(
                        x=cam_names,
                        y=[m.get('single_tag_count', 0) for m in metrics],
                        name='Single-tag', marker_color='#3498db',
                    ))
                    fig.update_layout(template='plotly_dark', barmode='stack', height=260,
                                       yaxis_title='Result count',
                                       margin=dict(l=40, r=10, t=20, b=40))
                    st.plotly_chart(fig, width='stretch', key='tag_type_a')

                with col6:
                    st.caption('Log B')
                    fig = go.Figure()
                    cam_names_b = [m['camera'] for m in metrics_b]
                    fig.add_trace(go.Bar(
                        x=cam_names_b,
                        y=[m.get('multi_tag_count', 0) for m in metrics_b],
                        name='Multi-tag', marker_color='#27ae60',
                    ))
                    fig.add_trace(go.Bar(
                        x=cam_names_b,
                        y=[m.get('single_tag_count', 0) for m in metrics_b],
                        name='Single-tag', marker_color='#3498db',
                    ))
                    fig.update_layout(template='plotly_dark', barmode='stack', height=260,
                                       yaxis_title='Result count',
                                       margin=dict(l=40, r=10, t=20, b=40))
                    st.plotly_chart(fig, width='stretch', key='tag_type_b')

                with col7:
                    st.caption('Δ Multi-tag rate % (B − A)')
                    fig = go.Figure()
                    for m in metrics:
                        mb = b_by_cam.get(m['camera'])
                        if mb is None:
                            continue
                        total_a = m.get('multi_tag_count', 0) + m.get('single_tag_count', 0)
                        total_b = mb.get('multi_tag_count', 0) + mb.get('single_tag_count', 0)
                        rate_a = 100.0 * m.get('multi_tag_count', 0) / total_a if total_a else 0.0
                        rate_b = 100.0 * mb.get('multi_tag_count', 0) / total_b if total_b else 0.0
                        delta  = rate_b - rate_a
                        fig.add_trace(go.Bar(
                            x=[m['camera']], y=[delta],
                            name=m['camera'],
                            marker_color='#27ae60' if delta >= 0 else '#E74C3C',
                        ))
                    fig.add_hline(y=0, line_color='white', line_width=1, opacity=0.4)
                    fig.update_layout(
                        template='plotly_dark', height=260,
                        yaxis=dict(title='Δ multi-tag rate (%)'),
                        margin=dict(l=40, r=10, t=20, b=40),
                    )
                    st.plotly_chart(fig, width='stretch', key='tag_type_delta')

            else:
                col5, col6 = st.columns(2)

                with col5:
                    fig = go.Figure()
                    cam_names = [m['camera'] for m in metrics]
                    fig.add_trace(go.Bar(
                        x=cam_names,
                        y=[m.get('multi_tag_count', 0) for m in metrics],
                        name='Multi-tag', marker_color='#27ae60',
                    ))
                    fig.add_trace(go.Bar(
                        x=cam_names,
                        y=[m.get('single_tag_count', 0) for m in metrics],
                        name='Single-tag', marker_color='#3498db',
                    ))
                    fig.update_layout(
                        template='plotly_dark', barmode='stack', height=280,
                        yaxis_title='Result count',
                        margin=dict(l=40, r=10, t=20, b=40),
                    )
                    st.plotly_chart(fig, width='stretch')

                with col6:
                    # Multi-tag rate as a percentage
                    fig = go.Figure()
                    for m in metrics:
                        total = m.get('multi_tag_count', 0) + m.get('single_tag_count', 0)
                        multi_pct = 100.0 * m.get('multi_tag_count', 0) / total if total else 0.0
                        fig.add_trace(go.Bar(
                            x=[m['camera']], y=[multi_pct],
                            name=m['camera'], marker_color=_cam_color(m['camera']),
                        ))
                    fig.add_hline(y=50, line_dash='dot', line_color='white', line_width=1,
                                   annotation_text='50%', annotation_position='top right')
                    fig.update_layout(
                        template='plotly_dark', height=280,
                        yaxis=dict(title='Multi-tag rate (%)', range=[0, 105]),
                        margin=dict(l=40, r=10, t=20, b=40),
                    )
                    st.plotly_chart(fig, width='stretch')
