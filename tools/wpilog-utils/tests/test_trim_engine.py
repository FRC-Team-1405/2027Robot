"""The multi-segment trim engine (trim.py) and its independent verifier (verify.py)."""
import json
import pathlib
import struct

import pytest

import wpilog_builder as wb
from wpilog_utils.decode import parse_wpilog_bytes
from wpilog_utils.index import build_index, load_index
from wpilog_utils.trim import (SEGMENT_MAP_ENTRY, Segment, TrimPlan, dry_run, mode_segments, resolve_plan,
                               trim_log)
from wpilog_utils.verify import verify_trim

NOTES = pathlib.Path(__file__).resolve().parents[3] / 'notes' / '6-20'
CYCLE = 20_000          # µs; ds_log's default

TWO_AUTOS = [('disabled', 1.0), ('auto', 1.0), ('disabled', 5.0), ('auto', 1.0), ('disabled', 2.0), ('teleop', 1.0)]


def run(raw, plan, expect_ok=True):
    """Index -> resolve -> dry-run -> write -> verify. Also asserts dry_run's size is the written size."""
    ix = build_index(raw)
    res = resolve_plan(ix, plan)
    out, st = trim_log(raw, ix, plan, res)
    assert dry_run(raw, ix, plan, res).bytes_out == len(out) == st.bytes_out
    rep = verify_trim(out, raw, ix, plan, res)
    if expect_ok:
        assert rep.ok, str(rep)
    return ix, res, out, st, rep


def ds_values(out, name):
    return [v for _, v in parse_wpilog_bytes(out)[name]]


def secs(spans_us):
    return [x / 1e6 for x in spans_us]


# ── single segment ──────────────────────────────────────────────────────────────────────────────

def test_keep_one_auto_period():
    raw, _ = wb.ds_log(TWO_AUTOS)
    ix = build_index(raw)
    plan = TrimPlan(mode_segments(ix, ['auto'], which=[0]))
    _, res, out, st, _ = run(raw, plan)
    assert len(res.ranges) == 1 and res.ranges[0].n_cycles == 50
    o = build_index(out)
    assert o.t_min_us == ix.t_min_us                      # output starts where the source started
    assert len(o.cycles_us) == 50
    assert [m for *_, m in o.mode_spans()] == ['auto']
    assert st.bytes_out < len(raw) * 0.2


def test_output_header_is_the_sources_and_cycles_are_evenly_spaced():
    raw, _ = wb.ds_log(TWO_AUTOS)
    ix = build_index(raw)
    _, res, out, _, _ = run(raw, TrimPlan(mode_segments(ix, ['auto'], which=[1])))
    assert out[:ix.header_end] == raw[:ix.header_end] and b'AdvantageKit' in out[:24]
    c = build_index(out).cycles_us
    assert {b - a for a, b in zip(c, c[1:])} == {CYCLE}


def test_time_mirror_entry_is_restamped():
    raw, _ = wb.ds_log(TWO_AUTOS)
    ix = build_index(raw)
    _, _, out, _, _ = run(raw, TrimPlan(mode_segments(ix, ['auto'], which=[1])))
    ts = parse_wpilog_bytes(out)['Timestamp']
    assert ts and all(round(t * 1e6) == v for t, v in ts)
    assert ts[0][0] == pytest.approx(ix.t_min_us / 1e6)   # ...and it now starts at the source's start


def test_manual_segment_snaps_to_whole_cycles():
    raw, info = wb.ds_log(TWO_AUTOS)
    c0 = info['cycles_us'][0]
    # 0.505 s..1.005 s after start straddles cycle boundaries (cycles every 0.02 s)
    ix, res, out, *_ = run(raw, TrimPlan([Segment(0.505, 1.005)]))
    kept = [info['cycles_us'][i] - c0 for i in range(res.ranges[0].first, res.ranges[0].last + 1)]
    assert kept[0] == 520_000 and kept[-1] == 1_000_000     # first cycle >= start, last cycle < end


def test_segment_past_end_keeps_the_final_cycle():
    raw, info = wb.ds_log(TWO_AUTOS)
    ix, res, *_ = run(raw, TrimPlan([Segment(10.0, 999.0)]))
    assert res.ranges[0].last == len(info['cycles_us']) - 1 and res.ranges[0].hi_us is None


# ── multiple segments + gap ─────────────────────────────────────────────────────────────────────

def test_two_autos_are_joined_by_a_short_gap_of_real_cycles():
    raw, _ = wb.ds_log(TWO_AUTOS)
    ix = build_index(raw)
    plan = TrimPlan(mode_segments(ix, ['auto']), gap_ms=200)
    _, res, out, st, _ = run(raw, plan)
    assert len(res.ranges) == 2 and res.gap_cycles == 10
    assert [r.n_cycles for r in res.ranges] == [50 + 5, 5 + 50]           # each auto + 5 real disabled cycles
    o = build_index(out)
    assert len(o.cycles_us) == 110
    spans = o.mode_spans()
    assert [m for *_, m in spans] == ['auto', 'disabled', 'auto']
    assert spans[1][1] - spans[1][0] == pytest.approx(10 * CYCLE / 1e6)   # 5 real + 5 real cycles = the requested 200 ms
    assert ds_values(out, 'DriverStation/Enabled') == [True, False, True]
    assert ds_values(out, 'DriverStation/Autonomous') == [True, False, True]


def test_seam_is_exactly_one_nominal_period_wide():
    raw, _ = wb.ds_log(TWO_AUTOS)
    ix = build_index(raw)
    _, res, out, *_ = run(raw, TrimPlan(mode_segments(ix, ['auto'])))
    c = build_index(out).cycles_us
    assert all(b - a == CYCLE for a, b in zip(c, c[1:]))                  # no visible discontinuity anywhere


@pytest.mark.parametrize('gap_ms,kept', [(0, 0), (20, 1), (40, 2), (100, 5), (200, 10), (500, 25)])
def test_gap_size_controls_how_many_real_cycles_are_kept(gap_ms, kept):
    raw, _ = wb.ds_log(TWO_AUTOS)
    ix = build_index(raw)
    _, res, out, *_ = run(raw, TrimPlan(mode_segments(ix, ['auto']), gap_ms=gap_ms))
    assert res.gap_cycles == kept
    assert len(build_index(out).cycles_us) == 100 + kept


def test_a_dropped_stretch_shorter_than_the_gap_is_kept_whole_and_ranges_merge():
    raw, _ = wb.ds_log([('disabled', 1), ('auto', 1), ('disabled', 0.1), ('auto', 1), ('disabled', 1)])
    ix = build_index(raw)
    _, res, out, *_ = run(raw, TrimPlan(mode_segments(ix, ['auto']), gap_ms=200))
    assert len(res.ranges) == 1 and res.seams == []
    assert len(build_index(out).cycles_us) == 50 + 5 + 50                 # nothing dropped in between


def test_overlapping_and_touching_segments_merge():
    raw, _ = wb.ds_log(TWO_AUTOS)
    plan = TrimPlan([Segment(1.0, 1.5), Segment(1.4, 1.8), Segment(1.8, 2.0)])
    _, res, *_ = run(raw, plan)
    assert len(res.ranges) == 1 and res.ranges[0].n_cycles == 50


def test_segment_order_does_not_matter():
    raw, _ = wb.ds_log(TWO_AUTOS)
    ix = build_index(raw)
    a, b = mode_segments(ix, ['auto'])
    _, _, out1, *_ = run(raw, TrimPlan([a, b]))
    _, _, out2, *_ = run(raw, TrimPlan([b, a]))
    assert out1 == out2


def test_padding_keeps_extra_real_cycles_around_a_segment():
    raw, _ = wb.ds_log(TWO_AUTOS)
    ix = build_index(raw)
    seg = mode_segments(ix, ['auto'], which=[0], pad_pre_ms=100, pad_post_ms=60)[0]
    _, res, out, *_ = run(raw, TrimPlan([seg]))
    assert res.ranges[0].n_cycles == 50 + 5 + 3
    assert [m for *_, m in build_index(out).mode_spans()] == ['disabled', 'auto', 'disabled']


def test_preserve_policy_keeps_original_timestamps_and_leaves_a_hole():
    raw, info = wb.ds_log(TWO_AUTOS)
    ix = build_index(raw)
    _, res, out, *_ = run(raw, TrimPlan(mode_segments(ix, ['auto']), gap_policy='preserve'))
    assert all(r.offset_us == 0 for r in res.ranges)
    kept = set(build_index(out).cycles_us)
    assert kept <= set(info['cycles_us']) and len(kept) == 100
    assert build_index(out).t_min_us == ix.cycles_us[res.ranges[0].first]


# ── state at seams ──────────────────────────────────────────────────────────────────────────────

def test_values_set_before_or_during_dropped_time_are_restated_at_range_start():
    # /Cfg/K is written once in cycle 0; /Cfg/M is written once during the long disabled gap, cycle 100.
    raw, _ = wb.ds_log(TWO_AUTOS, extra_entries=[('/Cfg/K', 'double'), ('/Cfg/M', 'double')],
                       extra_records=[('/Cfg/K', 0, wb.double(3.5)), ('/Cfg/M', 100, wb.double(9.0))])
    ix = build_index(raw)
    _, res, out, st, _ = run(raw, TrimPlan(mode_segments(ix, ['auto'], which=[1])))
    sig = parse_wpilog_bytes(out)
    assert [v for _, v in sig['Cfg/K']] == [3.5] and [v for _, v in sig['Cfg/M']] == [9.0]
    assert sig['Cfg/K'][0][0] == pytest.approx(ix.t_min_us / 1e6)          # restated on the first cycle
    assert st.n_carried >= 2


def test_a_value_that_changed_inside_the_dropped_gap_is_corrected_on_the_far_side_of_the_seam():
    # K=1 in cycle 0, K=2 at cycle 80 (inside the 5 s disabled gap; gap = cycles 100..349) -> not kept by the pads.
    raw, _ = wb.ds_log(TWO_AUTOS, extra_entries=[('/K', 'double')],
                       extra_records=[('/K', 0, wb.double(1.0)), ('/K', 200, wb.double(2.0))])
    ix = build_index(raw)
    _, res, out, *_ = run(raw, TrimPlan(mode_segments(ix, ['auto'])))
    vals = [v for _, v in parse_wpilog_bytes(out)['K']]
    assert vals == [1.0, 2.0]                        # 1.0 at the start, 2.0 restated on the second range's first cycle
    t2 = parse_wpilog_bytes(out)['K'][1][0]
    assert t2 == pytest.approx((build_index(out).cycles_us[res.ranges[0].n_cycles]) / 1e6)


def test_unchanged_values_are_not_restated_after_a_seam():
    raw, _ = wb.ds_log(TWO_AUTOS, extra_entries=[('/K', 'double')], extra_records=[('/K', 0, wb.double(1.0))])
    ix = build_index(raw)
    _, res, out, *_ = run(raw, TrimPlan(mode_segments(ix, ['auto'])))
    assert [v for _, v in parse_wpilog_bytes(out)['K']] == [1.0]           # written once, holds across the seam


def test_entries_first_logged_after_the_kept_range_do_not_appear():
    raw, _ = wb.ds_log(TWO_AUTOS, extra_entries=[('/Late', 'double')], extra_records=[('/Late', 300, wb.double(1.0))])
    ix = build_index(raw)
    _, _, out, _, rep = run(raw, TrimPlan(mode_segments(ix, ['auto'], which=[0])))
    assert 'Late' not in parse_wpilog_bytes(out)
    assert '/Late' in rep.info['entries_without_output_records']


# ── exclusion ───────────────────────────────────────────────────────────────────────────────────

def test_excluded_entries_and_prefixes_are_removed_and_save_bytes():
    raw, _ = wb.ds_log(TWO_AUTOS, extra_entries=[('/Vision/L/A', 'double'), ('/Vision/L/B', 'double'), ('/Visionary', 'double')],
                       extra_records=[('/Vision/L/A', 0, wb.double(1)), ('/Vision/L/B', 0, wb.double(1)), ('/Visionary', 0, wb.double(1))])
    ix = build_index(raw)
    segs = mode_segments(ix, ['auto'])
    _, _, base, base_st, _ = run(raw, TrimPlan(segs))
    _, res, out, st, _ = run(raw, TrimPlan(segs, exclude=['/Sensor/X'], exclude_prefixes=['Vision']))
    sig = parse_wpilog_bytes(out)
    assert 'Sensor/X' not in sig and 'Vision/L/A' not in sig and 'Vision/L/B' not in sig
    assert 'Visionary' in sig                                              # prefix match respects '/' boundaries
    assert st.bytes_out < base_st.bytes_out and st.n_excluded_records > 0


def test_excluding_the_cycle_marker_warns():
    raw, _ = wb.ds_log(TWO_AUTOS)
    ix = build_index(raw)
    res = resolve_plan(ix, TrimPlan(mode_segments(ix, ['auto']), exclude=['/Timestamp']))
    assert any('cycle marker' in w for w in res.warnings)


# ── the recoverable note ────────────────────────────────────────────────────────────────────────

def test_segment_map_recovers_original_times():
    raw, info = wb.ds_log(TWO_AUTOS)
    ix = build_index(raw)
    plan = TrimPlan(mode_segments(ix, ['auto']), gap_ms=200, source_name='src.wpilog')
    _, res, out, *_ = run(raw, plan)
    note = json.loads(parse_wpilog_bytes(out)[SEGMENT_MAP_ENTRY.lstrip('/')][0][1])
    assert note['schema'] == 'wpilog-janitor.segmap/v1' and note['source_file'] == 'src.wpilog'
    assert note['source_bytes'] == len(raw) and note['gap_ms'] == 200 and note['cycle_period_ms'] == 20.0
    o_cycles = [c / 1e6 for c in build_index(out).cycles_us]
    s_cycles = {c / 1e6 for c in info['cycles_us']}
    for seg in note['segments']:
        assert seg['new_first'] - seg['offset'] == pytest.approx(seg['orig_first'], abs=1e-6)
        assert round(seg['orig_first'], 6) in {round(c, 6) for c in s_cycles}      # a real source cycle
        assert any(abs(c - seg['new_first']) < 1e-6 for c in o_cycles)              # ...that exists in the output
    assert note['rewritten_time_entries'] == ['/Timestamp']
    assert len(note['seams']) == 1 and note['seams'][0]['dropped_cycles'] > 0


def test_segment_map_lists_exclusions():
    raw, _ = wb.ds_log(TWO_AUTOS)
    ix = build_index(raw)
    _, _, out, *_ = run(raw, TrimPlan(mode_segments(ix, ['auto']), exclude=['/Sensor/X']))
    note = json.loads(parse_wpilog_bytes(out)[SEGMENT_MAP_ENTRY.lstrip('/')][0][1])
    assert note['excluded_entries'] == ['/Sensor/X']


# ── other log shapes ────────────────────────────────────────────────────────────────────────────

def test_log_without_a_cycle_marker_entry():
    raw, _ = wb.ds_log(TWO_AUTOS, with_timestamp_entry=False)
    ix = build_index(raw)
    _, res, out, *_ = run(raw, TrimPlan(mode_segments(ix, ['auto'])))
    assert len(build_index(out).cycles_us) == 110


def test_wide_source_headers_and_huge_timestamps():
    raw, _ = wb.ds_log(TWO_AUTOS, minimal=False, t0_us=5_000_000_000)
    ix = build_index(raw)
    _, res, out, st, _ = run(raw, TrimPlan(mode_segments(ix, ['auto'])))
    assert build_index(out).t_min_us == 5_000_000_000 and st.bytes_out < len(raw)


def test_log_with_no_driverstation_data_supports_manual_segments():
    b = wb.LogBuilder(); b.entry('/A', 'double')
    for k in range(100):
        b.data('/A', 1_000_000 + k * 20_000, wb.double(k))
    raw = b.build()
    ix = build_index(raw)
    assert ix.mode_spans() == [] and mode_segments(ix, ['auto']) == []
    _, res, out, *_ = run(raw, TrimPlan([Segment(0.2, 0.6)]))
    assert res.ranges[0].n_cycles == 20


def test_finish_and_late_metadata_records_are_reported_not_silently_lost():
    b = wb.LogBuilder(); b.entry('/A', 'double')
    b.data('/A', 1_000_000, wb.double(1)); b.data('/A', 1_020_000, wb.double(2))
    b.raw(wb.finish(1, 1_030_000)); b.data('/A', 1_040_000, wb.double(3))
    raw = b.build()
    _, _, out, st, _ = run(raw, TrimPlan([Segment(0, 1)]))
    assert st.control_records_dropped == 1


def test_data_for_never_started_entries_is_dropped():
    b = wb.LogBuilder(); b.entry('/A', 'double')
    b.data('/A', 1_000_000, wb.double(1)); b.raw(wb.record(77, 1_000_000, wb.double(1)))
    b.data('/A', 1_020_000, wb.double(2))
    _, _, out, *_ = run(b.build(), TrimPlan([Segment(0, 1)]))
    assert sorted(parse_wpilog_bytes(out)) == ['A', SEGMENT_MAP_ENTRY.lstrip('/')]


def test_truncated_source_still_trims_and_verifies():
    raw, _ = wb.ds_log(TWO_AUTOS)
    raw = raw[:-7]
    ix = build_index(raw)
    run(raw, TrimPlan(mode_segments(ix, ['auto'])))


# ── argument validation ─────────────────────────────────────────────────────────────────────────

def test_resolve_errors_are_clear():
    raw, _ = wb.ds_log(TWO_AUTOS)
    ix = build_index(raw)
    with pytest.raises(ValueError, match='no segments'):
        resolve_plan(ix, TrimPlan([]))
    with pytest.raises(ValueError, match='after start'):
        resolve_plan(ix, TrimPlan([Segment(2, 1)]))
    with pytest.raises(ValueError, match='gap_policy'):
        resolve_plan(ix, TrimPlan([Segment(0, 1)], gap_policy='stretch'))
    with pytest.raises(ValueError, match='any data'):
        resolve_plan(ix, TrimPlan([Segment(500, 600)]))


def test_out_of_order_source_is_refused():
    b = wb.LogBuilder(); b.entry('/A', 'double')
    b.data('/A', 2_000_000, wb.double(1)); b.data('/A', 1_000_000, wb.double(2))
    ix = build_index(b.build())
    with pytest.raises(ValueError, match='time order'):
        resolve_plan(ix, TrimPlan([Segment(0, 1)]))


def test_an_empty_segment_is_skipped_with_a_warning_when_others_have_data():
    raw, _ = wb.ds_log(TWO_AUTOS)
    ix = build_index(raw)
    res = resolve_plan(ix, TrimPlan([Segment(0.505, 0.51), Segment(1.0, 2.0)]))
    assert len(res.ranges) == 1 and any('no cycles' in w for w in res.warnings)


# ── the verifier catches what it should ─────────────────────────────────────────────────────────

def test_verifier_flags_a_tampered_output():
    raw, _ = wb.ds_log(TWO_AUTOS)
    ix = build_index(raw)
    plan = TrimPlan(mode_segments(ix, ['auto']))
    res = resolve_plan(ix, plan)
    out, _ = trim_log(raw, ix, plan, res)
    assert verify_trim(out, raw, ix, plan, res).ok
    assert not verify_trim(out[:-40], raw, ix, plan, res).ok                                 # lost records
    assert not verify_trim(out[:5] + b'X' + out[6:], raw, ix, plan, res).ok                  # header damaged
    bad_hdr = raw[:12] + b'Advantage!Kit'[:len(ix.extra_header)] + out[ix.header_end:]
    assert not verify_trim(bad_hdr, raw, ix, plan, res).ok


# ── real logs ───────────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not NOTES.exists(), reason='sample logs not present')
def test_real_log_auto_plus_tail_of_disabled():
    raw, ix = load_index(next(NOTES.glob('*decimateBack.wpilog')))
    auto = mode_segments(ix, ['auto'])[0]
    tail = Segment(ix.duration_s - 3.0, ix.duration_s + 1, 'disabled')
    plan = TrimPlan([auto, tail], gap_ms=200)
    _, res, out, st, _ = run(raw, plan)
    assert len(res.ranges) == 2 and st.saved_pct > 85
    o = build_index(out)
    assert [m for *_, m in o.mode_spans()] == ['auto', 'disabled']
    assert o.header_end == ix.header_end and o.extra_header == b'AdvantageKit'
    assert parse_wpilog_bytes(out)                      # the project's own decoder still reads it end to end


@pytest.mark.skipif(not NOTES.exists(), reason='sample logs not present')
def test_real_log_full_range_is_lossless_in_preserve_mode():
    raw, ix = load_index(next(NOTES.glob('*baseline.wpilog')))
    plan = TrimPlan([Segment(0, ix.duration_s + 1)], gap_policy='preserve')
    _, _, out, st, _ = run(raw, plan)
    src, dst = parse_wpilog_bytes(raw), parse_wpilog_bytes(out)
    dst.pop(SEGMENT_MAP_ENTRY.lstrip('/'))
    assert src == dst                                   # every decoded sample identical
    assert st.n_carried == 0
