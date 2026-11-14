"""Quick (spin & drive): solve a camera's mount from one run of the robot's "CalibrateCameras" auto.

No tape measuring. See docs/camera-autocal-plan.md for the method and its limits.
"""
import logging
import os

import numpy as np
import pandas as pd
import streamlit as st

from ..autocal import cross_camera_agreement, solve, with_tag_height_correction
from ..autocal_io import calibration_window, extract_run, list_cameras, list_tag_ids, phase_diagnostics
from ..autocal_report import RESULTS_DIR, save_agreement, save_result
from ..robot_defaults import camera_defaults, mount_for
from ..solver import matrix_to_params, params_to_matrix

log = logging.getLogger(__name__)

LABEL = 'Quick · Spin & drive'

_KEY = '_autocal_results'


def render(ctx: dict) -> None:
    signals = ctx.get('signals')

    st.markdown(
        '**No tape needed.** Put the robot level on the floor about 2–2.5 m from the tag, roughly '
        'facing it, with ~1 m of clear floor around it. Cover the tags you do not want seen. Run the '
        '**CalibrateCameras** auto (about 25 s), fetch the log, and load it in the sidebar. '
        'Solve each camera in turn from the same log, then check the two against each other below.'
    )
    with st.expander('How it works, and what it cannot fix'):
        st.markdown(
            '- The robot spins in place and drives short straight lines with vision corrections off. '
            'The tool compares how the **camera** moved (from the tag) with how the **robot** moved '
            '(wheels + gyro), and solves the mount that explains the difference.\n'
            '- Spinning gives the camera x, y. Driving straight gives its yaw. Height, roll and pitch '
            'come from the tag view with the robot level.\n'
            '- A tag pair placed a bit off cancels out. A wrong tag **height**, a **tilted** tag, or a wrong '
            '**spacing between the two tags** does not. Check those (see the plan doc).\n'
            '- Camera intrinsics must be calibrated at the resolution in use.'
        )

    if signals is None:
        st.info('Load a `.wpilog` from a CalibrateCameras run in the sidebar.')
        return

    cams = list_cameras(signals)
    if not cams:
        st.error('No Vision/<camera>/rawEstimatedPoses in this log.')
        return
    # Camera and its current mount come from the log and the robot code; nothing to set in the sidebar.
    camera = st.selectbox('Camera to calibrate', cams,
                          help='The cameras found in this log. Solve one, then the other.')
    defaults, defaults_src = camera_defaults()
    d = mount_for(camera, defaults)
    with st.expander(f'Current mount in the robot code: {defaults_src}', expanded=False):
        st.caption('Prefilled from VisionConstants.java, so there is normally nothing to change. '
                   'Edit only if the log was recorded with a different mount.')
        c1, c2 = st.columns(2)
        k = camera
        x_in = c1.number_input('X (in)', value=d['x_in'], step=0.01, format='%.3f', key=f'aq_x_{k}')
        y_in = c1.number_input('Y (in)', value=d['y_in'], step=0.01, format='%.3f', key=f'aq_y_{k}')
        z_in = c1.number_input('Z (in)', value=d['z_in'], step=0.01, format='%.3f', key=f'aq_z_{k}')
        roll = c2.number_input('Roll (°)', value=d['roll_deg'], step=0.1, format='%.2f', key=f'aq_r_{k}')
        pitch = c2.number_input('Pitch (°)', value=d['pitch_deg'], step=0.1, format='%.2f', key=f'aq_p_{k}')
        yaw = c2.number_input('Yaw (°)', value=d['yaw_deg'], step=0.1, format='%.2f', key=f'aq_y2_{k}')
    T_rc_current = params_to_matrix(x_in * 0.0254, y_in * 0.0254, z_in * 0.0254, roll, pitch, yaw)

    window = calibration_window(signals)
    if window:
        st.caption(f'Calibration run found in the log: {window[0]:.1f}–{window[1]:.1f} s '
                   f'({window[1] - window[0]:.0f} s).')
    else:
        st.warning('No `Calibration/Phase` in this log, so this is not a CalibrateCameras run. '
                   'The whole log will be used, and the result will not be meaningful.')

    seen = list_tag_ids(signals, camera, window)
    if not seen:
        st.error(f'{camera} saw no tags during the run.')
        return
    ranked = sorted(seen, key=lambda i: -seen[i])
    default = [i for i in ranked if seen[i] >= 0.2 * seen[ranked[0]]]
    tag_ids = st.multiselect(
        f'Tags to use ({camera})', ranked, default=default,
        format_func=lambda i: f'tag {i}  ({seen[i]} results)',
        help='Only results that use ONLY these tags are kept. Pick the pair you left uncovered.',
    )
    if not tag_ids:
        st.info('Pick at least one tag.')
        return

    measured_in = st.number_input(
        'Measured tag centre height (in), optional', value=0.0, min_value=0.0, step=0.125, format='%.3f',
        help='Floor to the centre of the tag pair. Leave at 0 to trust the field layout. If the real tags '
             'are not at the layout height, every camera height is off by the difference; this corrects it.',
    )

    if st.button(f'Solve {camera}', type='primary'):
        try:
            run = extract_run(signals, camera, T_rc_current, tag_ids=set(tag_ids), window=window)
            res = solve(run['t_obs'], run['obs_T'], run['t_odo'], run['odo'], T_rc_current, camera)
            tag_poses = ctx.get('tag_cfg', {}).get('tag_poses', {})
            zs = [tag_poses[i][2, 3] for i in tag_ids if i in tag_poses]
            if measured_in > 0 and zs:
                layout_z = float(np.mean(zs))
                res = with_tag_height_correction(res, layout_z, measured_in * 0.0254, camera)
                run['notes'].append(
                    f'Camera height corrected for the tag height: layout {layout_z / 0.0254:.2f} in, '
                    f'measured {measured_in:.2f} in.')
        except Exception as exc:  # noqa: BLE001 - shown to the user
            log.exception('Auto-calibration failed for %r', camera)
            st.error(f'Could not solve: {exc}')
            return
        store = st.session_state.setdefault(_KEY, {})
        phases = phase_diagnostics(run.get('spans', []), res.sample_t, res.err_t_mm, res.err_r_deg)
        try:
            saved = save_result(camera, res, run, tag_ids, matrix_to_params(T_rc_current), phases,
                                ctx.get('log_name'))
        except OSError as exc:
            saved = None
            st.warning(f'Could not save the result: {exc}')
        store[camera] = {'res': res, 'run': run, 'T_rc_current': T_rc_current, 'phases': phases,
                         'saved': saved, 'log_name': ctx.get('log_name')}

    store = st.session_state.get(_KEY, {})
    if camera in store:
        _show(camera, store[camera])
    if len(store) >= 2:
        _show_agreement(store)


def _show(camera: str, item: dict) -> None:
    res, run = item['res'], item['run']
    cur = matrix_to_params(item['T_rc_current'])
    new = res.params

    st.markdown(f'### {camera} result')
    if item.get('saved'):
        rel = os.path.relpath(item['saved'], RESULTS_DIR.parents[2]).replace('\\', '/')
        st.caption(f'Saved automatically: `{rel}` (and a `.json` beside it). The folder is git-ignored; '
                   f'to keep a result for the docs: `git add -f {rel}` and the matching `.json`.')
    for n in run['notes']:
        st.warning(n)
    for w in res.warnings:
        st.warning(w)
    if not res.warnings and not run['notes']:
        st.success('No warnings.')

    rows = []
    for label, key, sk, unit in (
        ('x', 'x_in', 'x_mm', 'in'), ('y', 'y_in', 'y_mm', 'in'), ('z', 'z_in', 'z_mm', 'in'),
        ('roll', 'roll_deg', 'roll_deg', '°'), ('pitch', 'pitch_deg', 'pitch_deg', '°'),
        ('yaw', 'yaw_deg', 'yaw_deg', '°'),
    ):
        sig = res.sigma[sk]
        sig_txt = f'{sig / 25.4:.3f} in' if unit == 'in' else f'{sig:.2f}°'
        rows.append({'Parameter': label, 'Calibrated': round(new[key], 3), 'Current': round(cur[key], 3),
                     'Change': round(new[key] - cur[key], 3), '±1σ (optimistic)': sig_txt, 'Unit': unit})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Vision samples used', f'{res.n_inliers} / {res.n_samples}')
    c2.metric('Position residual (RMS)', f'{res.rms_t_mm:.1f} mm')
    c3.metric('Rotation residual (RMS)', f'{res.rms_r_deg:.2f}°')
    c4.metric('Vision vs odometry clock', f'{res.tau_s * 1000:+.0f} ms')
    if res.split_half:
        sh = res.split_half
        st.caption(
            f'**Repeatability:** the tool also solved two halves of the run separately (alternating '
            f'1-second pieces). Their mounts differ by {sh["dx_mm"]:+.1f} / {sh["dy_mm"]:+.1f} / '
            f'{sh["dz_mm"]:+.1f} mm (x / y / z) and {sh["rot_deg"]:.2f}° in angle. If the answer changes '
            'that much depending on which seconds you use, the data does not pin it down. '
            'Treat this as the real uncertainty, more than ±1σ.'
        )
    if item.get('phases'):
        st.markdown('**Where the data came from, by phase of the routine**')
        st.caption('Samples/s far below the other phases means the tag left that camera\'s view. A large '
                   'error in one phase is where the model and the data disagree (odometry slip, a lost tag, '
                   'a bad tag pose). Wheel-odometry distance scale fitted: '
                   f'{res.odo_scale:.3f} (1.000 = wheels exact).')
        st.dataframe(pd.DataFrame([{
            'Phase': p['phase'], 'Seconds': round(p['seconds'], 1), 'Samples': p['samples'],
            'Samples/s': round(p['rate']), 'Position err (mm)': None if p['rms_t_mm'] is None else round(p['rms_t_mm'], 1),
            'Rotation err (°)': None if p['rms_r_deg'] is None else round(p['rms_r_deg'], 2),
        } for p in item['phases']]), hide_index=True, use_container_width=True)
    st.markdown('**Paste into VisionConstants.java**')
    st.code(res.java_snippet, language='java')


def _show_agreement(store: dict) -> None:
    st.markdown('### Do the two cameras agree?')
    (nameL, L), (nameR, R) = list(store.items())[:2]
    st.caption(
        f'Whenever {nameL} and {nameR} both saw the tag within 20 ms of each other, each one says where the '
        'robot is (its own position, shifted by its mount). If the mounts are right the two answers are the '
        'same spot. The table is how far apart the two answers are, in the middle of all those moments (the '
        '**median**; **p95** = the worst 5% are farther apart than this). Smaller is better.')
    args = (L['run']['t_obs'], L['run']['obs_T']), (R['run']['t_obs'], R['run']['obs_T'])
    new = cross_camera_agreement(*args[0], L['res'].T_rc, *args[1], R['res'].T_rc)
    old = cross_camera_agreement(*args[0], L['T_rc_current'], *args[1], R['T_rc_current'])
    if not new.get('n'):
        st.info('No overlapping samples: the two cameras did not see the tag at the same time.')
        return

    def row(label, d):
        return {'Mounts': label, 'Moments compared': d.get('n', 0),
                'Position apart, median (mm)': round(d.get('pos_median_mm', float('nan')), 1),
                'Position apart, p95 (mm)': round(d.get('pos_p95_mm', float('nan')), 1),
                'Heading apart, median (°)': round(d.get('yaw_median_deg', float('nan')), 2)}

    d_pos = new['pos_median_mm'] - old['pos_median_mm']
    d_yaw = new['yaw_median_deg'] - old['yaw_median_deg']
    change = {'Mounts': 'Change (calibrated - current)', 'Moments compared': '',
              'Position apart, median (mm)': round(d_pos, 1),
              'Position apart, p95 (mm)': round(new['pos_p95_mm'] - old['pos_p95_mm'], 1),
              'Heading apart, median (°)': round(d_yaw, 2)}
    st.dataframe(pd.DataFrame([row('Current mounts (VisionConstants)', old), row('Calibrated mounts', new), change]),
                 hide_index=True, use_container_width=True)

    pct = -100.0 * d_pos / old['pos_median_mm'] if old['pos_median_mm'] else 0.0
    if d_pos < -5 and pct > 15:
        st.success(f'The cameras agree {pct:.0f}% better with the calibrated mounts '
                   f'({old["pos_median_mm"]:.0f} -> {new["pos_median_mm"]:.0f} mm typical gap).')
    elif d_pos > 5:
        st.error('The cameras agree WORSE with the calibrated mounts. Do not use these; see the warnings and '
                 'the phase table above.')
    else:
        st.info('No clear change. Either the current mounts were already good, or the data is too noisy to tell. '
                'Single-frame noise alone keeps two cameras ~20-30 mm apart, so a gap near that is about as good as it gets.')
    # save once per pair of solves (Streamlit reruns this function on every click)
    key = ('_autocal_agreement_saved', id(L['res']), id(R['res']))
    saved = st.session_state.get(key)
    if saved is None:
        try:
            saved = save_agreement(nameL, nameR, old, new, L.get('log_name')).name
        except OSError:
            saved = ''
        st.session_state[key] = saved
    if saved:
        st.caption(f'Saved automatically: `tools/camera-calibration/results/{saved}` (git-ignored; '
                   '`git add -f` it to keep it).')
