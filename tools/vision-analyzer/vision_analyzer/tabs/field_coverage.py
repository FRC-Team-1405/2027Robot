"""Field coverage tab: field map with AprilTag detection frequency and robot path."""

LABEL = "Field"


def render(ctx: dict) -> None:
    import streamlit as st

    from ..metrics import _field_fig

    metrics = ctx['metrics']

    st.caption('Tags: red = never seen, orange -> green = detection frequency (log scale). '
               'Dots = robot positions where vision accepted an estimate.')
    st.plotly_chart(_field_fig(metrics), width='stretch')
