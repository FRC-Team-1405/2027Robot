"""Field coverage tab: field map with AprilTag detection frequency and robot path."""

LABEL = "Field"


def render(ctx: dict) -> None:
    import streamlit as st

    from ..metrics import _field_fig

    metrics     = ctx['metrics']
    has_compare = ctx.get('has_compare', False)
    metrics_b   = ctx.get('metrics_b') or []

    caption = (
        'Tags: red = never seen, orange → green = detection frequency (log scale). '
        'Small dots = accepted pose estimates. Rejected estimates are also plotted, '
        'shape-coded by rejection reason: X = boundary, triangle = velocity, '
        'diamond = ambiguity. Click any legend entry to toggle that pose type on/off '
        '(double-click to isolate it).'
    )

    if has_compare:
        display_name_a = ctx.get('display_name', 'Log A')
        display_name_b = ctx.get('display_name_b', 'Log B')
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader(f'Log A — {display_name_a}')
            st.caption(caption)
            st.plotly_chart(_field_fig(metrics), width='stretch', key='field_a')
        with col_b:
            st.subheader(f'Log B — {display_name_b}')
            st.caption(caption)
            st.plotly_chart(_field_fig(metrics_b), width='stretch', key='field_b')
    else:
        st.caption(caption)
        st.plotly_chart(_field_fig(metrics), width='stretch')
