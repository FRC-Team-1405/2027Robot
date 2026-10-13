"""Find the Orange Pis from NetworkTables instead of listing them in remote_config.json.

Each Pi's metrics publisher (coprocessor/orangepi-nt-publisher.py) writes its address under
/OrangePi/<board-name>/IP and /Host. Asking the roboRIO's NT server for that table gives
LogBench the names *and* where to SSH, so the Fetch Bundle page needs no per-robot Pi list.
Like camera names, nothing here assumes how many boards there are or what they are called.

What NetworkTables cannot say -- the SSH user and where recordings live -- comes from
`remote_config.DiscoveryConfig`. Anything listed by hand under "pis" wins over a discovered
Pi of the same name or address, so a bench Pi can be pinned to a fixed host or path.

NetworkTables is not the only way: `discover_via_scan` also looks for PhotonVision's web UI
(TCP 5800) across the robot subnet 10.TE.AM.0/24 and names each board by its /etc/hostname,
read over SSH. That finds a board whose publisher is old, stopped, or can't reach NT --
any PhotonVision box on the robot network shows up, whatever it is called. Both run in
parallel; a board found both ways is listed once (matched by address) under its NT name.

Discovery uses its own NT instance, never the default one, so it cannot disturb the Pit
Check page's live connection (live_nt.py). It is best-effort: when the laptop is not on the
robot network, or a Pi has not been re-synced with the version that publishes IP/Host, the
caller gets the hand-listed Pis plus a note saying what was missed.
"""
import dataclasses
import ipaddress
import logging
import re
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Callable, List, Optional, Tuple

import remote_config
from remote_config import DiscoveryConfig, HostConfig, RemoteConfig

log = logging.getLogger('logbench.pi_discovery')

ROOT_TABLE = 'OrangePi'
PHOTONVISION_PORT = 5800


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
        # stopClient() blocks ~30s while ntcore is still trying to reach an absent server,
        # so it runs on a daemon thread instead of holding up the Fetch Bundle page.
        def cleanup() -> None:
            try:
                if multi is not None:
                    multi.close()
                inst.stopClient()
                nt.NetworkTableInstance.destroy(inst)
            except Exception:
                log.debug('NT discovery cleanup failed', exc_info=True)
        cleaner = threading.Thread(target=cleanup, name='nt-discovery-cleanup', daemon=True)
        cleaner.start()
        cleaner.join(0.5)


# ── network scan ────────────────────────────────────────────────────────────────────

def team_from_host(host: str) -> Optional[int]:
    """1405 from roborio-1405-frc(.local) or 10.14.5.2; None if the host says nothing."""
    host = host.strip().lower()
    m = re.match(r'^roborio-(\d{1,5})-frc(\.local|\.lan|\.frc-field\.local)?$', host)
    if m:
        return int(m.group(1))
    m = re.match(r'^10\.(\d{1,3})\.(\d{1,3})\.\d{1,3}$', host)
    if m:
        return int(m.group(1)) * 100 + int(m.group(2))
    return None


def team_subnet(team: int) -> str:
    return '10.%d.%d.0/24' % (team // 100, team % 100)


def _local_ip_toward(ip: str) -> str:
    """The address this machine would send from to reach `ip` (no packets sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((ip, 9))
            return sock.getsockname()[0]
    except OSError:
        return ''


def _port_open(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _resolve_ipv4(host: str) -> str:
    try:
        return socket.getaddrinfo(host, None, socket.AF_INET)[0][4][0]
    except (OSError, IndexError):
        return ''


def _ssh_hostname(ip: str, defaults: DiscoveryConfig) -> str:
    """The board's own /etc/hostname, or '' when SSH fails (it is still listed, by IP,
    so the listing step can report exactly why it can't be reached)."""
    import remote_fetch
    cfg = HostConfig(host=ip, user=defaults.user, path='/', port=defaults.port,
                     key_filename=defaults.key_filename, password=defaults.password)
    try:
        client, sftp = remote_fetch._connect(cfg)
    except remote_fetch.RemoteFetchError as exc:
        log.info('scan: %s answers on %d but SSH failed: %s', ip, PHOTONVISION_PORT, exc)
        return ''
    try:
        with sftp.open('/etc/hostname') as f:
            return f.read().decode('utf-8', 'replace').strip().split('.')[0]
    except (OSError, IOError):
        return ''
    finally:
        sftp.close()
        client.close()


def scan_targets(defaults: DiscoveryConfig, rio_host: str,
                 _local_ip: Callable[[str], str] = _local_ip_toward) -> Tuple[List[str], List[str]]:
    """(addresses/hostnames to probe, notes). The team subnet is scanned only when this
    machine has an address on it, so a laptop at home doesn't spend seconds probing
    addresses that route out to the internet."""
    notes: List[str] = []
    subnets = list(defaults.scan_subnets)
    team = defaults.team or team_from_host(rio_host)
    if team:
        net = ipaddress.ip_network(team_subnet(team))
        local = _local_ip(str(net[2]))
        if local and ipaddress.ip_address(local) in net:
            subnets.insert(0, str(net))
        else:
            log.info('scan: this machine is not on %s (it would send from %s); skipping it',
                     net, local or 'nowhere')
    targets: List[str] = []
    for entry in subnets:
        try:
            network = ipaddress.ip_network(entry, strict=False)
        except ValueError:
            notes.append('pi_discovery.scan_subnets entry %r is not a subnet; skipped.' % entry)
            continue
        if network.num_addresses > 1024:
            notes.append('pi_discovery.scan_subnets entry %s is larger than a /22; skipped.' % entry)
            continue
        own = _local_ip(str(network.network_address + 1))
        targets.extend(str(ip) for ip in network.hosts() if str(ip) != own)
    targets.extend(h for h in defaults.scan_hosts if h)
    return list(dict.fromkeys(targets)), notes


def discover_via_scan(targets: List[str], defaults: DiscoveryConfig, probe_timeout: float = 0.4,
                      _probe=_port_open, _hostname=_ssh_hostname,
                      _resolve=_resolve_ipv4, deadline: Optional[float] = None) -> List[DiscoveredPi]:
    """Every target answering on PhotonVision's port, named by its hostname.

    Two boards reporting the same hostname (the stock image calls every board
    "photonvision") get their address appended so each still has its own name."""
    if not targets:
        return []
    # Hard deadline: Windows can spend ~12s failing to resolve an absent "LeftPi.local",
    # and the scan must never make the page slower than NetworkTables already does.
    # Stragglers are abandoned (their threads finish on their own) and count as misses.
    deadline = time.monotonic() + (defaults.timeout_seconds if deadline is None else deadline)

    def run_all(fn, items, workers):
        pool = ThreadPoolExecutor(max_workers=workers)
        try:
            futures = [pool.submit(fn, item) for item in items]
            wait(futures, timeout=max(0.0, deadline - time.monotonic()))
            return [f.result() if f.done() and not f.exception() else None for f in futures]
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    answered = run_all(lambda t: _probe(t, PHOTONVISION_PORT, probe_timeout), targets,
                       min(64, len(targets)))
    hits = [t for t, ok in zip(targets, answered) if ok]
    if not hits:
        log.info('scan: none of %d targets run PhotonVision', len(targets))
        return []
    ips = list(dict.fromkeys(_resolve(t) or t for t in hits))
    names = [n or '' for n in run_all(lambda ip: _hostname(ip, defaults), ips, len(ips))]

    counts: dict = {}
    for n in names:
        if n:
            counts[n.casefold()] = counts.get(n.casefold(), 0) + 1
    found = []
    for ip, name in zip(ips, names):
        if not name:
            label = ip
        elif counts[name.casefold()] > 1:
            label = '%s@%s' % (name, ip)
        else:
            label = name
        found.append(DiscoveredPi(name=label, ip=ip, host=('%s.local' % name) if name else ''))
    log.info('scan: %d of %d targets run PhotonVision: %s', len(found), len(targets),
             ', '.join('%s (%s)' % (d.name, d.ip) for d in found))
    return found


def merge_pis(configured: List[HostConfig], discovered: List[DiscoveredPi],
              defaults: DiscoveryConfig,
              found_by: str = 'NetworkTables') -> Tuple[List[HostConfig], List[str]]:
    """Hand-listed Pis first, then any discovered Pi not already covered (same name or same
    address, ignoring case). A hand-listed entry keeps all its own settings; if it had no
    name it takes the discovered one so the UI labels agree with NetworkTables."""
    pis = [dataclasses.replace(c) for c in configured]
    notes: List[str] = []
    added: List[str] = []

    for d in discovered:
        addresses = {a.casefold() for a in (d.ip, d.host) if a}
        match = next((p for p in pis if (p.name and p.name.casefold() == d.name.casefold())
                      or p.host.casefold() in addresses), None)
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
        notes.insert(0, 'Found on %s: %s.' % (found_by, ', '.join(added)))
    return pis, notes


_lock = threading.Lock()
_last: Optional[PiResolution] = None


def resolve_pis(cfg: RemoteConfig, refresh: bool = True) -> PiResolution:
    """The Pis to talk to right now: hand-listed, then found on NetworkTables, then found by
    the network scan, with notes for the UI.

    `refresh=True` queries (a few seconds at most; NT and the scan run in parallel).
    `refresh=False` reuses the last answer for this robot, which is what a download wants --
    the page listed the Pis moments earlier -- and only queries again if nothing has been
    resolved yet."""
    global _last
    if not cfg.discovery.enabled:
        return PiResolution(pis=list(cfg.pis), notes=list(cfg.warnings), rio_host=cfg.rio.host)

    with _lock:
        if not refresh and _last is not None and _last.rio_host == cfg.rio.host:
            return _last

    notes: List[str] = list(cfg.warnings)
    team = cfg.discovery.team or team_from_host(cfg.rio.host)
    # A team number lets ntcore try every address the rio answers on (10.TE.AM.2, mDNS,
    # USB 172.22.11.2) instead of one name that might not resolve.
    nt_server = str(team) if team else cfg.rio.host

    targets: List[str] = []
    if cfg.discovery.scan:
        targets, scan_notes = scan_targets(cfg.discovery, cfg.rio.host)
        notes.extend(scan_notes)

    discovered: List[DiscoveredPi] = []
    scanned: List[DiscoveredPi] = []
    nt_error: Optional[DiscoveryError] = None
    with ThreadPoolExecutor(max_workers=2) as pool:
        nt_future = pool.submit(discover_via_nt, nt_server, cfg.discovery.timeout_seconds)
        scan_future = pool.submit(discover_via_scan, targets, cfg.discovery) if targets else None
        try:
            discovered = nt_future.result()
        except DiscoveryError as exc:
            log.warning('Pi discovery over NT failed: %s', exc)
            nt_error = exc
        if scan_future is not None:
            try:
                scanned = scan_future.result()
            except Exception as exc:  # the scan is a bonus; it must never break listing
                log.warning('Pi network scan failed', exc_info=True)
                notes.append('Network scan for Orange Pis failed: %s' % exc)

    pis, merge_notes = merge_pis(cfg.pis, discovered, cfg.discovery)
    pis, scan_merge_notes = merge_pis(pis, scanned, cfg.discovery, found_by='the network scan')
    if nt_error is not None:
        if pis:
            fallback = 'using the Pis %s.' % ('found by the network scan' if scanned else
                                               'listed in %s' % cfg.source_path.name)
        else:
            fallback = ('and none were found by a network scan or listed in %s, so no vision '
                        'recordings can be fetched.' % cfg.source_path.name)
        notes.append('Could not discover Orange Pis from NetworkTables (%s); %s' % (nt_error, fallback))
    notes.extend(merge_notes)
    notes.extend(scan_merge_notes)
    if not pis and nt_error is None:
        scanned_what = ''
        if cfg.discovery.scan:
            scanned_what = (' or by a network scan for PhotonVision' if targets else
                            ' (no network scan: this machine is not on the robot subnet)')
        notes.append('No Orange Pis found under /OrangePi/ on NetworkTables%s. Is the laptop '
                     'on the robot network, and are the Pis powered?' % scanned_what)
    result = PiResolution(pis=pis, notes=notes, rio_host=cfg.rio.host)
    with _lock:
        _last = result
    log.info('resolved %d Orange Pi(s): %s', len(pis), ', '.join(p.name or p.host for p in pis))
    return result
