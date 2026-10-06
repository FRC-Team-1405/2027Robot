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
from typing import List, Optional

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
    # Which box this is. Only meaningful for Orange Pis, where a robot can have any
    # number of them and a session has to be fetched from the one that recorded it.
    name: str = ''


@dataclasses.dataclass
class DiscoveryConfig:
    """How Orange Pis are found without listing them. Each Pi publishes its name and
    address under /OrangePi/<name>/ on NetworkTables (coprocessor/orangepi-nt-publisher.py);
    the roboRIO's NT server is asked for them. What NT does not say -- the SSH user and
    where recordings live -- comes from here."""
    enabled: bool = True
    user: str = 'pi'
    recordings_path: str = '/home/pi/vision-recordings'
    port: int = 22
    key_filename: Optional[str] = None
    password: Optional[str] = None
    timeout_seconds: float = 6.0


@dataclasses.dataclass
class RemoteConfig:
    rio: HostConfig
    # Orange Pis listed by hand. Optional when discovery is on: an entry here wins over a
    # discovered Pi of the same name or address, so it can pin a host or a non-default
    # recordings path.
    pis: List[HostConfig]
    source_path: pathlib.Path
    transfer_idle_timeout_seconds: int = 60
    discovery: DiscoveryConfig = dataclasses.field(default_factory=DiscoveryConfig)

    def pi_by_name(self, name: str) -> HostConfig:
        return pick_pi(self.pis, name, self.source_path.name)


def pick_pi(pis: List[HostConfig], name: str, source: str = 'remote_config.json') -> HostConfig:
    """The Pi called `name`. An empty name is accepted only when there is exactly one Pi,
    so a client that predates multi-Pi support keeps working."""
    if not name and len(pis) == 1:
        return pis[0]
    for pi in pis:
        if pi.name == name:
            return pi
    raise KeyError('no Orange Pi named %r (known: %s; from %s)'
                   % (name, ', '.join(p.name or '(unnamed)' for p in pis) or 'none', source))


def _host_config(raw: dict, path_key: str, name: str = '') -> HostConfig:
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
        name=name,
    )


def _pi_configs(raw: dict) -> List[HostConfig]:
    """Orange Pi entries from either shape of config file:

      "pis": [{"name": "LeftPi", "host": ..., "user": ..., "recordings_path": ...}, ...]
      "pi":  {"host": ..., ...}        (the original single-Pi form, still accepted)
    """
    if 'pis' in raw and 'pi' in raw:
        raise ValueError('remote_config.json has both "pi" and "pis" -- use only "pis"')
    if 'pis' in raw:
        entries = raw['pis']
        if not isinstance(entries, list):
            raise ValueError('remote_config.json "pis" must be a list')
        pis = []
        for entry in entries:
            name = str(entry.get('name', '')).strip()
            if not name:
                raise ValueError('every entry in remote_config.json "pis" needs a "name"')
            if any(ch in name for ch in ('|', '/', '\\')):
                raise ValueError('Pi name %r may not contain | / or a backslash' % name)
            pis.append(_host_config(entry, 'recordings_path', name=name))
        names = [p.name for p in pis]
        if len(set(names)) != len(names):
            raise ValueError('remote_config.json "pis" names must be unique')
        return pis
    if 'pi' in raw:
        return [_host_config(raw['pi'], 'recordings_path', name=str(raw['pi'].get('name', '')).strip())]
    return []


def _discovery_config(raw: dict) -> DiscoveryConfig:
    """Optional "pi_discovery" block; discovery is on by default."""
    block = raw.get('pi_discovery', {})
    if not isinstance(block, dict):
        raise ValueError('remote_config.json "pi_discovery" must be an object')
    defaults = DiscoveryConfig()
    timeout = float(block.get('timeout_seconds', defaults.timeout_seconds))
    if timeout <= 0:
        raise ValueError('pi_discovery.timeout_seconds must be greater than zero')
    return DiscoveryConfig(
        enabled=bool(block.get('enabled', True)),
        user=block.get('user', defaults.user),
        recordings_path=block.get('recordings_path', defaults.recordings_path),
        port=int(block.get('port', defaults.port)),
        key_filename=block.get('key_filename'),
        password=block.get('password'),
        timeout_seconds=timeout,
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
    if 'rio' not in raw:
        raise ValueError('remote_config.json must have a "rio" entry')

    idle_timeout = int(raw.get('transfer_idle_timeout_seconds', 60))
    if idle_timeout <= 0:
        raise ValueError('transfer_idle_timeout_seconds must be greater than zero')

    pis = _pi_configs(raw)
    discovery = _discovery_config(raw)
    if not pis and not discovery.enabled:
        raise ValueError('remote_config.json lists no Orange Pis ("pis") and "pi_discovery" is '
                         'disabled -- there would be nothing to fetch vision frames from')

    return RemoteConfig(
        rio=_host_config(raw['rio'], 'logs_path'),
        pis=pis,
        source_path=cfg_path,
        transfer_idle_timeout_seconds=idle_timeout,
        discovery=discovery,
    )
