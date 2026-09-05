"""Builds a PlayerSpec for AprilTag camera health -- the one vision-aware module in
this tool.

Everything FRC/vision-specific lives here: which log keys to look for, what the eight
health factors are, the field geometry, the severity thresholds. server/model.py,
server/encode.py and the whole web/ front end stay generic; adding a different kind of
match playback means writing a sibling of this file, not touching those.

Ported from tools/camera-calibration/camera_calibration/tabs/replay.py, which built the
same view server-side with Plotly on every tick. Two behavior fixes came along with the
port:

  - Tag visibility looked for 'visibleTagIds', but the robot logs 'VisibleTagIds'. The
    lit-tag markers on the field were therefore always empty. _find_signal now falls
    back to a case-insensitive match.
  - Cameras are discovered from the log rather than hard-coded to ('Left', 'Right'), so
    a third camera on the 2027 robot shows up without a code change.
"""
import math
import re

from vision_analyzer.constants import (
    APRILTAG_POSITIONS,
    FIELD_LENGTH,
    FIELD_WIDTH,
    _cam_color,
)

from model import Group, Panel, PlayerSpec, Track

NAME = 'camera_health'
LABEL = 'Camera Health'

# (track suffix, legend label, line color, log-key suffix) -- mirrors the _FACTORS
# table in tabs/live_health.py and the old tabs/replay.py so the three views name and
# color the same factor identically.
FACTORS = [
    ('stillness', 'Stillness', '#f2c14e', 'StillnessPercent'),
    ('area', 'Tag area', '#3987e5', 'AreaPercent'),
    ('ambiguity', 'Ambiguity', '#9b59b6', 'AmbiguityPercent'),
    ('fps', 'FPS', '#2ecc71', 'FpsPercent'),
    ('jitter', 'Jitter', '#e67e22', 'JitterPercent'),
    ('acceptance', 'Acceptance', '#1abc9c', 'AcceptanceRateFactorPercent'),
    ('latency', 'Latency', '#e74c3c', 'LatencyPercent'),
    ('multitag', 'Multi-tag', '#95a5a6', 'MultiTagRatioPercent'),
]

# VisionHealth.java's 0-100 scale. Shipped in spec.static so the front end colors scores
# from the spec instead of hardcoding thresholds in TypeScript.
#
# These 80/40 boundaries also exist in camera_calibration/health_display.severity_word(),
# which Tab 5 (Live Health) still uses. They are duplicated rather than shared because the
# dependency only runs one way -- camera-calibration imports match-player, not the reverse
# -- so match-player cannot import health_display without creating a cycle. If the bands
# change, change both; the natural fix is to move health_display here once Tab 5 also
# renders through the player.
SEVERITY = [
    {'min': 80, 'color': '#2ecc71', 'label': 'good'},
    {'min': 40, 'color': '#e67e22', 'label': 'marginal'},
    {'min': 0, 'color': '#e74c3c', 'label': 'bad'},
]

TRAIL_SEC = 3.0

_ODOMETRY_COLOR = '#f5f5f5'
_CROSS_COLOR = '#c9a227'


def _find_signal(signals: dict, base_key: str):
    """Logs write these under a 'RealOutputs/' prefix (AdvantageKit) but older/NT-sourced
    ones don't, and at least one key differs in case from what the analyzer expected --
    so try exact, prefixed, then case-insensitive before giving up."""
    for prefix in ('RealOutputs/', ''):
        k = prefix + base_key
        if k in signals:
            return signals[k]
    target = base_key.lower()
    for k in signals:
        kl = k.lower()
        if kl == target or kl == 'realoutputs/' + target:
            return signals[k]
    return None


def _flatten_pose_signal(raw_signal):
    """Pose2d and Pose2d[] log entries both decode to (ts, list[dict]) -- the parser
    doesn't distinguish scalar vs array structs (vision_analyzer.parser._decode just
    chunks the payload by struct size). For a scalar (Drivetrain/Pose) the list always
    has exactly one entry; for an array (Vision/*/AcceptedPoses, 0+ accepted poses per
    loop) take the most recent one that loop. Either way this produces one flat
    (ts, {'x','y','rot'}) series."""
    return [(t, poses[-1]) for t, poses in raw_signal if poses]


def discover_cameras(signals: dict) -> list:
    """Camera names, from whichever Vision/<name>/Health/ScorePercent keys exist.

    Falls back to AcceptedPoses so a log predating health scoring still yields its
    cameras (and therefore still gets a field view)."""
    found = set()
    for pattern in (
        r'^(?:RealOutputs/)?Vision/([^/]+)/Health/ScorePercent$',
        r'^(?:RealOutputs/)?Vision/([^/]+)/AcceptedPoses$',
    ):
        rx = re.compile(pattern, re.IGNORECASE)
        for key in signals:
            m = rx.match(key)
            if m:
                found.add(m.group(1))
        if found:
            break
    # CrossCameraAgreement lives at the same level but is not a camera.
    found.discard('CrossCameraAgreement')
    # Left/Right first if present, then anything else alphabetically, so the common
    # two-camera robot always lays out the same way.
    preferred = [c for c in ('Left', 'Right') if c in found]
    return preferred + sorted(found - set(preferred))


def _time_bounds(data: dict) -> tuple:
    lo = math.inf
    hi = -math.inf
    for samples in data.values():
        if samples:
            lo = min(lo, samples[0][0])
            hi = max(hi, samples[-1][0])
    if lo is math.inf:
        return 0.0, 0.0
    return lo, hi


def build(signals: dict, title: str = 'Camera Health Replay') -> tuple:
    """Returns (PlayerSpec, data) where data maps track id -> raw [(t, value)].

    The two are kept separate so encode.py owns the wire format and this module owns
    only the domain mapping."""
    cameras = discover_cameras(signals)
    data: dict = {}
    tracks: list = []
    groups: list = []
    panels: list = []
    layout: list = []
    warnings: list = []

    # ── Position sources (all optional) ────────────────────────────────────────────
    field_tracks: list = []

    odometry = _flatten_pose_signal(_find_signal(signals, 'Drivetrain/Pose') or [])
    if odometry:
        groups.append(Group(id='Drivetrain', label='Odometry', color=_ODOMETRY_COLOR))
        tracks.append(Track(id='pose/odometry', label='Odometry', kind='pose2d',
                            group='Drivetrain', color=_ODOMETRY_COLOR))
        data['pose/odometry'] = odometry
        field_tracks.append('pose/odometry')

    for cam in cameras:
        color = _cam_color(cam)
        groups.append(Group(id=cam, label=f'{cam} camera', color=color))

        pose = _flatten_pose_signal(_find_signal(signals, f'Vision/{cam}/AcceptedPoses') or [])
        if pose:
            tid = f'pose/{cam}'
            tracks.append(Track(id=tid, label=f'{cam} cam est.', kind='pose2d',
                                group=cam, color=color))
            data[tid] = pose
            field_tracks.append(tid)

        tags = _find_signal(signals, f'Vision/{cam}/VisibleTagIds')
        if tags:
            tid = f'tags/{cam}'
            tracks.append(Track(id=tid, label=f'{cam} visible tags', kind='intset',
                                group=cam, color=color))
            data[tid] = tags

    # ── Health tracks ──────────────────────────────────────────────────────────────
    readout_tracks: list = []
    for cam in cameras:
        score = _find_signal(signals, f'Vision/{cam}/Health/ScorePercent')
        reason = _find_signal(signals, f'Vision/{cam}/Health/Reason')
        if score:
            tid = f'health/{cam}/score'
            tracks.append(Track(id=tid, label=f'{cam} score', kind='scalar', group=cam,
                                unit='%', color='#f5f5f5', domain=(0.0, 100.0)))
            data[tid] = score
            readout_tracks.append(tid)
        if reason:
            tid = f'health/{cam}/reason'
            tracks.append(Track(id=tid, label=f'{cam} reason', kind='string', group=cam))
            data[tid] = reason

        for suffix, label, color, log_suffix in FACTORS:
            sig = _find_signal(signals, f'Vision/{cam}/Health/{log_suffix}')
            if not sig:
                continue
            tid = f'health/{cam}/{suffix}'
            tracks.append(Track(id=tid, label=label, kind='scalar', group=cam, unit='%',
                                color=color, domain=(0.0, 100.0)))
            data[tid] = sig

    cross_score = _find_signal(signals, 'Vision/CrossCameraAgreement/ScorePercent')
    cross_reason = _find_signal(signals, 'Vision/CrossCameraAgreement/Reason')
    if cross_score:
        groups.append(Group(id='CrossCamera', label='Cross-camera agreement',
                            color=_CROSS_COLOR))
        tracks.append(Track(id='health/cross/score', label='Cross-camera agreement',
                            kind='scalar', group='CrossCamera', unit='%',
                            color=_CROSS_COLOR, domain=(0.0, 100.0)))
        data['health/cross/score'] = cross_score
        readout_tracks.append('health/cross/score')
    if cross_reason:
        tracks.append(Track(id='health/cross/reason', label='Cross-camera reason',
                            kind='string', group='CrossCamera'))
        data['health/cross/reason'] = cross_reason

    # ── Panels + layout ────────────────────────────────────────────────────────────
    panels.append(Panel(
        id='field', type='field', title='Field',
        tracks=field_tracks + [f'tags/{c}' for c in cameras],
        options={
            'trail_sec': TRAIL_SEC,
            'pose_tracks': field_tracks,
            'tag_tracks': [f'tags/{c}' for c in cameras],
        },
    ))
    panels.append(Panel(
        id='readout', type='readout', title='Overall Health',
        tracks=readout_tracks,
        # Pairs each score with the string track explaining why it is unmeasurable,
        # so the front end never has to guess the naming convention.
        options={
            'reason_for': {
                **{f'health/{c}/score': f'health/{c}/reason' for c in cameras},
                'health/cross/score': 'health/cross/reason',
            },
            # Kept with the health spec rather than the generic web player: these meanings
            # are specific to VisionHealth's calibration aid, not universal scalar tracks.
            'legend': [
                ('Overall score', 'Higher is better. A product of every factor below; it is a '
                 'calibration diagnostic, not a match-accuracy score.'),
                ('Stillness', 'Derived from instantaneous chassis velocity. It is intentionally '
                 'not smoothed: motion should immediately gate a calibration check.'),
                ('Tag area', 'Raw total tag image area is retained for diagnosis; the score uses '
                 'its 0.5s median. Higher means nearer/better-oriented tags.'),
                ('Ambiguity', 'Raw single-tag PnP ambiguity is retained; the score uses the 0.5s '
                 'median of its inverted goodness factor. Multi-tag is 100%.'),
                ('FPS', 'Raw camera FPS is retained; the score uses its 1s mean relative to target.'),
                ('Jitter', 'Derived 1-second pose standard deviation, then inverted. Higher means '
                 'less pose scatter.'),
                ('Acceptance', 'Raw per-loop acceptance is retained; the score uses accepted/raw '
                 'result counts over 1s.'),
                ('Latency', 'Raw newest-result latency is retained; the score uses its 1s median, '
                 'then inverts it.'),
                ('Multi-tag', 'Derived fraction of accepted results using 2+ tags in the previous '
                 'second.'),
                ('Availability lane', 'The thin red lane marks a disconnected camera; amber marks '
                 'a connected camera with no tag. Tag samples mode holds the last valid value '
                 'through either interval.'),
                ('5s average', 'A trailing five-second moving average of the currently selected '
                 'All samples or Tag samples view. Every factor uses the same window.'),
            ],
        },
    ))
    layout.append(['field', 'readout'])

    for cam in cameras:
        cam_tracks = [f'health/{cam}/score'] + [
            f'health/{cam}/{suffix}' for suffix, _, _, _ in FACTORS
        ]
        pid = f'trend-{cam}'
        panels.append(Panel(id=pid, type='timeseries',
                            title=f'{cam} Camera',
                            tracks=cam_tracks, options={
                                'domain': [0, 100], 'unit': '%',
                                'reason_track': f'health/{cam}/reason',
                            }))
        layout.append([pid])

    # ── Warnings: same graceful-degradation messages the old tab showed ────────────
    has_health = any(k.startswith('health/') for k in data)
    has_pose = bool(field_tracks)
    if not cameras:
        warnings.append('No Vision/*/ signals in this log — nothing to replay here.')
    if not has_health:
        warnings.append(
            'No `Vision/*/Health/*` signals in this log — it predates the live-health '
            'scoring added to Vision.java / VisionHealth.java. Record a fresh log to '
            'replay health here.'
        )
    if not has_pose:
        warnings.append(
            'No position data at all in this log (no `Drivetrain/Pose`, and no '
            '`Vision/*/AcceptedPoses`) — the field view will stay empty.'
        )
    elif not odometry:
        warnings.append(
            'No `Drivetrain/Pose` in this log (predates that addition) — field view is '
            'showing per-camera accepted-pose estimates only, no fused odometry marker.'
        )

    t0, t1 = _time_bounds(data)
    spec = PlayerSpec(
        title=title,
        t0=t0,
        t1=t1,
        groups=groups,
        tracks=tracks,
        panels=panels,
        layout=layout,
        static={
            'field': {
                'length': FIELD_LENGTH,
                'width': FIELD_WIDTH,
                'tags': {str(k): list(v) for k, v in APRILTAG_POSITIONS.items()},
            },
            'severity': SEVERITY,
            # nearest_value() in vision_analyzer.metrics treats a sample more than a
            # second from the playhead as no sample at all; the player applies the
            # same rule so a gap reads as "no data" instead of a frozen stale value.
            'staleness_sec': 1.0,
        },
        warnings=warnings,
    )
    return spec, data
