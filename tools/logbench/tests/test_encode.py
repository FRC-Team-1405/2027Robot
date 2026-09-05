"""Wire-format tests. The decoder in web/src/player/decode.ts mirrors these shapes --
if a test here changes, that file changes with it."""
import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import pytest

from encode import _decimate_scalar, _delta_encode_ms, _rle, encode_series, spec_to_dict
from model import Panel, PlayerSpec, Track


def _decode_dt(dt, t0=0.0):
    """The reference implementation of what decode.ts must do."""
    out, acc = [], 0
    for d in dt:
        acc += d
        out.append(t0 + acc / 1000.0)
    return out


def test_delta_encode_round_trips():
    times = [10.0, 10.02, 10.04, 10.10, 15.0]
    dt = _delta_encode_ms(times, 10.0)
    assert dt == [0, 20, 20, 60, 4900]
    assert _decode_dt(dt, 10.0) == pytest.approx(times)


def test_periodic_samples_delta_to_a_repeated_constant():
    """This is the property gzip exploits -- guard it so a refactor can't silently
    reintroduce absolute timestamps."""
    times = [10.0 + i * 0.02 for i in range(500)]
    dt = _delta_encode_ms(times, 10.0)
    assert set(dt[1:]) == {20}


def test_rle_collapses_runs():
    assert _rle(['a', 'a', 'a', 'b', 'b', 'a']) == [['a', 3], ['b', 2], ['a', 1]]


def test_scalar_encoding_rounds_and_ints():
    s = encode_series([(0.0, 45.0), (0.02, 45.123456), (0.04, 45.129)], 'scalar', 0.0)
    assert s['v'] == [45, 45.12, 45.13]
    assert s['n'] == 3


def test_nan_becomes_null_not_a_dropped_sample():
    """NaN means 'couldn't measure' (health_display.is_unmeasurable), not 'zero' and not
    'this instant didn't happen'. The sample must survive with a null value so the player
    draws a gap instead of holding the previous score."""
    s = encode_series([(0.0, 50.0), (0.02, float('nan')), (0.04, 60.0)], 'scalar', 0.0)
    assert s['n'] == 3
    assert s['v'] == [50, None, 60]
    # And it must be valid JSON -- json.dumps would happily emit a bare NaN token.
    assert 'NaN' not in json.dumps(s)


def test_pose_with_nan_is_dropped_entirely():
    s = encode_series(
        [(0.0, {'x': 1.0, 'y': 2.0, 'rot': 0.0}),
         (0.02, {'x': float('nan'), 'y': 2.0, 'rot': 0.0})],
        'pose2d', 0.0,
    )
    assert s['n'] == 1
    assert s['x'] == [1]


def test_string_dict_rle():
    s = encode_series(
        [(0.0, 'stale'), (0.02, 'stale'), (0.04, ''), (0.06, 'stale')], 'string', 0.0)
    assert s['vocab'] == ['stale', '']
    assert s['v'] == [[0, 2], [1, 1], [0, 1]]


def test_intset_dedupes_and_sorts():
    s = encode_series([(0.0, [10, 10, 3]), (0.02, [3, 10])], 'intset', 0.0)
    # Both samples normalize to the same set, so RLE collapses them to one run.
    assert s['v'] == [[[3, 10], 2]]


def test_empty_series_is_none():
    assert encode_series([], 'scalar', 0.0) is None
    assert encode_series([(0.0, None)], 'scalar', 0.0) is None


def test_decimation_preserves_spikes():
    """Stride sampling would drop exactly the dip someone opened the tool to find."""
    samples = [(i * 0.02, 50.0) for i in range(50_000)]
    samples[31_234] = (31_234 * 0.02, 3.0)
    samples[40_000] = (40_000 * 0.02, 99.0)
    out = _decimate_scalar(samples, 8_000)
    values = [v for _, v in out]
    assert min(values) == 3.0
    assert max(values) == 99.0
    times = [t for t, _ in out]
    assert times == sorted(times)


def test_decimation_only_above_threshold():
    small = [(i * 0.02, float(i)) for i in range(7_500)]
    s = encode_series(small, 'scalar', 0.0)
    assert s['n'] == 7_500
    assert 'decimated' not in s


def test_spec_to_dict_drops_empty_tracks_and_their_panels():
    spec = PlayerSpec(
        title='t', t0=0.0, t1=1.0,
        tracks=[Track(id='a', label='A', kind='scalar'),
                Track(id='gone', label='Gone', kind='scalar')],
        panels=[Panel(id='p1', type='timeseries', title='P1', tracks=['a', 'gone']),
                Panel(id='p2', type='timeseries', title='P2', tracks=['gone'])],
        layout=[['p1', 'p2']],
    )
    out = spec_to_dict(spec, {'a': [(0.0, 1.0)], 'gone': []})
    assert [t['id'] for t in out['tracks']] == ['a']
    # p2 had only the missing track, so it disappears -- and drops out of the layout.
    assert [p['id'] for p in out['panels']] == ['p1']
    assert out['panels'][0]['tracks'] == ['a']
    assert out['layout'] == [['p1']]


def test_spec_json_is_parseable_and_finite():
    spec = PlayerSpec(title='t', t0=0.0, t1=1.0,
                      tracks=[Track(id='a', label='A', kind='scalar')])
    payload = spec_to_dict(spec, {'a': [(0.0, math.nan), (0.5, 1.0)]})
    assert json.loads(json.dumps(payload))['data']['a']['v'] == [None, 1]
