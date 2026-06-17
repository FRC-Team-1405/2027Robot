"""
Streamlit application: sidebar, time-range selector, and tab orchestration.
"""
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


def _streamlit_app() -> None:
    import streamlit as st

    st.set_page_config(
        page_title='Vision Dashboard',
        page_icon='📡',
        layout='wide',
        initial_sidebar_state='expanded',
    )
    st.title('Vision Log Dashboard')

    with st.sidebar:
        st.header('Log File')
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
                        st.session_state['_robot_dl_path'] = str(_local)
                        st.session_state['_dl_status'] = ('ok', f'Downloaded: **{_local.name}**')
                    except (ConnectionError, FileNotFoundError, RuntimeError) as exc:
                        st.session_state['_dl_status'] = ('err', str(exc))
                    except Exception as exc:
                        st.session_state['_dl_status'] = ('err', f'Unexpected error: {exc}')
                st.rerun()

            # Indicator for the currently auto-loaded robot log
            _rdp = st.session_state.get('_robot_dl_path', '')
            if _rdp and pathlib.Path(_rdp).exists():
                st.caption(f'🤖 `{pathlib.Path(_rdp).name}`')
                if st.button('✕ Clear', key='_btn_dl_clear', use_container_width=True):
                    del st.session_state['_robot_dl_path']
                    st.rerun()

    # Determine source: uploaded file > robot download > typed path
    _rdp = st.session_state.get('_robot_dl_path', '')
    if uploaded is not None:
        source       = uploaded.getvalue()
        display_name = uploaded.name
        mtime_key    = 0.0
    elif _rdp and pathlib.Path(_rdp).exists():
        p            = pathlib.Path(_rdp)
        source       = str(p)
        display_name = p.name
        mtime_key    = p.stat().st_mtime
    elif log_path:
        p = pathlib.Path(log_path)
        if not p.exists():
            st.error(f'File not found: `{log_path}`')
            return
        source       = str(p)
        display_name = p.name
        mtime_key    = p.stat().st_mtime
    else:
        st.info('Drop a `.wpilog` file in the sidebar, enter a path, or download from the robot.')
        return

    # ── Stage 1: parse signals (cached by source + mtime) ────────────────────
    @st.cache_data(show_spinner='Scanning log...')
    def _scan_signals(src, mtime: float) -> Dict:
        if isinstance(src, bytes):
            return _parse_wpilog_bytes(src)
        return parse_wpilog(src)

    try:
        signals = _scan_signals(source, mtime_key)
    except Exception as exc:
        st.error(f'Failed to parse log: {exc}')
        st.exception(exc)
        return

    all_ts   = [t for sig in signals.values() for t, _ in sig]
    start_t  = min(all_ts) if all_ts else 0.0
    duration = (max(all_ts) if all_ts else 0.0) - start_t

    # Reset session state when the log file changes
    file_key = display_name if isinstance(source, bytes) else str(pathlib.Path(log_path))
    if st.session_state.get('_log_path') != file_key:
        st.session_state['_log_path']        = file_key
        st.session_state['_time_slider']     = (0.0, float(duration))
        st.session_state['_ni_lo']           = 0.0
        st.session_state['_ni_hi']           = float(duration)
        st.session_state.pop('_pending_range', None)
        st.session_state['_range_committed'] = None

    # ── Pending-range gate ────────────────────────────────────────────────────
    # Streamlit forbids writing a widget's session-state key after that widget
    # has rendered in the current run.  Snap buttons and on_change callbacks
    # store their desired range in _pending_range (a plain, non-widget key).
    # We apply it here — before the slider widget is instantiated — so the
    # slider reflects the change without triggering the policy violation.
    _pending = st.session_state.pop('_pending_range', None)
    if _pending is not None:
        lo_p, hi_p = _pending
        lo_p = max(0.0, min(float(lo_p), float(duration)))
        hi_p = max(lo_p, min(float(hi_p), float(duration)))
        st.session_state['_time_slider'] = (lo_p, hi_p)
        # Pre-load number-input keys so they reflect the snap immediately
        st.session_state['_ni_lo'] = lo_p
        st.session_state['_ni_hi'] = hi_p

    # ── Time range selector ───────────────────────────────────────────────────
    mode_spans = _compute_mode_spans(signals, start_t)

    # on_change callbacks write _pending_range; the gate above applies it
    # on the next rerun before the slider renders.
    def _apply_lo() -> None:
        lo = float(st.session_state.get('_ni_lo', 0.0))
        hi = float(st.session_state.get('_time_slider', (0.0, duration))[1])
        lo = max(0.0, min(lo, float(duration)))
        st.session_state['_pending_range'] = (lo, max(lo, hi))

    def _apply_hi() -> None:
        hi = float(st.session_state.get('_ni_hi', duration))
        lo = float(st.session_state.get('_time_slider', (0.0, duration))[0])
        hi = max(0.0, min(hi, float(duration)))
        st.session_state['_pending_range'] = (min(lo, hi), hi)

    committed = st.session_state.get('_range_committed')
    with st.expander('**Time Range**', expanded=(committed is None)):
        st.caption(
            ':gray[■ Disabled]   '
            ':blue[■ Teleop]   '
            ':green[■ Autonomous]'
        )

        # _time_slider is always pre-initialised above, so no value= param
        # (passing value= when the key exists triggers a Streamlit warning).
        sel: Tuple[float, float] = st.slider(
            'Select window (seconds from log start)',
            min_value=0.0,
            max_value=float(duration),
            step=0.5,
            key='_time_slider',
        )

        # Mirror slider position into number-input keys before they render.
        # Setting a widget key before the widget is instantiated is allowed.
        st.session_state['_ni_lo'] = sel[0]
        st.session_state['_ni_hi'] = sel[1]

        c_lo, c_hi = st.columns(2)
        with c_lo:
            st.number_input(
                'Start (s)', min_value=0.0, max_value=float(duration),
                step=0.5, format='%.1f', key='_ni_lo', on_change=_apply_lo,
                help='Type an exact start time and press Enter',
            )
        with c_hi:
            st.number_input(
                'End (s)', min_value=0.0, max_value=float(duration),
                step=0.5, format='%.1f', key='_ni_hi', on_change=_apply_hi,
                help='Type an exact end time and press Enter',
            )

        st.plotly_chart(
            _mode_timeline_fig(mode_spans, duration, sel[0], sel[1]),
            width='stretch',
            config={'displayModeBar': False},
            key='_mode_fig',
        )

        # Snap buttons — write _pending_range + rerun; the gate picks it up
        # before the slider renders in the next run, avoiding the post-render
        # session-state mutation error.
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
                            '▷ Start', key=f'_snap_lo_{t:.1f}',
                            use_container_width=True, help=f'Set start to {t:.1f} s',
                        ):
                            cur = st.session_state['_time_slider']
                            st.session_state['_pending_range'] = (
                                max(0.0, min(t, cur[1])), cur[1],
                            )
                            st.rerun()
                    with b_hi:
                        if st.button(
                            'End ◁', key=f'_snap_hi_{t:.1f}',
                            use_container_width=True, help=f'Set end to {t:.1f} s',
                        ):
                            cur = st.session_state['_time_slider']
                            st.session_state['_pending_range'] = (
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
            if st.button('Analyze', type='primary', use_container_width=True):
                st.session_state['_range_committed'] = sel
                committed = sel

    if committed is None:
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
    except Exception as exc:
        st.error(f'Failed to compute metrics: {exc}')
        st.exception(exc)
        return

    if not all_metrics:
        st.warning('No vision cameras found in this log (no `Vision/<name>/connected` signal).')
        return

    fmt = all_metrics[0]['format']

    # Camera filter + info in sidebar
    with st.sidebar:
        selected = st.multiselect('Cameras', cameras, default=cameras)
        st.caption(f'Window: {committed[0]:.0f} s – {committed[1]:.0f} s '
                   f'({committed[1] - committed[0]:.0f} s)')
        st.caption(f'Format: {"new (raw pre-filter)" if fmt == "new" else "old (post-filter)"}')
        if meta.get('ProjectName'):
            st.caption(f'{meta["ProjectName"]} @ {meta.get("GitHash", "")[:7]}')

    metrics = [m for m in all_metrics if m['camera'] in selected]
    if not metrics:
        st.warning('No cameras selected.')
        return

    st.caption(
        f'`{display_name}`  ·  '
        f'{committed[0]:.0f} s – {committed[1]:.0f} s  ·  '
        f'cameras: {", ".join(cameras)}'
    )

    # ── Tab layout (driven by TABS registry) ──────────────────────────────────
    tab_widgets = st.tabs([tab.LABEL for tab in TABS])

    # Build the context dict passed to each tab's render()
    ctx = {
        'metrics':   metrics,
        'signals':   signals,
        'fmt':       fmt,
        'cameras':   cameras,
        'committed': committed,
        'duration':  duration,
    }

    for tab_widget, tab_module in zip(tab_widgets, TABS):
        with tab_widget:
            tab_module.render(ctx)
