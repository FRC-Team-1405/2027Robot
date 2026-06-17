"""Export tab: dump every tab's headline metrics to .csv and .md for quick diffing."""
import pathlib

LABEL = "Export"


def render(ctx: dict) -> None:
    import streamlit as st

    from ..exporter import build_export_rows, rows_to_csv, rows_to_markdown

    metrics   = ctx['metrics']
    fmt       = ctx['fmt']
    cameras   = [m['camera'] for m in metrics]
    duration  = ctx['duration']
    committed = ctx.get('committed')
    meta      = ctx.get('meta', {})
    log_name  = ctx.get('display_name', 'log')

    st.caption(
        'A flat snapshot of every headline number shown across the other tabs — '
        'acceptance, FPS, latency, motion buckets, geometry stats, field/rejection '
        'counts — one row per metric per camera. Useful for diffing two runs or '
        'handing to an LLM for comparison.'
    )

    rows = build_export_rows(metrics, fmt)
    csv_str = rows_to_csv(rows)
    md_str  = rows_to_markdown(rows, cameras, log_name, fmt, duration, meta, committed)

    stem = pathlib.Path(log_name).stem

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            'Download .csv', data=csv_str, file_name=f'{stem}_vision_summary.csv',
            mime='text/csv', use_container_width=True,
        )
    with col2:
        st.download_button(
            'Download .md', data=md_str, file_name=f'{stem}_vision_summary.md',
            mime='text/markdown', use_container_width=True,
        )

    st.subheader('Markdown Preview')
    st.markdown(md_str)

    st.subheader('CSV Preview')
    st.code(csv_str, language='csv')
