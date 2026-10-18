"""The bundle job re-picks an automatic pairing from the downloaded log's own boot clock; a hand-picked
one is left alone. And the session listing shares sessions between the two logs of one boot. SFTP is
replaced by in-memory fakes."""
import datetime as dt
import pathlib
import sys
import time

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'wpilog-utils' / 'tests'))

import paths  # noqa: F401
import wpilog_builder as wb

from fastapi.testclient import TestClient

import main
import remote_config
import remote_fetch

client = TestClient(main.app)
UTC = dt.timezone.utc
BOOT = dt.datetime(2026, 10, 17, 12, 30, 0, tzinfo=UTC)
LOG = 'akit_26-10-17_12-35-00_nyroc1_q1.wpilog'
FRC = 'FRC_20261017_123503_NYROC1_Q1.wpilog'


def log_bytes(with_epoch=True):
    extra = [('/RealOutputs/RobotTime/EpochMs', 'int64')] if with_epoch else None
    records = [('/RealOutputs/RobotTime/EpochMs', 0, wb.int64(int(BOOT.timestamp() * 1000)))] if with_epoch else None
    return wb.ds_log([('disabled', 10), ('auto', 3), ('disabled', 10), ('teleop', 3), ('disabled', 10)],
                     extra_entries=extra, extra_records=records)[0]


def pi_session(camera, name, epoch, t0, t1, pi='RightPi'):
    return {'camera': camera, 'name': name, 'path': '/x', 'wall_clock': BOOT + dt.timedelta(seconds=t0),
            'epoch': epoch, 't_first': t0, 't_last': t1}


@pytest.fixture
def remote(tmp_path, monkeypatch):
    cfg = remote_config.RemoteConfig(
        rio=remote_config.HostConfig(host='rio', user='lvuser', path='/logs'),
        pis=[remote_config.HostConfig(host='pi.local', user='pi', path='/rec', name='RightPi')],
        source_path=pathlib.Path('remote_config.json'),
        discovery=remote_config.DiscoveryConfig(enabled=False))
    monkeypatch.setattr(main, 'LOG_ROOT', tmp_path)
    monkeypatch.setattr(remote_config, 'load_remote_config', lambda *a, **k: cfg)
    state = {'log': log_bytes(), 'fetched': []}
    sessions = [
        pi_session('RightCam', 'boot0003-auto', BOOT, 12, 14),
        pi_session('RightCam', 'boot0003-teleop', BOOT, 24, 26),
        pi_session('RightCam', 'boot0002-earlier', BOOT - dt.timedelta(hours=1), 12, 14),
        pi_session('RightCam', 'boot0003-after', BOOT, 4000, 4100),
    ]
    monkeypatch.setattr(remote_fetch, 'list_pi_sessions', lambda c: sessions)
    monkeypatch.setattr(remote_fetch, 'list_rio_logs', lambda c: [
        {'name': LOG, 'path': '/p', 'size': 1, 'mtime': 2.0, 'wall_clock': dt.datetime(2026, 10, 17, 12, 35, 0, tzinfo=UTC)},
        {'name': FRC, 'path': '/p', 'size': 1, 'mtime': 1.0, 'wall_clock': dt.datetime(2026, 10, 17, 12, 35, 3, tzinfo=UTC)}])
    monkeypatch.setattr(remote_fetch, 'rio_log_size', lambda *a: len(state['log']))
    monkeypatch.setattr(remote_fetch, 'pi_session_files', lambda *a: [{'name': 'manifest.jsonl', 'size': 8}])

    def fetch_log(cfg, name, dest, **kwargs):
        path = dest / name
        path.write_bytes(state['log'])
        return path

    def fetch_session(cfg, camera, name, dest, **kwargs):
        state['fetched'].append(name)
        path = dest / camera / name
        path.mkdir(parents=True)
        (path / 'manifest.jsonl').write_text('{}\n')
        return path

    monkeypatch.setattr(remote_fetch, 'fetch_rio_log', fetch_log)
    monkeypatch.setattr(remote_fetch, 'fetch_pi_session', fetch_session)
    state['sessions'] = sessions
    return state


def run_job(body):
    response = client.post('/api/remote/bundle/jobs', json=body)
    assert response.status_code == 202
    job_id = response.json()['job_id']
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        job = client.get('/api/remote/jobs/' + job_id).json()
        if job['status'] in ('complete', 'error'):
            return job
        time.sleep(.01)
    raise AssertionError('job did not finish')


REF = lambda name: {'camera': 'RightCam', 'name': name, 'pi': 'RightPi'}


def test_an_automatic_pick_is_redone_from_the_logs_boot_clock(remote):
    job = run_job({'rio_log': LOG, 'manual': False, 'pi_sessions': [REF('boot0002-earlier')]})   # the file-name guess
    assert job['status'] == 'complete', job
    assert sorted(remote['fetched']) == ['boot0003-auto', 'boot0003-teleop']       # not the other boot, not 4000 s on
    result = job['result']
    assert sorted(s['name'] for s in result['pi_sessions']) == ['boot0003-auto', 'boot0003-teleop']
    assert 'by boot clock' in result['pairing_note']
    assert job['files_total'] == 3                                                  # the log + the sessions actually fetched


def test_a_hand_picked_set_is_fetched_exactly_as_chosen(remote):
    job = run_job({'rio_log': LOG, 'manual': True, 'pi_sessions': [REF('boot0002-earlier')]})
    assert job['status'] == 'complete', job
    assert remote['fetched'] == ['boot0002-earlier']
    assert 'pairing_note' not in job['result']


def test_a_log_that_does_not_record_its_clock_keeps_the_file_name_pick(remote):
    remote['log'] = log_bytes(with_epoch=False)
    job = run_job({'rio_log': LOG, 'manual': False, 'pi_sessions': [REF('boot0003-auto')]})
    assert job['status'] == 'complete', job
    assert remote['fetched'] == ['boot0003-auto']
    assert 'file name' in job['result']['pairing_note']


def test_an_unlistable_pi_does_not_fail_the_bundle(remote, monkeypatch):
    def broken(cfg):
        raise remote_fetch.RemoteFetchError('pi unreachable')
    monkeypatch.setattr(remote_fetch, 'list_pi_sessions', broken)
    job = run_job({'rio_log': LOG, 'manual': False, 'pi_sessions': [REF('boot0003-auto')]})
    assert job['status'] == 'complete', job
    assert remote['fetched'] == ['boot0003-auto']


def test_the_listing_gives_both_logs_of_a_boot_the_same_sessions(remote):
    sessions = client.get('/api/remote/sessions').json()
    pairings = {p['rio_log']: p for p in sessions['pairings']}
    chosen = {name: sorted(s['name'] for s in p['pi_sessions']) for name, p in pairings.items()}
    expected = ['boot0003-after', 'boot0003-auto', 'boot0003-teleop']   # same boot; the log's range is not known yet
    assert chosen[LOG] == chosen[FRC] == expected
    assert pairings[LOG]['method'] == 'inferred'
    assert all(s['epoch'] for s in sessions['pi_sessions'])
