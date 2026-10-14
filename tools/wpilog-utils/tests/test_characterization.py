"""Holds wpilog_utils to what the ORIGINAL vision_analyzer parser/metrics/trim produced.

tests/golden/legacy_fingerprints.json was captured from the pre-move code (see make_golden.py) on
real logs in notes/6-20. These tests are the guard for M0's "move verbatim" claim: any behavioural
drift in the moved code fails here. Skipped when the sample logs aren't checked out.
"""
import hashlib
import json
import pathlib

import pytest

from wpilog_utils.decode import parse_wpilog_bytes
from wpilog_utils.modes import compute_mode_spans, filter_signals_by_time
from wpilog_utils.trim import trim_wpilog_bytes

ROOT = pathlib.Path(__file__).resolve().parents[3]
NOTES = ROOT / 'notes' / '6-20'
GOLDEN = json.loads((pathlib.Path(__file__).parent / 'golden' / 'legacy_fingerprints.json').read_text())


def _sha(obj) -> str:
    return hashlib.sha256(repr(obj).encode()).hexdigest()


@pytest.fixture(scope='module', params=sorted(GOLDEN))
def case(request):
    name = request.param
    path = NOTES / name
    if not path.exists():
        pytest.skip(f'sample log not present: {path}')
    raw = path.read_bytes()
    return name, raw, parse_wpilog_bytes(raw), GOLDEN[name]


def test_parsed_signals_identical(case):
    _, raw, sigs, g = case
    assert len(raw) == g['file_bytes']
    assert len(sigs) == g['n_signals']
    got = {k: [len(v), _sha(v)] for k, v in sorted(sigs.items())}
    assert got == g['signals']


def test_mode_spans_identical(case):
    _, _, sigs, g = case
    spans = compute_mode_spans(sigs, g['t0'], g['t1'])
    assert [list(s) for s in spans] == g['mode_spans']
    assert spans, 'sample log should contain DriverStation mode data'


def test_filter_signals_identical(case):
    _, _, sigs, g = case
    lo, hi = g['trim_window']
    assert _sha(filter_signals_by_time(sigs, lo, hi)) == g['filtered_sha']


def test_trim_bytes_identical(case):
    _, raw, _, g = case
    lo, hi = g['trim_window']
    out = trim_wpilog_bytes(raw, lo, hi)
    assert len(out) == g['trim_len']
    assert hashlib.sha256(out).hexdigest() == g['trim_sha256']
