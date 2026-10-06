"""Find the Orange Pis from NetworkTables instead of listing them in remote_config.json.

Each Pi's metrics publisher (coprocessor/orangepi-nt-publisher.py) writes its address under
/OrangePi/<board-name>/IP and /Host. Asking the roboRIO's NT server for that table gives
LogBench the names *and* where to SSH, so the Fetch Bundle page needs no per-robot Pi list.
Like camera names, nothing here assumes how many boards there are or what they are called.

What NetworkTables cannot say -- the SSH user and where recordings live -- comes from
`remote_config.DiscoveryConfig`. Anything listed by hand under "pis" wins over a discovered
Pi of the same name or address, so a bench Pi can be pinned to a fixed host or path.

Discovery uses its own NT instance, never the default one, so it cannot disturb the Pit
Check page's live connection (live_nt.py). It is best-effort: when the laptop is not on the
robot network, or a Pi has not been re-synced with the version that publishes IP/Host, the
caller gets the hand-listed Pis plus a note saying what was missed.
"""
import dataclasses
import logging
import threading
import time
from typing import List, Optional, Tuple

import remote_config
from remote_config import DiscoveryConfig, HostConfig, RemoteConfig

log = logging.getLogger('logbench.pi_discovery')

ROOT_TABLE = 'OrangePi'


class DiscoveryError(Exception):
    """NetworkTables could not be queried at all (no ntcore, or the server never answered)."""


@dataclasses.dataclass
class DiscoveredPi:
    name: str
    ip: str = ''
    host: str = ''

    @property
    def address(self) -> str:
        # IP first: two PhotonVision boards often share a default hostname, which makes
        # mDNS names unreliable, while the address the board reports is exactly where it is.
        return self.ip or self.host


@dataclasses.dataclass
class PiResolution:
    pis: List[HostConfig]
    notes: List[str]
    rio_host: str = ''


def discover_via_nt(server: str, timeout: float = 6.0, settle: float = 1.5,
                    poll: float = 0.1, _ntcore=None) -> List[DiscoveredPi]:
    """Names and addresses of every board publishing under /OrangePi/<name>/.

    `server` is a team number or a host/IP. Returns as soon as the set of boards has been
    stable for `settle` seconds (boards publish once a second, so a second board can appear
    a moment after the first), or at `timeout`. A board that appears without an IP/Host is
    still returned, with empty address fields, so the caller can say why it was skipped.
    """
    try:
        nt = _ntcore or __import__('ntcore')
    except ImportError as exc:
        raise DiscoveryError('pyntcore is not installed on this machine') from exc

    inst = nt.NetworkTableInstance.create()
    multi = None
    try:
        inst.startClient4('LogbenchPiDiscovery')
        server = server.strip()
        if server.isdigit() and len(server) <= 5:
            inst.setServerTeam(int(server))
        else:
            inst.setServer(server)
        multi = nt.MultiSubscriber(inst, [f'/{ROOT_TABLE}/'])
        table = inst.getTable(ROOT_TABLE)

        field_subs: dict = {}
        known: set = set()
        stable_since = time.monotonic()
        deadline = stable_since + timeout
        while time.monotonic() < deadline:
            now = time.monotonic()
            if inst.isConnected():
                names = set(table.getSubTables())
                for name in names - set(field_subs):
                    field_subs[name] = {
                        field: inst.getStringTopic(f'/{ROOT_TABLE}/{name}/{field}').subscribe('')
                        for field in ('IP', 'Host')
                    }
                if names != known:
                    known, stable_since = names, now
                elif known and now - stable_since >= settle:
                    # Everyone has an address -> done. Someone does not (publisher not
                    # updated yet) -> give their first values a little longer, then stop.
                    have_all = all(field_subs[n]['IP'].get() or field_subs[n]['Host'].get() for n in known)
                    if have_all or now - stable_since >= settle * 2:
                        break
            time.sleep(poll)

        if not inst.isConnected():
            raise DiscoveryError('could not connect to the NetworkTables server at %s within %.0fs'
                                 % (server, timeout))
        return [DiscoveredPi(name=n, ip=field_subs[n]['IP'].get().strip(),
                             host=field_subs[n]['Host'].get().strip())
                for n in sorted(known, key=lambda n: (n.casefold(), n)) if n in field_subs]
    finally:
        # Best-effort cleanup of a throwaway client; nothing here may mask the real result.
        try:
            if multi is not None:
                multi.close()
            inst.stopClient()
            nt.NetworkTableInstance.destroy(inst)
        except Exception:
            log.debug('NT discovery cleanup failed', exc_info=True)


def merge_pis(configured: List[HostConfig], discovered: List[DiscoveredPi],
              defaults: DiscoveryConfig) -> Tuple[List[HostConfig], List[str]]:
    """Hand-listed Pis first, then any discovered Pi not already covered (same name or same
    address, ignoring case). A hand-listed entry keeps all its own settings; if it had no
    name it takes the discovered one so the UI labels agree with NetworkTables."""
    pis = [dataclasses.replace(c) for c in configured]
    notes: List[str] = []
    added: List[str] = []

    for d in discovered:
        match = next((p for p in pis if (p.name and p.name.casefold() == d.name.casefold())
                      or (d.address and p.host.casefold() in (d.ip.casefold(), d.host.casefold()))), None)
        if match is not None:
            if not match.name:
                match.name = d.name
            continue
        if not d.address:
            notes.append('Orange Pi "%s" is on NetworkTables but publishes no IP/Host, so LogBench '
                         'cannot reach it. Re-sync coprocessor/orangepi-nt-publisher.py to that '
                         'board, or list it under "pis" in remote_config.json.' % d.name)
            continue
        pis.append(HostConfig(
            host=d.address, user=defaults.user, path=defaults.recordings_path, port=defaults.port,
            key_filename=defaults.key_filename, password=defaults.password, name=d.name))
        added.append('%s (%s)' % (d.name, d.address))

    if added:
        notes.insert(0, 'Found on NetworkTables: %s.' % ', '.join(added))
    return pis, notes


_lock = threading.Lock()
_last: Optional[PiResolution] = None


def resolve_pis(cfg: RemoteConfig, refresh: bool = True) -> PiResolution:
    """The Pis to talk to right now: discovered plus hand-listed, with notes for the UI.

    `refresh=True` queries NetworkTables (a few seconds at most). `refresh=False` reuses the
    last answer for this robot, which is what a download wants -- the page listed the Pis
    moments earlier -- and only queries again if nothing has been resolved yet."""
    global _last
    if not cfg.discovery.enabled:
        return PiResolution(pis=list(cfg.pis), notes=[], rio_host=cfg.rio.host)

    with _lock:
        if not refresh and _last is not None and _last.rio_host == cfg.rio.host:
            return _last

    notes: List[str] = []
    discovered: List[DiscoveredPi] = []
    try:
        discovered = discover_via_nt(cfg.rio.host, cfg.discovery.timeout_seconds)
    except DiscoveryError as exc:
        log.warning('Pi discovery failed: %s', exc)
        fallback = ('using the Pis listed in %s.' % cfg.source_path.name) if cfg.pis else \
            'and no Pis are listed in %s, so no vision recordings can be fetched.' % cfg.source_path.name
        notes.append('Could not discover Orange Pis from NetworkTables (%s); %s' % (exc, fallback))

    pis, merge_notes = merge_pis(cfg.pis, discovered, cfg.discovery)
    notes.extend(merge_notes)
    if not discovered and not notes:
        notes.append('No Orange Pis are publishing under /OrangePi/ on NetworkTables.')
    result = PiResolution(pis=pis, notes=notes, rio_host=cfg.rio.host)
    with _lock:
        _last = result
    log.info('resolved %d Orange Pi(s): %s', len(pis), ', '.join(p.name or p.host for p in pis))
    return result
