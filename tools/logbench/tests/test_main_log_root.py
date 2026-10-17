"""server/main.py's runtime log-root switch: POST /api/log-root changes what /api/logs
lists and what relative log paths resolve against. The native-dialog endpoint
(/api/log-root/pick) needs a desktop, so only its already-open guard is checked here."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401

import pytest
from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


@pytest.fixture
def two_roots(tmp_path, monkeypatch):
    a, b = tmp_path / 'a', tmp_path / 'b'
    (a / 'sub').mkdir(parents=True)
    b.mkdir()
    (a / 'sub' / 'one.wpilog').write_bytes(b'')
    (b / 'two.wpilog').write_bytes(b'')
    monkeypatch.setattr(main, 'LOG_ROOT', a)
    return a, b


def test_changing_the_root_changes_the_listing(two_roots):
    a, b = two_roots
    assert [l['path'] for l in client.get('/api/logs').json()['logs']] == ['sub/one.wpilog']

    r = client.post('/api/log-root', json={'path': str(b)})
    assert r.status_code == 200
    assert r.json() == {'root': str(b.resolve()), 'cancelled': False}

    listing = client.get('/api/logs').json()
    assert listing['root'] == str(b.resolve())
    assert [l['path'] for l in listing['logs']] == ['two.wpilog']


def test_a_missing_directory_is_rejected_and_the_root_is_kept(two_roots):
    a, b = two_roots
    r = client.post('/api/log-root', json={'path': str(a / 'nope')})
    assert r.status_code == 400
    assert main.LOG_ROOT == a


def test_only_one_folder_dialog_at_a_time(two_roots):
    main._pick_lock.acquire()
    try:
        assert client.post('/api/log-root/pick').status_code == 409
    finally:
        main._pick_lock.release()
