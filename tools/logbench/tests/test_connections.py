"""Offline diagnostics tests: direct Ethernet, SSH-only Pi, and failure isolation."""
import pathlib
import socket
import sys
from types import SimpleNamespace

import paramiko
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import connections
import remote_fetch
from remote_config import HostConfig


def test_adapter_targets_direct_ethernet():
    targets, notes = connections.adapter_targets([
        {'name': 'Ethernet', 'address': '192.168.50.2', 'network': '192.168.50.0/24', 'up': True},
        {'name': 'WiFi', 'address': '10.0.0.2', 'network': '10.0.0.0/24', 'up': False},
        {'name': 'Link local', 'address': '169.254.2.2', 'network': '169.254.0.0/16', 'up': True},
    ])
    assert '192.168.50.10' in targets
    assert '192.168.50.2' not in targets
    assert len(targets) == 253
    assert '169.254' in notes[0]


@pytest.mark.parametrize('value', ['10.0.0.0/8', '::1', 'bad hostname', '192.168.1.0/16'])
def test_reject_unbounded_or_invalid_targets(value):
    with pytest.raises(ValueError):
        connections.manual_targets(value)


def test_manual_ip():
    assert connections.manual_targets('192.168.50.10') == ['192.168.50.10']


@pytest.fixture
def network(monkeypatch):
    monkeypatch.setattr(socket, 'gethostbyname', lambda host: '192.168.50.10')
    monkeypatch.setattr(connections.pi_discovery, '_local_ip_toward', lambda ip: '192.168.50.2')
    monkeypatch.setattr(connections.pi_discovery, '_port_open', lambda *args: True)


def test_auth_failure_is_not_network_failure(network, monkeypatch):
    def fail(*args, **kwargs):
        raise remote_fetch.RemoteFetchError('contains sensitive configuration') from paramiko.AuthenticationException()
    monkeypatch.setattr(remote_fetch, '_connect', fail)
    row = connections.check_host(HostConfig('pi.local', 'pi', '/recordings'))
    assert row['ssh'] is True
    assert row['login'] == 'authentication failed'
    assert 'sensitive' not in str(row)


def test_ssh_only_board_identified_and_missing_folder(network, monkeypatch):
    import io
    closed = []
    class SFTP:
        def get_channel(self):
            return SimpleNamespace(settimeout=lambda timeout: None)
        def open(self, path):
            return io.BytesIO(b'Orange Pi 5 Plus\x00' if 'model' in path else b'LeftPi\n')
        def listdir(self, path):
            raise PermissionError()
        def close(self):
            closed.append('sftp')
    monkeypatch.setattr(remote_fetch, '_connect', lambda *a, **k: (SimpleNamespace(close=lambda: closed.append('ssh')), SFTP()))
    row = connections.check_host(HostConfig('pi.local', 'pi', '/recordings'))
    assert row['identity'] == 'Confirmed Orange Pi'
    assert row['login'] == 'connected'
    assert row['recordings'] == 'unavailable'
    assert row['photonvision'] is False
    assert closed == ['sftp', 'ssh']


def test_scan_without_rio_includes_ssh_only_and_unreachable_manual(monkeypatch):
    monkeypatch.setattr(connections, 'local_interfaces', lambda: [])
    monkeypatch.setattr(connections.pi_discovery, '_port_open', lambda host, port, timeout: port == 22)
    monkeypatch.setattr(connections, 'check_host', lambda cfg, photon: {'host': cfg.host, 'photonvision': photon})
    result = connections.scan_connections(extra='192.168.50.10')
    assert result['devices'] == [{'host': '192.168.50.10', 'photonvision': False}]
    monkeypatch.setattr(connections.pi_discovery, '_port_open', lambda *args: False)
    assert len(connections.scan_connections(extra='192.168.50.10')['devices']) == 1


def test_dns_failure(monkeypatch):
    def fail(host):
        raise socket.gaierror()
    monkeypatch.setattr(socket, 'gethostbyname', fail)
    row = connections.check_host(HostConfig('bad.local', 'pi', '/recordings'))
    assert row['ssh'] is False
    assert 'Name resolution failed' in row['detail']


def test_scan_api_validates_before_starting(monkeypatch):
    import main
    from fastapi.testclient import TestClient
    monkeypatch.setattr(main.remote_jobs, 'start', lambda *args: pytest.fail('must validate first'))
    response = TestClient(main.app).post('/api/connections/scan/jobs', json={'target': '10.0.0.0/8'})
    assert response.status_code == 400


def test_scan_api_works_without_remote_config(monkeypatch):
    import main
    from fastapi.testclient import TestClient
    monkeypatch.setattr(main.remote_config, 'load_remote_config', lambda: None)
    monkeypatch.setattr(connections, 'scan_connections', lambda cfg, target, **kwargs: {
        'devices': [], 'interfaces': [], 'notes': [], 'targets_checked': 0})
    captured = {}
    def start(kind, work):
        captured['result'] = work('test')
        return 'test'
    monkeypatch.setattr(main.remote_jobs, 'start', start)
    response = TestClient(main.app).post('/api/connections/scan/jobs', json={'target': ''})
    assert response.status_code == 202
    assert response.json()['job_id'] == 'test'
    assert captured['result']['devices'] == []


def test_failed_device_does_not_hide_other_results(monkeypatch):
    monkeypatch.setattr(connections, 'local_interfaces', lambda: [])
    monkeypatch.setattr(connections.pi_discovery, '_port_open', lambda *args: True)
    def check(cfg, photon):
        if cfg.host.endswith('.0'):
            raise OSError('connection dropped')
        return {'host': cfg.host}
    monkeypatch.setattr(connections, 'check_host', check)
    result = connections.scan_connections(extra='192.168.50.0/31')
    assert len(result['devices']) == 2
    assert result['devices'][0]['login'] == 'check interrupted'
    assert result['devices'][1]['host'] == '192.168.50.1'


def test_cancel_skips_probes(monkeypatch):
    monkeypatch.setattr(connections, 'local_interfaces', lambda: [])
    monkeypatch.setattr(connections.pi_discovery, '_port_open', lambda *args: pytest.fail('cancelled'))
    assert connections.scan_connections(extra='192.168.50.10', cancelled=lambda: True)['devices'] == []
