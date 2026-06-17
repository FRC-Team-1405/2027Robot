"""
roboRIO SSH download. Requires paramiko.
"""
import pathlib
import socket
from typing import Optional

from .constants import (
    _ROBORIO_HOSTS,
    _ROBORIO_USER,
    _ROBORIO_PASS,
    _ROBOT_LOG_DIR,
)

try:
    import paramiko as _paramiko
    _HAS_PARAMIKO = True
except ImportError:
    _HAS_PARAMIKO = False

# robot.py is inside vision_analyzer/, so go up 4 levels to reach repo root
_REPO_ROOT    = pathlib.Path(__file__).resolve().parent.parent.parent.parent
_DEFAULT_LOGS = _REPO_ROOT / 'logs'


def _fetch_latest_robot_log(suffix: str, logs_dir: pathlib.Path) -> pathlib.Path:
    """
    SSH into the roboRIO, find the newest .wpilog, download it to logs_dir.
    suffix must already be sanitised (letters/digits/spaces only); spaces become
    underscores in the filename.
    Raises ConnectionError, FileNotFoundError, or RuntimeError on failure.
    """
    if not _HAS_PARAMIKO:
        raise RuntimeError('paramiko is not installed — run: pip install paramiko')

    logs_dir.mkdir(parents=True, exist_ok=True)

    ssh = _paramiko.SSHClient()
    ssh.set_missing_host_key_policy(_paramiko.AutoAddPolicy())

    last_exc: Exception = ConnectionError('no hosts tried')
    connected_host: Optional[str] = None
    for host in _ROBORIO_HOSTS:
        try:
            ssh.connect(
                host,
                username=_ROBORIO_USER, password=_ROBORIO_PASS,
                timeout=3.0, auth_timeout=5.0, banner_timeout=5.0,
                look_for_keys=False, allow_agent=False,
            )
            connected_host = host
            break
        except (socket.timeout, socket.gaierror, OSError) as exc:
            last_exc = exc
        except Exception as exc:           # paramiko.SSHException etc.
            last_exc = exc

    if connected_host is None:
        raise ConnectionError(
            f'Could not reach roboRIO — tried {", ".join(_ROBORIO_HOSTS)}.\n'
            f'Make sure the robot is powered on and on the same network.\n'
            f'Last error: {last_exc}'
        )

    try:
        sftp = ssh.open_sftp()
        try:
            entries = sftp.listdir_attr(_ROBOT_LOG_DIR)
        except OSError as exc:
            raise FileNotFoundError(
                f'Log directory {_ROBOT_LOG_DIR!r} not found on roboRIO: {exc}'
            ) from exc

        wpi = [e for e in entries
               if e.filename.endswith('.wpilog') and e.st_mtime is not None]
        if not wpi:
            raise FileNotFoundError(
                f'No .wpilog files found in {_ROBOT_LOG_DIR} on roboRIO.'
            )

        latest     = max(wpi, key=lambda e: e.st_mtime)
        stem       = pathlib.PurePosixPath(latest.filename).stem
        tag        = ('_' + suffix.replace(' ', '_')) if suffix else ''
        local_path = logs_dir / f'{stem}{tag}.wpilog'
        sftp.get(f'{_ROBOT_LOG_DIR}/{latest.filename}', str(local_path))
        sftp.close()
    finally:
        ssh.close()

    return local_path
