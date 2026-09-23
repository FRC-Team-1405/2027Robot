"""Out-of-order logs (plain WPILib FRC_*.wpilog): the log-info, battery and spec endpoints report how many
records are out of time order, so the pages can say the WPILog Janitor can clean it up; an in-order log
gets no notice."""
import pathlib
import sys

_TOOLS = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_TOOLS / 'logbench' / 'server'))
sys.path.insert(0, str(_TOOLS / 'wpilog-utils' / 'tests'))

import paths  # noqa: F401

import pytest
from fastapi.testclient import TestClient

import main
import wpilog_builder as wb

client = TestClient(main.app)


def write_log(path: pathlib.Path, late: bool) -> None:
    raw = wb.header('') + wb.start(1, 'NT:/FMSInfo/FMSControlData', 'int64', '') + wb.start(2, 'NT:/x', 'double', '')
    for i in range(10):
        t = 1_000_000 + 20_000 * i
        raw += wb.record(1, t, wb.int64(0x31))
        raw += wb.record(2, t - 5_000 if late else t, wb.double(i))
    path.write_bytes(raw)


@pytest.fixture
def root(tmp_path, monkeypatch):
    write_log(tmp_path / 'FRC_late.wpilog', late=True)
    write_log(tmp_path / 'akit_fine.wpilog', late=False)
    monkeypatch.setattr(main, 'LOG_ROOT', tmp_path)
    main._log_cache.clear()
    main._spec_cache.clear()
    return tmp_path


def test_log_info_reports_out_of_order_records(root):
    order = client.get('/api/log-info', params={'log': 'FRC_late.wpilog'}).json()['order']
    assert order == {'n_late': 10, 'late_pct': pytest.approx(50.0), 'max_late_ms': pytest.approx(5.0)}
    assert client.get('/api/log-info', params={'log': 'akit_fine.wpilog'}).json()['order'] is None


def test_spec_carries_the_notice(root):
    assert client.get('/api/spec', params={'log': 'FRC_late.wpilog'}).json()['order']['n_late'] == 10
    assert client.get('/api/spec', params={'log': 'akit_fine.wpilog'}).json()['order'] is None
