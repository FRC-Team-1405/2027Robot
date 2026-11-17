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
import re
import threading
from typing import Dict, Iterable, List, NamedTuple, Optional, Tuple

from core.composites import COMPOSITES

log = logging.getLogger(__name__)

# AdvantageKit's `new NT4Publisher()` (see Robot.java) publishes to this root table by
# default.
DEFAULT_ROOT_TABLE = 'AdvantageKit'
DEFAULT_CAMERAS = ('LeftCam', 'RightCam')

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
HEALTH_EXTRA_ROOTS = ('OrangePi',)   # tables outside the AdvantageKit root that checks read
# Health Check signals whose values the snapshot reads (see set_health_signals). The mode signals are
# always read: the page shows disabled/auto/teleop.
ALWAYS_READ = ('DriverStation/Enabled', 'DriverStation/Autonomous')
_wanted_src: Tuple[str, ...] = ()
_wanted_rx: Tuple['re.Pattern', ...] = ()
# A key in a log or the live view may carry these in front of the name a check uses.
_KEY_PREFIXES = ('RealOutputs/', 'NT:/')
# Health Check subscriptions (see set_health_signals for why they are shaped like this):
_ntcore_mod = None
_names_sub = None                    # topicsOnly, over the checks' path prefixes: discovers names
_names_prefixes: Tuple[str, ...] = ()
_values_sub = None                   # ONE subscription to exactly the topics the checks read
_values_names: Tuple[str, ...] = ()
_values_built_at = 0.0
_poller = None                       # values arrive here as events; nothing subscribes per topic
_values: Dict[str, object] = {}      # topic name -> latest ntcore Value
VALUES_PERIOD_SEC = 0.25             # the page polls every 0.4 s; faster updates would be wasted
REBUILD_MIN_SEC = 1.0                # new checked topics join at most once a second (startup burst)


def _signal_regex(pattern: str) -> 're.Pattern':
    """health_checks.toml's `signal` syntax: `*` (or a lookup's `{1}`) is one path segment."""
    pattern = re.sub(r'\{[^}/]*\}', '*', pattern.strip().strip('/'))
    return re.compile('^' + '[^/]+'.join(re.escape(part) for part in pattern.split('*')) + '$')


def set_health_signals(patterns: Iterable[str]) -> None:
    """Which topics the Health Check snapshot reads: every check's `signal` and `lookup` patterns.
    Called before each snapshot; cheap when unchanged.

    Why this module is careful about subscriptions: the old snapshot subscribed to the values of
    every AdvantageKit topic and then opened one more subscription per topic (getEntry) on its
    first poll -- hundreds of subscribe requests at once, each of which the roboRIO's NT server
    matches against every topic, on the thread that also forwards PhotonVision's results to robot
    code. On 10-27 every LogBench connect was followed ~0.35 s later by 100-280 ms late vision
    results on both cameras for about a second, and the client dropped and reconnected every
    ~2.4 s, repeating it (docs/experiments/vision/2026-10-27-pv-throughput, learning 8). Now: one
    names-only subscription over the checks' prefixes, and one value subscription to exactly the
    topics the checks read, rebuilt at most once a second as new ones appear."""
    global _wanted_src, _wanted_rx
    src = tuple(sorted({p.strip().strip('/') for p in list(patterns) + list(ALWAYS_READ) if p and p.strip()}))
    with _lock:
        if src != _wanted_src:
            _wanted_src, _wanted_rx = src, tuple(_signal_regex(p) for p in src)
            log.info('Health Check reads values for %d signal patterns', len(src))


def _name_prefixes(root: str) -> Tuple[str, ...]:
    """NT prefixes that cover every wanted pattern: the part before its first `*` (cut back to a
    whole segment), under the AdvantageKit root, its RealOutputs/, and the Pis' own tables."""
    heads = set()
    for p in _wanted_src:
        p = re.sub(r'\{[^}/]*\}', '*', p)
        head = p.split('*')[0]
        if '*' in p:
            head = head[:head.rfind('/') + 1]
        heads.add(head)
    out = set()
    for head in heads:
        out.add(f'/{root}/{head}')
        if not head.startswith('RealOutputs/'):
            out.add(f'/{root}/RealOutputs/{head}')
        if any(head == r or head.startswith(r + '/') for r in HEALTH_EXTRA_ROOTS):
            out.add(f'/{head}')
    # drop prefixes another one already covers
    ordered = sorted(out)
    return tuple(p for p in ordered if not any(q != p and p.startswith(q) for q in ordered))


def _wanted(key: str) -> bool:
    forms = [key] + [key[len(p):] for p in _KEY_PREFIXES if key.startswith(p)]
    return any(rx.match(form) for rx in _wanted_rx for form in forms)


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
            # AdvantageKit names these after the Java field with the first letter capitalised
            # (Vision/LeftCam/Connected in every log). The lower-case spelling this used before never
            # matched, so the camera dot, fps and tag list on the page were always empty.
            _sub(f'{camera}/connected', 'getBooleanTopic', f'{base}/Connected', False)
            _sub(f'{camera}/current_fps', 'getDoubleTopic', f'{base}/CurrentFps', 0.0)
            _sub(f'{camera}/visible_tag_ids', 'getIntegerArrayTopic', f'{base}/VisibleTagIds', [])

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

        global _ntcore_mod
        _ntcore_mod = ntcore
        _inst = inst
        _params = params
        _channels = channels
        _cameras = cameras
        _ensure_names_sub()


def _close(obj, what: str) -> None:
    if obj is None:
        return
    try:
        obj.close()
    except Exception:
        log.exception('Error closing the %s', what)


def _ensure_names_sub() -> None:
    """(Re)subscribe topicsOnly to the prefixes the checks need, if they changed. Caller holds _lock."""
    global _names_sub, _names_prefixes
    if _inst is None or _params is None:
        return
    prefixes = _name_prefixes(_params[1])
    if prefixes == _names_prefixes and _names_sub is not None:
        return
    _close(_names_sub, 'health topic-name subscriber')
    _names_sub, _names_prefixes = None, prefixes
    try:
        _names_sub = _ntcore_mod.MultiSubscriber(_inst, list(prefixes), _ntcore_mod.PubSubOptions(topicsOnly=True))
        log.info('Health Check discovers topic names under %d prefixes', len(prefixes))
    except Exception:
        log.exception('Could not subscribe to %s; Health Check will see only the vision topics', prefixes)


def _close_values() -> None:
    global _values_sub, _values_names, _poller
    _close(_poller, 'health value poller')
    _close(_values_sub, 'health value subscriber')
    _values_sub, _values_names, _poller = None, (), None
    _values.clear()


def _ensure_values_sub(names: Tuple[str, ...], now: float) -> None:
    """One subscription to exactly `names` (a prefix list of whole topic names), values read through
    a poller. Rebuilt when the set grows, but at most every REBUILD_MIN_SEC. Caller holds _lock."""
    global _values_sub, _values_names, _poller, _values_built_at
    if names == _values_names or not names:
        return
    if _values_sub is not None and now - _values_built_at < REBUILD_MIN_SEC:
        return
    nt = _ntcore_mod
    old_values = dict(_values)
    _close_values()
    try:
        _values_sub = nt.MultiSubscriber(_inst, list(names), nt.PubSubOptions(periodic=VALUES_PERIOD_SEC))
        _poller = nt.NetworkTableListenerPoller(_inst)
        _poller.addListener(_values_sub, nt.EventFlags.kValueAll | nt.EventFlags.kImmediate)
        _values_names, _values_built_at = names, now
        _values.update({k: v for k, v in old_values.items() if k in names})
        log.info('Health Check reads values of %d topics', len(names))
    except Exception:
        log.exception('Could not subscribe to the Health Check topics')
        _close_values()


def _teardown() -> None:
    global _inst, _params, _channels, _conn_listener_handle, _names_sub, _names_prefixes
    _close_values()
    _close(_names_sub, 'health topic-name subscriber')
    _names_sub, _names_prefixes = None, ()
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


# ── Health Check snapshot ────────────────────────────────────────────────────────────────

def health_snapshot(_ntcore=None) -> Dict[str, Tuple[object, Optional[float]]]:
    """Every topic under the AdvantageKit root and the Orange Pi tables that a Health Check reads
    (set_health_signals) as {key: (latest value, seconds since it last updated)}. Keys drop the
    AdvantageKit root and the leading slash (so 'SystemStats/CANBus/Utilization',
    'RealOutputs/Vision/...', 'OrangePi/LeftPi/CPU_Pct') -- the same names a log uses. A newly
    announced topic joins the value subscription within REBUILD_MIN_SEC, so it can take a poll or
    two to show up. {} when not connected."""
    global _ntcore_mod
    if _inst is None or _params is None:
        return {}
    ntcore = _ntcore or _ntcore_mod or _import_ntcore()
    root_prefix = f'/{_params[1]}/'
    now = ntcore._now()
    out: Dict[str, Tuple[object, Optional[float]]] = {}
    with _lock:
        _ntcore_mod = ntcore
        _ensure_names_sub()
        wanted: Dict[str, str] = {}                  # topic name -> log-style key
        for prefix in _names_prefixes:
            for topic in _inst.getTopics(prefix):
                name = topic.getName()
                key = name[len(root_prefix):] if name.startswith(root_prefix) else name.lstrip('/')
                if _wanted(key):
                    wanted[name] = key
        _ensure_values_sub(tuple(sorted(wanted)), now / 1e6)
        if _poller is not None:
            for event in _poller.readQueue():
                data = getattr(event, 'data', None)
                if data is not None and hasattr(data, 'topic'):
                    _values[data.topic.getName()] = data.value
        for name, key in wanted.items():
            value = _values.get(name)
            if value is None or not value.isValid():
                continue
            stamp = value.time()
            age = max(0.0, (now - stamp) / 1e6) if stamp else None
            out[key] = (value.value(), age)
    return out
