"""Loader for the per-machine remote_config.json (gitignored -- see
remote_config.json.example, which IS committed, for the shape).

A JSON file rather than env vars or an in-app form: bench/competition/home hosts differ
by *venue*, not by session, so the file is swapped (or --remote-config points at a
different one, e.g. remote.bench.json / remote.comp.json) instead of re-entering
settings each time logbench is run.

Every field this module reads is optional beyond host/user/path -- auth is left to
paramiko's own defaults (SSH agent / ~/.ssh keys) unless a machine-specific override is
given, so the common case (keys already set up, as is typical for an FRC team's bench and
competition laptops) needs only the three fields shown in the example file.
"""
import dataclasses
import json
import pathlib
from typing import Optional

_HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = _HERE / 'remote_config.json'


@dataclasses.dataclass
class HostConfig:
    host: str
    user: str
    path: str  # logs_path for the RIO, recordings_path for the Pi
    port: int = 22
    # Left None to use paramiko's default SSH-agent / ~/.ssh key lookup, matching how
    # this team already SSHes into both boxes by hand. Set only if a machine needs a
    # non-default key or (discouraged, but sometimes true on a fresh bench Pi) a
    # password.
    key_filename: Optional[str] = None
    password: Optional[str] = None


@dataclasses.dataclass
class RemoteConfig:
    rio: HostConfig
    pi: HostConfig
    source_path: pathlib.Path


def _host_config(raw: dict, path_key: str) -> HostConfig:
    missing = [k for k in ('host', 'user', path_key) if k not in raw]
    if missing:
        raise ValueError('remote_config.json entry missing required field(s): %s' % ', '.join(missing))
    return HostConfig(
        host=raw['host'],
        user=raw['user'],
        path=raw[path_key],
        port=int(raw.get('port', 22)),
        key_filename=raw.get('key_filename'),
        password=raw.get('password'),
    )


def load_remote_config(path: Optional[pathlib.Path] = None) -> Optional[RemoteConfig]:
    """Returns None if no config file exists at `path` (default: remote_config.json
    beside this module) -- callers treat that as "remote fetch isn't set up here" rather
    than an error, since a laptop that only ever browses locally-copied logs never needs
    this file."""
    cfg_path = pathlib.Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not cfg_path.is_file():
        return None

    raw = json.loads(cfg_path.read_text(encoding='utf-8'))
    if 'rio' not in raw or 'pi' not in raw:
        raise ValueError('remote_config.json must have both "rio" and "pi" entries')

    return RemoteConfig(
        rio=_host_config(raw['rio'], 'logs_path'),
        pi=_host_config(raw['pi'], 'recordings_path'),
        source_path=cfg_path,
    )
