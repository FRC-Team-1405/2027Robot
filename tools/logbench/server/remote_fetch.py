"""SFTP access to the roboRIO and the Orange Pi, for the Fetch Bundle page.

Uses paramiko (stdlib has no SFTP client). Every function takes a `remote_config.HostConfig`
and raises `RemoteFetchError` -- never a raw paramiko/socket exception -- so
server/main.py can turn a bad host, refused auth, or a dropped connection into a clean
502 instead of a traceback.

Auth follows whatever this team already uses to SSH into these boxes by hand: paramiko's
own default SSH-agent / `~/.ssh` key lookup (`look_for_keys=True, allow_agent=True`),
optionally overridden per host by `key_filename` or `password` in remote_config.json.
Host keys are trusted on first use (`AutoAddPolicy`) rather than checked against a known
hosts file -- this tool runs on a private bench/competition network talking to two boxes
the team owns, not over the open internet, so this matches the trust model of `ssh
photon@...` from a bench laptop for the first time.
"""
import dataclasses
import datetime as dt
import logging
import pathlib
import posixpath
import re
import stat
import time
from typing import Callable, List, Optional

from remote_config import HostConfig

# WPILib renames a wpilog from FRC_TBD_<something>.wpilog to
# FRC_<yyyyMMdd>_<HHmmss>.wpilog once the Driver Station connects -- an existing,
# built-in wall-clock anchor. Anything still named FRC_TBD_* has no reliable wall clock
# and is flagged wall_clock=None (auto-match-ineligible; still listed so it can be
# manually paired or bundled logs-only).
_RIO_LOG_RE = re.compile(r'^FRC_(\d{8})_(\d{6})\.wpilog$')

# orangepi-vision-recorder.py's session folder naming: boot<NNNN>-<YYYYMMDD>-<HHMMSS>.
_PI_SESSION_RE = re.compile(r'^boot(\d+)-(\d{8})-(\d{6})$')


class RemoteFetchError(Exception):
    """Any SSH/SFTP failure talking to the RIO or the Pi -- bad host, refused auth,
    timed out, path doesn't exist, etc. server/main.py maps this to a 502."""


log = logging.getLogger('logbench.remote_fetch')
ProgressCallback = Callable[[str, int, int], None]


def _connect(cfg: HostConfig):
    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        started = time.monotonic()
        log.info('connecting to %s@%s:%d', cfg.user, cfg.host, cfg.port)
        client.connect(
            cfg.host, port=cfg.port, username=cfg.user,
            password=cfg.password, key_filename=cfg.key_filename,
            look_for_keys=True, allow_agent=True, timeout=10,
        )
        sftp = client.open_sftp()
        log.info('connected to %s@%s:%d in %.2fs', cfg.user, cfg.host, cfg.port,
                 time.monotonic() - started)
        return client, sftp
    except Exception as exc:
        client.close()
        log.warning('connection to %s@%s:%d failed: %s', cfg.user, cfg.host, cfg.port, exc)
        raise RemoteFetchError('could not connect to %s@%s:%d -- %s'
                                % (cfg.user, cfg.host, cfg.port, exc)) from exc


def _parse_rio_wall_clock(name: str) -> Optional[dt.datetime]:
    m = _RIO_LOG_RE.match(name)
    if not m:
        return None
    date_s, time_s = m.groups()
    try:
        return dt.datetime.strptime(date_s + time_s, '%Y%m%d%H%M%S')
    except ValueError:
        return None


def _parse_pi_session_wall_clock(name: str) -> Optional[dt.datetime]:
    m = _PI_SESSION_RE.match(name)
    if not m:
        return None
    _, date_s, time_s = m.groups()
    try:
        return dt.datetime.strptime(date_s + time_s, '%Y%m%d%H%M%S')
    except ValueError:
        return None


def list_rio_logs(cfg: HostConfig) -> List[dict]:
    """[{name, path (remote, posix), size, mtime, wall_clock: datetime|None}, ...],
    newest first."""
    client, sftp = _connect(cfg)
    try:
        try:
            entries = sftp.listdir_attr(cfg.path)
        except (OSError, IOError) as exc:
            raise RemoteFetchError('could not list %s on %s -- %s' % (cfg.path, cfg.host, exc)) from exc

        out = []
        for entry in entries:
            if not entry.filename.endswith('.wpilog') or stat.S_ISDIR(entry.st_mode or 0):
                continue
            out.append({
                'name': entry.filename,
                'path': posixpath.join(cfg.path, entry.filename),
                'size': entry.st_size,
                'mtime': entry.st_mtime,
                'wall_clock': _parse_rio_wall_clock(entry.filename),
            })
        out.sort(key=lambda r: r['mtime'], reverse=True)
        log.info('listed %d RoboRIO logs from %s', len(out), cfg.host)
        return out
    finally:
        sftp.close()
        client.close()


def list_pi_sessions(cfg: HostConfig) -> List[dict]:
    """[{camera, name, path (remote, posix), wall_clock: datetime|None}, ...] across both
    the camera-namespaced layout (<recordings_path>/<camera>/boot####-*) and the legacy,
    single-camera layout (<recordings_path>/boot####-*), newest first."""
    client, sftp = _connect(cfg)
    try:
        try:
            top_entries = sftp.listdir_attr(cfg.path)
        except (OSError, IOError) as exc:
            raise RemoteFetchError('could not list %s on %s -- %s' % (cfg.path, cfg.host, exc)) from exc

        def _boot_dirs(remote_dir: str, entries) -> List[dict]:
            return [e for e in entries if stat.S_ISDIR(e.st_mode or 0) and e.filename.startswith('boot')]

        legacy = _boot_dirs(cfg.path, top_entries)
        out = []
        if legacy:
            for entry in legacy:
                out.append({
                    'camera': '',
                    'name': entry.filename,
                    'path': posixpath.join(cfg.path, entry.filename),
                    'wall_clock': _parse_pi_session_wall_clock(entry.filename),
                })
        else:
            for cam_entry in top_entries:
                if not stat.S_ISDIR(cam_entry.st_mode or 0) or cam_entry.filename.startswith('.'):
                    continue
                cam_dir = posixpath.join(cfg.path, cam_entry.filename)
                try:
                    cam_entries = sftp.listdir_attr(cam_dir)
                except (OSError, IOError):
                    continue
                for entry in _boot_dirs(cam_dir, cam_entries):
                    out.append({
                        'camera': cam_entry.filename,
                        'name': entry.filename,
                        'path': posixpath.join(cam_dir, entry.filename),
                        'wall_clock': _parse_pi_session_wall_clock(entry.filename),
                    })
        out.sort(key=lambda s: s['name'], reverse=True)
        log.info('listed %d Pi recording sessions from %s', len(out), cfg.host)
        return out
    finally:
        sftp.close()
        client.close()


def rio_log_size(cfg: HostConfig, name: str) -> int:
    """Return the remote size of a log so the UI can show a real byte total."""
    client, sftp = _connect(cfg)
    try:
        try:
            return int(sftp.stat(posixpath.join(cfg.path, name)).st_size)
        except (OSError, IOError) as exc:
            raise RemoteFetchError('could not stat %s on %s -- %s' % (name, cfg.host, exc)) from exc
    finally:
        sftp.close()
        client.close()


def pi_session_files(cfg: HostConfig, camera: str, session_name: str) -> List[dict]:
    """List flat Pi session files, including their sizes, without downloading them."""
    remote_session = posixpath.join(cfg.path, camera, session_name) if camera else \
        posixpath.join(cfg.path, session_name)
    client, sftp = _connect(cfg)
    try:
        try:
            entries = sftp.listdir_attr(remote_session)
        except (OSError, IOError) as exc:
            raise RemoteFetchError('could not list %s on %s -- %s' %
                                   (remote_session, cfg.host, exc)) from exc
        return [
            {'name': entry.filename, 'size': int(entry.st_size)}
            for entry in entries if not stat.S_ISDIR(entry.st_mode or 0)
        ]
    finally:
        sftp.close()
        client.close()


def _set_idle_timeout(sftp, idle_timeout_seconds: Optional[int]) -> None:
    """Make a silent SFTP socket fail after the configured no-progress interval."""
    if idle_timeout_seconds is None:
        return
    try:
        sftp.get_channel().settimeout(idle_timeout_seconds)
    except (AttributeError, OSError) as exc:
        log.warning('could not set SFTP idle timeout: %s', exc)


def _download_error(remote_path: str, cfg: HostConfig, exc: Exception,
                    idle_timeout_seconds: Optional[int]) -> RemoteFetchError:
    message = str(exc).lower()
    if idle_timeout_seconds is not None and ('timed out' in message or 'timeout' in message):
        return RemoteFetchError(
            'download of %s from %s made no progress for %d seconds' %
            (remote_path, cfg.host, idle_timeout_seconds))
    return RemoteFetchError('could not fetch %s from %s -- %s' % (remote_path, cfg.host, exc))


def fetch_rio_log(cfg: HostConfig, name: str, dest_dir: pathlib.Path,
                  progress: Optional[ProgressCallback] = None,
                  idle_timeout_seconds: Optional[int] = None) -> pathlib.Path:
    """Downloads <logs_path>/<name> into dest_dir (typically LOG_ROOT). Returns the local
    path."""
    dest_dir = pathlib.Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    remote_path = posixpath.join(cfg.path, name)
    local_path = dest_dir / name

    client, sftp = _connect(cfg)
    try:
        try:
            _set_idle_timeout(sftp, idle_timeout_seconds)
            started = time.monotonic()

            def callback(done: int, total: int) -> None:
                if progress:
                    progress(name, done, total)

            if progress:
                sftp.get(remote_path, str(local_path), callback=callback)
            else:
                sftp.get(remote_path, str(local_path))
            log.info('downloaded RIO log %s (%d bytes) in %.2fs', name, local_path.stat().st_size,
                     time.monotonic() - started)
        except (OSError, IOError) as exc:
            raise _download_error(remote_path, cfg, exc, idle_timeout_seconds) from exc
    finally:
        sftp.close()
        client.close()
    return local_path


def fetch_pi_session(cfg: HostConfig, camera: str, session_name: str, dest_dir: pathlib.Path,
                     progress: Optional[ProgressCallback] = None,
                     idle_timeout_seconds: Optional[int] = None) -> pathlib.Path:
    """Recursively downloads <recordings_path>/<camera>/<session_name>/ (or
    <recordings_path>/<session_name>/ when camera is '') into
    dest_dir/<camera>/<session_name>/ (or dest_dir/<session_name>/), matching
    bundles.py's on-disk convention exactly -- dest_dir is expected to already be a
    `<name>.vision` directory. Returns the local session directory."""
    remote_session = posixpath.join(cfg.path, camera, session_name) if camera \
        else posixpath.join(cfg.path, session_name)
    local_session = pathlib.Path(dest_dir) / camera / session_name if camera \
        else pathlib.Path(dest_dir) / session_name
    local_session.mkdir(parents=True, exist_ok=True)

    client, sftp = _connect(cfg)
    try:
        _set_idle_timeout(sftp, idle_timeout_seconds)
        try:
            entries = sftp.listdir_attr(remote_session)
        except (OSError, IOError) as exc:
            raise RemoteFetchError(
                'could not list %s on %s -- %s' % (remote_session, cfg.host, exc)) from exc
        for entry in entries:
            if stat.S_ISDIR(entry.st_mode or 0):
                continue  # sessions are flat: manifest.jsonl + frame_*.jpg, no subdirs
            remote_file = posixpath.join(remote_session, entry.filename)
            try:
                display_name = '%s/%s' % (camera or 'vision', entry.filename)
                started = time.monotonic()

                def callback(done: int, total: int, display_name=display_name) -> None:
                    if progress:
                        progress(display_name, done, total)

                if progress:
                    sftp.get(remote_file, str(local_session / entry.filename), callback=callback)
                else:
                    sftp.get(remote_file, str(local_session / entry.filename))
                log.info('downloaded Pi file %s (%d bytes) in %.2fs', display_name,
                         entry.st_size, time.monotonic() - started)
            except (OSError, IOError) as exc:
                raise _download_error(remote_file, cfg, exc, idle_timeout_seconds) from exc
    finally:
        sftp.close()
        client.close()
    return local_session
