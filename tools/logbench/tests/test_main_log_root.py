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


def test_listing_reports_folder_and_recorded_vision_cameras(two_roots):
    a, _ = two_roots
    session = a / 'sub' / 'one.vision' / 'LeftCam' / 'boot0001-20260101'
    session.mkdir(parents=True)
    (session / 'frame.jpg').write_bytes(b'x')
    row = client.get('/api/logs').json()['logs'][0]
    assert row['folder'] == 'sub'
    assert row['vision_cameras'] == ['LeftCam']


def test_log_details_reports_the_match_the_driver_station_recorded(two_roots, monkeypatch):
    from core.log import Log
    signals = {
        'DriverStation/EventName': [(0, ''), (5, 'nyroc1')],
        'DriverStation/MatchType': [(0, 0), (5, 2)],
        'DriverStation/MatchNumber': [(0, 0), (5, 17)],
        'DriverStation/FMSAttached': [(0, False), (5, True)],
        'DriverStation/Enabled': [(0, False), (10, True), (40, False)],
        'DriverStation/Autonomous': [(0, False), (10, True), (25, False)],
    }
    monkeypatch.setattr(main, '_load_log', lambda path: Log(pathlib.Path(path), signals))
    body = client.get('/api/log-details', params={'log': 'sub/one.wpilog'}).json()
    assert (body['event'], body['match_type'], body['match_number'], body['fms']) == ('nyroc1', 'Qualification', 17, True)
    assert body['auto_sec'] == pytest.approx(15) and body['teleop_sec'] == pytest.approx(15)


def test_log_details_leaves_unrecorded_match_fields_empty(two_roots, monkeypatch):
    from core.log import Log
    monkeypatch.setattr(main, '_load_log', lambda path: Log(pathlib.Path(path), {'DriverStation/Enabled': [(0, False), (9, False)]}))
    body = client.get('/api/log-details', params={'log': 'sub/one.wpilog'}).json()
    assert body['event'] is None and body['match_type'] is None and body['match_number'] is None and body['fms'] is False
