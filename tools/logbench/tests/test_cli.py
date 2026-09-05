"""server/cli.py: the CLI is a thin argparse/JSON layer over core/, so these tests stub
Log.load with a synthetic fixture (same pattern as the other test modules) rather than
parsing a real .wpilog, and assert on the --json output an LLM or a script would consume."""
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401

import cli
from core.log import Log


def _log(signals: dict) -> Log:
    return Log(path=pathlib.Path('fake.wpilog'), signals=signals)


FIXTURES = {
    'a.wpilog': _log({
        'Vision/Left/Health/StillnessPercent': [(10.0, 50.0)],
        'DriverStation/Enabled': [(10.0, True), (10.5, True)],
        'DriverStation/Autonomous': [(10.0, True)],
    }),
    'b.wpilog': _log({
        'Vision/Left/Health/StillnessPercent': [(10.0, 90.0)],
        'DriverStation/Enabled': [(10.0, True), (10.5, True)],
        'DriverStation/Autonomous': [(10.0, True)],
    }),
}


@pytest.fixture(autouse=True)
def _stub_log_load(monkeypatch):
    monkeypatch.setattr(Log, 'load', classmethod(lambda cls, path: FIXTURES[path]))


def test_metrics_json_shape(capsys):
    rc = cli.main(['metrics', 'a.wpilog', '--metric', 'stillness_pct', '--camera', 'Left', '--json'])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload['log'] == 'a.wpilog'
    assert payload['cameras'] == ['Left']
    assert payload['metrics'] == [{'metric': 'stillness_pct', 'camera': 'Left', 'value': 50.0}]


def test_metrics_text_output_lists_every_requested_metric(capsys):
    rc = cli.main(['metrics', 'a.wpilog', '--metric', 'stillness_pct', '--camera', 'Left'])
    assert rc == 0
    out = capsys.readouterr().out
    assert 'stillness_pct' in out
    assert '50.00' in out


def test_compare_json_shape(capsys):
    rc = cli.main([
        'compare', 'a.wpilog', 'b.wpilog',
        '--metric', 'stillness_pct', '--camera', 'Left', '--json',
    ])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload['a']['log'] == 'a.wpilog'
    assert payload['b']['log'] == 'b.wpilog'
    delta = payload['deltas'][0]
    assert (delta['a'], delta['b'], delta['verdict']) == (50.0, 90.0, 'improved')


def test_compare_supports_independent_manual_windows_per_log(capsys):
    rc = cli.main([
        'compare', 'a.wpilog', 'b.wpilog',
        '--metric', 'stillness_pct', '--camera', 'Left',
        '--window-a', '0', '1', '--window-b', '0', '1', '--json',
    ])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload['a']['window']['lo'] == pytest.approx(10.0)
    assert payload['b']['window']['lo'] == pytest.approx(10.0)


def test_mode_selection_via_cli(capsys):
    rc = cli.main(['metrics', 'a.wpilog', '--metric', 'stillness_pct', '--mode', 'auto', '--json'])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload['window']['lo'] == pytest.approx(10.0)


def test_missing_mode_exits_nonzero_with_a_message(capsys):
    rc = cli.main(['metrics', 'a.wpilog', '--mode', 'teleop'])
    assert rc == 1
    assert "no 'teleop' span found" in capsys.readouterr().err
