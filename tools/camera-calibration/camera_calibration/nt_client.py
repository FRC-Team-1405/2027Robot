"""Live NetworkTables 4 client for the health-check tab (Tab 5).

Connects as an NT4 client to whatever the robot's own AdvantageKit NT4Publisher
talks to — same server the Orange Pi metrics publisher connects to (see
coprocessor/orangepi-nt-publisher.py) — and reads back the Vision IO inputs and
drivetrain speed outputs live. This is what makes Tab 5 a *live* view: unlike
every other tab in this app, it does not read a .wpilog file.

`ntcore` is imported lazily (inside connect()) so importing this module never
fails just because robotpy-ntcore isn't installed — the tab checks for it up
front and shows an install hint instead of a traceback.
"""
import logging
import threading
from typing import Optional

log = logging.getLogger(__name__)

# AdvantageKit's `new NT4Publisher()` (see Robot.java) publishes to this root
# table by default. Exposed/overridable in the UI in case a project changes it.
DEFAULT_ROOT_TABLE = 'AdvantageKit'

_CAMERAS = ('Left', 'Right')

_lock = threading.Lock()
_inst = None
_params: Optional[tuple[str, str]] = None
_subs: dict = {}


def is_connected() -> bool:
    return _inst is not None and _inst.isConnected()


def connect(server: str, root_table: str = DEFAULT_ROOT_TABLE) -> None:
    """(Re)connect the NT4 client. No-op if already connected with the same settings."""
    import ntcore

    global _inst, _params, _subs
    with _lock:
        params = (server.strip(), root_table.strip('/'))
        if _inst is not None and params == _params:
            return
        if _inst is not None:
            _teardown()

        server_str, root = params
        inst = ntcore.NetworkTableInstance.getDefault()
        inst.startClient4('CameraCalibrationHealth')
        if server_str.isdigit() and len(server_str) <= 5:
            inst.setServerTeam(int(server_str))
        else:
            inst.setServer(server_str)

        subs: dict = {}
        for camera in _CAMERAS:
            base = f'/{root}/Vision/{camera}'
            subs[f'{camera}/connected'] = inst.getBooleanTopic(f'{base}/connected').subscribe(False)
            subs[f'{camera}/current_fps'] = inst.getDoubleTopic(f'{base}/currentFps').subscribe(0.0)
            subs[f'{camera}/visible_tag_ids'] = inst.getIntegerArrayTopic(f'{base}/visibleTagIds').subscribe([])
            subs[f'{camera}/sum_tag_areas'] = inst.getDoubleArrayTopic(f'{base}/rawSumTagAreas').subscribe([])
            subs[f'{camera}/ambiguities'] = inst.getDoubleArrayTopic(f'{base}/rawAmbiguities').subscribe([])

        speeds_base = f'/{root}/RealOutputs/Drivetrain/Speeds'
        subs['vx'] = inst.getDoubleTopic(f'{speeds_base}/vxMetersPerSecond').subscribe(0.0)
        subs['omega'] = inst.getDoubleTopic(f'{speeds_base}/omegaRadiansPerSecond').subscribe(0.0)

        _inst = inst
        _params = params
        _subs = subs
        log.info('Connected NT4 health client to %r (root table %r)', server_str, root)


def _teardown() -> None:
    global _inst, _params, _subs
    if _inst is not None:
        try:
            _inst.stopClient()
        except Exception:
            log.exception('Error stopping previous NT4 client')
    _inst = None
    _params = None
    _subs = {}


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
        'lin_speed': _subs['vx'].get(),
        'ang_speed': _subs['omega'].get(),
    }
    for camera in _CAMERAS:
        areas = _subs[f'{camera}/sum_tag_areas'].get()
        ambiguities = _subs[f'{camera}/ambiguities'].get()
        out[camera] = {
            'connected': _subs[f'{camera}/connected'].get(),
            'current_fps': _subs[f'{camera}/current_fps'].get(),
            'visible_tag_ids': list(_subs[f'{camera}/visible_tag_ids'].get()),
            # Raw arrays hold one entry per pipeline result this loop (see
            # VisionIO.java) — the last entry is the most recent result.
            'sum_tag_area': areas[-1] if areas else 0.0,
            'ambiguity': ambiguities[-1] if ambiguities else -1.0,
        }
    return out
