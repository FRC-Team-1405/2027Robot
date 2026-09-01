"""Tab 5 — Live Health: live 0-100 camera health snapshot read straight from NT4.

Unlike every other tab in this app, this one does not read a .wpilog — it
connects live to the robot/coprocessor's NetworkTables server and polls it.
It's a tuning aid for "did that mount/config change help or hurt," not a
match-accuracy tool — see tools/vision-analyzer for that.
"""
import logging
import time
from typing import Optional

import streamlit as st

from .. import health as health_mod
from .. import nt_client

log = logging.getLogger(__name__)

LABEL = '5 · Live Health'

_HISTORY_WINDOW_SEC = 60.0
_BG = '#111827'  # matches tabs/timeline.py's dark plot background


def _status_color(pct: Optional[float]) -> str:
    if pct is None:
        return '#5c5b57'
    if pct >= 80:
        return '#0ca30c'
    if pct >= 60:
        return '#fab219'
    if pct >= 40:
        return '#ec835a'
    return '#d03b3b'


def _meter_figure(rows: list[tuple[str, Optional[float]]]):
    import plotly.graph_objects as go

    labels = [r[0] for r in rows][::-1]
    values = [0.0 if r[1] is None else r[1] for r in rows][::-1]
    colors = [_status_color(r[1]) for r in rows][::-1]
    texts = ['n/a' if r[1] is None else f'{r[1]:.0f}' for r in rows][::-1]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[100] * len(rows), y=labels, orientation='h',
        marker_color='rgba(255,255,255,0.08)', hoverinfo='skip', showlegend=False, width=0.6,
    ))
    fig.add_trace(go.Bar(
        x=values, y=labels, orientation='h',
        marker_color=colors, text=texts, textposition='outside',
        hoverinfo='skip', showlegend=False, width=0.6,
    ))
    fig.update_layout(
        barmode='overlay', template='plotly_dark',
        height=42 * len(rows) + 30,
        xaxis=dict(range=[0, 112], showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False),
        margin=dict(l=90, r=30, t=10, b=10),
        plot_bgcolor=_BG, paper_bgcolor=_BG,
    )
    return fig


def _sparkline_figure(points: list[tuple[float, float]]):
    import plotly.graph_objects as go

    xs = [-p[0] for p in points]
    ys = [p[1] for p in points]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode='lines', line=dict(color='#3987e5', width=2),
        fill='tozeroy', fillcolor='rgba(57,135,229,0.15)',
        hovertemplate='%{y:.0f}<extra></extra>',
    ))
    fig.update_layout(
        template='plotly_dark', height=130,
        xaxis=dict(title='seconds ago', range=[-_HISTORY_WINDOW_SEC, 0], showgrid=False),
        yaxis=dict(title='Health', range=[0, 100]),
        margin=dict(l=40, r=10, t=10, b=30),
        plot_bgcolor=_BG, paper_bgcolor=_BG,
    )
    return fig


def _render_camera_panel(camera: str, reading: health_mod.HealthReading, cam_data: dict,
                          history: list[tuple[float, Optional[float]]], now: float) -> None:
    st.markdown(f'#### {camera} camera')

    if reading.score is None:
        st.markdown(
            f"<div style='padding:14px;border-radius:8px;background:#5c5b5733;"
            f"color:#c3c2b7;text-align:center;font-size:1.1em'>⚪ {reading.reason}</div>",
            unsafe_allow_html=True,
        )
    else:
        color = _status_color(reading.score)
        st.markdown(
            f"<div style='padding:10px;border-radius:8px;background:{color}22;"
            f"border:1px solid {color};color:{color};text-align:center;"
            f"font-size:2.4em;font-weight:700'>{reading.score:.0f}</div>",
            unsafe_allow_html=True,
        )

    tags = cam_data.get('visible_tag_ids', [])
    st.caption(
        f"Tags visible: {tags if tags else '—'}  |  FPS: {cam_data.get('current_fps', 0.0):.1f}"
    )

    st.plotly_chart(
        _meter_figure([
            ('Stillness', None if reading.score is None else reading.stillness_pct),
            ('Tag area',  None if reading.score is None else reading.area_pct),
            ('Ambiguity', None if reading.score is None else reading.ambiguity_pct),
            ('FPS',       None if reading.score is None else reading.fps_pct),
        ]),
        use_container_width=True, config={'displayModeBar': False}, key=f'_health_meter_{camera}',
    )

    spark = [(now - t, v) for t, v in history if v is not None]
    if len(spark) >= 2:
        st.plotly_chart(_sparkline_figure(spark), use_container_width=True,
                         config={'displayModeBar': False}, key=f'_health_spark_{camera}')
    else:
        st.caption('Collecting history…')

    with st.expander('Raw values'):
        st.json({
            'sum_tag_area_pct': round(cam_data.get('sum_tag_area', 0.0), 3),
            'ambiguity': round(cam_data.get('ambiguity', -1.0), 3),
            'current_fps': round(cam_data.get('current_fps', 0.0), 1),
            'visible_tag_ids': tags,
        })


def _render_diagnostics(snapshot: dict, root_table: str) -> None:
    """Splits "why is this blank" into the three places it can actually break:
    no TCP connection to any server, connection but wrong topic paths, or right
    paths but no value received yet. Refreshes live alongside the rest of the tab.
    """
    conns = nt_client.get_connections()
    diag_rows = nt_client.topic_diagnostics()
    any_topic_exists = any(r['exists'] for r in diag_rows)
    any_camera_connected = any(snapshot.get(cam, {}).get('connected') for cam in ('Left', 'Right'))

    with st.expander('🔍 Diagnostics', expanded=not conns or not any_topic_exists or not any_camera_connected):
        st.markdown('**NT4 connections** — ground truth on whether we have reached any server at all')
        if conns:
            st.dataframe(conns, use_container_width=True, hide_index=True)
        else:
            st.error(
                'No active NT4 connection — the client has never reached a server. Check the '
                'team number/address, that the robot or coprocessor is powered and reachable on '
                'this network, and that nothing is blocking NT4 (port 5810).'
            )

        events = nt_client.connection_events()
        if events:
            st.caption('Recent connection events (most recent first):')
            st.code('\n'.join(events[:10]))

        st.markdown('**Expected topics** — does each exist on the wire, and has it ever produced a value?')
        if diag_rows:
            st.dataframe(diag_rows, use_container_width=True, hide_index=True)
        if diag_rows and not any_topic_exists:
            st.warning(
                'None of the expected topics exist on the server. The NT root table name is '
                'almost certainly wrong for this robot — compare against "Discovered topics" '
                'below and update **NT root table** in the Connection panel to match.'
            )
        elif diag_rows and not any(r['ever_received'] for r in diag_rows if r['exists']):
            st.warning(
                'Topics exist but none have ever produced a value — the type we subscribed with '
                "(bool/double/double[]/int[]) may not match what's actually being published."
            )

        st.markdown(f'**Discovered topics under `/{root_table}`** — the real tree, from the wire')
        discovered = nt_client.discover_topics(f'/{root_table}')
        if not discovered:
            st.caption(f'Nothing announced under `/{root_table}` yet — showing everything instead:')
            discovered = nt_client.discover_topics('')
        if discovered:
            st.dataframe(
                [{'topic': name, 'type': t} for name, t in discovered],
                use_container_width=True, hide_index=True, height=240,
            )
        else:
            st.caption('No topics discovered at all yet.')


def _live_panel(target_fps: float, root_table: str) -> None:
    snapshot = nt_client.read()
    history = st.session_state['_health_history']
    now = time.time()

    if not snapshot.get('nt_connected', False):
        st.warning('NT4 client lost its connection to the server — check the radio/network.')

    lin_speed = snapshot.get('lin_speed', 0.0)
    ang_speed = snapshot.get('ang_speed', 0.0)
    still = abs(lin_speed) <= 0.06 and abs(ang_speed) <= 0.06
    st.caption(
        f"Drivetrain: {lin_speed:.3f} m/s linear, {ang_speed:.3f} rad/s angular — "
        + ('stationary ✓' if still else 'moving — hold the robot still for an accurate reading')
    )

    cols = st.columns(2)
    for col, camera in zip(cols, ('Left', 'Right')):
        cam_data = snapshot.get(camera, {})
        reading = health_mod.compute_health(
            connected=cam_data.get('connected', False),
            has_tag=len(cam_data.get('visible_tag_ids', [])) > 0,
            lin_speed=lin_speed, ang_speed=ang_speed,
            sum_tag_area=cam_data.get('sum_tag_area', 0.0),
            ambiguity=cam_data.get('ambiguity', -1.0),
            current_fps=cam_data.get('current_fps', 0.0),
            target_fps=target_fps,
        )

        hist = history[camera]
        hist.append((now, reading.score))
        cutoff = now - _HISTORY_WINDOW_SEC
        while hist and hist[0][0] < cutoff:
            hist.pop(0)

        with col:
            _render_camera_panel(camera, reading, cam_data, hist, now)

    _render_diagnostics(snapshot, root_table)


def render(ctx: dict) -> None:
    try:
        import ntcore  # noqa: F401
    except ImportError:
        st.error(
            'This tab needs `pyntcore` to talk to NetworkTables live.\n\n'
            'Install it with:\n```\npip install pyntcore\n```\nthen reload this page.'
        )
        return

    st.markdown(
        'Live 0–100 health snapshot per camera, sampled straight from NetworkTables while '
        'the robot sits still with a tag in view. This is a **tuning aid** — watch it while '
        'you change a mount angle or pipeline setting, not a match-accuracy report (see '
        '**Vision Analyzer** for that). A camera at a worse angle than the other will always '
        'read lower; what matters is the *same* camera trending up or down as you adjust it.'
    )

    if '_health_history' not in st.session_state:
        st.session_state['_health_history'] = {'Left': [], 'Right': []}

    with st.expander('Connection', expanded=not nt_client.is_connected()):
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            server = st.text_input(
                'Team number or server address', value='1405',
                help='"1405" over the FMS/radio, or an address like "10.14.5.2" / '
                     '"localhost" (simulateJava) to connect directly.',
            )
        with c2:
            root_table = st.text_input(
                'NT root table', value=nt_client.DEFAULT_ROOT_TABLE,
                help="AdvantageKit's NT4Publisher table root — only change this if the "
                     'project overrode the default.',
            )
        with c3:
            target_fps = st.number_input(
                'Target FPS', value=30.0, min_value=1.0, step=1.0,
                help='Camera/pipeline-dependent. Set to the FPS you expect at 100% health.',
            )

        b1, b2 = st.columns(2)
        with b1:
            if st.button('Connect' if not nt_client.is_connected() else 'Reconnect', type='primary'):
                nt_client.connect(server, root_table)
                st.rerun()
        with b2:
            if nt_client.is_connected() and st.button('Disconnect'):
                nt_client.disconnect()
                st.session_state['_health_history'] = {'Left': [], 'Right': []}
                st.rerun()

        st.caption('🟢 NT connected' if nt_client.is_connected() else '⚪ Not connected')

    if not nt_client.is_connected():
        st.info('Connect to NetworkTables above to start the live health view.')
        return

    refresh_s = st.select_slider('Refresh interval', options=[0.25, 0.5, 1.0, 2.0], value=0.5)
    st.fragment(run_every=f'{refresh_s}s')(_live_panel)(target_fps, root_table.strip('/'))
