"""Local adapter inventory and independent, read-only Pi connection diagnostics."""
import ipaddress
import socket
import logging
from concurrent.futures import ThreadPoolExecutor

import pi_discovery
import remote_config
import remote_fetch


def local_interfaces():
    import psutil
    stats = psutil.net_if_stats()
    rows = []
    for name, addresses in psutil.net_if_addrs().items():
        for addr in addresses:
            if addr.family != socket.AF_INET or not addr.netmask:
                continue
            interface = ipaddress.ip_interface(f'{addr.address}/{addr.netmask}')
            if interface.ip.is_loopback:
                continue
            rows.append({'name': name, 'address': addr.address,
                         'network': str(interface.network),
                         'up': bool(stats.get(name) and stats[name].isup)})
    return rows


def adapter_targets(interfaces):
    targets, notes = [], []
    own = {row['address'] for row in interfaces}
    for row in interfaces:
        net = ipaddress.ip_network(row['network'])
        if not row['up'] or not (net.is_private or net.is_link_local):
            continue
        if net.num_addresses > 1024:
            notes.append(f"{row['name']} has {net}; automatic scanning is limited to /22 or smaller. "
                         'Enter the Pi IP or a smaller subnet below. A 169.254 address often means no DHCP server answered.')
            continue
        targets.extend(str(ip) for ip in net.hosts() if str(ip) not in own)
    return list(dict.fromkeys(targets)), notes


def manual_targets(value):
    """Explicit IPv4 address or bounded subnet, never an unbounded sweep."""
    if not value.strip():
        return []
    try:
        net = ipaddress.ip_network(value.strip(), strict=False)
    except ValueError as exc:
        raise ValueError('Enter an IPv4 address or subnet, for example 10.14.5.11 or 192.168.1.0/24.') from exc
    if net.version != 4 or net.num_addresses > 1024:
        raise ValueError('Use an IPv4 address or subnet with at most 1024 addresses (/22 or smaller).')
    return [str(ip) for ip in net.hosts()]


def check_host(cfg, photon=False):
    """Keep DNS, TCP, authentication, and directory access failures distinct."""
    row = {'host': cfg.host, 'name': cfg.name, 'user': cfg.user, 'port': cfg.port,
           'address': '', 'source_address': '', 'photonvision': photon,
           'ssh': False, 'login': 'not checked', 'recordings': 'not checked',
           'identity': 'PhotonVision candidate' if photon else 'Unverified device',
           'model': '', 'hostname': '', 'detail': ''}
    try:
        row['address'] = socket.gethostbyname(cfg.host)
    except OSError:
        row['detail'] = 'Name resolution failed. Try the numeric IP; duplicate .local hostnames can be unreliable.'
        return row
    row['source_address'] = pi_discovery._local_ip_toward(row['address'])
    if not pi_discovery._port_open(row['address'], cfg.port, 0.4):
        row['detail'] = ('SSH port did not answer. Check power, Ethernet link, IP/subnet, firewall, '
                         'and whether SSH is enabled. A direct cable does not assign matching IP addresses.')
        return row
    row['ssh'] = True
    try:
        client, sftp = remote_fetch._connect(cfg, timeout=3)
    except remote_fetch.RemoteFetchError as exc:
        import paramiko
        if isinstance(exc.__cause__, paramiko.AuthenticationException):
            row['login'] = 'authentication failed'
            row['detail'] = f'SSH is reachable but login as {cfg.user} was rejected. Check the configured user, key, or password.'
        else:
            row['login'] = 'SSH/SFTP failed'
            row['detail'] = 'TCP is reachable but SSH negotiation or SFTP failed. Check the SSH service and server logs.'
        return row
    try:
        sftp.get_channel().settimeout(3)
        row['login'] = 'connected'
        for path, key in [('/etc/hostname', 'hostname'), ('/proc/device-tree/model', 'model')]:
            try:
                with sftp.open(path) as file:
                    row[key] = file.read(256).decode('utf-8', 'replace').strip('\x00\r\n ')
            except OSError:
                pass
        if 'orange pi' in row['model'].lower() or 'orangepi' in row['model'].lower():
            row['identity'] = 'Confirmed Orange Pi'
        elif row['model']:
            row['identity'] = row['model']
        try:
            sftp.listdir(cfg.path)
            row['recordings'] = 'readable'
            row['detail'] = f'Connected; recordings folder {cfg.path} is readable.'
        except OSError:
            row['recordings'] = 'unavailable'
            row['detail'] = f'Login works; {cfg.path} is missing or not readable. Check recordings_path and permissions.'
    finally:
        sftp.close()
        client.close()
    return row


def scan_connections(cfg=None, extra='', cancelled=lambda: False, phase=lambda text: None):
    interfaces = local_interfaces()
    targets, notes = adapter_targets(interfaces)
    explicit = manual_targets(extra)
    targets.extend(explicit)
    defaults = cfg.discovery if cfg else remote_config.DiscoveryConfig()
    known = {p.host: p for p in cfg.pis} if cfg else {}
    if cfg:
        configured, config_notes = pi_discovery.scan_targets(defaults, cfg.rio.host)
        targets.extend(configured)
        notes.extend(config_notes)
    targets.extend(defaults.scan_hosts)
    targets.extend(known)
    targets = list(dict.fromkeys(targets))
    if len(targets) > 4096:
        raise ValueError('Scan has more than 4096 targets. Reduce configured subnets or active adapters.')
    phase(f'Checking SSH and PhotonVision on {len(targets)} addresses')

    def probe(host):
        if cancelled():
            return None
        port = known[host].port if host in known else defaults.port
        photon = pi_discovery._port_open(host, 5800, 0.3)
        ssh = pi_discovery._port_open(host, port, 0.3)
        # Include unreachable explicit/configured hosts, but hide silent subnet addresses.
        if not (photon or ssh or host in known or (len(explicit) == 1 and host in explicit)
                or host in defaults.scan_hosts):
            return None
        return host, photon, ssh

    with ThreadPoolExecutor(max_workers=64) as pool:
        found = [row for row in pool.map(probe, targets) if row]
    phase(f'Checking login and recordings on {len(found)} visible or requested devices')

    def diagnose(hit):
        host, photon, ssh = hit
        if cancelled():
            return None
        config = known.get(host) or remote_config.HostConfig(
            host=host, user=defaults.user, path=defaults.recordings_path, port=defaults.port,
            password=defaults.password, key_filename=defaults.key_filename)
        # SSH-only devices may be Pis with PhotonVision stopped; identity is verified
        # via the read-only device-tree model, never inferred from an open port.
        try:
            return check_host(config, photon)
        except Exception:
            logging.getLogger('logbench.connections').warning('Device check failed for %s', host, exc_info=True)
            return {'host': host, 'name': config.name, 'user': config.user, 'port': config.port,
                    'address': host, 'source_address': '', 'photonvision': photon,
                    'ssh': ssh, 'login': 'check interrupted', 'recordings': 'not checked',
                    'identity': 'Unverified device', 'model': '', 'hostname': '',
                    'detail': 'Connection dropped or the device check failed. Retry and check Logbench server logs.'}

    with ThreadPoolExecutor(max_workers=16) as pool:
        devices = [row for row in pool.map(diagnose, found) if row]
    if cfg is None:
        notes.append('No remote_config.json found: login checks use user pi and local SSH keys. Configure pi_discovery credentials and recordings_path to match your boards.')
    notes.append('Checks run from the computer running Logbench. SSH uses remote_config.json credentials or local SSH keys; no settings on the devices are changed.')
    if not devices:
        notes.append('No SSH or PhotonVision endpoints answered. Check the adapter addresses below. With a direct cable and no DHCP, assign the laptop an unused address in the Pi’s subnet, then check the Pi IP explicitly.')
    return {'interfaces': interfaces, 'devices': devices, 'notes': notes, 'targets_checked': len(targets)}
