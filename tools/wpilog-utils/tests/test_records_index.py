"""records.py additions and index.py, on synthetic logs (and the real ones when present)."""
import pathlib
import struct

import pytest

import wpilog_builder as wb
from wpilog_utils.index import build_index, load_index
from wpilog_utils.records import (ControlRecord, encode_record, encode_start_payload, iter_records,
                                  parse_control, wpilog_header_end)

NOTES = pathlib.Path(__file__).resolve().parents[3] / 'notes' / '6-20'


# ── records ─────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('eid,ts_us,payload', [
    pytest.param(1, 0, b'', id='empty'),
    pytest.param(1, 255, b'x', id='1B-fields'),
    pytest.param(256, 65_535, b'abc', id='2B-fields'),
    pytest.param(70_000, 2**32, b'\x00' * 300, id='3B-id-5B-ts'),
    pytest.param(2**24, 2**40, b'\x01' * 70_000, id='4B-id-3B-size'),
])
def test_encode_record_round_trips_through_the_reader(eid, ts_us, payload):
    raw = wb.header() + encode_record(eid, ts_us, payload)
    (got,) = list(iter_records(raw, wpilog_header_end(raw)))
    assert got[0] == eid and round(got[1] * 1e6) == ts_us and got[2] == payload


def test_encode_record_uses_minimal_widths():
    assert len(encode_record(1, 100, b'\x00' * 8)) == 1 + 1 + 1 + 1 + 8


def test_encode_matches_an_independent_encoder():
    for eid, ts, p in [(3, 12345, b'hello'), (300, 2**33, b'\x00' * 400)]:
        assert encode_record(eid, ts, p) == wb.record(eid, ts, p, minimal=True)


def test_parse_control_start_finish_metadata():
    start = encode_start_payload(7, '/A/b', 'double', '{"k":1}')
    assert parse_control(start) == ControlRecord('start', 7, '/A/b', 'double', '{"k":1}')
    assert parse_control(b'\x01' + struct.pack('<I', 7)) == ControlRecord('finish', 7)
    meta = b'\x02' + struct.pack('<I', 7) + struct.pack('<I', 2) + b'{}'
    assert parse_control(meta) == ControlRecord('set_metadata', 7, metadata='{}')


@pytest.mark.parametrize('payload', [b'', b'\x00', b'\x00\x01\x00\x00\x00', b'\x00' + struct.pack('<I', 1) + struct.pack('<I', 99) + b'ab', b'\x09abc'])
def test_parse_control_tolerates_garbage(payload):
    assert parse_control(payload) is None


# ── index ───────────────────────────────────────────────────────────────────────────────────────

SPANS = [('disabled', 1.0), ('auto', 2.0), ('disabled', 1.5), ('teleop', 1.0), ('disabled', 0.5)]


def test_index_basic_facts():
    raw, info = wb.ds_log(SPANS)
    ix = build_index(raw)
    assert list(ix.cycles_us) == info['cycles_us']
    assert ix.cycle_period_us() == 20_000
    assert ix.t_min_us == info['cycles_us'][0] and ix.t_max_us == info['cycles_us'][-1]
    assert ix.extra_header == b'AdvantageKit'
    assert ix.time_ordered
    assert ix.n_control['start'] == 4 and ix.n_unregistered_records == 0
    assert ix.header_end + ix.control_bytes + ix.data_bytes == len(raw)
    assert sum(ix.cycle_bytes) == ix.data_bytes == sum(ix.byte_hist)


def test_index_mode_spans_match_the_construction():
    raw, info = wb.ds_log(SPANS)
    spans = build_index(raw).mode_spans()
    assert [m for _, _, m in spans] == ['disabled', 'auto', 'disabled', 'teleop', 'disabled']
    t0 = info['cycles_us'][0] / 1e6
    for (a, b, m), (mode, ea, eb) in zip(spans, info['bounds']):
        assert m == mode and a == pytest.approx(ea - t0, abs=1e-6) and b == pytest.approx(eb - t0, abs=0.021)


def test_index_detects_time_mirror_entries_only():
    raw, _ = wb.ds_log(SPANS)
    ix = build_index(raw)
    assert [e.name for e in ix.entries.values() if e.time_mirror] == ['/Timestamp']


def test_index_without_cycle_entry_uses_distinct_timestamps():
    raw, info = wb.ds_log(SPANS, with_timestamp_entry=False)
    ix = build_index(raw)
    assert ix.cycle_entry_id is None and list(ix.cycles_us) == info['cycles_us']


def test_index_stray_record_between_cycles_belongs_to_the_earlier_cycle():
    b = wb.LogBuilder()
    b.entry('/Timestamp', 'int64'); b.entry('/Other', 'double')
    for t in (1_000_000, 1_020_000):
        b.data('/Timestamp', t, wb.int64(t))
    b.data('/Other', 1_025_000, wb.double(1.0))         # between cycles 1 and 2
    for t in (1_040_000, 1_060_000):
        b.data('/Timestamp', t, wb.int64(t))
    ix = build_index(b.build())
    assert list(ix.cycles_us) == [1_000_000, 1_020_000, 1_040_000, 1_060_000]
    assert ix.cycle_bytes[1] > ix.cycle_bytes[0]        # cycle 1 absorbed the stray record


def test_index_flags_out_of_order_records():
    b = wb.LogBuilder(); b.entry('/A', 'double')
    b.data('/A', 2_000_000, wb.double(1)); b.data('/A', 1_000_000, wb.double(2))
    assert not build_index(b.build()).time_ordered


def test_index_counts_unregistered_and_unknown_control_records():
    b = wb.LogBuilder(); b.entry('/A', 'double')
    b.data('/A', 1_000_000, wb.double(1))
    b.raw(wb.record(99, 1_000_000, wb.double(1)))            # entry 99 never started
    b.raw(wb.finish(1, 1_100_000))
    ix = build_index(b.build())
    assert ix.n_unregistered_records == 1 and ix.n_control['finish'] == 1


def test_index_tolerates_a_truncated_final_record():
    raw, _ = wb.ds_log(SPANS)
    ix = build_index(raw[:-5])
    assert ix.n_records > 0 and ix.total_bytes == len(raw) - 5


def test_index_handles_wide_headers_and_huge_timestamps():
    raw, info = wb.ds_log(SPANS, t0_us=5_000_000_000, minimal=False)
    ix = build_index(raw)
    assert ix.t_min_us == 5_000_000_000 and list(ix.cycles_us) == info['cycles_us']


def test_index_of_a_log_with_no_data_records():
    b = wb.LogBuilder(); b.entry('/A', 'double')
    ix = build_index(b.build())
    assert len(ix.cycles_us) == 0 and ix.duration_s == 0 and ix.mode_spans() == []


def test_index_rejects_non_wpilog():
    with pytest.raises(ValueError):
        build_index(b'not a log at all, sorry')


@pytest.mark.skipif(not NOTES.exists(), reason='sample logs not present')
def test_index_of_a_real_log_accounts_for_every_byte():
    path = next(NOTES.glob('*baseline.wpilog'))
    raw, ix = load_index(path)
    assert len(ix.entries) == 314 and len(ix.cycles_us) == 1876
    unparsed_tail = len(raw) - (ix.header_end + ix.control_bytes + ix.data_bytes)
    assert 0 <= unparsed_tail < 256                            # only a truncated final record may be unaccounted
    assert [m for *_, m in ix.mode_spans()] == ['disabled', 'auto', 'disabled']
    assert [e.name for e in ix.entries.values() if e.time_mirror] == ['/Timestamp']
