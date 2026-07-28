"""Tab 3 — Session: assign measurements to stationary windows."""
import streamlit as st

LABEL = '3 · Session'

_LIN_THRESH  = 0.06   # m/s
_ANG_THRESH  = 0.06   # rad/s
_MIN_DUR     = 2.0    # seconds


def _detect_windows(signals: dict, start_t: float) -> list[tuple[float, float]]:
    """Return list of (abs_start, abs_end) stationary windows from velocity signals."""
    import sys, pathlib
    _va = pathlib.Path(__file__).parents[3] / 'vision-analyzer'
    if str(_va) not in sys.path:
        sys.path.insert(0, str(_va))
    from vision_analyzer.metrics import find_drivetrain_speeds

    lin_key, ang_key = find_drivetrain_speeds(signals)
    lin_sig = signals.get(lin_key, []) if lin_key else []
    ang_sig = signals.get(ang_key, []) if ang_key else []

    events: list[tuple[float, str, float]] = []
    for t, v in lin_sig:
        events.append((t, 'lin', abs(float(v))))
    for t, v in ang_sig:
        events.append((t, 'ang', abs(float(v))))
    events.sort(key=lambda e: e[0])

    if not events:
        return []

    first_t = events[0][0]

    cur_lin = 0.0
    cur_ang = 0.0
    in_stat = False
    win_start = 0.0
    windows: list[tuple[float, float]] = []

    for t, sig, val in events:
        if sig == 'lin':
            cur_lin = val
        else:
            cur_ang = val
        stat = cur_lin < _LIN_THRESH and cur_ang < _ANG_THRESH
        if stat and not in_stat:
            in_stat = True
            win_start = t
        elif not stat and in_stat:
            in_stat = False
            # A window already underway at the very first sample is
            # truncated by the log's own start, not by an observed motion
            # transition — we don't know how long the robot was actually
            # stationary before recording began, so its *visible* duration
            # is only a lower bound and must not be held to _MIN_DUR.
            leading_truncated = win_start == first_t
            if leading_truncated or t - win_start >= _MIN_DUR:
                windows.append((win_start, t))

    if in_stat:
        # Mirror image of the above: the log ends while the robot is still
        # stationary, so this window's true duration extends past what we
        # can see. This is frequently the *last* calibration stop (operator
        # grabs a few vision frames and stops recording soon after), so it
        # must never be dropped just because the visible slice is short.
        last_t = events[-1][0]
        windows.append((win_start, last_t))

    return windows


def _count_poses_in_window(signals: dict, camera: str, t0: float, t1: float,
                            tag_id: int) -> int:
    """Count rawEstimatedPoses frames in [t0, t1] that include tag_id."""
    import sys, pathlib
    _va = pathlib.Path(__file__).parents[3] / 'vision-analyzer'
    if str(_va) not in sys.path:
        sys.path.insert(0, str(_va))

    def _find(base_key):
        for prefix in ('', 'RealOutputs/'):
            k = prefix + base_key
            if k in signals:
                return signals[k]
            parts = base_key.rsplit('/', 1)
            if len(parts) == 2:
                cap = parts[0] + '/' + parts[1][0].upper() + parts[1][1:]
                kk = prefix + cap
                if kk in signals:
                    return signals[kk]
        return None

    poses_sig   = _find(f'Vision/{camera}/rawEstimatedPoses')
    counts_sig  = _find(f'Vision/{camera}/rawTagCountsPerResult')
    ids_sig     = _find(f'Vision/{camera}/rawTagIdsFlat')

    if not poses_sig:
        return 0

    counts_by_t = {t: v for t, v in (counts_sig or [])}
    ids_by_t    = {t: v for t, v in (ids_sig    or [])}

    total = 0
    for t, poses in poses_sig:
        if not (t0 <= t <= t1) or not poses:
            continue
        counts  = counts_by_t.get(t, [])
        ids_flat = ids_by_t.get(t, [])
        if not counts or not ids_flat:
            total += len(poses)
            continue
        flat_i = 0
        for ri, cnt in enumerate(counts):
            ids_for_result = ids_flat[flat_i:flat_i + cnt]
            flat_i += cnt
            if tag_id in ids_for_result:
                total += 1
    return total


def render(ctx: dict) -> None:
    signals    = ctx.get('signals')
    start_t    = ctx.get('start_t', 0.0)
    camera     = ctx.get('camera', 'Left')
    tag_cfg    = ctx.get('tag_cfg', {})
    robot_cfg  = ctx.get('robot_cfg', {})

    tag_id     = tag_cfg.get('tag_id', 7)
    tag_height = tag_cfg.get('tag_height_m', 0.9144)
    tag_poses  = tag_cfg.get('tag_poses', {})

    if signals is None:
        st.info('Load a `.wpilog` file in the sidebar first.')
        return

    # ── Auto-detect button ────────────────────────────────────────────────────
    col_btn, col_info = st.columns([2, 5])
    with col_btn:
        if st.button('Detect stationary windows', type='primary'):
            windows = _detect_windows(signals, start_t)
            st.session_state['_calib_windows'] = windows
            # Pre-populate the session entries list
            entries = []
            for i, (t0, t1) in enumerate(windows):
                n = _count_poses_in_window(signals, camera, t0, t1, tag_id)
                entries.append({
                    'label':   f'W{i+1}',
                    'enabled': True,
                    't_start': round(t0 - start_t, 2),
                    't_end':   round(t1 - start_t, 2),
                    't0_abs':  t0,
                    't1_abs':  t1,
                    'n_frames': n,
                    'meas_label': None,  # assigned below
                    'manual_x_m': 0.0,
                    'manual_y_m': 0.0,
                    'manual_h_deg': 0.0,
                })
            st.session_state['_calib_session_entries'] = entries

    windows = st.session_state.get('_calib_windows', [])
    with col_info:
        if windows:
            st.success(f'{len(windows)} stationary windows found')
        else:
            st.caption('No windows detected yet.')

    if not windows:
        return

    entries: list[dict] = st.session_state.get('_calib_session_entries', [])
    meas_results: list[dict] = st.session_state.get('_calib_meas_results', [])
    meas_labels = [r['Label'] for r in meas_results] if meas_results else []

    st.markdown(f'**Camera:** {camera}  |  **Tag ID:** {tag_id}  '
                f'|  **Tag height:** {tag_height/0.0254:.1f} in')
    st.markdown('Assign a measurement (from Tab 1) to each window, or enter the robot pose manually.')
    st.divider()

    for i, entry in enumerate(entries):
        with st.expander(
            f"{'✓' if entry['enabled'] else '✗'}  "
            f"**{entry['label']}** — "
            f"{entry['t_start']:.1f} s → {entry['t_end']:.1f} s  "
            f"({entry['t1_abs'] - entry['t0_abs']:.1f} s,  {entry['n_frames']} frames)",
            expanded=(entry.get('meas_label') is None and entry['enabled']),
        ):
            c_en, c_label, c_t0, c_t1, c_n = st.columns([1, 2, 1.5, 1.5, 1])
            with c_en:
                enabled = st.checkbox('Use', value=entry['enabled'],
                                      key=f'_calib_en_{i}')
                entries[i]['enabled'] = enabled
            with c_t0:
                t_start_new = st.number_input('Start (s)', value=entry['t_start'],
                                               step=0.1, format='%.1f',
                                               key=f'_calib_t0_{i}')
                entries[i]['t_start'] = t_start_new
                entries[i]['t0_abs']  = start_t + t_start_new
            with c_t1:
                t_end_new = st.number_input('End (s)', value=entry['t_end'],
                                             step=0.1, format='%.1f',
                                             key=f'_calib_t1_{i}')
                entries[i]['t_end'] = t_end_new
                entries[i]['t1_abs'] = start_t + t_end_new
            with c_n:
                # Recount if window changed
                n_new = _count_poses_in_window(
                    signals, camera,
                    entries[i]['t0_abs'], entries[i]['t1_abs'], tag_id,
                )
                entries[i]['n_frames'] = n_new
                st.metric('Frames', n_new)

            # Measurement source selector
            src_opts = (['(manual)'] + meas_labels) if meas_labels else ['(manual)']
            cur_src = entry.get('meas_label') or '(manual)'
            if cur_src not in src_opts:
                cur_src = '(manual)'
            chosen = st.selectbox('Robot pose source', src_opts,
                                   index=src_opts.index(cur_src),
                                   key=f'_calib_src_{i}')
            entries[i]['meas_label'] = chosen if chosen != '(manual)' else None

            if chosen != '(manual)' and meas_results:
                m = next((r for r in meas_results if r['Label'] == chosen), None)
                if m:
                    st.caption(
                        f"x = {m['x_m']:.4f} m  |  y = {m['y_m']:.4f} m  "
                        f"|  heading = {m['heading']:.2f}°"
                    )
            else:
                mc1, mc2, mc3 = st.columns(3)
                with mc1:
                    entries[i]['manual_x_m'] = st.number_input(
                        'x (m)', value=entry['manual_x_m'], step=0.01, format='%.4f',
                        key=f'_calib_mx_{i}',
                    )
                with mc2:
                    entries[i]['manual_y_m'] = st.number_input(
                        'y (m)', value=entry['manual_y_m'], step=0.01, format='%.4f',
                        key=f'_calib_my_{i}',
                    )
                with mc3:
                    entries[i]['manual_h_deg'] = st.number_input(
                        'heading (°)', value=entry['manual_h_deg'], step=0.5, format='%.2f',
                        key=f'_calib_mh_{i}',
                    )

    st.session_state['_calib_session_entries'] = entries

    # ── Build and store final session data for Tab 4 ───────��──────────────────
    session_rows = []
    for entry in entries:
        if not entry['enabled']:
            continue
        if entry.get('meas_label') and meas_results:
            m = next((r for r in meas_results if r['Label'] == entry['meas_label']), None)
            if m:
                x_m, y_m, h_deg = m['x_m'], m['y_m'], m['heading']
            else:
                continue
        else:
            x_m   = entry['manual_x_m']
            y_m   = entry['manual_y_m']
            h_deg = entry['manual_h_deg']

        if tag_poses and tag_id in tag_poses:
            from ..session import user_heading_to_wpilib_yaw
            from ..field import robot_pose_to_field
            yaw_wpi = user_heading_to_wpilib_yaw(h_deg)
            T_robot_true = robot_pose_to_field(
                tag_poses[tag_id], x_m, y_m, tag_height, yaw_wpi,
            )
        else:
            T_robot_true = None

        session_rows.append({
            'label':           entry['label'],
            't0_abs':          entry['t0_abs'],
            't1_abs':          entry['t1_abs'],
            'x_m':             x_m,
            'y_m':             y_m,
            'heading_deg':     h_deg,
            'robot_pose_true': T_robot_true,
        })

    st.session_state['_calib_session_rows'] = session_rows

    if session_rows:
        st.success(f'{len(session_rows)} window(s) ready for solving.')
    else:
        st.warning('No windows enabled with poses assigned.')
