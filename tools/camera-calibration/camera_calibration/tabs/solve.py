"""Tab 4 — Solve: run calibration, show results, output Java snippet."""
import logging

import streamlit as st

log = logging.getLogger(__name__)

LABEL = '4 · Solve'


def _find_sig(signals, base_key):
    for prefix in ('', 'RealOutputs/'):
        k = prefix + base_key
        if k in signals:
            return signals[k]
    parts = base_key.rsplit('/', 1)
    if len(parts) == 2:
        cap = parts[0] + '/' + parts[1][0].upper() + parts[1][1:]
        for prefix in ('', 'RealOutputs/'):
            k = prefix + cap
            if k in signals:
                return signals[k]
    return None


def _get_poses(signals, camera, t0, t1, tag_id):
    poses_sig  = _find_sig(signals, f'Vision/{camera}/rawEstimatedPoses')
    counts_sig = _find_sig(signals, f'Vision/{camera}/rawTagCountsPerResult')
    ids_sig    = _find_sig(signals, f'Vision/{camera}/rawTagIdsFlat')
    if not poses_sig:
        return []

    counts_by_t = {t: v for t, v in (counts_sig or [])}
    ids_by_t    = {t: v for t, v in (ids_sig    or [])}

    result = []
    for t, poses in poses_sig:
        if not (t0 <= t <= t1) or not poses:
            continue
        counts   = counts_by_t.get(t, [])
        ids_flat = ids_by_t.get(t, [])
        if not counts or not ids_flat:
            result.extend(poses)
            continue
        flat_i = 0
        for ri, cnt in enumerate(counts):
            ids_for_result = ids_flat[flat_i:flat_i + cnt]
            flat_i += cnt
            if tag_id in ids_for_result and ri < len(poses):
                result.append(poses[ri])
    return result


def render(ctx: dict) -> None:
    signals     = ctx.get('signals')
    camera      = ctx.get('camera', 'Left')
    tag_cfg     = ctx.get('tag_cfg', {})
    T_rc_current = ctx.get('T_rc_current')

    tag_id = tag_cfg.get('tag_id', 7)

    if signals is None:
        st.info('Load a `.wpilog` file in the sidebar first.')
        return

    session_rows: list[dict] = st.session_state.get('_calib_session_rows', [])
    if not session_rows:
        st.info('Go to **3 · Session**, detect windows, and assign poses first.')
        return

    # Validate: all rows need robot_pose_true
    missing = [r['label'] for r in session_rows if r.get('robot_pose_true') is None]
    if missing:
        st.error(
            f'Tag poses not loaded for window(s): {missing}. '
            'Check that `src/main/deploy/field_calibration.json` is accessible '
            'and the tag ID is valid.'
        )
        return

    if st.button('Solve', type='primary'):
        from ..solver import run_calibration

        # Build windows_data for solver
        windows_data = []
        for row in session_rows:
            poses = _get_poses(signals, camera, row['t0_abs'], row['t1_abs'], tag_id)
            if not poses:
                log.warning(
                    'Window %r [%.2f, %.2f]s: no poses found for tag %d on camera %r — skipping.',
                    row['label'], row['t0_abs'], row['t1_abs'], tag_id, camera,
                )
                st.warning(f"Window {row['label']}: no poses found for tag {tag_id} — skipping.")
                continue
            windows_data.append({
                'label':           row['label'],
                'poses':           poses,
                'robot_pose_true': row['robot_pose_true'],
            })

        if not windows_data:
            st.error('No valid windows with pose data. Cannot solve.')
            return

        try:
            result = run_calibration(windows_data, T_rc_current, camera_name=camera)
            st.session_state['_calib_result'] = result
        except Exception as exc:
            log.exception('Solver failed for camera %r', camera)
            st.error(f'Solver failed: {exc}')
            return

    result = st.session_state.get('_calib_result')
    if result is None:
        return

    _render_results(result, T_rc_current, camera)


def _render_results(result: dict, T_rc_current, camera: str) -> None:
    from ..solver import matrix_to_params

    p_cal  = result['params']
    p_cur  = matrix_to_params(T_rc_current)

    st.markdown(f'### Results — {camera} camera')
    st.caption(f'{result["n_total_frames"]} total frames across {len(result["window_residuals"])} windows')

    # ── Side-by-side comparison ───────��───────────────────────────────────────
    col_cal, col_cur, col_delta = st.columns(3)

    with col_cal:
        st.markdown('**Calibrated**')
        _param_table(p_cal)

    with col_cur:
        st.markdown('**Current (in VisionConstants)**')
        _param_table(p_cur)

    with col_delta:
        st.markdown('**Δ (calibrated − current)**')
        delta = {
            'x_m':    p_cal['x_m']    - p_cur['x_m'],
            'y_m':    p_cal['y_m']    - p_cur['y_m'],
            'z_m':    p_cal['z_m']    - p_cur['z_m'],
            'x_in':   p_cal['x_in']   - p_cur['x_in'],
            'y_in':   p_cal['y_in']   - p_cur['y_in'],
            'z_in':   p_cal['z_in']   - p_cur['z_in'],
            'roll_deg':  p_cal['roll_deg']  - p_cur['roll_deg'],
            'pitch_deg': p_cal['pitch_deg'] - p_cur['pitch_deg'],
            'yaw_deg':   p_cal['yaw_deg']   - p_cur['yaw_deg'],
        }
        _param_table(delta, show_delta=True)

    # ── Per-window residuals ──────────────────────────────────────────────────
    st.markdown('---')
    st.markdown('#### Per-window residuals (after calibration)')
    st.caption(
        'Residual = distance in SE(3) between this window\'s average estimate and the '
        'global average.  High residual → noisy measurement at this position.'
    )

    import pandas as pd
    rows = result['window_residuals']
    df = pd.DataFrame({
        'Window':     [r['label']    for r in rows],
        'Frames':     [r['n_frames'] for r in rows],
        'Trans (mm)': [round(r['trans_mm'], 2) for r in rows],
        'Rot (°)':    [round(r['rot_deg'],  3) for r in rows],
    })
    st.dataframe(df, use_container_width=True, hide_index=True)

    std_t = result['stddev_trans_mm']
    std_r = result['stddev_rot_deg']
    flag_t = '⚠️' if std_t > 10 else '✓'
    flag_r = '⚠️' if std_r > 1.0 else '✓'
    st.markdown(
        f'**Cross-window σ:** {flag_t} {std_t:.2f} mm translation  |  '
        f'{flag_r} {std_r:.3f}° rotation'
    )
    if std_t > 10 or std_r > 1.0:
        st.warning(
            'High residual variance. Check for windows where the robot was moving, '
            'poorly centered poses, or measurement errors. Remove outlier windows in '
            'Tab 3 and re-solve.'
        )

    # ── Java snippet ───��─────────────────────────���────────────────────────────
    st.markdown('---')
    st.markdown('#### Java Snippet')
    st.caption('Paste into `VisionConstants.java` replacing the current Transform3d for this camera.')

    snippet = result['java_snippet']
    st.code(snippet, language='java')

    # st.code already provides a built-in copy button in Streamlit ≥ 1.35


def _param_table(p: dict, show_delta: bool = False) -> None:
    import streamlit as st

    def _fmt(val: float, unit: str) -> str:
        if show_delta:
            sign = '+' if val >= 0 else ''
            return f'{sign}{val:.3f} {unit}'
        return f'{val:.4f} {unit}' if abs(val) < 100 else f'{val:.2f} {unit}'

    st.markdown(
        f'X: `{_fmt(p["x_m"], "m")}` / `{_fmt(p["x_in"], "in")}`  \n'
        f'Y: `{_fmt(p["y_m"], "m")}` / `{_fmt(p["y_in"], "in")}`  \n'
        f'Z: `{_fmt(p["z_m"], "m")}` / `{_fmt(p["z_in"], "in")}`  \n'
        f'Roll:  `{_fmt(p["roll_deg"],  "°")}`  \n'
        f'Pitch: `{_fmt(p["pitch_deg"], "°")}`  \n'
        f'Yaw:   `{_fmt(p["yaw_deg"],   "°")}`'
    )
