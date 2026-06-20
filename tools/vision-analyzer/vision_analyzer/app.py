"""
Streamlit application: sidebar, time-range selector, and tab orchestration.
"""
import logging
import pathlib
import re
from typing import Any, Dict, List, Optional, Tuple

from .parser import _parse_wpilog_bytes, parse_wpilog
from .metrics import (
    discover_cameras,
    detect_format,
    find_drivetrain_speeds,
    compute_camera_metrics,
    _filter_signals_by_time,
    _compute_mode_spans,
)
from .robot import _HAS_PARAMIKO, _fetch_latest_robot_log, _DEFAULT_LOGS
from .tabs import TABS

log = logging.getLogger(__name__)


def _running_under_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False


def _mode_timeline_fig(
    mode_spans: List[Tuple[float, float, str]],
    duration:   float,
    sel_lo:     float,
    sel_hi:     float,
) -> Any:
    """Compact Plotly timeline: robot mode color bands + selected window overlay."""
    import plotly.graph_objects as go

    MODE_COLORS = {
        'auto':     'rgba(39, 174, 96, 0.62)',
        'teleop':   'rgba(41, 128, 185, 0.62)',
        'disabled': 'rgba(110, 110, 110, 0.50)',
    }

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=[0, duration], y=[0.5, 0.5],
        mode='markers', marker=dict(opacity=0),
        showlegend=False, hoverinfo='skip',
    ))

    for span_start, span_end, mode in mode_spans:
        fig.add_shape(
            type='rect',
            x0=span_start, x1=span_end,
            y0=0, y1=1, yref='paper',
            fillcolor=MODE_COLORS.get(mode, 'rgba(80,80,80,0.3)'),
            line_width=0,
        )
        span_dur = span_end - span_start
        if span_dur > max(duration * 0.06, 3):
            fig.add_annotation(
                x=(span_start + span_end) / 2, y=0.5, yref='paper',
                text=mode.capitalize(), showarrow=False,
                font=dict(color='white', size=10), opacity=0.9,
            )

    # Transition callouts — dotted line + time badge at each mode boundary
    for i, (span_start, _span_end, _mode) in enumerate(mode_spans):
        if i == 0 and span_start < 0.5:
            continue  # skip the implicit start-of-log boundary
        fig.add_shape(
            type='line',
            x0=span_start, x1=span_start,
            y0=0, y1=1, yref='paper',
            line=dict(color='rgba(255,255,255,0.55)', width=1, dash='dot'),
        )
        fig.add_annotation(
            x=span_start, y=1.0, yref='paper',
            text=f'<b>{span_start:.1f}s</b>',
            showarrow=False, xanchor='left', yanchor='top',
            font=dict(color='rgba(255,255,255,0.90)', size=9),
            bgcolor='rgba(20,20,40,0.80)', borderpad=2,
        )

    # Selected window overlay
    fig.add_shape(
        type='rect',
        x0=sel_lo, x1=sel_hi,
        y0=0, y1=1, yref='paper',
        fillcolor='rgba(255, 255, 255, 0.10)',
        line=dict(color='rgba(255,255,255,0.80)', width=1.5, dash='dot'),
    )

    fig.update_layout(
        template='plotly_dark',
        height=108,
        showlegend=False,
        xaxis=dict(range=[0, duration], title='Time (s from log start)',
                   showgrid=False, zeroline=False),
        yaxis=dict(visible=False, range=[0, 1]),
        margin=dict(l=40, r=10, t=18, b=30),
        plot_bgcolor='#111827',
        paper_bgcolor='#111827',
    )
    return fig


def _time_range_ui(
    prefix: str,
    mode_spans: List[Tuple[float, float, str]],
    duration: float,
    file_key: str,
    label: str = 'Time Range',
) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
    """
    Shared time-range selector widget.
    prefix: namespace prefix for all session-state keys (e.g. 'a' or 'b').
    Returns (sel, committed): sel is current slider position; committed is
    the range last confirmed with Analyze (None until button is clicked).
    """
    import streamlit as st

    sk = f'_{prefix}'  # session-state key prefix

    # Reset state when the log file changes or the slider state is stale
    stale_slider = not isinstance(st.session_state.get(f'{sk}_time_slider'), tuple)
    if st.session_state.get(f'{sk}_log_path') != file_key or stale_slider:
        st.session_state[f'{sk}_log_path']        = file_key
        st.session_state[f'{sk}_time_slider']     = (0.0, float(duration))
        st.session_state[f'{sk}_ni_lo']           = 0.0
        st.session_state[f'{sk}_ni_hi']           = float(duration)
        st.session_state.pop(f'{sk}_pending_range', None)
        st.session_state[f'{sk}_range_committed'] = None

    # Apply pending range set by snap buttons or on_change callbacks —
    # must happen before the slider widget renders.
    _pending = st.session_state.pop(f'{sk}_pending_range', None)
    if _pending is not None:
        lo_p, hi_p = _pending
        lo_p = max(0.0, min(float(lo_p), float(duration)))
        hi_p = max(lo_p, min(float(hi_p), float(duration)))
        st.session_state[f'{sk}_time_slider'] = (lo_p, hi_p)
        st.session_state[f'{sk}_ni_lo'] = lo_p
        st.session_state[f'{sk}_ni_hi'] = hi_p

    committed = st.session_state.get(f'{sk}_range_committed')

    # Capture sk and duration in closures at definition time
    _sk = sk
    _dur = duration

    def _apply_lo() -> None:
        lo = float(st.session_state.get(f'{_sk}_ni_lo', 0.0))
        hi = float(st.session_state.get(f'{_sk}_time_slider', (0.0, _dur))[1])
        lo = max(0.0, min(lo, _dur))
        st.session_state[f'{_sk}_pending_range'] = (lo, max(lo, hi))

    def _apply_hi() -> None:
        hi = float(st.session_state.get(f'{_sk}_ni_hi', _dur))
        lo = float(st.session_state.get(f'{_sk}_time_slider', (0.0, _dur))[0])
        hi = max(0.0, min(hi, _dur))
        st.session_state[f'{_sk}_pending_range'] = (min(lo, hi), hi)

    with st.expander(f'**{label}**', expanded=(committed is None)):
        st.caption(
            ':gray[■ Disabled]   '
            ':blue[■ Teleop]   '
            ':green[■ Autonomous]'
        )

        sel: Tuple[float, float] = st.slider(
            'Select window (seconds from log start)',
            min_value=0.0,
            max_value=float(duration),
            step=0.5,
            key=f'{sk}_time_slider',
        )

        # Mirror slider position into number-input keys before they render
        st.session_state[f'{sk}_ni_lo'] = sel[0]
        st.session_state[f'{sk}_ni_hi'] = sel[1]

        c_lo, c_hi = st.columns(2)
        with c_lo:
            st.number_input(
                'Start (s)', min_value=0.0, max_value=float(duration),
                step=0.5, format='%.1f', key=f'{sk}_ni_lo', on_change=_apply_lo,
                help='Type an exact start time and press Enter',
            )
        with c_hi:
            st.number_input(
                'End (s)', min_value=0.0, max_value=float(duration),
                step=0.5, format='%.1f', key=f'{sk}_ni_hi', on_change=_apply_hi,
                help='Type an exact end time and press Enter',
            )

        st.plotly_chart(
            _mode_timeline_fig(mode_spans, duration, sel[0], sel[1]),
            width='stretch',
            config={'displayModeBar': False},
            key=f'{sk}_mode_fig',
        )

        _MODE_LABEL = {'auto': 'Auto', 'teleop': 'Teleop', 'disabled': 'Disabled'}
        transitions = [(s[0], s[2]) for s in mode_spans if s[0] > 0.5]
        if transitions:
            st.caption('**Snap to transition:**')
            snap_cols = st.columns(len(transitions))
            for snap_col, (t, mode) in zip(snap_cols, transitions):
                with snap_col:
                    st.caption(f'**{t:.1f} s** → {_MODE_LABEL.get(mode, mode)}')
                    b_lo, b_hi = st.columns(2)
                    with b_lo:
                        if st.button(
                            '▷ Start', key=f'{sk}_snap_lo_{t:.1f}',
                            use_container_width=True, help=f'Set start to {t:.1f} s',
                        ):
                            cur = st.session_state[f'{sk}_time_slider']
                            st.session_state[f'{sk}_pending_range'] = (
                                max(0.0, min(t, cur[1])), cur[1],
                            )
                            st.rerun()
                    with b_hi:
                        if st.button(
                            'End ◁', key=f'{sk}_snap_hi_{t:.1f}',
                            use_container_width=True, help=f'Set end to {t:.1f} s',
                        ):
                            cur = st.session_state[f'{sk}_time_slider']
                            st.session_state[f'{sk}_pending_range'] = (
                                cur[0], min(float(duration), max(t, cur[0])),
                            )
                            st.rerun()

        col_info, col_btn = st.columns([5, 1])
        with col_info:
            st.caption(
                f'Selected: **{sel[0]:.1f} s** to **{sel[1]:.1f} s** '
                f'({sel[1] - sel[0]:.1f} s of {duration:.1f} s total)'
            )
        with col_btn:
            if st.button('Analyze', type='primary', use_container_width=True,
                         key=f'{sk}_analyze_btn'):
                st.session_state[f'{sk}_range_committed'] = sel
                committed = sel

    return sel, committed


def _streamlit_app() -> None:
    import streamlit as st

    st.set_page_config(
        page_title='Vision Dashboard',
        page_icon='📡',
        layout='wide',
        initial_sidebar_state='expanded',
    )
    st.title('Vision Log Dashboard')

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header('Log A')
        uploaded = st.file_uploader(
            'Drop or browse a .wpilog file',
            type=['wpilog'],
            help='Drag and drop a log file here, or click to browse.',
        )
        st.caption('— or enter a path —')
        log_path_raw = st.text_input(
            'Path to .wpilog',
            placeholder='logs/offseason/6-13-26/akit_26-06-13_17-05-06.wpilog',
        )
        log_path = log_path_raw.strip().strip('"')

        # ── Download from Robot ───────────────────────────────────────────────
        st.divider()
        st.subheader('Download from Robot')

        if not _HAS_PARAMIKO:
            st.warning('`paramiko` not installed.\n\nRun: `pip install paramiko`')
        else:
            suffix_raw = st.text_input(
                'Log suffix (optional)',
                placeholder='practice run 1',
                key='_dl_suffix',
                help='Appended to the filename as _my_note. Letters, numbers, and spaces only.',
            )
            # Strip anything that isn't a letter, digit, or space
            dl_suffix = re.sub(r'[^a-zA-Z0-9 ]', '', suffix_raw).strip()

            # Show one-shot status from the previous button click
            _dl_status = st.session_state.pop('_dl_status', None)
            if _dl_status:
                if _dl_status[0] == 'ok':
                    st.success(_dl_status[1], icon='✅')
                else:
                    st.error(_dl_status[1], icon='🚫')

            if st.button('Download Latest Log', key='_btn_dl', use_container_width=True):
                with st.spinner('Connecting to roboRIO…'):
                    try:
                        _local = _fetch_latest_robot_log(dl_suffix, _DEFAULT_LOGS)
                        log.info('Robot log downloaded: %s', _local)
                        st.session_state['_robot_dl_path'] = str(_local)
                        st.session_state['_dl_status'] = ('ok', f'Downloaded: **{_local.name}**')
                    except (ConnectionError, FileNotFoundError, RuntimeError) as exc:
                        log.error('Robot log download failed: %s', exc, exc_info=True)
                        st.session_state['_dl_status'] = ('err', str(exc))
                    except Exception as exc:
                        log.exception('Unexpected error during robot log download: %s', exc)
                        st.session_state['_dl_status'] = ('err', f'Unexpected error: {exc}')
                st.rerun()

            # Indicator for the currently auto-loaded robot log
            _rdp = st.session_state.get('_robot_dl_path', '')
            if _rdp and pathlib.Path(_rdp).exists():
                st.caption(f'🤖 `{pathlib.Path(_rdp).name}`')
                if st.button('✕ Clear', key='_btn_dl_clear', use_container_width=True):
                    del st.session_state['_robot_dl_path']
                    st.rerun()

        # ── Log B (comparison — optional) ─────────────────────────────────────
        st.divider()
        st.header('Log B — Compare')
        uploaded_b = st.file_uploader(
            'Drop a second .wpilog for comparison',
            type=['wpilog'],
            key='_uploader_b',
            help='Optional. When loaded, every chart gains a delta view vs. Log A.',
        )
        st.caption('— or enter a path —')
        log_path_b_raw = st.text_input(
            'Path to .wpilog (B)',
            placeholder='logs/offseason/6-13-26/akit_26-06-13_18-00-00.wpilog',
            key='_log_path_b_input',
        )
        log_path_b = log_path_b_raw.strip().strip('"')

    # ── Determine Log A source ────────────────────────────────────────────────
    _rdp = st.session_state.get('_robot_dl_path', '')
    if uploaded is not None:
        source       = uploaded.getvalue()
        display_name = uploaded.name
        mtime_key    = 0.0
        file_key     = display_name
        log.info('Log A: uploaded file %r (%d bytes)', display_name, len(source))
    elif _rdp and pathlib.Path(_rdp).exists():
        p            = pathlib.Path(_rdp)
        source       = str(p)
        display_name = p.name
        mtime_key    = p.stat().st_mtime
        file_key     = source
        log.info('Log A: robot download %s (%.1f KB)', p.name, p.stat().st_size / 1024)
    elif log_path:
        p = pathlib.Path(log_path)
        if not p.exists():
            log.error('Log A path not found: %s', log_path)
            st.error(f'File not found: `{log_path}`')
            return
        source       = str(p)
        display_name = p.name
        mtime_key    = p.stat().st_mtime
        file_key     = source
        log.info('Log A: file path %s (%.1f KB)', p.name, p.stat().st_size / 1024)
    else:
        st.info('Drop a `.wpilog` file in the sidebar, enter a path, or download from the robot.')
        return

    # ── Determine Log B source (optional) ────────────────────────────────────
    source_b       = None
    display_name_b = None
    mtime_key_b    = 0.0
    file_key_b     = ''

    if uploaded_b is not None:
        source_b       = uploaded_b.getvalue()
        display_name_b = uploaded_b.name
        mtime_key_b    = 0.0
        file_key_b     = display_name_b
        log.info('Log B: uploaded file %r (%d bytes)', display_name_b, len(source_b))
    elif log_path_b:
        p_b = pathlib.Path(log_path_b)
        if not p_b.exists():
            log.error('Log B path not found: %s', log_path_b)
            st.warning(f'Log B not found: `{log_path_b}`')
        else:
            source_b       = str(p_b)
            display_name_b = p_b.name
            mtime_key_b    = p_b.stat().st_mtime
            file_key_b     = source_b
            log.info('Log B: file path %s (%.1f KB)', p_b.name, p_b.stat().st_size / 1024)

    # ── Stage 1: parse signals (cached by source + mtime) ────────────────────
    @st.cache_data(show_spinner='Scanning log...')
    def _scan_signals(src, mtime: float) -> Dict:
        if isinstance(src, bytes):
            return _parse_wpilog_bytes(src)
        return parse_wpilog(src)

    try:
        signals = _scan_signals(source, mtime_key)
    except Exception as exc:
        log.exception('Failed to parse Log A (%s): %s', display_name, exc)
        st.error(f'Failed to parse Log A: {exc}')
        st.exception(exc)
        return

    all_ts   = [t for sig in signals.values() for t, _ in sig]
    start_t  = min(all_ts) if all_ts else 0.0
    end_t    = max(all_ts) if all_ts else 0.0
    duration = end_t - start_t

    # ── Log A time range selector ─────────────────────────────────────────────
    mode_spans = _compute_mode_spans(signals, start_t, end_t)
    sel, committed = _time_range_ui('a', mode_spans, duration, file_key,
                                    label='Log A — Time Range')

    # ── Log B: parse + time range (conditional) ───────────────────────────────
    signals_b   = None
    start_t_b   = 0.0
    duration_b  = 0.0
    committed_b = None

    if source_b is not None:
        try:
            signals_b = _scan_signals(source_b, mtime_key_b)
        except Exception as exc:
            log.exception('Failed to parse Log B (%s): %s', display_name_b, exc)
            st.warning(f'Failed to parse Log B: {exc}')

    if signals_b is not None:
        all_ts_b  = [t for sig in signals_b.values() for t, _ in sig]
        start_t_b = min(all_ts_b) if all_ts_b else 0.0
        end_t_b   = max(all_ts_b) if all_ts_b else 0.0
        duration_b = end_t_b - start_t_b

        mode_spans_b = _compute_mode_spans(signals_b, start_t_b, end_t_b)
        _, committed_b = _time_range_ui('b', mode_spans_b, duration_b, file_key_b,
                                        label='Log B — Time Range')

    # ── Guard: Log A must be committed ────────────────────────────────────────
    if committed is None:
        if signals_b is not None and committed_b is None:
            st.info('Set time ranges for both logs and click **Analyze** for each.')
        else:
            st.info('Adjust the time range above and click **Analyze** to load the dashboard.')
        return

    t_lo = start_t + committed[0]
    t_hi = start_t + committed[1]

    # ── Stage 2: compute metrics for the committed window (cached) ────────────
    @st.cache_data(show_spinner='Analyzing...')
    def _compute_metrics(src, mtime: float, t_lo_k: float, t_hi_k: float):
        sig      = _scan_signals(src, mtime)           # instant — already cached
        filtered = _filter_signals_by_time(sig, t_lo_k, t_hi_k)
        cameras  = discover_cameras(filtered)

        ft_list  = [t for s in filtered.values() for t, _ in s]
        f_start  = min(ft_list) if ft_list else t_lo_k
        f_end    = max(ft_list) if ft_list else t_hi_k

        meta: Dict[str, str] = {}
        for key in ('RealMetadata/ProjectName', 'RealMetadata/GitHash', 'RealMetadata/RuntimeType'):
            if key in filtered and filtered[key]:
                meta[key.split('/')[-1]] = str(filtered[key][-1][1])

        lin_key, omega_key = find_drivetrain_speeds(filtered)
        linear_sig = filtered[lin_key]   if lin_key   else None
        omega_sig  = filtered[omega_key] if omega_key else None

        all_m = []
        for cam in cameras:
            fmt = detect_format(filtered, cam)
            m   = compute_camera_metrics(filtered, cam, fmt, f_start, f_end, linear_sig, omega_sig)
            all_m.append(m)

        return all_m, meta, cameras

    try:
        all_metrics, meta, cameras = _compute_metrics(
            source, mtime_key,
            round(t_lo, 1), round(t_hi, 1),
        )
        log.info(
            'Log A metrics computed: %d camera(s) in window %.1f–%.1f s',
            len(all_metrics), committed[0], committed[1],
        )
    except Exception as exc:
        log.exception(
            'Failed to compute Log A metrics (%s, window %.1f–%.1f s): %s',
            display_name, committed[0], committed[1], exc,
        )
        st.error(f'Failed to compute Log A metrics: {exc}')
        st.exception(exc)
        return

    if not all_metrics:
        st.warning('No vision cameras found in Log A (no `Vision/<name>/connected` signal).')
        return

    fmt = all_metrics[0]['format']

    # ── Stage 2b: compute Log B metrics (conditional) ────────────────────────
    all_metrics_b: List[Dict] = []
    cameras_b: List[str]      = []
    meta_b: Dict              = {}
    fmt_b: str                = fmt

    if signals_b is not None and committed_b is not None:
        t_lo_b = start_t_b + committed_b[0]
        t_hi_b = start_t_b + committed_b[1]
        try:
            all_metrics_b, meta_b, cameras_b = _compute_metrics(
                source_b, mtime_key_b,
                round(t_lo_b, 1), round(t_hi_b, 1),
            )
            if all_metrics_b:
                fmt_b = all_metrics_b[0]['format']
                log.info(
                    'Log B metrics computed: %d camera(s) in window %.1f–%.1f s',
                    len(all_metrics_b), committed_b[0], committed_b[1],
                )
        except Exception as exc:
            log.exception(
                'Failed to compute Log B metrics (%s, window %.1f–%.1f s): %s',
                display_name_b, committed_b[0], committed_b[1], exc,
            )
            st.warning(f'Failed to compute Log B metrics: {exc}')

    # ── Camera filter + sidebar info ──────────────────────────────────────────
    with st.sidebar:
        selected = st.multiselect('Cameras', cameras, default=cameras)
        st.caption(
            f'**Log A:** {committed[0]:.0f} s – {committed[1]:.0f} s '
            f'({committed[1] - committed[0]:.0f} s)'
        )
        st.caption(f'Format A: {"new (raw pre-filter)" if fmt == "new" else "old (post-filter)"}')
        if all_metrics_b and committed_b is not None:
            st.caption(
                f'**Log B:** {committed_b[0]:.0f} s – {committed_b[1]:.0f} s '
                f'({committed_b[1] - committed_b[0]:.0f} s)'
            )
            st.caption(f'Format B: {"new" if fmt_b == "new" else "old"}')
            st.caption(f'Cameras B: {", ".join(cameras_b)}')
        if meta.get('ProjectName'):
            st.caption(f'{meta["ProjectName"]} @ {meta.get("GitHash", "")[:7]}')

    metrics = [m for m in all_metrics if m['camera'] in selected]
    if not metrics:
        st.warning('No cameras selected.')
        return

    metrics_b = [m for m in all_metrics_b if m['camera'] in selected] if all_metrics_b else []
    has_compare = len(metrics_b) > 0

    # Header caption
    parts = [
        f'`{display_name}`  ·  {committed[0]:.0f} s – {committed[1]:.0f} s  ·  '
        f'cameras: {", ".join(cameras)}'
    ]
    if has_compare and committed_b is not None:
        parts.append(
            f'`{display_name_b}`  ·  {committed_b[0]:.0f} s – {committed_b[1]:.0f} s'
        )
    st.caption('  **vs.**  '.join(parts))

    # ── Tab layout (driven by TABS registry) ──────────────────────────────────
    tab_widgets = st.tabs([tab.LABEL for tab in TABS])

    ctx = {
        'metrics':        metrics,
        'signals':        signals,
        'fmt':            fmt,
        'cameras':        cameras,
        'committed':      committed,
        'duration':       duration,
        'meta':           meta,
        'display_name':   display_name,
        'source':         source,
        'start_t':        start_t,
        'mode_spans':     mode_spans,
        # Comparison
        'has_compare':    has_compare,
        'metrics_b':      metrics_b if has_compare else None,
        'signals_b':      signals_b,
        'fmt_b':          fmt_b,
        'committed_b':    committed_b,
        'duration_b':     duration_b,
        'display_name_b': display_name_b,
        'meta_b':         meta_b,
    }

    for tab_widget, tab_module in zip(tab_widgets, TABS):
        with tab_widget:
            try:
                tab_module.render(ctx)
            except Exception as exc:
                log.exception('Error rendering tab %r: %s', tab_module.LABEL, exc)
                st.error(f'Error rendering tab "{tab_module.LABEL}": {exc}')
                st.exception(exc)
