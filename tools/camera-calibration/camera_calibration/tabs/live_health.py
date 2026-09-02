"""Tab 5 — Live Health: live 0-100 camera health snapshot read straight from NT4.

Unlike every other tab in this app, this one does not read a .wpilog — it
connects live to the robot/coprocessor's NetworkTables server and polls it.
It's a tuning aid for "did that mount/config change help or hurt," not a
match-accuracy tool — see tools/vision-analyzer for that.

The score itself is computed on the robot (VisionHealth.java) and published
under RealOutputs/Vision/*/Health/* -- this tab only displays what nt_client.py
reads back. It used to compute the score itself from raw per-sample vision
inputs, duplicating LerpTable curves that lived in VisionConstants.java; now
there's one implementation, and it's replayable against match logs too.

Layout note: earlier versions redrew a bar-meter chart from scratch every
refresh tick with no memory of history, and ran the (expensive -- it enumerates
every NT topic on the server) Diagnostics panel on that same fast tick, which
together made the whole page flicker unusably fast. This version keeps a
rolling history buffer per camera so the trend and rolling average are
visible instead of a single noisy instant, and Diagnostics gets its own
independent, much slower refresh cycle.
"""
import logging
import math
import time
from typing import Optional

import streamlit as st

from .. import nt_client
from ..health_display import is_unmeasurable, severity_word

log = logging.getLogger(__name__)

LABEL = '5 · Live Health'

_BG = '#111827'  # matches tabs/timeline.py's dark plot background
_TREND_WINDOW_SEC = 60.0
_AVG_WINDOW_SEC = 10.0
_DIAGNOSTICS_REFRESH_SEC = 3.0

# (history key, legend label, line color) -- kept dim/legend-only by default so the trend
# chart opens on just the composite Score line; click a legend entry to drill into that
# specific factor's trace without cluttering the default view.
_FACTORS = [
    ('stillness', 'Stillness', '#f2c14e'),
    ('area', 'Tag area', '#3987e5'),
    ('ambiguity', 'Ambiguity', '#9b59b6'),
    ('fps', 'FPS', '#2ecc71'),
    ('jitter', 'Jitter', '#e67e22'),
    ('acceptance', 'Acceptance', '#1abc9c'),
    ('latency', 'Latency', '#e74c3c'),
    ('multitag', 'Multi-tag', '#95a5a6'),
]


def _rolling_avg(records: list[dict], field: str, window_sec: float, now: float) -> float:
    vals = [r[field] for r in records if now - r['t'] <= window_sec and not math.isnan(r[field])]
    return sum(vals) / len(vals) if vals else float('nan')


def _trend_figure(records: list[dict], now: float):
    import plotly.graph_objects as go

    recent = [r for r in records if now - r['t'] <= _TREND_WINDOW_SEC]
    xs = [-(now - r['t']) for r in recent]

    fig = go.Figure()
    for field, label, color in _FACTORS:
        fig.add_trace(go.Scatter(
            x=xs, y=[r.get(field, float('nan')) for r in recent],
            mode='lines', name=label, line=dict(color=color, width=1.5),
            visible='legendonly', hovertemplate=f'{label}: %{{y:.0f}}<extra></extra>',
        ))
    fig.add_trace(go.Scatter(
        x=xs, y=[r.get('score', float('nan')) for r in recent],
        mode='lines', name='Score', line=dict(color='#f5f5f5', width=3),
        hovertemplate='Score: %{y:.0f}<extra></extra>',
    ))
    fig.update_layout(
        template='plotly_dark', height=280,
        xaxis=dict(title='seconds ago', range=[-_TREND_WINDOW_SEC, 0], showgrid=False),
        yaxis=dict(title='%', range=[0, 100]),
        legend=dict(orientation='h', y=-0.22),
        margin=dict(l=40, r=10, t=10, b=10),
        plot_bgcolor=_BG, paper_bgcolor=_BG,
        uirevision='trend',  # preserves legend show/hide + zoom state across refreshes
    )
    return fig


def _render_camera_panel(camera: str, cam_data: dict, records: list[dict], now: float) -> None:
    score = cam_data.get('health_score', float('nan'))
    reason = cam_data.get('health_reason', '')
    unmeasurable = is_unmeasurable(score, reason)
    avg = _rolling_avg(records, 'score', _AVG_WINDOW_SEC, now)

    avg_text = 'n/a' if math.isnan(avg) else f'{avg:.0f}'
    st.markdown(f'#### {camera} — {_AVG_WINDOW_SEC:.0f}s avg: :{severity_word(avg)}[{avg_text}]')

    inst_text = 'n/a' if unmeasurable else f'{score:.0f}'
    detail = f' — {reason}' if reason else ''
    st.caption(f'Instantaneous: {inst_text}{detail}')

    tags = cam_data.get('visible_tag_ids', [])
    st.caption(
        f"Tags visible: {tags if tags else '—'}  |  FPS: {cam_data.get('current_fps', 0.0):.1f}"
    )

    if len(records) >= 2:
        st.plotly_chart(_trend_figure(records, now), use_container_width=True,
                         config={'displayModeBar': False}, key=f'_health_trend_{camera}')
    else:
        st.caption('Collecting history…')

    with st.expander(f'{camera} — recent raw samples'):
        rows = [
            {
                'sec_ago': round(now - r['t'], 1),
                'score': round(r['score'], 1) if not math.isnan(r['score']) else None,
                **{label: round(r.get(field, float('nan')), 1) for field, label, _ in _FACTORS},
            }
            for r in list(records)[-20:][::-1]
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_score_gap(left_records: list[dict], right_records: list[dict], now: float) -> None:
    """Makes the *magnitude* of the difference between cameras explicit instead of requiring
    a visual eyeball comparison of two independently-updating panels."""
    left_avg = _rolling_avg(left_records, 'score', _AVG_WINDOW_SEC, now)
    right_avg = _rolling_avg(right_records, 'score', _AVG_WINDOW_SEC, now)
    if math.isnan(left_avg) or math.isnan(right_avg):
        return
    gap = left_avg - right_avg
    leader = 'Left' if gap > 0 else 'Right' if gap < 0 else None
    if leader is None:
        st.markdown(f'**Score gap ({_AVG_WINDOW_SEC:.0f}s avg):** 0 — cameras reading equal')
    else:
        st.markdown(
            f'**Score gap ({_AVG_WINDOW_SEC:.0f}s avg):** {abs(gap):.1f} points '
            f'— **{leader}** reading higher (Left {left_avg:.0f} / Right {right_avg:.0f})'
        )


def _render_cross_camera_panel(snapshot: dict, records: list[dict], now: float) -> None:
    """The one check on this tab that can catch a systematically mis-calibrated camera
    (wrong mount transform) -- a bad camera can look perfectly clean on every
    single-camera metric above and still disagree with the other camera's read."""
    score = snapshot.get('cross_score', float('nan'))
    reason = snapshot.get('cross_reason', '')
    unmeasurable = is_unmeasurable(score, reason)
    avg = _rolling_avg(records, 'score', _AVG_WINDOW_SEC, now)

    avg_text = 'n/a' if math.isnan(avg) else f'{avg:.0f}'
    st.markdown(f'#### Cross-camera agreement — {_AVG_WINDOW_SEC:.0f}s avg: :{severity_word(avg)}[{avg_text}]')

    inst_text = 'n/a' if unmeasurable else f'{score:.0f}'
    detail = f' — {reason}' if reason else ''
    st.caption(
        f'Instantaneous: {inst_text}{detail}  |  '
        f"Translation delta: {snapshot.get('cross_translation_delta', 0.0) * 100:.1f} cm  |  "
        f"Rotation delta: {snapshot.get('cross_rotation_delta', 0.0):.1f}°"
    )


def _render_diagnostics(root_table: str) -> None:
    """Splits "why is this blank" into the three places it can actually break:
    no TCP connection to any server, connection but wrong topic paths, or right
    paths but no value received yet. Deliberately its own slow-refresh fragment
    (see _diagnostics_panel) -- discover_topics() enumerates every topic on the
    server, which is too heavy to run on the same fast tick as the health panels.
    """
    snapshot = nt_client.read()
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
                "(bool/double/double[]/int[]/string) may not match what's actually being published."
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


def _record_from(cam_data: dict, now: float) -> dict:
    return {
        't': now,
        'score': cam_data.get('health_score', float('nan')),
        **{field: cam_data.get(f'health_{field}', float('nan')) for field, _, _ in _FACTORS},
    }


def _append_trimmed(records: list[dict], record: dict) -> None:
    records.append(record)
    cutoff = record['t'] - _TREND_WINDOW_SEC
    while records and records[0]['t'] < cutoff:
        records.pop(0)


def _live_panel(root_table: str) -> None:
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

    for camera in ('Left', 'Right'):
        _append_trimmed(history[camera], _record_from(snapshot.get(camera, {}), now))
    _append_trimmed(history['cross'], {'t': now, 'score': snapshot.get('cross_score', float('nan'))})

    _render_score_gap(history['Left'], history['Right'], now)

    cols = st.columns(2)
    for col, camera in zip(cols, ('Left', 'Right')):
        with col:
            _render_camera_panel(camera, snapshot.get(camera, {}), history[camera], now)

    _render_cross_camera_panel(snapshot, history['cross'], now)


def _diagnostics_panel(root_table: str) -> None:
    _render_diagnostics(root_table)


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
        'the robot sits still with a tag in view. Scored on the robot (VisionHealth.java) — '
        'this tab just displays it. This is a **tuning aid** — watch it while you change a '
        'mount angle or pipeline setting, not a match-accuracy report (see **Vision Analyzer** '
        'for that). A camera at a worse angle than the other will always read lower; what '
        'matters is the *same* camera trending up or down as you adjust it.'
    )

    if '_health_history' not in st.session_state:
        st.session_state['_health_history'] = {'Left': [], 'Right': [], 'cross': []}

    with st.expander('Connection', expanded=not nt_client.is_connected()):
        c1, c2 = st.columns([2, 2])
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

        b1, b2 = st.columns(2)
        with b1:
            if st.button('Connect' if not nt_client.is_connected() else 'Reconnect', type='primary'):
                nt_client.connect(server, root_table)
                st.rerun()
        with b2:
            if nt_client.is_connected() and st.button('Disconnect'):
                nt_client.disconnect()
                st.session_state['_health_history'] = {'Left': [], 'Right': [], 'cross': []}
                st.rerun()

        st.caption('🟢 NT connected' if nt_client.is_connected() else '⚪ Not connected')

    if not nt_client.is_connected():
        st.info('Connect to NetworkTables above to start the live health view.')
        return

    refresh_s = st.select_slider('Refresh interval', options=[0.5, 1.0, 2.0, 5.0], value=1.0)
    root_table_clean = root_table.strip('/')
    st.fragment(run_every=f'{refresh_s}s')(_live_panel)(root_table_clean)
    st.fragment(run_every=f'{_DIAGNOSTICS_REFRESH_SEC}s')(_diagnostics_panel)(root_table_clean)
