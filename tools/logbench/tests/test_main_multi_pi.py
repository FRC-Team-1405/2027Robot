"""Fetch Bundle with more than one Orange Pi: sessions from every board are listed and
tagged with their Pi, and each one is downloaded from the board that holds it. No network:
remote_fetch's SFTP functions are replaced."""
import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401

import pytest
from fastapi.testclient import TestClient

import main
import pi_discovery
import remote_config
import remote_fetch

client = TestClient(main.app)

_WALL = dt.datetime(2026, 1, 15, 14, 30, 10)


def _cfg():
    host = lambda name, h, path: remote_config.HostConfig(host=h, user='pi', path=path, name=name)
    return remote_config.RemoteConfig(
        rio=remote_config.HostConfig(host='rio', user='lvuser', path='/home/lvuser/logs'),
        pis=[host('LeftPi', 'leftpi.local', '/rec'), host('RightPi', 'rightpi.local', '/rec')],
        source_path=pathlib.Path('remote_config.json'),
        discovery=remote_config.DiscoveryConfig(enabled=False),  # these tests are about listed Pis
    )


@pytest.fixture
def fake_remote(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'LOG_ROOT', tmp_path)
    monkeypatch.setattr(remote_config, 'load_remote_config', lambda *a, **k: _cfg())

    sessions = {
        'leftpi.local': [{'camera': 'left', 'name': 'boot0003-20260115-143010', 'path': '/x', 'wall_clock': _WALL}],
        'rightpi.local': [{'camera': 'right', 'name': 'boot0007-20260115-143012', 'path': '/y', 'wall_clock': _WALL}],
    }
    monkeypatch.setattr(remote_fetch, 'list_pi_sessions', lambda cfg: sessions[cfg.host])
    monkeypatch.setattr(remote_fetch, 'list_rio_logs', lambda cfg: [{
        'name': 'FRC_20260115_143000.wpilog', 'path': '/p', 'size': 1, 'mtime': 1.0,
        'wall_clock': dt.datetime(2026, 1, 15, 14, 30, 0)}])

    fetched = []

    def fake_fetch_rio(cfg, name, dest_dir, **kwargs):
        path = pathlib.Path(dest_dir) / name
        path.write_bytes(b'')
        return path

    def fake_fetch_pi(cfg, camera, session_name, dest_dir, **kwargs):
        fetched.append((cfg.host, camera, session_name))
        out = pathlib.Path(dest_dir) / camera / session_name
        out.mkdir(parents=True)
        return out

    monkeypatch.setattr(remote_fetch, 'fetch_rio_log', fake_fetch_rio)
    monkeypatch.setattr(remote_fetch, 'fetch_pi_session', fake_fetch_pi)
    return fetched


def test_sessions_from_both_pis_are_listed_tagged_and_suggested_together(fake_remote):
    body = client.get('/api/remote/sessions').json()

    assert {(s['pi'], s['camera']) for s in body['pi_sessions']} == {('LeftPi', 'left'), ('RightPi', 'right')}
    [pairing] = body['pairings']
    assert {(s['pi'], s['camera']) for s in pairing['pi_sessions']} == {('LeftPi', 'left'), ('RightPi', 'right')}


def test_each_session_is_downloaded_from_the_pi_that_holds_it(fake_remote):
    r = client.post('/api/remote/bundle', json={
        'rio_log': 'FRC_20260115_143000.wpilog',
        'pi_sessions': [
            {'pi': 'LeftPi', 'camera': 'left', 'name': 'boot0003-20260115-143010'},
            {'pi': 'RightPi', 'camera': 'right', 'name': 'boot0007-20260115-143012'},
        ],
    })

    assert r.status_code == 200
    assert fake_remote == [
        ('leftpi.local', 'left', 'boot0003-20260115-143010'),
        ('rightpi.local', 'right', 'boot0007-20260115-143012'),
    ]


def test_a_session_for_an_unconfigured_pi_is_rejected_not_fetched_from_a_guess(fake_remote):
    r = client.post('/api/remote/bundle', json={
        'rio_log': 'FRC_20260115_143000.wpilog',
        'pi_sessions': [{'pi': 'NopePi', 'camera': 'left', 'name': 'boot0003-20260115-143010'}],
    })
    assert r.status_code == 400
    assert 'NopePi' in r.json()['detail']
    assert fake_remote == []


def test_an_unreachable_pi_fails_the_listing_instead_of_hiding_its_camera(fake_remote, monkeypatch):
    def flaky(cfg):
        if cfg.host == 'rightpi.local':
            raise remote_fetch.RemoteFetchError('could not connect to pi@rightpi.local:22 -- timed out')
        return []

    monkeypatch.setattr(remote_fetch, 'list_pi_sessions', flaky)
    r = client.get('/api/remote/sessions')
    assert r.status_code == 502
    assert 'rightpi.local' in r.json()['detail']


# ── Pis found on NetworkTables, none listed in the config ───────────────────────────

@pytest.fixture
def discovered_remote(fake_remote, monkeypatch):
    """Same fake SFTP, but remote_config.json lists no Pis and the boards are discovered."""
    cfg = _cfg()
    cfg.pis, cfg.discovery = [], remote_config.DiscoveryConfig(enabled=True)
    monkeypatch.setattr(remote_config, 'load_remote_config', lambda *a, **k: cfg)
    monkeypatch.setattr(pi_discovery, '_last', None)
    monkeypatch.setattr(pi_discovery, 'discover_via_nt', lambda server, timeout: [
        pi_discovery.DiscoveredPi('LeftPi', ip='leftpi.local'),
        pi_discovery.DiscoveredPi('RightPi', ip='rightpi.local'),
    ])
    return fake_remote


def test_pis_need_not_be_listed_when_they_publish_themselves(discovered_remote):
    body = client.get('/api/remote/sessions').json()
    assert {(s['pi'], s['camera']) for s in body['pi_sessions']} == {('LeftPi', 'left'), ('RightPi', 'right')}
    assert 'LeftPi' in body['pi_notes'][0] and 'RightPi' in body['pi_notes'][0]


def test_a_discovered_pi_is_downloaded_from_its_published_address(discovered_remote):
    client.get('/api/remote/sessions')  # the page lists first, which resolves the Pis
    r = client.post('/api/remote/bundle', json={
        'rio_log': 'FRC_20260115_143000.wpilog',
        'pi_sessions': [{'pi': 'RightPi', 'camera': 'right', 'name': 'boot0007-20260115-143012'}],
    })
    assert r.status_code == 200
    assert discovered_remote == [('rightpi.local', 'right', 'boot0007-20260115-143012')]


def test_when_nt_is_unreachable_and_no_pis_are_listed_the_logs_still_list_with_a_note(fake_remote, monkeypatch):
    cfg = _cfg()
    cfg.pis, cfg.discovery = [], remote_config.DiscoveryConfig(enabled=True)
    monkeypatch.setattr(remote_config, 'load_remote_config', lambda *a, **k: cfg)

    def no_nt(server, timeout):
        raise pi_discovery.DiscoveryError('could not connect to the NetworkTables server')
    monkeypatch.setattr(pi_discovery, 'discover_via_nt', no_nt)

    body = client.get('/api/remote/sessions').json()
    assert [l['name'] for l in body['rio_logs']] == ['FRC_20260115_143000.wpilog']
    assert body['pi_sessions'] == []
    assert 'could not connect' in body['pi_notes'][0]
