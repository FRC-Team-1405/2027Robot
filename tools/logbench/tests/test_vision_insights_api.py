"""Vision Insights API uses the same interval rates as Compare."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import paths  # noqa: F401
from fastapi.testclient import TestClient
from core.log import Log
import main

client = TestClient(main.app)


@pytest.fixture
def log_file(tmp_path, monkeypatch):
    p = tmp_path / 'test.wpilog'
    p.touch()
    monkeypatch.setattr(main, 'LOG_ROOT', tmp_path)
    monkeypatch.setattr(main, '_load_log', lambda _: Log(p, {
        'Timestamp': [(0, 0), (1, 1000000), (2, 2000000), (3, 3000000)],
        'Vision/Left/RawEstimatedPoses': [(0, [{}, {}])],
        'Vision/Left/AcceptedPoses': [(0, [{}])],
    }))


def test_window_rates_match_compare(log_file):
    response = client.get('/api/vision-insights', params={'log': 'test.wpilog', 'window': '1,3'})
    assert response.status_code == 200
    camera = response.json()['cameras'][0]
    assert camera['accepted_count'] == 2
    compare = client.get('/api/compare', params={
        'log_a': 'test.wpilog', 'log_b': 'test.wpilog', 'window_a': '1,3', 'window_b': '1,3',
        'metric': 'accepted_poses_per_sec',
    })
    assert compare.status_code == 200
    assert compare.json()['deltas'][0]['a'] == camera['accepted_poses_per_sec']


@pytest.mark.parametrize('params', [
    {'window': '2,1'}, {'window': '-1,3'}, {'window': '0,99'},
    {'window': 'nan,3'}, {'window': 'bad'}, {'rolling_sec': 0}, {'mode': 'auto'},
])
def test_bad_selections_are_errors(log_file, params):
    assert client.get('/api/vision-insights', params={'log': 'test.wpilog', **params}).status_code == 400


def test_missing_file_is_404(log_file):
    assert client.get('/api/vision-insights', params={'log': 'missing.wpilog'}).status_code == 404
