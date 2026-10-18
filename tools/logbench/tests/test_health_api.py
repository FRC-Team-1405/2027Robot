"""The /api/health/* endpoints: a log report, a live report with latching, and config errors surfaced."""
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'server'))
sys.path.insert(0, str(HERE))

import paths  # noqa: F401

from fastapi.testclient import TestClient

import live_nt
import main
from testkit import build_bundle

client = TestClient(main.app)

TOML = '''
[[check]]
id = "can"
section = "roboRIO"
group = "CAN bus"
label = "CAN utilization"
signal = "SystemStats/CANBus/Utilization"
measure = "max"
scale = 100
unit = "%"
warn_above = 70
fail_above = 90
'''


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    path = tmp_path / 'health.toml'
    path.write_text(TOML)
    monkeypatch.setattr(main, 'HEALTH_CONFIG_PATH', path)
    return path


def checks(report):
    return [c for s in report['sections'] for g in s['groups'] for sub in g['subjects'] for c in sub['checks']]


def test_config_endpoint_lists_the_checks_and_any_errors(config_file):
    r = client.get('/api/health/config').json()
    assert r['checks'] == 1 and r['errors'] == [] and r['sections'] == ['roboRIO']
    config_file.write_text(TOML + '\n[[check]]\nid = "bad"\nsection = "S"\nlabel = "L"\nsignal = "X"\nwarn_abve = 1\n')
    import os
    os.utime(config_file, (config_file.stat().st_atime, config_file.stat().st_mtime + 5))
    r = client.get('/api/health/config').json()
    assert r['checks'] == 1 and len(r['errors']) == 1 and 'warn_abve' in r['errors'][0]


def test_log_report_runs_the_checks_over_the_log(tmp_path, monkeypatch, config_file):
    bundle = build_bundle.build_bundle(tmp_path / 'logs', 'no-recording', cycle_ms=250)
    monkeypatch.setattr(main, 'LOG_ROOT', bundle.out_dir)
    r = client.get('/api/health/log', params={'path': bundle.log_path.name})
    assert r.status_code == 200
    report = r.json()
    assert report['kind'] == 'log' and report['config_errors'] == []
    [row] = checks(report)
    assert row['status'] == 'nodata' and 'not in this log' in row['detail']      # the synthetic log has no CAN stats
    assert report['meta']['log'] == bundle.log_path.name
    assert [m['mode'] for m in report['meta']['modes']] == ['disabled', 'auto', 'disabled', 'teleop', 'disabled']


def test_log_report_for_a_missing_log_is_a_404(tmp_path, monkeypatch, config_file):
    monkeypatch.setattr(main, 'LOG_ROOT', tmp_path)
    assert client.get('/api/health/log', params={'path': 'nope.wpilog'}).status_code == 404


def test_log_report_refuses_paths_outside_the_log_root(tmp_path, monkeypatch, config_file):
    monkeypatch.setattr(main, 'LOG_ROOT', tmp_path)
    assert client.get('/api/health/log', params={'path': '../x.wpilog'}).status_code == 400


def test_live_report_when_not_connected(config_file, monkeypatch):
    monkeypatch.setattr(live_nt, 'is_connected', lambda: False)
    r = client.get('/api/health/live').json()
    assert r['connected'] is False and r['config_errors'] == []


def test_live_report_latches_until_reset(config_file, monkeypatch):
    values = {'v': 0.2}
    monkeypatch.setattr(live_nt, 'is_connected', lambda: True)
    monkeypatch.setattr(live_nt, 'health_snapshot', lambda: {
        'SystemStats/CANBus/Utilization': (values['v'], 0.1),
        'DriverStation/Enabled': (True, 0.1), 'DriverStation/Autonomous': (False, 0.1)})
    client.post('/api/health/live/reset')

    def row():
        report = client.get('/api/health/live').json()
        assert report['connected'] and report['kind'] == 'live'
        assert report['meta']['robot'] == 'teleop' and report['meta']['topics'] == 3
        return checks(report)[0]

    assert (row()['status'], row()['worst']) == ('ok', 'ok')
    values['v'] = 0.95
    r = row()
    assert (r['status'], r['worst'], r['display']) == ('fail', 'fail', '95 %')
    values['v'] = 0.3
    r = row()
    assert (r['status'], r['worst'], r['peak_display']) == ('ok', 'fail', '95 %')
    assert client.post('/api/health/live/reset').json() == {'reset': True}
    assert row()['worst'] == 'ok'


def test_live_report_names_the_robot_mode(config_file, monkeypatch):
    monkeypatch.setattr(live_nt, 'is_connected', lambda: True)
    for enabled, auto, expected in ((False, False, 'disabled'), (True, True, 'auto'), (True, False, 'teleop')):
        monkeypatch.setattr(live_nt, 'health_snapshot', lambda e=enabled, a=auto: {
            'DriverStation/Enabled': (e, 0.1), 'DriverStation/Autonomous': (a, 0.1)})
        assert client.get('/api/health/live').json()['meta']['robot'] == expected
    monkeypatch.setattr(live_nt, 'health_snapshot', lambda: {})
    assert client.get('/api/health/live').json()['meta']['robot'] is None
