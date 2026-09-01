"""Streamlit camera calibration app: sidebar, log parsing, and tab routing."""
import logging
import pathlib
from typing import Optional

import streamlit as st

# vision-analyzer is put on sys.path (and its logging bridged into ours) by
# camera_calibration/__init__.py -> logger.py, which always runs first as
# part of importing this package.
from vision_analyzer.parser import _parse_wpilog_bytes, parse_wpilog

from .field   import load_tag_poses
from .logger  import get_log_file
from .solver  import params_to_matrix
from .tabs    import TABS

log = logging.getLogger(__name__)

# Default T_rc values per camera from VisionConstants.java (2026 baseline)
_DEFAULTS = {
    'Left':  {'x_in': 2.19,  'y_in':  10.91, 'z_in': 28.7, 'pitch': -25.0, 'yaw': -10.0},
    'Right': {'x_in': 2.19,  'y_in': -10.91, 'z_in': 28.7, 'pitch': -25.0, 'yaw':  10.0},
}


def _running_under_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False


def _streamlit_app() -> None:
    st.set_page_config(
        page_title='Camera Calibration',
        page_icon='📐',
        layout='wide',
        initial_sidebar_state='expanded',
    )
    st.title('📐 Camera Mount Calibration')

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        session_log = get_log_file()
        if session_log:
            st.caption(f'📝 Session log: `{session_log}`')

        st.header('Log File')
        uploaded = st.file_uploader(
            'Drop or browse a .wpilog file', type=['wpilog'],
            help='Teleop calibration run logged from the roboRIO.',
        )
        log_path_raw = st.text_input(
            'Or enter a file path',
            placeholder='/home/user/logs/cal_run.wpilog',
        )

        st.divider()
        st.header('Robot Dimensions')
        st.caption('Used in Tab 1 to convert tape readings to robot center position.')
        col1, col2 = st.columns(2)
        with col1:
            half_len      = st.number_input('½ length (in)', value=14.5, step=0.25, format='%.2f',
                                             help='Half robot frame length along drive axis, bumper excluded')
            half_wid      = st.number_input('½ width (in)',  value=13.5, step=0.25, format='%.2f',
                                             help='Half robot frame width')
        with col2:
            bumper_depth  = st.number_input('Bumper depth (in)',    value=3.25, step=0.125, format='%.3f',
                                             help='Thickness of bumper frame assembly')
            bumper_rail_w = st.number_input('Bumper rail width (in)', value=27.0, step=0.5, format='%.2f',
                                             help='Outer-to-outer distance between front bumper corners')

        st.divider()
        st.header('Calibration Tag')
        try:
            tag_poses = load_tag_poses()
            tag_id_options = sorted(tag_poses.keys())
        except Exception as exc:
            log.warning('Could not load field_calibration.json: %s', exc)
            tag_poses = {}
            tag_id_options = list(range(1, 33))

        tag_id = st.selectbox(
            'Tag ID on your wall', tag_id_options,
            index=tag_id_options.index(7) if 7 in tag_id_options else 0,
            help='Must match the ID of the AprilTag you physically mounted.',
        )
        tag_height_in = st.number_input(
            'Tag center height (in)', value=36.0, step=1.0, format='%.1f',
            help='Measured from floor to center of the tag.',
        )

        st.divider()
        st.header('Camera to Calibrate')
        camera_name = st.selectbox('Camera', ['Left', 'Right'])
        d = _DEFAULTS.get(camera_name, _DEFAULTS['Left'])

        st.caption('Current transform (copy from VisionConstants.java)')
        ca, cb = st.columns(2)
        with ca:
            cur_x_in  = st.number_input('X (in)',    value=d['x_in'],  step=0.01, format='%.3f', key='tc_x')
            cur_y_in  = st.number_input('Y (in)',    value=d['y_in'],  step=0.01, format='%.3f', key='tc_y')
            cur_z_in  = st.number_input('Z (in)',    value=d['z_in'],  step=0.01, format='%.3f', key='tc_z')
        with cb:
            cur_roll  = st.number_input('Roll (°)',  value=0.0,        step=0.1,  format='%.2f', key='tc_roll')
            cur_pitch = st.number_input('Pitch (°)', value=d['pitch'], step=0.1,  format='%.2f', key='tc_pitch')
            cur_yaw   = st.number_input('Yaw (°)',   value=d['yaw'],   step=0.1,  format='%.2f', key='tc_yaw')

    # ── Build context objects ─────────────────────────────────────────────────
    robot_cfg = {
        'half_len':     half_len,
        'half_wid':     half_wid,
        'bumper_depth': bumper_depth,
        'bumper_rail_w': bumper_rail_w,
    }
    tag_cfg = {
        'tag_id':       tag_id,
        'tag_height_in': tag_height_in,
        'tag_height_m':  tag_height_in * 0.0254,
        'tag_poses':    tag_poses,
    }
    T_rc_current = params_to_matrix(
        x_m=cur_x_in * 0.0254,
        y_m=cur_y_in * 0.0254,
        z_m=cur_z_in * 0.0254,
        roll_deg=cur_roll,
        pitch_deg=cur_pitch,
        yaw_deg=cur_yaw,
    )

    # ── Parse log ─────────────────────────────────────────────────────────────
    signals: Optional[dict] = None
    display_name: Optional[str] = None
    mtime_key = 0.0

    log_path = log_path_raw.strip().strip('"')

    if uploaded is not None:
        raw_bytes = uploaded.getvalue()
        display_name = uploaded.name

        @st.cache_data(show_spinner='Parsing log…')
        def _parse_bytes(data: bytes, name: str) -> dict:
            return _parse_wpilog_bytes(data)

        try:
            signals = _parse_bytes(raw_bytes, uploaded.name)
        except Exception as exc:
            log.exception('Failed to parse uploaded log %r', uploaded.name)
            st.sidebar.error(f'Parse error: {exc}')

    elif log_path:
        p = pathlib.Path(log_path)
        if not p.exists():
            st.sidebar.error(f'Not found: `{log_path}`')
        else:
            display_name = p.name
            mtime_key    = p.stat().st_mtime

            @st.cache_data(show_spinner='Parsing log…')
            def _parse_file(path: str, mtime: float) -> dict:
                return parse_wpilog(path)

            try:
                signals = _parse_file(log_path, mtime_key)
            except Exception as exc:
                log.exception('Failed to parse log file %r', log_path)
                st.sidebar.error(f'Parse error: {exc}')

    if display_name and signals:
        all_ts  = [t for sig in signals.values() for t, _ in sig]
        start_t = min(all_ts) if all_ts else 0.0
        end_t   = max(all_ts) if all_ts else 0.0
        st.sidebar.success(f'✓ {display_name}  —  {end_t - start_t:.1f}s of data')
        st.sidebar.caption(
            'If this looks shorter than the recorded session, check the session '
            'log above for a "PARSING STOPPED EARLY" line.'
        )
    else:
        start_t = 0.0

    # Expose detected windows to Timeline tab
    detected_windows = st.session_state.get('_calib_windows', [])

    # ── Tab routing ───────────────────────────────────────────────────────────
    tab_widgets = st.tabs([tab.LABEL for tab in TABS])

    ctx = {
        'signals':           signals,
        'start_t':           start_t,
        'camera':            camera_name,
        'tag_cfg':           tag_cfg,
        'robot_cfg':         robot_cfg,
        'T_rc_current':      T_rc_current,
        '_detected_windows': detected_windows,
    }

    for widget, tab_module in zip(tab_widgets, TABS):
        with widget:
            try:
                tab_module.render(ctx)
            except Exception as exc:
                log.exception('Error in tab %r: %s', tab_module.LABEL, exc)
                st.error(f'Error in tab "{tab_module.LABEL}": {exc}')
                st.exception(exc)
