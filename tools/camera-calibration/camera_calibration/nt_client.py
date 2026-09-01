"""Live NetworkTables 4 client for the health-check tab (Tab 5).

Connects as an NT4 client to whatever the robot's own AdvantageKit NT4Publisher
talks to — same server the Orange Pi metrics publisher connects to (see
coprocessor/orangepi-nt-publisher.py) — and reads back the Vision IO inputs and
drivetrain speed outputs live. This is what makes Tab 5 a *live* view: unlike
every other tab in this app, it does not read a .wpilog file.

Diagnostics: getting from "client connected" to "seeing real numbers" has three
independent failure points — no TCP connection to any server (network/team
number/firewall), a connection but our guessed topic paths don't exist (wrong
root table name, or AdvantageKit publishing under a different structure than
assumed), or paths exist but never receive a value (type mismatch). The
functions in the Diagnostics section below exist to tell those apart instead of
the tab just showing a blank "no tag in view" that could mean any of the three.
"""
import collections
import logging
import threading
from typing import NamedTuple, Optional

log = logging.getLogger(__name__)

# AdvantageKit's `new NT4Publisher()` (see Robot.java) publishes to this root
# table by default. Exposed/overridable in the UI in case a project changes it.
DEFAULT_ROOT_TABLE = 'AdvantageKit'

_CAMERAS = ('Left', 'Right')


class _Channel(NamedTuple):
    path: str
    topic: object       # ntcore.Topic
    subscriber: object  # ntcore typed Subscriber


_lock = threading.Lock()
_inst = None
_params: Optional[tuple[str, str]] = None
_channels: dict[str, _Channel] = {}
_conn_listener_handle = None
_conn_events: collections.deque = collections.deque(maxlen=100)


def is_connected() -> bool:
    return _inst is not None and _inst.isConnected()


def _on_connection_event(event) -> None:
    import ntcore

    try:
        info = event.data
        addr = f'{info.remote_ip}:{info.remote_port}' if info is not None else '?'
        kind = 'CONNECTED to' if event.is_(ntcore.EventFlags.kConnected) else 'DISCONNECTED from'
        msg = f'{kind} {addr} (protocol v{getattr(info, "protocol_version", "?")})'
    except Exception:
        log.exception('Malformed connection event')
        msg = 'connection event (details unavailable — see traceback above)'
    log.info('NT4 %s', msg)
    _conn_events.appendleft(msg)


def connect(server: str, root_table: str = DEFAULT_ROOT_TABLE) -> None:
    """(Re)connect the NT4 client. No-op if already connected with the same settings."""
    import ntcore

    global _inst, _params, _channels, _conn_listener_handle
    with _lock:
        params = (server.strip(), root_table.strip('/'))
        if _inst is not None and params == _params:
            log.info('connect() called with unchanged settings %r — no-op', params)
            return
        if _inst is not None:
            _teardown()

        server_str, root = params
        is_team_number = server_str.isdigit() and len(server_str) <= 5
        log.info(
            'Connecting NT4 client: server=%r root_table=%r mode=%s',
            server_str, root, 'team number' if is_team_number else 'direct address',
        )

        inst = ntcore.NetworkTableInstance.getDefault()
        _conn_events.clear()
        _conn_listener_handle = inst.addConnectionListener(True, _on_connection_event)

        inst.startClient4('CameraCalibrationHealth')
        if is_team_number:
            inst.setServerTeam(int(server_str))
        else:
            inst.setServer(server_str)

        channels: dict[str, _Channel] = {}

        def _sub(key: str, getter_name: str, path: str, default) -> None:
            topic = getattr(inst, getter_name)(path)
            log.info('Subscribing %-22s %s -> %s', getter_name, key, path)
            channels[key] = _Channel(path=path, topic=topic, subscriber=topic.subscribe(default))

        for camera in _CAMERAS:
            base = f'/{root}/Vision/{camera}'
            _sub(f'{camera}/connected', 'getBooleanTopic', f'{base}/connected', False)
            _sub(f'{camera}/current_fps', 'getDoubleTopic', f'{base}/currentFps', 0.0)
            _sub(f'{camera}/visible_tag_ids', 'getIntegerArrayTopic', f'{base}/visibleTagIds', [])
            _sub(f'{camera}/sum_tag_areas', 'getDoubleArrayTopic', f'{base}/rawSumTagAreas', [])
            _sub(f'{camera}/ambiguities', 'getDoubleArrayTopic', f'{base}/rawAmbiguities', [])

        speeds_base = f'/{root}/RealOutputs/Drivetrain/Speeds'
        _sub('vx', 'getDoubleTopic', f'{speeds_base}/vxMetersPerSecond', 0.0)
        _sub('omega', 'getDoubleTopic', f'{speeds_base}/omegaRadiansPerSecond', 0.0)

        log.info('Subscribed to %d topics under root %r', len(channels), root)

        _inst = inst
        _params = params
        _channels = channels
        log.info('NT4 client started for %r (root table %r) — see Diagnostics in the tab '
                  'for live connection/topic status', server_str, root)


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
    log.info('Disconnected NT4 health client')


def read() -> dict:
    """Snapshot the latest value of every subscribed topic. {} if not connected."""
    if _inst is None:
        return {}

    out: dict = {
        'nt_connected': _inst.isConnected(),
        'lin_speed': _channels['vx'].subscriber.get(),
        'ang_speed': _channels['omega'].subscriber.get(),
    }
    for camera in _CAMERAS:
        areas = _channels[f'{camera}/sum_tag_areas'].subscriber.get()
        ambiguities = _channels[f'{camera}/ambiguities'].subscriber.get()
        out[camera] = {
            'connected': _channels[f'{camera}/connected'].subscriber.get(),
            'current_fps': _channels[f'{camera}/current_fps'].subscriber.get(),
            'visible_tag_ids': list(_channels[f'{camera}/visible_tag_ids'].subscriber.get()),
            # Raw arrays hold one entry per pipeline result this loop (see
            # VisionIO.java) — the last entry is the most recent result.
            'sum_tag_area': areas[-1] if areas else 0.0,
            'ambiguity': ambiguities[-1] if ambiguities else -1.0,
        }
    log.debug('read() snapshot: %r', out)
    return out


# ── Diagnostics — surfaced live in the tab's "Diagnostics" expander ──────────

def get_connections() -> list[dict]:
    """Ground truth on whether we've reached any NT4 server at all, and which one."""
    if _inst is None:
        return []
    return [
        {
            'remote_id': c.remote_id,
            'remote_ip': c.remote_ip,
            'remote_port': c.remote_port,
            'protocol_version': c.protocol_version,
        }
        for c in _inst.getConnections()
    ]


def connection_events() -> list[str]:
    """Most-recent-first log of connect/disconnect events seen this session."""
    return list(_conn_events)


def topic_diagnostics() -> list[dict]:
    """For every path we subscribe to: does it exist on the wire, and have we ever
    gotten a value for it? Distinguishes "wrong path" from "path is right but the
    robot just hasn't published a sample yet"."""
    import ntcore

    if _inst is None:
        return []
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


def discover_topics(prefix: str, limit: int = 200) -> list[tuple[str, str]]:
    """Every topic currently announced under `prefix`, name+type — the ground-truth
    tree to compare our guessed paths against when they don't match."""
    if _inst is None:
        return []
    topics = _inst.getTopics(prefix)
    rows = sorted((t.getName(), t.getTypeString()) for t in topics)
    return rows[:limit]
