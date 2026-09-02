"""Tab 6 — Replay: play/pause/scrub a .wpilog and watch camera health track the robot's
position on the field, together, instead of as two separate disconnected numbers.

Uses whatever log is already loaded in the sidebar (same uploader every other tab reads
from) -- there's no separate file picker here.

Needs two signals this session's changes added:
  - Vision/*/Health/* (VisionHealth.java / Vision.java) -- the 0-100 health score over time.
  - Drivetrain/Pose (CommandSwerveDrivetrain.java) -- the robot's fused field pose. This
    genuinely did not exist before: only Drivetrain/Speeds was logged via AdvantageKit, so
    there was no way to know where the robot was without this addition.
Logs recorded before those changes will be missing one or both; this tab says so plainly
rather than silently rendering an empty field/chart.
"""
import logging
import math

import streamlit as st

from vision_analyzer.constants import APRILTAG_POSITIONS, FIELD_LENGTH, FIELD_WIDTH
from vision_analyzer.metrics import nearest_value

from ..health_display import is_unmeasurable, severity_word

log = logging.getLogger(__name__)

LABEL = '6 · Replay'

_BG = '#111827'
_CAMERAS = ('Left', 'Right')
_TRAIL_SEC = 3.0
_TICK_SEC = 0.2

# (record key, legend label, line color) — mirrors tabs/live_health.py's _FACTORS.
_FACTORS = [
    ('stillness', 'Stillness', '#f2c14e', 'StillnessPercent'),
    ('area', 'Tag area', '#3987e5', 'AreaPercent'),
    ('ambiguity', 'Ambiguity', '#9b59b6', 'AmbiguityPercent'),
    ('fps', 'FPS', '#2ecc71', 'FpsPercent'),
    ('jitter', 'Jitter', '#e67e22', 'JitterPercent'),
    ('acceptance', 'Acceptance', '#1abc9c', 'AcceptanceRateFactorPercent'),
    ('latency', 'Latency', '#e74c3c', 'LatencyPercent'),
    ('multitag', 'Multi-tag', '#95a5a6', 'MultiTagRatioPercent'),
]


def _find_signal(signals: dict, base_key: str):
    for prefix in ('RealOutputs/', ''):
        k = prefix + base_key
        if k in signals:
            return signals[k]
    return None


def _load_series(signals: dict) -> dict:
    """Pulls every signal this tab needs out of the parsed log once per log, cached by the
    signals dict's identity (app.py's st.cache_data already guarantees the same dict object
    is reused across reruns for the same uploaded/pathed log) so scrubbing/playback doesn't
    re-walk signal lookups on every tick."""
    cache = st.session_state.setdefault('_replay_series_cache', {})
    key = id(signals)
    if key in cache:
        return cache[key]

    result: dict = {'pose': _find_signal(signals, 'Drivetrain/Pose') or [], 'cameras': {}}
    for cam in _CAMERAS:
        cam_series = {
            'score': _find_signal(signals, f'Vision/{cam}/Health/ScorePercent') or [],
            'reason': _find_signal(signals, f'Vision/{cam}/Health/Reason') or [],
            'visible_tags': _find_signal(signals, f'Vision/{cam}/visibleTagIds') or [],
        }
        for field, _, _, suffix in _FACTORS:
            cam_series[field] = _find_signal(signals, f'Vision/{cam}/Health/{suffix}') or []
        result['cameras'][cam] = cam_series
    result['cross_score'] = _find_signal(signals, 'Vision/CrossCameraAgreement/ScorePercent') or []
    result['cross_reason'] = _find_signal(signals, 'Vision/CrossCameraAgreement/Reason') or []

    cache.clear()  # only the most-recently-loaded log's series is worth keeping around
    cache[key] = result
    return result


def _trend_figure(cam_series: dict, start_t: float, playhead: float):
    import plotly.graph_objects as go

    fig = go.Figure()
    for field, label, color, _ in _FACTORS:
        sig = cam_series.get(field, [])
        if not sig:
            continue
        fig.add_trace(go.Scatter(
            x=[t - start_t for t, _ in sig], y=[v for _, v in sig],
            mode='lines', name=label, line=dict(color=color, width=1.2),
            visible='legendonly', hovertemplate=f'{label}: %{{y:.0f}}<extra></extra>',
        ))
    score_sig = cam_series.get('score', [])
    if score_sig:
        fig.add_trace(go.Scatter(
            x=[t - start_t for t, _ in score_sig], y=[v for _, v in score_sig],
            mode='lines', name='Score', line=dict(color='#f5f5f5', width=2.2),
            hovertemplate='Score: %{y:.0f}<extra></extra>',
        ))
    fig.add_vline(x=playhead - start_t, line_color='#e74c3c', line_width=2)
    fig.update_layout(
        template='plotly_dark', height=230,
        xaxis=dict(title='s from log start'), yaxis=dict(title='%', range=[0, 100]),
        legend=dict(orientation='h', y=-0.35),
        margin=dict(l=40, r=10, t=10, b=10),
        plot_bgcolor=_BG, paper_bgcolor=_BG,
        uirevision='replay-trend',  # keeps legend show/hide + zoom stable while the vline moves
    )
    return fig


def _field_figure(pose_now, trail: list[tuple[float, float]], visible_tags: set[int]):
    import plotly.graph_objects as go

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[0, FIELD_LENGTH, FIELD_LENGTH, 0, 0], y=[0, 0, FIELD_WIDTH, FIELD_WIDTH, 0],
        mode='lines', line=dict(color='#555', width=1), showlegend=False, hoverinfo='skip',
    ))

    dim_ids = [t for t in APRILTAG_POSITIONS if t not in visible_tags]
    lit_ids = [t for t in APRILTAG_POSITIONS if t in visible_tags]
    if dim_ids:
        fig.add_trace(go.Scatter(
            x=[APRILTAG_POSITIONS[t][0] for t in dim_ids], y=[APRILTAG_POSITIONS[t][1] for t in dim_ids],
            mode='markers', marker=dict(size=9, color='#3a3a3a', line=dict(color='#666', width=1)),
            hovertext=[f'Tag {t}' for t in dim_ids], hoverinfo='text', showlegend=False,
        ))
    if lit_ids:
        fig.add_trace(go.Scatter(
            x=[APRILTAG_POSITIONS[t][0] for t in lit_ids], y=[APRILTAG_POSITIONS[t][1] for t in lit_ids],
            mode='markers+text', text=[str(t) for t in lit_ids],
            textposition='top center', textfont=dict(size=9),
            marker=dict(size=15, color='#27ae60', line=dict(color='white', width=2)),
            name='Visible now',
        ))

    if trail:
        fig.add_trace(go.Scatter(
            x=[p[0] for p in trail], y=[p[1] for p in trail], mode='lines',
            line=dict(color='rgba(79,195,247,0.45)', width=2), showlegend=False, hoverinfo='skip',
        ))

    if pose_now is not None:
        x, y, rot = pose_now
        hx, hy = x + 0.5 * math.cos(rot), y + 0.5 * math.sin(rot)
        fig.add_trace(go.Scatter(
            x=[x, hx], y=[y, hy], mode='lines', line=dict(color='#f5f5f5', width=3),
            showlegend=False, hoverinfo='skip',
        ))
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode='markers',
            marker=dict(size=16, color='#f5f5f5', line=dict(color='#111827', width=2)),
            name='Robot',
        ))

    fig.update_layout(
        template='plotly_dark',
        xaxis=dict(title='X (m)', range=[0, FIELD_LENGTH]),
        yaxis=dict(title='Y (m)', range=[0, FIELD_WIDTH], scaleanchor='x', scaleratio=1),
        height=420, margin=dict(l=40, r=20, t=20, b=40),
        plot_bgcolor=_BG, paper_bgcolor=_BG,
        legend=dict(orientation='h', y=-0.12),
        uirevision='replay-field',
    )
    return fig


def _score_line(label: str, score, reason: str) -> str:
    unmeasurable = is_unmeasurable(score, reason)
    text = 'n/a' if unmeasurable else f'{score:.0f}'
    word = severity_word(None if unmeasurable else score)
    suffix = f' — {reason}' if reason else ''
    return f'**{label}:** :{word}[{text}]{suffix}'


def _playback_body(series: dict, start_t: float, end_t: float, duration: float) -> None:
    if st.session_state['_replay_playing']:
        speed = st.session_state['_replay_speed']
        st.session_state['_replay_t'] = min(end_t, st.session_state['_replay_t'] + speed * _TICK_SEC)
        if st.session_state['_replay_t'] >= end_t:
            # Stops advancing immediately; the fragment itself keeps ticking on the old
            # interval until the next full-page rerun (e.g. Play/Reset/Speed outside this
            # fragment) picks up run_every=None — harmless, since nothing visible changes
            # once _replay_t is pinned at end_t.
            st.session_state['_replay_playing'] = False

    now_rel = st.session_state['_replay_t'] - start_t
    slider_val = st.slider(
        'Scrub', 0.0, duration, value=min(max(now_rel, 0.0), duration), step=0.05,
    )
    if abs(slider_val - now_rel) > 1e-9:
        st.session_state['_replay_t'] = start_t + slider_val
        st.session_state['_replay_playing'] = False

    playhead = st.session_state['_replay_t']
    st.caption(
        f't = {playhead - start_t:.1f}s / {duration:.1f}s'
        + ('  ▶ playing' if st.session_state['_replay_playing'] else '  ⏸ paused')
    )

    pose_sig = series['pose']
    pose_now = None
    trail: list[tuple[float, float]] = []
    if pose_sig:
        raw = nearest_value(pose_sig, playhead)
        if raw is not None:
            pose_now = (raw['x'], raw['y'], raw['rot'])
        trail = [(v['x'], v['y']) for t, v in pose_sig if playhead - _TRAIL_SEC <= t <= playhead]

    visible_tags: set[int] = set()
    for cam in _CAMERAS:
        tags = nearest_value(series['cameras'][cam]['visible_tags'], playhead)
        if tags:
            visible_tags.update(tags)

    col_field, col_health = st.columns([3, 2])
    with col_field:
        st.plotly_chart(_field_figure(pose_now, trail, visible_tags), use_container_width=True,
                         config={'displayModeBar': False}, key='_replay_field')
        if pose_sig and pose_now is None:
            st.caption('No pose sample within 1s of this timestamp.')

    with col_health:
        for cam in _CAMERAS:
            cam_series = series['cameras'][cam]
            score = nearest_value(cam_series['score'], playhead)
            reason = nearest_value(cam_series['reason'], playhead) or ''
            st.markdown(_score_line(f'{cam} camera', score, reason))
        cross_score = nearest_value(series['cross_score'], playhead)
        cross_reason = nearest_value(series['cross_reason'], playhead) or ''
        st.markdown(_score_line('Cross-camera agreement', cross_score, cross_reason))

    for cam in _CAMERAS:
        cam_series = series['cameras'][cam]
        if cam_series['score']:
            st.markdown(f'##### {cam} camera — health over time')
            st.plotly_chart(_trend_figure(cam_series, start_t, playhead), use_container_width=True,
                             config={'displayModeBar': False}, key=f'_replay_trend_{cam}')


def render(ctx: dict) -> None:
    signals = ctx.get('signals')
    start_t = ctx.get('start_t', 0.0)

    if not signals:
        st.info('Load a `.wpilog` file in the sidebar to replay it here.')
        return

    series = _load_series(signals)
    has_pose = bool(series['pose'])
    has_health = any(series['cameras'][cam]['score'] for cam in _CAMERAS)

    if not has_health:
        st.warning(
            'No `Vision/*/Health/*` signals in this log — it predates the live-health scoring '
            'added to Vision.java / VisionHealth.java. Record a fresh log to replay health here.'
        )
    if not has_pose:
        st.warning(
            'No `Drivetrain/Pose` signal in this log — it predates pose logging added to '
            'CommandSwerveDrivetrain.java. The field view will stay empty; health playback '
            'below still works if the log has it.'
        )
    if not has_health and not has_pose:
        return

    st.caption(
        'Play/pause/scrub through this log while watching camera health and the robot\'s '
        'field position together — useful for tying a health dip to what was actually '
        'happening at that point in a match or practice run.'
    )

    all_ts = [t for t, _ in series['pose']]
    for cam in _CAMERAS:
        all_ts += [t for t, _ in series['cameras'][cam]['score']]
    if not all_ts:
        st.info('No timestamps found in the replay signals.')
        return
    end_t = max(all_ts)
    duration = max(end_t - start_t, 0.01)

    st.session_state.setdefault('_replay_t', start_t)
    st.session_state.setdefault('_replay_playing', False)
    st.session_state.setdefault('_replay_speed', 1.0)

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        label = '⏸ Pause' if st.session_state['_replay_playing'] else '▶ Play'
        if st.button(label, key='_replay_toggle'):
            if not st.session_state['_replay_playing'] and st.session_state['_replay_t'] >= end_t:
                st.session_state['_replay_t'] = start_t  # replay from the start if it ran off the end
            st.session_state['_replay_playing'] = not st.session_state['_replay_playing']
    with c2:
        if st.button('⏮ Reset', key='_replay_reset'):
            st.session_state['_replay_t'] = start_t
            st.session_state['_replay_playing'] = False
    with c3:
        st.session_state['_replay_speed'] = st.select_slider(
            'Playback speed', options=[0.25, 0.5, 1.0, 2.0, 4.0],
            value=st.session_state['_replay_speed'],
        )

    # Buttons/speed above live outside the fragment so clicking them does a full rerun and
    # re-wraps the fragment below with the right run_every (ticking while playing, fully
    # static -- no background polling at all -- while paused). The scrub slider and all
    # visuals live inside the fragment so dragging/ticking only reruns this fragment, not
    # the whole page (see tabs/live_health.py's flicker fix for why that separation matters).
    run_every = _TICK_SEC if st.session_state['_replay_playing'] else None
    st.fragment(run_every=run_every)(_playback_body)(series, start_t, end_t, duration)
