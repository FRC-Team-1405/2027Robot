"""Export tab: dump every tab's headline metrics to .csv and .md for quick diffing."""
import pathlib

LABEL = "Export"


def _render_trim_section(ctx: dict) -> None:
    """Trim leading/trailing disabled periods and offer the raw .wpilog for download."""
    import streamlit as st

    from ..metrics import _auto_trim_window
    from ..parser import trim_wpilog_bytes

    st.divider()
    st.subheader('Trim & Export Raw Log')
    st.caption(
        'Drops the leading and trailing disabled periods from the raw .wpilog '
        '(almost always extraneous pre/post-match data) and re-packages the rest '
        'byte-for-byte — no re-encoding, so the result is a fully valid .wpilog.'
    )

    mode_spans = ctx.get('mode_spans') or []
    duration   = ctx.get('duration', 0.0)
    start_t    = ctx.get('start_t', 0.0)
    source     = ctx.get('source')
    log_name   = ctx.get('display_name', 'log')

    if not mode_spans or source is None:
        st.info('No `DriverStation/Enabled` signal found in this log — nothing to trim.')
        return

    lo, hi = _auto_trim_window(mode_spans, duration)
    if lo <= 0.0 and hi >= duration:
        st.caption('No leading/trailing disabled period detected — nothing to trim.')
        return

    st.caption(
        f'Auto-detected keep window: **{lo:.1f} s** to **{hi:.1f} s** '
        f'(cuts {lo:.1f} s from the start and {duration - hi:.1f} s from the end).'
    )

    raw = source if isinstance(source, bytes) else pathlib.Path(source).read_bytes()
    trimmed = trim_wpilog_bytes(raw, start_t + lo, start_t + hi)

    orig_mb = len(raw) / (1024 * 1024)
    trim_mb = len(trimmed) / (1024 * 1024)
    pct = 100.0 * (1 - len(trimmed) / len(raw)) if raw else 0.0
    st.caption(f'Original: **{orig_mb:.1f} MB** → Trimmed: **{trim_mb:.1f} MB** ({pct:.0f}% smaller)')

    stem = pathlib.Path(log_name).stem
    st.download_button(
        'Download trimmed .wpilog',
        data=trimmed,
        file_name=f'{stem}_trimmed.wpilog',
        mime='application/octet-stream',
    )


def render(ctx: dict) -> None:
    import streamlit as st

    from ..exporter import (
        build_export_rows,
        build_delta_rows,
        rows_to_csv,
        rows_to_csv_comparison,
        rows_to_markdown,
        rows_to_markdown_comparison,
    )

    metrics     = ctx['metrics']
    fmt         = ctx['fmt']
    cameras     = [m['camera'] for m in metrics]
    duration    = ctx['duration']
    committed   = ctx.get('committed')
    meta        = ctx.get('meta', {})
    log_name    = ctx.get('display_name', 'log')
    has_compare = ctx.get('has_compare', False)
    metrics_b   = ctx.get('metrics_b') or []

    if not has_compare:
        # ── Single-log export (original behavior) ─────────────────────────────
        st.caption(
            'A flat snapshot of every headline number shown across the other tabs — '
            'acceptance, FPS, latency, motion buckets, geometry stats, field/rejection '
            'counts — one row per metric per camera. Useful for diffing two runs or '
            'handing to an LLM for comparison.'
        )

        rows    = build_export_rows(metrics, fmt)
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

        _render_trim_section(ctx)
        return

    # ── Comparison export (Log A / Log B / Δ) ─────────────────────────────────
    st.caption(
        'Comparison export: Log A rows, Log B rows, and Δ (B − A) rows — '
        'one row per (log, section, metric, camera). '
        'The Markdown report shows all three side by side per section.'
    )

    fmt_b      = ctx.get('fmt_b', fmt)
    cameras_b  = [m['camera'] for m in metrics_b]
    log_name_b = ctx.get('display_name_b', 'log_b')
    committed_b = ctx.get('committed_b')
    duration_b  = ctx.get('duration_b', 0.0)
    meta_b      = ctx.get('meta_b', {})

    rows_a     = build_export_rows(metrics,   fmt)
    rows_b     = build_export_rows(metrics_b, fmt_b)
    delta_rows = build_delta_rows(metrics, metrics_b, fmt)

    csv_str = rows_to_csv_comparison(rows_a, rows_b, delta_rows)
    md_str  = rows_to_markdown_comparison(
        rows_a, rows_b, delta_rows,
        cameras_a=cameras,
        cameras_b=cameras_b,
        log_name_a=log_name,
        log_name_b=log_name_b,
        fmt_a=fmt,
        fmt_b=fmt_b,
        duration_a=duration,
        duration_b=duration_b,
        committed_a=committed,
        committed_b=committed_b,
        meta_a=meta,
        meta_b=meta_b,
    )

    stem_a = pathlib.Path(log_name).stem
    stem_b = pathlib.Path(log_name_b).stem

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.download_button(
            'Download comparison .csv',
            data=csv_str,
            file_name=f'{stem_a}_vs_{stem_b}_comparison.csv',
            mime='text/csv',
            use_container_width=True,
        )
    with col2:
        st.download_button(
            'Download comparison .md',
            data=md_str,
            file_name=f'{stem_a}_vs_{stem_b}_comparison.md',
            mime='text/markdown',
            use_container_width=True,
        )
    with col3:
        csv_a = rows_to_csv(rows_a, log_label='')
        st.download_button(
            'Download Log A .csv',
            data=csv_a,
            file_name=f'{stem_a}_vision_summary.csv',
            mime='text/csv',
            use_container_width=True,
        )
    with col4:
        csv_b = rows_to_csv(rows_b, log_label='')
        st.download_button(
            'Download Log B .csv',
            data=csv_b,
            file_name=f'{stem_b}_vision_summary.csv',
            mime='text/csv',
            use_container_width=True,
        )

    st.subheader('Comparison Report')
    st.markdown(md_str)

    st.subheader('Raw CSV Preview')
    st.code(csv_str[:4000] + ('…' if len(csv_str) > 4000 else ''), language='csv')
