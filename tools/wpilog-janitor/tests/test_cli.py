"""The janitor CLI, end to end on synthetic logs."""
import json
import pathlib

import pytest

import wpilog_builder as wb
from janitor.cli import main
from janitor.core import sizes
from wpilog_utils.decode import parse_wpilog_bytes
from wpilog_utils.index import build_index

SPANS = [('disabled', 1.0), ('auto', 1.0), ('disabled', 5.0), ('auto', 1.0), ('disabled', 2.0), ('teleop', 1.0)]


@pytest.fixture
def log(tmp_path):
    raw, _ = wb.ds_log(SPANS, extra_entries=[('/Vision/L/A', 'double'), ('/Vision/L/B', 'double')],
                       extra_records=[('/Vision/L/A', 0, wb.double(1)), ('/Vision/L/B', 60, wb.double(2))])
    p = tmp_path / 'akit_test.wpilog'
    p.write_bytes(raw)
    return p


def test_analyze_lists_modes_and_sizes(log, capsys):
    assert main(['analyze', str(log), '--top', '5']) == 0
    out = capsys.readouterr().out
    assert out.count('auto') >= 2 and 'teleop' in out and 'disabled' in out
    assert '/Sensor' in out and '/Timestamp' in out and 'AdvantageKit' in out


def test_trim_writes_a_verified_file_next_to_the_source_by_default(log, capsys):
    assert main(['trim', str(log), '--modes', 'auto']) == 0
    dest = log.with_name('akit_test_trimmed.wpilog')
    assert dest.exists() and dest.stat().st_size < log.stat().st_size
    assert 'verify: OK' in capsys.readouterr().out
    # original timestamps by default: the two autos stay apart, with a hole (not a disabled seam) between them
    assert [m for *_, m in build_index(dest.read_bytes()).mode_spans()] == ['auto']
    note = json.loads(parse_wpilog_bytes(dest.read_bytes())['Janitor/SegmentMap'][0][1])
    assert note['gap_policy'] == 'preserve' and all(s['offset'] == 0 for s in note['segments'])


def test_compact_flag_re_times_into_short_seams(log, tmp_path):
    out = tmp_path / 'o.wpilog'
    assert main(['trim', str(log), '--modes', 'auto', '--compact', '-o', str(out)]) == 0
    assert [m for *_, m in build_index(out.read_bytes()).mode_spans()] == ['auto', 'disabled', 'auto']
    note = json.loads(parse_wpilog_bytes(out.read_bytes())['Janitor/SegmentMap'][0][1])
    assert note['gap_policy'] == 'compact'


def test_preserve_and_compact_cannot_be_combined(log, tmp_path):
    with pytest.raises(SystemExit):
        main(['trim', str(log), '--modes', 'auto', '--preserve', '--compact', '-o', str(tmp_path / 'o.wpilog')])


def test_dry_run_writes_nothing_and_reports_the_size_the_real_run_produces(log, tmp_path, capsys):
    assert main(['trim', str(log), '--modes', 'auto', '--dry-run']) == 0
    assert not log.with_name('akit_test_trimmed.wpilog').exists()
    dry = capsys.readouterr().out
    out = tmp_path / 'o.wpilog'
    assert main(['trim', str(log), '--modes', 'auto', '-o', str(out)]) == 0
    assert sizes.human(out.stat().st_size) in dry


def test_only_selects_among_matching_spans(log, tmp_path):
    out = tmp_path / 'o.wpilog'
    assert main(['trim', str(log), '--modes', 'auto', '--only', '1', '-o', str(out)]) == 0
    assert [m for *_, m in build_index(out.read_bytes()).mode_spans()] == ['auto']


def test_range_and_gap_options(log, tmp_path):
    out = tmp_path / 'o.wpilog'
    assert main(['trim', str(log), '--range', '0:1', '--range', '4:5', '--compact', '--gap-ms', '0', '-o', str(out)]) == 0
    assert len(build_index(out.read_bytes()).cycles_us) == 100


def test_preserve_flag(log, tmp_path):
    out = tmp_path / 'o.wpilog'
    assert main(['trim', str(log), '--modes', 'auto', '--preserve', '-o', str(out)]) == 0
    note = json.loads(parse_wpilog_bytes(out.read_bytes())['Janitor/SegmentMap'][0][1])
    assert note['gap_policy'] == 'preserve' and all(s['offset'] == 0 for s in note['segments'])


def test_exclude_options(log, tmp_path):
    out = tmp_path / 'o.wpilog'
    assert main(['trim', str(log), '--modes', 'auto', '--exclude', '/Sensor/X', '--exclude-prefix', 'Vision', '-o', str(out)]) == 0
    sig = parse_wpilog_bytes(out.read_bytes())
    assert 'Sensor/X' not in sig and not any(k.startswith('Vision') for k in sig)


def test_segmap_prints_the_original_time_map(log, tmp_path, capsys):
    out = tmp_path / 'o.wpilog'
    main(['trim', str(log), '--modes', 'auto', '-o', str(out)])
    capsys.readouterr()
    assert main(['segmap', str(out)]) == 0
    text = capsys.readouterr().out
    assert 'akit_test.wpilog' in text and 'offset' in text and text.count('auto') == 2
    assert main(['segmap', str(out), '--json']) == 0
    assert json.loads(capsys.readouterr().out)['schema'] == 'wpilog-janitor.segmap/v1'


def test_segmap_on_a_log_that_was_not_trimmed(log, capsys):
    assert main(['segmap', str(log)]) == 1
    assert 'not produced by wpilog-janitor' in capsys.readouterr().err


def test_bad_invocations_exit_nonzero_with_a_message(log, capsys):
    assert main(['trim', str(log)]) == 2
    assert 'nothing selected' in capsys.readouterr().err
    assert main(['trim', str(log), '--range', '900:999']) == 2
    assert 'error' in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(['trim', str(log), '--range', 'nonsense'])


def test_rollup_groups_by_depth(log):
    ix = build_index(log.read_bytes())
    by2 = {g.prefix: g for g in sizes.rollup(ix, 2)}
    assert '/Vision/L' in by2 and by2['/Vision/L'].entries == 2
    assert sizes.rollup(ix, 1)[0].bytes >= sizes.rollup(ix, 1)[-1].bytes


# ── bad paths give a message, not a traceback ───────────────────────────────────────────────────

def test_a_folder_lists_the_logs_inside_it_newest_first(log, tmp_path, capsys):
    sub = tmp_path / 'nested'
    sub.mkdir()
    newer = sub / 'newer.wpilog'
    newer.write_bytes(log.read_bytes())
    import os
    os.utime(log, (1_000_000_000, 1_000_000_000))
    for cmd in ('analyze', 'trim', 'segmap'):
        assert main([cmd, str(tmp_path)] + (['--modes', 'auto'] if cmd == 'trim' else [])) == 2
        err = capsys.readouterr().err
        assert 'is a folder' in err and '2 .wpilog' in err
        assert err.index('newer.wpilog') < err.index('akit_test.wpilog')


def test_an_empty_folder_says_so(tmp_path, capsys):
    assert main(['analyze', str(tmp_path)]) == 2
    assert 'contains no .wpilog files' in capsys.readouterr().err


def test_missing_and_non_log_files_are_reported_cleanly(tmp_path, capsys):
    assert main(['analyze', str(tmp_path / 'nope.wpilog')]) == 2
    assert 'no such file' in capsys.readouterr().err
    junk = tmp_path / 'junk.wpilog'
    junk.write_bytes(b'this is not a log, just some text')
    for cmd in ('analyze', 'segmap'):
        assert main([cmd, str(junk)]) == 2
        assert 'not a readable .wpilog' in capsys.readouterr().err


def test_modes_that_match_nothing_explain_what_the_log_does_have(tmp_path, capsys):
    raw, _ = wb.ds_log([('disabled', 1.0), ('teleop', 1.0), ('disabled', 1.0)])
    p = tmp_path / 'noauto.wpilog'
    p.write_bytes(raw)
    assert main(['trim', str(p), '--modes', 'auto']) == 2
    err = capsys.readouterr().err
    assert 'no span matches --modes auto' in err and 'disabled, teleop' in err


# ── dupes ───────────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def dup_log(tmp_path):
    b = wb.LogBuilder()
    for n in ['/Timestamp', '/Pickup/Velocity', '/RealOutputs/Pickup/Velocity', '/Vision/A/Raw', '/Vision/A/Copy', '/Cfg/Zero']:
        b.entry(n, 'int64' if n == '/Timestamp' else 'double', 1_000_000)
    for k in range(400):
        t = 1_000_000 + k * 20_000
        v = round(((k * 0.37) % 7) - 3, 3)
        w = round(((k * 0.11) % 5) - 2, 3)                      # a different series for the Vision pair
        b.data('/Timestamp', t, wb.int64(t))
        for n, val in (('/Pickup/Velocity', v), ('/RealOutputs/Pickup/Velocity', v), ('/Vision/A/Raw', w), ('/Vision/A/Copy', w)):
            b.data(n, t, wb.double(val))
        b.data('/Cfg/Zero', t, wb.double(0.0))
    p = tmp_path / 'dups.wpilog'
    p.write_bytes(b.build())
    return p


def test_dupes_reports_constants_groups_keepers_and_protection(dup_log, capsys):
    assert main(['dupes', str(dup_log)]) == 0
    out = capsys.readouterr().out
    assert 'Constants: 1 of 6 entries' in out and 'Duplicates: 2 group(s)' in out
    assert 'keep /Pickup/Velocity' in out and 'drop /RealOutputs/Pickup/Velocity' in out
    assert 'keep /Vision/A/Raw' in out and 'drop /Vision/A/Copy' in out and '<- protected: replay input' in out   # both are replay inputs
    assert 'Weak matches' not in out


def test_dupes_without_protection_and_with_a_window(dup_log, capsys):
    assert main(['dupes', str(dup_log), '--protect', '']) == 0
    assert 'protected' not in capsys.readouterr().out.replace('protecting: nothing', '')
    assert main(['dupes', str(dup_log), '--range', '1:3']) == 0
    assert '1 kept period(s), 100 of 400 cycles' in capsys.readouterr().out


def test_dupes_bad_arguments(dup_log, capsys):
    assert main(['dupes', str(dup_log), '--protect', 'everything']) == 2
    assert 'unknown protection profile' in capsys.readouterr().err
    assert main(['dupes', str(dup_log), '--modes', 'auto']) == 2
    assert 'nothing selected' in capsys.readouterr().err
    assert main(['dupes', str(dup_log.parent)]) == 2
