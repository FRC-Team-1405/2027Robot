"""server/main.py's /api/live/* endpoints. No real NT4 server is available in CI or this
sandbox (ntcore usually isn't even installed) -- these check the two things that don't
need one: a clean 501 with an actionable message when ntcore is missing, and that
snapshot/disconnect never crash when nothing is connected."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401

from fastapi.testclient import TestClient

import live_nt
import main

client = TestClient(main.app)


def test_snapshot_is_empty_when_nothing_is_connected():
    live_nt.disconnect()
    r = client.get('/api/live/snapshot')
    assert r.status_code == 200
    assert r.json() == {}


def test_disconnect_is_safe_to_call_when_nothing_is_connected():
    live_nt.disconnect()
    r = client.post('/api/live/disconnect')
    assert r.status_code == 200
    assert r.json() == {'connected': False}


def test_connect_without_ntcore_installed_returns_a_clean_501():
    r = client.post('/api/live/connect', params={'server': '10.14.5.2'})
    assert r.status_code == 501
    assert 'ntcore' in r.json()['detail']
