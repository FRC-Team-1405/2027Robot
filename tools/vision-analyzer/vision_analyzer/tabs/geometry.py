"""Geometry tab: distance, area/weight, Z-height, ambiguity, and single vs multi-tag."""

LABEL = "Geometry"


def render(ctx: dict) -> None:
    import plotly.graph_objects as go
    import streamlit as st

    from ..metrics import _histogram_data
    from ..constants import _cam_color

    metrics = ctx['metrics']
    fmt     = ctx['fmt']

    col1, col2 = st.columns(2)

    with col1:
        st.subheader('Distance Distribution')
        label = 'All raw estimates (pre-filter)' if fmt == 'new' else 'Accepted estimates only'
        st.caption(f'{label}. Close range = higher quality estimates.')
        fig = go.Figure()
        for m in metrics:
            centers, counts = _histogram_data(m['distances'])
            if centers:
                fig.add_trace(go.Bar(x=centers, y=counts, name=m['camera'], opacity=0.7,
                                      marker_color=_cam_color(m['camera'])))
        fig.update_layout(template='plotly_dark', barmode='overlay', height=280,
                           xaxis_title='Avg distance (m)', yaxis_title='Samples',
                           margin=dict(l=40, r=10, t=20, b=40))
        st.plotly_chart(fig, width='stretch')

    with col2:
        if fmt == 'new':
            st.subheader('Tag Area Distribution')
            st.caption('Higher area = larger/closer tags, more reliable.')
            fig = go.Figure()
            for m in metrics:
                centers, counts = _histogram_data(m.get('areas', []))
                if centers:
                    fig.add_trace(go.Bar(x=centers, y=counts, name=m['camera'], opacity=0.7,
                                          marker_color=_cam_color(m['camera'])))
            fig.update_layout(template='plotly_dark', barmode='overlay', height=280,
                               xaxis_title='Sum tag area', yaxis_title='Samples',
                               margin=dict(l=40, r=10, t=20, b=40))
            st.plotly_chart(fig, width='stretch')
        else:
            st.subheader('Weight / Trust Distribution')
            st.caption('Higher weight = more influence on pose estimator.')
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
            st.plotly_chart(fig, width='stretch')

    if fmt == 'new':
        col3, col4 = st.columns(2)

        with col3:
            st.subheader('Z-Height Distribution')
            st.caption('Should peak at 0. Non-zero mean indicates a calibration error '
                        '(height or pitch angle wrong in VisionConstants).')
            fig = go.Figure()
            for m in metrics:
                centers, counts = _histogram_data(m.get('z_heights', []), nbins=40)
                if centers:
                    fig.add_trace(go.Bar(x=centers, y=counts, name=m['camera'], opacity=0.7,
                                          marker_color=_cam_color(m['camera'])))
            fig.add_vline(x=0, line_dash='dot', line_color='white', line_width=1)
            fig.update_layout(template='plotly_dark', barmode='overlay', height=280,
                               xaxis_title='Z height (m)', yaxis_title='Samples',
                               margin=dict(l=40, r=10, t=20, b=40))
            st.plotly_chart(fig, width='stretch')

        with col4:
            st.subheader('Ambiguity Distribution (Single-Tag Only)')
            st.caption('Multi-tag results are excluded (they report -1 and have no ambiguity). '
                        'Rejection threshold at 0.2 — mass near there = operating near limit.')
            fig = go.Figure()
            for m in metrics:
                centers, counts = _histogram_data(m.get('ambiguities', []), nbins=20)
                if centers:
                    fig.add_trace(go.Bar(x=centers, y=counts, name=m['camera'], opacity=0.7,
                                          marker_color=_cam_color(m['camera'])))
            fig.add_vline(x=0.2, line_dash='dash', line_color='#F39C12', line_width=1,
                           annotation_text='reject', annotation_position='top right')
            fig.update_layout(template='plotly_dark', barmode='overlay', height=280,
                               xaxis_title='Ambiguity', yaxis_title='Samples',
                               margin=dict(l=40, r=10, t=20, b=40))
            st.plotly_chart(fig, width='stretch')

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
