"""Live NetworkTables 4 client for the Pit Check page.

Ported from tools/camera-calibration/camera_calibration/nt_client.py rather than
reimplemented: that module already got this exactly right after learning the hard way
(see its docstring) that a live-NT client must be a pure display client, never
recomputing VisionHealth.java's LerpTable curves itself -- doing so let camera-calibration
silently drift out of sync with the robot. This module reads back the same
RealOutputs/Vision/*/Health/* topics the robot already publishes and never re-derives a
factor from a raw sensor reading. It becomes the canonical copy once camera-calibration's
Tab 5 is retired in favor of this tool's Pit Check page (see CLAUDE.md).

The one thing this module computes itself is motion_score, and that's safe for the same
reason core/composites.py's version is: it's arithmetic over factors the robot already
scored (Vision/*/Health/*Percent), not a rederivation from a raw sensor reading.

`ntcore` is imported lazily inside connect() (like the module this was ported from) so
importing this file -- and therefore the rest of the server -- never fails just because
`ntcore` isn't installed. `_ntcore` is an injection seam for tests, which run with no
NT4 server and no `ntcore` package available.
"""
import collections
import logging
import threading
from typing import Dict, List, NamedTuple, Optional, Tuple

from core.composites import COMPOSITES

log = logging.getLogger(__name__)

# AdvantageKit's `new NT4Publisher()` (see Robot.java) publishes to this root table by
# default.
DEFAULT_ROOT_TABLE = 'AdvantageKit'
DEFAULT_CAMERAS = ('Left', 'Right')

_MOTION_SCORE_DEPS = COMPOSITES['motion_score'].deps


class _Channel(NamedTuple):
    path: str
    topic: object
    subscriber: object


_lock = threading.Lock()
_inst = None
_params: Optional[Tuple[str, str]] = None
_channels: Dict[str, _Channel] = {}
_cameras: Tuple[str, ...] = DEFAULT_CAMERAS
_conn_listener_handle = None
_conn_events: collections.deque = collections.deque(maxlen=100)


def _import_ntcore():
    import ntcore
    return ntcore


def is_connected() -> bool:
    return _inst is not None and _inst.isConnected()


def _on_connection_event(event, ntcore) -> None:
    try:
        info = event.data
        addr = f'{info.remote_ip}:{info.remote_port}' if info is not None else '?'
        kind = 'CONNECTED to' if event.is_(ntcore.EventFlags.kConnected) else 'DISCONNECTED from'
        msg = f'{kind} {addr} (protocol v{getattr(info, "protocol_version", "?")})'
    except Exception:
        log.exception('Malformed connection event')
        msg = 'connection event (details unavailable -- see traceback above)'
    log.info('NT4 %s', msg)
    _conn_events.appendleft(msg)


def connect(server: str, root_table: str = DEFAULT_ROOT_TABLE,
            cameras: Tuple[str, ...] = DEFAULT_CAMERAS, _ntcore=None) -> None:
    """(Re)connect the NT4 client. No-op if already connected with the same settings."""
    ntcore = _ntcore or _import_ntcore()

    global _inst, _params, _channels, _cameras, _conn_listener_handle
    with _lock:
        params = (server.strip(), root_table.strip('/'))
        if _inst is not None and params == _params:
            log.info('connect() called with unchanged settings %r -- no-op', params)
            return
        if _inst is not None:
            _teardown()

        server_str, root = params
        is_team_number = server_str.isdigit() and len(server_str) <= 5
        log.info('Connecting NT4 client: server=%r root_table=%r mode=%s',
                  server_str, root, 'team number' if is_team_number else 'direct address')

        inst = ntcore.NetworkTableInstance.getDefault()
        _conn_events.clear()
        _conn_listener_handle = inst.addConnectionListener(
            True, lambda event: _on_connection_event(event, ntcore))

        inst.startClient4('Logbench')
        if is_team_number:
            inst.setServerTeam(int(server_str))
        else:
            inst.setServer(server_str)

        channels: Dict[str, _Channel] = {}

        def _sub(key: str, getter_name: str, path: str, default) -> None:
            topic = getattr(inst, getter_name)(path)
            log.info('Subscribing %-22s %s -> %s', getter_name, key, path)
            channels[key] = _Channel(path=path, topic=topic, subscriber=topic.subscribe(default))

        for camera in cameras:
            base = f'/{root}/Vision/{camera}'
            health_base = f'/{root}/RealOutputs/Vision/{camera}/Health'
            _sub(f'{camera}/connected', 'getBooleanTopic', f'{base}/connected', False)
            _sub(f'{camera}/current_fps', 'getDoubleTopic', f'{base}/currentFps', 0.0)
            _sub(f'{camera}/visible_tag_ids', 'getIntegerArrayTopic', f'{base}/visibleTagIds', [])

            _sub(f'{camera}/health_score', 'getDoubleTopic', f'{health_base}/ScorePercent', float('nan'))
            _sub(f'{camera}/health_reason', 'getStringTopic', f'{health_base}/Reason', '')
            _sub(f'{camera}/health_stillness', 'getDoubleTopic', f'{health_base}/StillnessPercent', 0.0)
            _sub(f'{camera}/health_area', 'getDoubleTopic', f'{health_base}/AreaPercent', 0.0)
            _sub(f'{camera}/health_ambiguity', 'getDoubleTopic', f'{health_base}/AmbiguityPercent', 0.0)
            _sub(f'{camera}/health_fps', 'getDoubleTopic', f'{health_base}/FpsPercent', 0.0)
            _sub(f'{camera}/health_jitter', 'getDoubleTopic', f'{health_base}/JitterPercent', 0.0)
            _sub(f'{camera}/health_acceptance', 'getDoubleTopic',
                 f'{health_base}/AcceptanceRateFactorPercent', 0.0)
            _sub(f'{camera}/health_latency', 'getDoubleTopic', f'{health_base}/LatencyPercent', 0.0)
            _sub(f'{camera}/health_multitag', 'getDoubleTopic', f'{health_base}/MultiTagRatioPercent', 0.0)

        speeds_base = f'/{root}/RealOutputs/Drivetrain/Speeds'
        _sub('vx', 'getDoubleTopic', f'{speeds_base}/vxMetersPerSecond', 0.0)
        _sub('omega', 'getDoubleTopic', f'{speeds_base}/omegaRadiansPerSecond', 0.0)

        cross_base = f'/{root}/RealOutputs/Vision/CrossCameraAgreement'
        _sub('cross/score', 'getDoubleTopic', f'{cross_base}/ScorePercent', float('nan'))
        _sub('cross/reason', 'getStringTopic', f'{cross_base}/Reason', '')

        log.info('Subscribed to %d topics under root %r', len(channels), root)

        _inst = inst
        _params = params
        _channels = channels
        _cameras = cameras


def _teardown() -> None:
    global _inst, _params, _channels, _conn_listener_handle
    if _inst is not None:
        if _conn_listener_handle is not None:
            try:
                _inst.removeListener(_conn_listener_handle)
            except Exception:
                log.exception('Error removing connection listener')
        try:
            _inst.stopClient()
        except Exception:
            log.exception('Error stopping previous NT4 client')
    _inst = None
    _params = None
    _channels = {}
    _conn_listener_handle = None


def disconnect() -> None:
    with _lock:
        _teardown()
    log.info('Disconnected NT4 live client')


def _motion_score(camera_reading: dict) -> Optional[float]:
    """Cheap arithmetic over factors the robot already scored -- see module docstring
    for why this is safe to compute here rather than on the robot."""
    values = {dep: camera_reading[f'health_{dep.replace("_pct", "")}'] for dep in _MOTION_SCORE_DEPS}
    if any(v is None or v != v for v in values.values()):  # v != v is the NaN check
        return None
    return COMPOSITES['motion_score'].combine(values)


def read() -> dict:
    """Snapshot the latest value of every subscribed topic, plus motion_score computed
    from them. {} if not connected."""
    if _inst is None:
        return {}

    def _get(key: str):
        return _channels[key].subscriber.get()

    out: dict = {
        'nt_connected': _inst.isConnected(),
        'lin_speed': _get('vx'),
        'ang_speed': _get('omega'),
        'cross_score': _get('cross/score'),
        'cross_reason': _get('cross/reason'),
        'cameras': {},
    }
    for camera in _cameras:
        reading = {
            'connected': _get(f'{camera}/connected'),
            'current_fps': _get(f'{camera}/current_fps'),
            'visible_tag_ids': list(_get(f'{camera}/visible_tag_ids')),
            'health_score': _get(f'{camera}/health_score'),
            'health_reason': _get(f'{camera}/health_reason'),
            'health_stillness': _get(f'{camera}/health_stillness'),
            'health_area': _get(f'{camera}/health_area'),
            'health_ambiguity': _get(f'{camera}/health_ambiguity'),
            'health_fps': _get(f'{camera}/health_fps'),
            'health_jitter': _get(f'{camera}/health_jitter'),
            'health_acceptance': _get(f'{camera}/health_acceptance'),
            'health_latency': _get(f'{camera}/health_latency'),
            'health_multitag': _get(f'{camera}/health_multitag'),
        }
        reading['motion_score'] = _motion_score(reading)
        out['cameras'][camera] = reading
    return out


# ── Diagnostics ──────────────────────────────────────────────────────────────────────

def connection_events() -> List[str]:
    return list(_conn_events)


def topic_diagnostics() -> List[dict]:
    """For every path we subscribe to: does it exist on the wire, and have we ever
    gotten a value for it? Distinguishes "wrong path" from "path is right but the robot
    just hasn't published a sample yet"."""
    if _inst is None:
        return []
    ntcore = _import_ntcore()
    now = ntcore._now()
    rows = []
    for key, ch in _channels.items():
        last_change = ch.subscriber.getLastChange()
        rows.append({
            'key': key,
            'path': ch.path,
            'exists': ch.topic.exists(),
            'ever_received': last_change > 0,
            'age_sec': round((now - last_change) / 1e6, 1) if last_change > 0 else None,
        })
    return rows
