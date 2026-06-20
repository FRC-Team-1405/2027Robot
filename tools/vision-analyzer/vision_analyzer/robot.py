"""
roboRIO SSH download. Requires paramiko.
"""
import logging
import pathlib
import socket
import time
from typing import Optional

from .constants import (
    _ROBORIO_HOSTS,
    _ROBORIO_USER,
    _ROBORIO_PASS,
    _ROBOT_LOG_DIR,
)

log = logging.getLogger(__name__)

# Hard cap on a single SFTP read/write stall (socket-level), in seconds.
# Without this, paramiko's channel reads block indefinitely if the
# connection goes quiet (e.g. flaky robot radio), which previously caused
# the download to hang forever with no error and no log output.
_SFTP_SOCKET_TIMEOUT = 30.0

# Minimum interval between progress log lines during a download.
_PROGRESS_LOG_INTERVAL = 2.0

try:
    import paramiko as _paramiko
    _HAS_PARAMIKO = True
except ImportError:
    _HAS_PARAMIKO = False
    log.warning('paramiko not installed — robot log download unavailable (pip install paramiko)')

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

    log.info('Starting robot log download — suffix=%r  dest=%s', suffix, logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    ssh = _paramiko.SSHClient()
    ssh.set_missing_host_key_policy(_paramiko.AutoAddPolicy())

    last_exc: Exception = ConnectionError('no hosts tried')
    connected_host: Optional[str] = None
    for host in _ROBORIO_HOSTS:
        log.debug('Attempting SSH connection to %s (user=%s)', host, _ROBORIO_USER)
        try:
            ssh.connect(
                host,
                username=_ROBORIO_USER, password=_ROBORIO_PASS,
                timeout=3.0, auth_timeout=5.0, banner_timeout=5.0,
                look_for_keys=False, allow_agent=False,
            )
            connected_host = host
            log.info('SSH connected to roboRIO at %s', host)
            transport = ssh.get_transport()
            if transport is not None:
                transport.set_keepalive(10)
                sock = transport.sock
                if sock is not None:
                    sock.settimeout(_SFTP_SOCKET_TIMEOUT)
            break
        except (socket.timeout, socket.gaierror, OSError) as exc:
            log.debug('Connection to %s failed (network/timeout): %s', host, exc)
            last_exc = exc
        except Exception as exc:           # paramiko.SSHException etc.
            log.debug('Connection to %s failed (SSH error): %s', host, exc)
            last_exc = exc

    if connected_host is None:
        err = (
            f'Could not reach roboRIO — tried {", ".join(_ROBORIO_HOSTS)}.\n'
            f'Make sure the robot is powered on and on the same network.\n'
            f'Last error: {last_exc}'
        )
        log.error('Robot download failed: %s', err)
        raise ConnectionError(err)

    try:
        log.debug('Opening SFTP channel')
        sftp = ssh.open_sftp()
        try:
            entries = sftp.listdir_attr(_ROBOT_LOG_DIR)
        except OSError as exc:
            log.error(
                'Could not list log directory %r on roboRIO: %s',
                _ROBOT_LOG_DIR, exc, exc_info=True,
            )
            raise FileNotFoundError(
                f'Log directory {_ROBOT_LOG_DIR!r} not found on roboRIO: {exc}'
            ) from exc

        wpi = [e for e in entries
               if e.filename.endswith('.wpilog') and e.st_mtime is not None]
        log.debug(
            'Found %d total entries in %s, %d are .wpilog files',
            len(entries), _ROBOT_LOG_DIR, len(wpi),
        )

        if not wpi:
            msg = f'No .wpilog files found in {_ROBOT_LOG_DIR} on roboRIO.'
            log.error(msg)
            raise FileNotFoundError(msg)

        latest     = max(wpi, key=lambda e: e.st_mtime)
        remote_path = f'{_ROBOT_LOG_DIR}/{latest.filename}'
        stem       = pathlib.PurePosixPath(latest.filename).stem
        tag        = ('_' + suffix.replace(' ', '_')) if suffix else ''
        local_path = logs_dir / f'{stem}{tag}.wpilog'

        remote_size_kb = latest.st_size / 1024 if latest.st_size is not None else None
        log.info(
            'Downloading %s (remote mtime=%s, size=%s) -> %s',
            remote_path, latest.st_mtime,
            f'{remote_size_kb:.1f} KB' if remote_size_kb is not None else 'unknown',
            local_path,
        )

        last_log_time = time.monotonic()

        def _progress(transferred: int, total: int) -> None:
            nonlocal last_log_time
            now = time.monotonic()
            if now - last_log_time < _PROGRESS_LOG_INTERVAL and transferred < total:
                return
            last_log_time = now
            pct = (transferred / total * 100) if total else 0.0
            log.debug(
                'Download progress: %.1f KB / %.1f KB (%.0f%%)',
                transferred / 1024, total / 1024, pct,
            )

        try:
            sftp.get(remote_path, str(local_path), callback=_progress)
        except socket.timeout as exc:
            log.error(
                'Download stalled for >%.0fs with no data transferred — '
                'aborting (%s)', _SFTP_SOCKET_TIMEOUT, exc,
            )
            raise ConnectionError(
                f'Download of {latest.filename} stalled (no data for '
                f'{_SFTP_SOCKET_TIMEOUT:.0f}s) — robot connection likely dropped.'
            ) from exc
        finally:
            sftp.close()

        size_kb = local_path.stat().st_size / 1024
        log.info('Download complete: %s (%.1f KB)', local_path.name, size_kb)
    except (FileNotFoundError, ConnectionError):
        raise
    except Exception as exc:
        log.exception('Unexpected error during SFTP operation: %s', exc)
        raise
    finally:
        log.debug('Closing SSH connection to %s', connected_host)
        ssh.close()

    return local_path
