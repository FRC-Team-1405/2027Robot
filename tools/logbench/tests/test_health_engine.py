"""health/engine.py over synthetic signals: every measure, the rules, wildcards, windows, live
snapshots, latching and the report's roll-ups. No real log or robot needed."""
import math
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401

from health import config, engine
from health.engine import FAIL, NA, NODATA, OK, WARN

# A 100 s log starting at t=10 s: disabled 0-20, auto 20-30, disabled 30-40, teleop 40-90, disabled 90-100
# (spans are relative to the log start, as Log.mode_spans() gives them).
T0 = 10.0
SPANS = [(0, 20, 'disabled'), (20, 30, 'auto'), (30, 40, 'disabled'), (40, 90, 'teleop'), (90, 100, 'disabled')]


def ts(*pairs):
    """[(seconds after log start, value), ...] -> a signal series in absolute log time."""
    return [(T0 + t, v) for t, v in pairs]


def log(signals, spans=SPANS):
    base = {'Anchor': ts((0, 0), (100, 0))}      # pins the log's bounds to [T0, T0 + 100]
    base.update(signals)
    return engine.LogSource(base, spans)


def run(toml, source):
    specs, errors = config.parse(toml)
    assert errors == [], errors
    return engine.evaluate(specs, source)


def one(toml, source):
    report = run(toml, source)
    checks = [c for s in report['sections'] for g in s['groups'] for sub in g['subjects'] for c in sub['checks']]
    assert len(checks) == 1, checks
    return checks[0]


def check_toml(body, signal='X'):
    return f'[[check]]\nid="c"\nsection="S"\nlabel="L"\nsignal="{signal}"\n{body}\n'


# ── measures ──────────────────────────────────────────────────────────────────────────────────

def test_max_over_the_window_and_when_it_happened():
    src = log({'X': ts((0, 10), (50, 95), (60, 20))})
    c = one(check_toml('measure="max"\nwarn_above=70\nfail_above=90\nunit="%"'), src)
    assert (c['status'], c['value'], c['display']) == (FAIL, 95.0, '95 %')
    assert 'at 50.0 s into the log' in c['detail']


def test_the_window_selects_only_matching_modes():
    # a spike during the disabled lead-in must not count against "enabled"
    src = log({'X': ts((0, 10), (5, 99), (6, 10), (50, 40), (60, 10))})
    assert one(check_toml('measure="max"\nwindow="all"\nfail_above=90'), src)['status'] == FAIL
    c = one(check_toml('measure="max"\nwindow="enabled"\nfail_above=90'), src)
    assert (c['status'], c['value']) == (OK, 40.0)
    assert one(check_toml('measure="max"\nwindow="teleop"'), src)['value'] == 40.0
    assert one(check_toml('measure="max"\nwindow="auto"'), src)['value'] == 10.0   # carried in from before the window


def test_a_value_that_held_before_the_window_still_counts_for_it():
    src = log({'X': ts((0, 7))})          # one record, held for the whole log
    assert one(check_toml('measure="min"\nwindow="teleop"'), src)['value'] == 7.0


def test_min_mean_first_last_delta():
    src = log({'X': ts((0, 4), (25, 8), (50, 12))})
    assert one(check_toml('measure="min"'), src)['value'] == 4.0
    assert one(check_toml('measure="first"'), src)['value'] == 4.0
    assert one(check_toml('measure="last"'), src)['value'] == 12.0
    assert one(check_toml('measure="delta"'), src)['value'] == 8.0
    # time-weighted: 4 for 25 s, 8 for 25 s, 12 for 50 s
    assert one(check_toml('measure="mean"'), src)['value'] == pytest.approx((4 * 25 + 8 * 25 + 12 * 50) / 100)


def test_mean_is_time_weighted_not_a_mean_of_records():
    # 100 for one second then 0 for 99 s, but with many records during the second
    pairs = [(i / 10, 100 if i % 2 == 0 else 0) for i in range(10)] + [(1, 0)]
    c = one(check_toml('measure="mean"'), log({'X': ts(*pairs)}))
    assert c['value'] == pytest.approx(0.5, abs=0.01)         # ~50% of one second, not 50% of the log


def test_seconds_above_and_below():
    src = log({'X': ts((0, 0), (40, 10), (60, 0))})           # above 5 for 20 s, all inside teleop
    c = one(check_toml('measure="seconds_above"\nabove=5\nwindow="enabled"\nunit="s"\nwarn_above=15'), src)
    assert (c['value'], c['status']) == (20.0, WARN)
    # below 5: all 10 s of auto (value 0), then teleop 60-90 s (30 s) -> 40 s of the 60 s enabled
    assert one(check_toml('measure="seconds_below"\nbelow=5\nwindow="enabled"'), src)['value'] == pytest.approx(40.0)


def test_booleans_true_time_fraction_any_all():
    src = log({'X': ts((0, False), (45, True), (65, False))})   # true for 20 s of 50 s teleop
    assert one(check_toml('measure="seconds_true"\nwindow="teleop"'), src)['value'] == pytest.approx(20.0)
    assert one(check_toml('measure="seconds_false"\nwindow="teleop"'), src)['value'] == pytest.approx(30.0)
    assert one(check_toml('measure="fraction_true"\nwindow="teleop"'), src)['value'] == pytest.approx(0.4)
    assert one(check_toml('measure="fraction_false"\nwindow="teleop"'), src)['value'] == pytest.approx(0.6)
    assert one(check_toml('measure="any_true"'), src)['value'] is True
    assert one(check_toml('measure="all_true"'), src)['value'] is False


def test_fraction_true_can_be_scaled_into_a_percent_with_thresholds():
    src = log({'X': ts((0, True), (45, False), (50, True))})      # false 5 s of 50 s teleop -> 90% true
    c = one(check_toml('measure="fraction_true"\nwindow="teleop"\nscale=100\nunit="%"\nwarn_below=95\nfail_below=80'), src)
    assert (c['status'], c['display']) == (WARN, '90 %')


def test_changes_counts_transitions_inside_the_window():
    src = log({'X': ts((0, 'a'), (45, 'b'), (50, 'a'), (55, 'a'), (60, 'c'))})
    assert one(check_toml('measure="changes"\nwindow="teleop"'), src)['value'] == 3.0


def test_max_len_reports_alert_text():
    src = log({'X': ts((0, []), (50, ['Motor 3 stalled', 'Low battery']), (60, []))})
    c = one(check_toml('measure="max_len"\nfail_above=0\ndecimals=0'), src)
    assert c['status'] == FAIL and c['display'] == '2'
    assert 'Low battery' in c['detail']


def test_nan_means_no_measurement():
    src = log({'X': ts((0, float('nan')), (50, float('nan')))})
    c = one(check_toml('measure="max"\nwarn_above=1'), src)
    assert c['status'] == NODATA
    src = log({'X': ts((0, 3), (10, float('nan')), (50, 5))})
    assert one(check_toml('measure="max"'), src)['value'] == 5.0


# ── rules ─────────────────────────────────────────────────────────────────────────────────────

def test_threshold_boundaries_and_fail_beats_warn():
    base = 'measure="last"\nwarn_above=10\nfail_above=20\n'
    for value, status in ((10, OK), (10.1, WARN), (20, WARN), (20.1, FAIL)):
        assert one(check_toml(base), log({'X': ts((0, value))}))['status'] == status, value
    below = 'measure="last"\nwarn_below=10\nfail_below=5\n'
    for value, status in ((10, OK), (9.9, WARN), (5, WARN), (4.9, FAIL)):
        assert one(check_toml(below), log({'X': ts((0, value))}))['status'] == status, value


def test_scale_applies_before_thresholds_and_to_the_displayed_value():
    c = one(check_toml('measure="max"\nscale=100\nunit="%"\nfail_above=90'), log({'X': ts((0, 0.95))}))
    assert (c['status'], c['value'], c['display']) == (FAIL, pytest.approx(95.0), '95 %')


def test_expect_boolean_string_and_number():
    assert one(check_toml('measure="last"\nexpect=true'), log({'X': ts((0, True))}))['status'] == OK
    assert one(check_toml('measure="last"\nexpect=true'), log({'X': ts((0, False))}))['status'] == FAIL
    assert one(check_toml('measure="last"\nexpect=false\nseverity="warn"'), log({'X': ts((0, True))}))['status'] == WARN
    assert one(check_toml('measure="last"\nexpect="OK"'), log({'X': ts((0, 'OK'))}))['status'] == OK
    assert one(check_toml('measure="last"\nexpect="OK"'), log({'X': ts((0, 'RxTimeout'))}))['status'] == FAIL
    assert one(check_toml('measure="last"\nexpect=3'), log({'X': ts((0, 3))}))['status'] == OK
    assert one(check_toml('measure="last"\nexpect=3'), log({'X': ts((0, 4))}))['status'] == FAIL


def test_expect_in():
    toml = 'measure="last"\nexpect_in=["idle","recording"]'
    assert one(check_toml(toml), log({'X': ts((0, 'idle'))}))['status'] == OK
    assert one(check_toml(toml), log({'X': ts((0, 'no_stream'))}))['status'] == FAIL


def test_a_check_with_no_rules_is_informational_and_never_red():
    c = one(check_toml('measure="max"'), log({'X': ts((0, 1e9))}))
    assert c['status'] == OK and c['rule'] == 'info only'


def test_the_rule_is_described_in_words():
    c = one(check_toml('measure="max"\nunit="%"\nwarn_above=70\nfail_above=90'), log({'X': ts((0, 1))}))
    assert c['rule'] == 'warn above 70 %, fail above 90 %'
    c = one(check_toml('measure="last"\nexpect=true'), log({'X': ts((0, True))}))
    assert c['rule'] == 'expect yes (fail otherwise)'


# ── finding signals ───────────────────────────────────────────────────────────────────────────

def test_realoutputs_and_nt_prefixes_are_found():
    for key in ('Vision/A/Score', 'RealOutputs/Vision/A/Score', 'NT:/Vision/A/Score'):
        c = one(check_toml('measure="last"', 'Vision/A/Score'), log({key: ts((0, 5))}))
        assert c['value'] == 5.0, key


def test_wildcards_expand_with_captures_lookups_and_subjects():
    toml = '''
[[check]]
id = "m"
section = "Robot"
group = "{subsystem}"
subject = "{name}"
label = "temp"
signal = "Motors/*/Temp"
lookup = { name = "Motors/{1}/Name", subsystem = "Motors/{1}/Subsystem" }
measure = "max"
warn_above = 50
'''
    src = log({
        'Motors/rio-1/Temp': ts((0, 30)), 'Motors/rio-1/Name': ts((0, 'Drive 0')), 'Motors/rio-1/Subsystem': ts((0, 'Drivetrain')),
        'Motors/rio-2/Temp': ts((0, 60)), 'Motors/rio-2/Name': ts((0, 'Drive 1')), 'Motors/rio-2/Subsystem': ts((0, 'Drivetrain')),
        'Motors/rio-9/Temp': ts((0, 20)), 'Motors/rio-9/Name': ts((0, 'Climber')), 'Motors/rio-9/Subsystem': ts((0, 'Climber')),
    })
    report = run(toml, src)
    [sec] = report['sections']
    assert [g['label'] for g in sec['groups']] == ['Drivetrain', 'Climber']    # first appearance, by key
    drive = sec['groups'][0]
    assert [(s['label'], s['status']) for s in drive['subjects']] == [('Drive 0', OK), ('Drive 1', WARN)]
    assert drive['status'] == WARN and sec['groups'][1]['status'] == OK and sec['status'] == WARN


def test_an_unnamed_item_falls_back_to_its_captured_name():
    toml = check_toml('measure="last"', 'Motors/*/Temp').replace('label="L"', 'label="temp {1}"')
    c = one(toml, log({'Motors/rio-4/Temp': ts((0, 1))}))
    assert c['label'] == 'temp rio-4'


def test_two_wildcards():
    toml = ('[[check]]\nid="c"\nsection="S"\ngroup="{1}"\nsubject="Recorder ({2})"\nlabel="state"\n'
            'signal="Pi/*/Rec/*/State"\nmeasure="last"\n')
    src = log({'Pi/Left/Rec/A/State': ts((0, 'idle')), 'Pi/Left/Rec/B/State': ts((0, 'idle')),
               'Pi/Right/Rec/A/State': ts((0, 'idle'))})
    report = run(toml, src)
    groups = {g['label']: [s['label'] for s in g['subjects']] for g in report['sections'][0]['groups']}
    assert groups == {'Left': ['Recorder (A)', 'Recorder (B)'], 'Right': ['Recorder (A)']}


# ── missing data ──────────────────────────────────────────────────────────────────────────────

def test_missing_signal_follows_the_missing_setting():
    for setting, status in (('nodata', NODATA), ('ok', OK), ('warn', WARN), ('fail', FAIL)):
        c = one(check_toml(f'measure="last"\nmissing="{setting}"'), log({}))
        assert c['status'] == status, setting
    c = one(check_toml('measure="last"'), log({}))
    assert 'not in this log' in c['detail']


def test_expect_items_must_all_be_present():
    toml = check_toml('measure="last"\nexpect_items=["A","B"]', 'Cam/*/On')
    report = run(toml, log({'Cam/A/On': ts((0, 1))}))
    rows = [c for s in report['sections'] for g in s['groups'] for sub in g['subjects'] for c in sub['checks']]
    by_status = sorted(c['status'] for c in rows)
    assert by_status == [FAIL, OK]
    assert any('expected B' in c['detail'] for c in rows)


def test_expect_items_do_not_fail_a_log_that_has_none_of_that_data():
    toml = check_toml('measure="last"\nexpect_items=["A","B"]', 'Cam/*/On')
    report = run(toml, log({}))
    rows = [c for s in report['sections'] for g in s['groups'] for sub in g['subjects'] for c in sub['checks']]
    assert [c['status'] for c in rows] == [NODATA]


def test_fraction_and_seconds_equal_to_a_value():
    src = log({'X': ts((0, 'OK'), (45, 'CanMessageStale'), (50, 'OK'))})          # 5 s stale of 50 s teleop
    c = one(check_toml('measure="fraction_equals"\nequals="OK"\nwindow="teleop"\nscale=100\nunit="%"\nwarn_below=95'), src)
    assert (c['status'], c['display']) == (WARN, '90 %')
    assert one(check_toml('measure="seconds_equals"\nequals="CanMessageStale"\nwindow="teleop"'), src)['value'] == pytest.approx(5.0)
    nums = log({'X': ts((0, 3), (45, 4))})
    assert one(check_toml('measure="seconds_equals"\nequals=3\nwindow="teleop"'), nums)['value'] == pytest.approx(5.0)
    flags = log({'X': ts((0, True), (45, False))})
    # false from 45 s to the end of teleop at 90 s
    assert one(check_toml('measure="seconds_equals"\nequals=false\nwindow="teleop"'), flags)['value'] == pytest.approx(45.0)


def test_equals_live_is_the_current_value_and_the_seconds_form_needs_a_log():
    src = engine.SnapshotSource({'X': ('OK', 0.1)})
    assert one(check_toml('measure="fraction_equals"\nequals="OK"\nscale=100\nfail_below=90'), src)['value'] == 100.0
    assert one(check_toml('measure="fraction_equals"\nequals="OK"\nscale=100\nfail_below=90'),
               engine.SnapshotSource({'X': ('RxTimeout', 0.1)}))['status'] == FAIL
    assert one(check_toml('measure="seconds_equals"\nequals="OK"'), src)['status'] == NA


def test_unfilled_wildcard_rows_go_to_a_shared_no_data_group():
    toml = ('[[check]]\nid="c"\nsection="S"\ngroup="{1}"\nsubject="Recorder ({2})"\nlabel="state {2}"\n'
            'signal="Pi/*/Rec/*/State"\n')
    report = run(toml, log({}))
    [g] = report['sections'][0]['groups']
    assert g['label'] == 'No data'
    [sub] = g['subjects']
    assert sub['label'] == 'Recorder (...)' and sub['checks'][0]['label'] == 'state ...'


def test_a_window_on_a_log_without_mode_data_explains_itself():
    src = log({'X': ts((0, 1))}, spans=[])
    c = one(check_toml('measure="max"\nwindow="enabled"'), src)
    assert c['status'] == NODATA and 'no driver-station mode data' in c['detail']
    assert one(check_toml('measure="max"\nwindow="all"'), src)['value'] == 1.0


def test_no_samples_in_the_window():
    src = engine.LogSource({'X': ts((0, 1)), 'Anchor': ts((0, 0), (100, 0))}, [(0, 100, 'disabled')])
    c = one(check_toml('measure="max"\nwindow="teleop"'), src)
    assert c['status'] == NODATA


# ── live snapshots ────────────────────────────────────────────────────────────────────────────

def snap(**kw):
    return engine.SnapshotSource({k.replace('__', '/'): v for k, v in kw.items()})


def test_live_uses_the_current_value_and_the_same_rules():
    src = engine.SnapshotSource({'SystemStats/CANBus/Utilization': (0.95, 0.1)})
    c = one(check_toml('measure="max"\nscale=100\nunit="%"\nfail_above=90', 'SystemStats/CANBus/Utilization'), src)
    assert (c['status'], c['display']) == (FAIL, '95 %')


def test_live_wildcards_and_lookups_work_the_same():
    src = engine.SnapshotSource({'OrangePi/LeftPi/CPU_Pct': (50.0, 0.2), 'OrangePi/RightPi/CPU_Pct': (96.0, 0.2)})
    toml = ('[[check]]\nid="c"\nsection="S"\ngroup="{1}"\nlabel="CPU"\nsignal="OrangePi/*/CPU_Pct"\n'
            'warn_above=75\nfail_above=92\n')
    groups = {g['label']: g['status'] for g in run(toml, src)['sections'][0]['groups']}
    assert groups == {'LeftPi': OK, 'RightPi': FAIL}


def test_stale_after_fails_a_silent_topic():
    toml = check_toml('stale_after=5', 'OrangePi/LeftPi/CPU_Pct')
    fresh = one(toml, engine.SnapshotSource({'OrangePi/LeftPi/CPU_Pct': (10.0, 1.0)}))
    stale = one(toml, engine.SnapshotSource({'OrangePi/LeftPi/CPU_Pct': (10.0, 12.0)}))
    assert fresh['status'] == OK
    assert stale['status'] == FAIL and 'last updated 12 s ago' in stale['detail']


def test_history_measures_are_log_only_in_a_live_view():
    toml = check_toml('measure="seconds_above"\nabove=5', 'X')
    c = one(toml, engine.SnapshotSource({'X': (9.0, 0.1)}))
    assert c['status'] == NA and 'needs a log' in c['detail']


def test_checks_restricted_to_log_or_live_are_not_applicable_in_the_other():
    assert one(check_toml('mode="live"\nmeasure="last"'), log({'X': ts((0, 1))}))['status'] == NA
    assert one(check_toml('mode="log"\nmeasure="last"'), engine.SnapshotSource({'X': (1.0, 0.1)}))['status'] == NA
    assert one(check_toml('mode="log"\nmeasure="last"'), log({'X': ts((0, 1))}))['status'] == OK


def test_live_booleans_and_fractions_and_lengths():
    src = engine.SnapshotSource({'B': (True, 0.1), 'L': (['a', 'b'], 0.1), 'S': ('idle', 0.1)})
    assert one(check_toml('measure="any_true"\nexpect=false', 'B'), src)['status'] == FAIL
    c = one(check_toml('measure="fraction_true"\nscale=100\nunit="%"\nfail_below=90', 'B'), src)
    assert (c['status'], c['value']) == (OK, 100.0)
    assert one(check_toml('measure="max_len"\nwarn_above=0', 'L'), src)['status'] == WARN
    assert one(check_toml('measure="last"\nexpect_in=["idle"]', 'S'), src)['status'] == OK


# ── latching ──────────────────────────────────────────────────────────────────────────────────

def test_latch_remembers_the_worst_status_and_the_peak_until_reset():
    specs, _ = config.parse(check_toml('measure="max"\nfail_above=90\nunit="V"', 'X'))
    latch = engine.Latch()

    def poll(value):
        report = engine.evaluate(specs, engine.SnapshotSource({'X': (value, 0.1)}), latch=latch)
        return report['sections'][0]['groups'][0]['subjects'][0]['checks'][0]

    assert poll(10)['worst'] == OK
    row = poll(95)
    assert (row['status'], row['worst']) == (FAIL, FAIL)
    row = poll(20)
    assert (row['status'], row['worst'], row['peak'], row['peak_display']) == (OK, FAIL, 95, '95 V')
    latch.reset()
    row = poll(30)
    assert (row['worst'], 'peak' not in row) == (OK, True)


def test_downward_rules_track_the_lowest_value():
    specs, _ = config.parse(check_toml('measure="min"\nwarn_below=12', 'X'))
    latch = engine.Latch()
    for v in (13, 9, 12.5):
        report = engine.evaluate(specs, engine.SnapshotSource({'X': (v, 0.1)}), latch=latch)
    row = report['sections'][0]['groups'][0]['subjects'][0]['checks'][0]
    assert row['peak'] == 9 and row['worst'] == WARN


# ── the report ────────────────────────────────────────────────────────────────────────────────

def test_roll_ups_verdicts_and_counts():
    def report_for(values):
        toml = ''.join(f'[[check]]\nid="c{i}"\nsection="S"\nlabel="L{i}"\nsignal="K{i}"\nmeasure="last"\nwarn_above=1\nfail_above=5\n'
                       for i in range(len(values)))
        signals = {f'K{i}': ts((0, v)) for i, v in enumerate(values) if v is not None}
        return run(toml, log(signals))
    assert report_for([0, 0])['verdict'] == 'ok'
    assert report_for([0, 2])['verdict'] == 'warn'
    assert report_for([0, 2, 9])['verdict'] == 'fail'
    assert report_for([0, None])['verdict'] == 'incomplete'
    r = report_for([0, 2, 9, None])
    assert r['counts'] == {'ok': 1, 'warn': 1, 'fail': 1, 'nodata': 1, 'na': 0}
    assert r['sections'][0]['status'] == FAIL
    assert engine.evaluate([], log({}))['verdict'] == 'empty'


def test_sections_and_groups_keep_the_configuration_order():
    toml = ''.join(f'[[check]]\nid="c{i}"\nsection="{s}"\ngroup="{g}"\nlabel="L"\nsignal="K{i}"\n'
                   for i, (s, g) in enumerate([('B', 'x'), ('A', 'y'), ('B', 'w'), ('A', 'y')]))
    report = run(toml, log({f'K{i}': ts((0, 1)) for i in range(4)}))
    assert [s['label'] for s in report['sections']] == ['B', 'A']
    assert [g['label'] for g in report['sections'][0]['groups']] == ['x', 'w']


def test_display_formatting():
    d = engine.display
    assert d(3.0, '', None) == '3' and d(3.14159, 'V', None) == '3.14 V' and d(31.4159, '', None) == '31.4'
    assert d(314.159, 'A', None) == '314 A' and d(0.5, '%', 0) == '0 %' and d(True, '', None) == 'yes'
    assert d('idle', '', None) == 'idle' and d(None, '', None) == ''
    assert math.isnan(float('nan'))     # (NaN never reaches display: it reads as no data)


def test_the_shipped_checks_run_on_a_synthetic_match_log(tmp_path):
    """The shipped health_checks.toml must evaluate on a plain testkit log without raising."""
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    from testkit import build_bundle
    from vision_analyzer.parser import parse_wpilog
    from core.log import Log
    bundle = build_bundle.build_bundle(tmp_path, 'no-recording', cycle_ms=250)
    log_ = Log.load(str(bundle.log_path))
    specs, errors = config.load(pathlib.Path(__file__).resolve().parents[1] / 'server' / 'health_checks.toml')
    assert errors == []
    report = engine.evaluate(specs, engine.LogSource(log_.signals, log_.mode_spans()))
    assert report['verdict'] in ('incomplete', 'warn', 'fail', 'ok')
    assert {s['label'] for s in report['sections']} == {'Vision', 'Orange Pis', 'roboRIO', 'Robot'}
