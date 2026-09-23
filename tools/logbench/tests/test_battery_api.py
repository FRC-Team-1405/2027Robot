import pathlib
import sys
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import paths  # noqa: F401
from fastapi.testclient import TestClient
from core.log import Log
import main


@pytest.fixture
def client(tmp_path, monkeypatch):
    (tmp_path / 'match.wpilog').write_bytes(b'fixture')
    log = Log(tmp_path / 'match.wpilog', {
        'SystemStats/BatteryVoltage': [(0, 12.0)],
        'SystemStats/BrownedOut': [(0, False)],
        'PowerDistribution/Voltage': [(0, 12.0)],
        'PowerDistribution/TotalCurrent': [(0, 25.0)],
        'End': [(10, 0)],
    })
    monkeypatch.setattr(main, 'LOG_ROOT', tmp_path)
    monkeypatch.setattr(main, '_load_log', lambda path: log)
    return TestClient(main.app)


def test_analysis_export_parity(client):
    params = {'log': 'match.wpilog', 'window': '2,8'}
    result = client.get('/api/battery', params=params)
    assert result.status_code == 200
    exported = client.get('/api/battery/export', params={**params, 'format': 'json'})
    assert exported.json() == result.json()
    html = client.get('/api/battery/export', params={**params, 'format': 'html'})
    assert html.status_code == 200
    assert 'Battery Insights' in html.text
    assert 'attachment;' in html.headers['content-disposition']


def test_comparison_export_preserves_both_windows(client):
    result = client.get('/api/battery/export', params={'log': 'match.wpilog', 'log_b': 'match.wpilog',
                                                      'window': '0,10', 'window_b': '0,5', 'format': 'json'})
    assert result.status_code == 200
    body = result.json()
    assert body['schema'] == 'logbench.battery-comparison/v1'
    assert body['b']['window'] == [0, 5]
    assert body['deltas']['average'] == 0
    assert body['deltas']['ah'] < 0


@pytest.mark.parametrize('params,status', [
    ({'log': '../outside.wpilog'}, 400), ({'log': 'missing.wpilog'}, 404),
    ({'log': 'match.wpilog', 'window': 'nan,2'}, 400),
    ({'log': 'match.wpilog', 'window': 'broken'}, 400),
    ({'log': 'match.wpilog', 'window': '8,2'}, 400),
    ({'log': 'match.wpilog', 'low_voltage': '-1'}, 400),
])
def test_invalid_requests(client, params, status):
    assert client.get('/api/battery', params=params).status_code == status
