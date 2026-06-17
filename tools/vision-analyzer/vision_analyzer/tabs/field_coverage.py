"""Field coverage tab: field map with AprilTag detection frequency and robot path."""

LABEL = "Field"


def render(ctx: dict) -> None:
    import streamlit as st

    from ..metrics import _field_fig

    metrics = ctx['metrics']

    st.caption('Tags: red = never seen, orange -> green = detection frequency (log scale). '
               'Small dots = accepted pose estimates. Rejected estimates are also plotted, '
               'shape-coded by rejection reason: X = boundary, triangle = velocity, '
               'diamond = ambiguity. Click any legend entry to toggle that pose type on/off '
               '(double-click to isolate it).')
    st.plotly_chart(_field_fig(metrics), width='stretch')
