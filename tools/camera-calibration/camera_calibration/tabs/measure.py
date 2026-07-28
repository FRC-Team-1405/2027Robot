"""Tab 1 — Measure: convert tape readings to robot poses, showing all math steps."""
import pandas as pd
import streamlit as st

from ..session import (
    compute_x_in, compute_y_in, compute_heading_deg,
    user_heading_to_wpilib_yaw, math_breakdown,
)

LABEL = '1 · Measure'

_DEFAULT_DF = pd.DataFrame({
    'Label':        ['Stop 1', 'Stop 2', 'Stop 3'],
    'Tape A (in)':  [72.0,     84.0,     60.0],
    'Tape B (in)':  [0.0,      6.0,      0.0],
    'Side':         ['left',   'left',   'right'],
    'Corner L (in)':[0.5,      1.2,      0.5],
    'Corner R (in)':[0.5,      2.8,      0.5],
})


def render(ctx: dict) -> None:
    rc = ctx['robot_cfg']  # bumper_depth, half_len, half_wid, bumper_rail_w

    st.markdown(
        '**Enter one row per robot stop.** '
        'Tape A = perpendicular distance from tag-face wall to nearest bumper face. '
        'Tape B = distance from tag centerline to nearest bumper rail edge (unsigned). '
        'Corner L/R = distance from each front bumper corner to the tag-face wall.'
    )

    if '_calib_meas_df' not in st.session_state:
        st.session_state['_calib_meas_df'] = _DEFAULT_DF.copy()

    edited: pd.DataFrame = st.data_editor(
        st.session_state['_calib_meas_df'],
        column_config={
            'Label':         st.column_config.TextColumn('Label', width='small'),
            'Tape A (in)':   st.column_config.NumberColumn('Tape A (in)', format='%.2f', min_value=0.0),
            'Tape B (in)':   st.column_config.NumberColumn('Tape B (in)', format='%.2f', min_value=0.0),
            'Side':          st.column_config.SelectboxColumn('Side', options=['left', 'right'], width='small'),
            'Corner L (in)': st.column_config.NumberColumn('Corner L (in)', format='%.2f', min_value=0.0),
            'Corner R (in)': st.column_config.NumberColumn('Corner R (in)', format='%.2f', min_value=0.0),
        },
        num_rows='dynamic',
        use_container_width=True,
        key='_calib_meas_editor',
    )
    # Do NOT write `edited` back into '_calib_meas_df': that key only seeds
    # the widget's `value=` on first render, and nothing else reads it
    # afterward, so reassigning it here just fights the widget's own
    # per-cell edit tracking (keyed by '_calib_meas_editor') for no benefit.
    # Read live data from `edited` below instead.
    #
    # Note: this does NOT fix the "typing fast clears the cell, works on the
    # second try" glitch reported against this table. That reproduces even
    # in a bare `st.data_editor` with none of this app's code — it's an
    # upstream Streamlit/glide-data-grid issue where fast keystrokes race a
    # re-render and only the last character survives (matches
    # streamlit/streamlit#7831). Workaround: paste values instead of typing
    # them, or pause briefly between digits.

    # Compute results
    rows = []
    for _, row in edited.iterrows():
        try:
            x_in = compute_x_in(row['Tape A (in)'], rc['bumper_depth'], rc['half_len'])
            y_in = compute_y_in(row['Tape B (in)'], rc['half_wid'], row['Side'])
            h    = compute_heading_deg(row['Corner L (in)'], row['Corner R (in)'],
                                       rc['bumper_rail_w'])
        except Exception:
            x_in = y_in = h = float('nan')
        rows.append({
            'Label':   row['Label'],
            'x_m':     round(x_in * 0.0254, 4),
            'y_m':     round(y_in * 0.0254, 4),
            'heading': round(h, 2),
            'x_in':    round(x_in, 3),
            'y_in':    round(y_in, 3),
        })

    results_df = pd.DataFrame(rows)[['Label', 'x_m', 'y_m', 'heading', 'x_in', 'y_in']]
    results_df.columns = ['Label', 'x (m)', 'y (m)', 'heading (°)', 'x (in)', 'y (in)']
    st.session_state['_calib_meas_results'] = rows

    st.markdown('---')
    st.markdown('#### Computed Robot Poses')
    st.caption(
        'x = perpendicular distance from tag face plane to robot center  |  '
        'y = lateral offset (−left, +right from robot POV facing tag)  |  '
        'heading = CCW positive, 0° = facing tag straight-on'
    )
    st.dataframe(results_df, use_container_width=True, hide_index=True)

    # Math breakdown expander — shows steps for the selected row
    st.markdown('---')
    st.markdown('#### Step-by-Step Math')
    if rows:
        labels = [r['Label'] for r in rows]
        sel_label = st.selectbox('Show breakdown for', labels, key='_calib_meas_sel')
        sel_row = next((r for r in rows if r['Label'] == sel_label), None)
        if sel_row is not None:
            orig = edited[edited['Label'] == sel_label].iloc[0]
            steps = math_breakdown(
                tape_a_in=orig['Tape A (in)'],
                bumper_depth_in=rc['bumper_depth'],
                half_length_in=rc['half_len'],
                tape_b_in=orig['Tape B (in)'],
                half_width_in=rc['half_wid'],
                side=orig['Side'],
                corner_l_in=orig['Corner L (in)'],
                corner_r_in=orig['Corner R (in)'],
                bumper_rail_width_in=rc['bumper_rail_w'],
            )
            _render_math_steps(steps)

    st.markdown('---')
    st.markdown('#### Heading Formula Reference')
    with st.expander('How to measure heading'):
        st.markdown(
            '''
**Setup:** lay a tape measure along the floor parallel to the wall, passing near the
front of the robot. When the robot is straight (facing the tag), both front bumper corners
are the same distance from the wall face.

**Measure:** hold a tape measure or stick perpendicularly from the wall face to each
front bumper corner:
- **Corner L** = left front corner distance to wall (smaller = closer to wall)
- **Corner R** = right front corner distance to wall

**Formula:**
```
heading = asin((Corner L − Corner R) / bumper rail width)
```
This is exact for a rigid rectangular footprint pivoting about its center —
not just a small-angle approximation — so it holds at large headings too.

| Scenario | Corner R vs. Corner L | Heading |
|---|---|---|
| Facing tag straight | R = L | 0° |
| Turned CCW (left) | R < L | + degrees |
| Turned CW (right)  | R > L | − degrees |

**Tip:** for ≤5° heading, a square or speed-square against the bumper is faster and
good enough. Use the corner method for larger angles.
'''
        )


def _render_math_steps(steps: list[tuple[str, str, str]]) -> None:
    for name, formula, result in steps:
        col_name, col_formula, col_result = st.columns([1.4, 4, 1.2])
        with col_name:
            st.markdown(f'**{name}**')
        with col_formula:
            st.code(formula, language=None)
        with col_result:
            st.markdown(f'**{result}**')
