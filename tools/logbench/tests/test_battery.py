import json
import math
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import paths  # noqa: F401
import battery
import battery_export
from core.log import Log


def make_log(extra=None, end=10):
    signals = {
        'SystemStats/BatteryVoltage': [(0, 12.0)],
        'SystemStats/BrownoutVoltage': [(0, 6.75)],
        'SystemStats/BrownedOut': [(0, False)],
        'PowerDistribution/Voltage': [(0, 12.0)],
        'PowerDistribution/TotalCurrent': [(0, 20.0)],
        'End': [(end, 0)],
    }
    signals.update(extra or {})
    return Log(pathlib.Path('test.wpilog'), signals)


def motor(extra=None):
    fields = {'Name': 'Pickup', 'Subsystem': 'Pickup', 'SupplyCurrentAmps': 5.0,
              'StatorCurrentAmps': 50.0, 'Valid': True, 'SupplyLimited': False,
              'StatorLimited': False, 'SupplyLimitAmps': 20.0}
    signals = {'Power/Motors/rio-29/' + k: [(0, v)] for k, v in fields.items()}
    signals.update(extra or {})
    return signals


def test_integrals_are_time_weighted_and_change_only_values_persist():
    r = battery.analyze(make_log({'PowerDistribution/TotalCurrent': [(0, 10.0), (9, 100.0)]}))
    assert r['summary']['average'] == pytest.approx(19)
    assert r['summary']['ah'] == pytest.approx(190 / 3600)
    assert r['summary']['wh'] == pytest.approx(190 * 12 / 3600)
    assert r['summary']['coverage'] == 1


def test_suspect_pdh_is_not_brownout_or_zero_consumption():
    r = battery.analyze(make_log({'PowerDistribution/Voltage': [(0, 12.0), (2, 0.0), (4, 12.0)]}))
    assert r['summary']['coverage'] == .8
    assert r['summary']['ah'] == pytest.approx(20 * 8 / 3600)
    assert r['summary']['brownout_count'] == 0
    assert any(e['kind'] == 'Suspect PDH telemetry' for e in r['events'])


def test_threshold_dip_and_reported_brownout_are_separate():
    r = battery.analyze(make_log({'SystemStats/BatteryVoltage': [(0, 12.0), (2, 7.0), (5, 12.0)],
                                 'SystemStats/BrownedOut': [(0, False), (3, True), (4, False)]}))
    assert r['summary']['low_voltage_seconds'] == 3
    assert r['summary']['brownout_seconds'] == 1


def test_deduplicates_physical_alias_and_new_schema_over_legacy():
    s = motor({'Pickup/SupplyCurrentAmps': [(0, 5.0)], 'Intake/PickupSupplyCurrentAmps': [(0, 6.0)]})
    r = battery.analyze(make_log(s))
    assert len(r['motors']) == 1
    assert r['motors'][0]['stats']['average'] == 5
    assert any('aliases disagree' in w for w in r['warnings'])


def test_stator_is_not_added_to_supply_and_followers_count_individually():
    s = motor()
    for i in (41, 42, 43):
        s.update({f'Power/Motors/rio-{i}/Name': [(0, f'Shooter Motor{i-40}')],
                  f'Power/Motors/rio-{i}/Subsystem': [(0, 'Shooter')],
                  f'Power/Motors/rio-{i}/SupplyCurrentAmps': [(0, 2.0)]})
    r = battery.analyze(make_log(s))
    assert r['spec']['data']['motor_sum']['v'][0] == 11
    assert r['summary']['average'] == 20


def test_flags_below_limit_are_reported_and_configured_limit_is_not_event():
    r = battery.analyze(make_log(motor({'Power/Motors/rio-29/SupplyLimited': [(0, False), (2, True), (3, False)]})))
    assert r['motors'][0]['limiting_seconds']['SupplyLimited'] == 1
    assert r['motors'][0]['limiting_seconds']['StatorLimited'] == 0
    assert r['motors'][0]['stats']['peak'] < 20


def test_missing_and_sticky_flags_are_not_active_limiting():
    r = battery.analyze(make_log({'Pickup/SupplyCurrentAmps': [(0, 5.0)],
                                  'Pickup/StickySupplyLimited': [(0, True)]}))
    assert r['motors'][0]['limiting_seconds']['SupplyLimited'] is None


def test_disconnect_creates_unknown_gap_and_excludes_limiting_duration():
    r = battery.analyze(make_log(motor({'Power/Motors/rio-29/Valid': [(0, True), (2, False), (5, True)],
                                        'Power/Motors/rio-29/SupplyLimited': [(0, True)]})))
    assert r['motors'][0]['stats']['coverage'] == .7
    assert r['motors'][0]['limiting_seconds']['SupplyLimited'] == 7
    assert None in r['spec']['data']['motor/rio-29/SupplyLimited']['v']


def test_trim_seams_do_not_integrate_removed_time():
    segmap = json.dumps({'segments': [{'new_first': 0, 'new_last': 2}, {'new_first': 7, 'new_last': 10}]})
    r = battery.analyze(make_log({'/Janitor/SegmentMap': [(0, segmap)]}))
    assert r['summary']['valid_seconds'] == 5
    assert r['summary']['ah'] == pytest.approx(100 / 3600)
    assert r['intervals'] == [[0, 2], [7, 10]]


def test_compacted_seam_splits_events():
    segmap = json.dumps({'segments': [{'new_first': 0, 'new_last': 2}, {'new_first': 2, 'new_last': 5}]})
    r = battery.analyze(make_log({'/Janitor/SegmentMap': [(0, segmap)], 'SystemStats/BrownedOut': [(0, True)]}))
    assert r['summary']['brownout_count'] == 2


def test_missing_voltage_cannot_generate_energy_or_low_voltage():
    log = make_log()
    del log.signals['SystemStats/BatteryVoltage']
    del log.signals['PowerDistribution/Voltage']
    r = battery.analyze(log)
    assert r['summary']['wh'] is None
    assert r['summary']['min_voltage'] is None
    assert r['summary']['low_voltage_seconds'] is None


def test_state_and_shadow_events_preserve_proposals_separately():
    r = battery.analyze(make_log({'RealOutputs/Power/State/Active': [(0, 'Unassigned'), (3, 'Scoring')],
                                  'RealOutputs/Power/Allocation/Drivetrain/Mode': [(0, 'shadow')],
                                  'RealOutputs/Power/Allocation/Drivetrain/ProposedLimitAmps': [(0, 25.0)],
                                  'RealOutputs/Power/Allocation/Drivetrain/AppliedLimitAmps': [(0, 45.0)]}))
    assert any('Scoring' in e['kind'] for e in r['events'])
    assert r['spec']['data']['Power/Allocation/Drivetrain/AppliedLimitAmps']['v'] == [45, None]


@pytest.mark.parametrize('window', [(5, 2), (-1, 3), (0, 11), (0, float('nan'))])
def test_invalid_windows_are_rejected(window):
    with pytest.raises(ValueError):
        battery.analyze(make_log(), window)


def test_export_is_strict_json_and_html_escaped():
    r = battery.analyze(make_log(motor({'Power/Motors/rio-29/SupplyLimitAmps': [(0, float('nan'))]})))
    r['log'] = '<script>alert(1)</script>'
    json.dumps(r, allow_nan=False)
    json.dumps(battery_export.export_json(r), allow_nan=False)
    html = battery_export.render_html(r)
    assert '<script>alert(1)' not in html
    assert '&lt;script&gt;' in html


def test_exports_carry_insights_not_the_timeline():
    r = battery.analyze(competition_log())
    ex = battery_export.export_json(r)
    assert 'spec' not in ex and ex['schema'] == 'logbench.battery-insights/v2'
    assert ex['summary']['brownouts']['count'] == 1 and len(ex['episodes']) == 2 and ex['findings']
    assert len(battery_export.dumps(ex)) < 20_000
    html = battery_export.render_html(r)
    assert 'Brownout' in html and '<svg' in html and 'Shooter/Motor1TorqueCurrent' in html
    assert '"dt"' not in html                                  # no timeline data dumped into the page


def test_sessions_are_not_merged_across_disabled_periods():
    r = battery.analyze(make_log({'DriverStation/Enabled': [(0, False), (1, True), (3, False), (6, True)],
                                  'DriverStation/Autonomous': [(0, False)]}))
    sessions = [w for w in r['windows'] if w['label'] == 'Enabled session']
    assert [(w['lo'], w['hi']) for w in sessions] == [(1, 3), (6, 10)]


def test_loop_heartbeat_gap_is_not_held_as_live_data():
    r = battery.analyze(make_log({'Power/HeartbeatSeconds': [(0, 0.0), (.02, .02), (9, 9.0), (9.02, 9.02)]}))
    assert r['summary']['valid_seconds'] == pytest.approx(1.02)


def test_configuration_change_is_event_but_failed_readback_is_unknown():
    r = battery.analyze(make_log(motor({'Power/Motors/rio-29/SupplyLimitAmps': [(0, 45.0), (5, 30.0)],
                                        'Power/Motors/rio-29/ConfigStatus': [(0, 'OK'), (7, 'Timeout')]})))
    assert any('Configuration SupplyLimitAmps: 30' in e['kind'] for e in r['events'])


def test_parser_normalized_trim_key_still_prevents_gap_integration():
    segmap = json.dumps({'segments': [{'new_first': 0, 'new_last': 2}, {'new_first': 7, 'new_last': 10}]})
    r = battery.analyze(make_log({'Janitor/SegmentMap': [(0, segmap)]}))
    assert r['summary']['valid_seconds'] == 5


def test_brownout_flag_outside_selection_is_unknown_not_zero():
    log = make_log({'SystemStats/BrownedOut': [(5, False)]})
    del log.signals['SystemStats/BatteryVoltage']           # no voltage either: nothing says whether it browned out
    r = battery.analyze(log, (0, 2))
    assert r['summary']['brownout_count'] is None
    assert r['summary']['brownout_coverage'] == 0


def test_voltage_below_the_threshold_is_a_brownout_without_the_flag():
    r = battery.analyze(make_log({'SystemStats/BatteryVoltage': [(0, 12.0), (2, 6.5), (2.5, 12.0), (6, 6.6), (6.2, 12.0)],
                                  'SystemStats/BrownedOut': [(0, False)]}))
    assert r['summary']['brownout_count'] == 2
    assert r['summary']['brownout_seconds'] == pytest.approx(0.7)
    assert r['summary']['low_voltage_count'] == 2


def test_channels_are_not_added_to_whole_robot_draw():
    r = battery.analyze(make_log({'PowerDistribution/ChannelCurrent': [(0, [10.0, 10.0])]}))
    assert r['summary']['average'] == 20
    assert len(r['channels']) == 2
    assert r['channels'][0]['stats']['average'] == 10


def test_failed_configuration_masks_enable_flags_as_unknown():
    r = battery.analyze(make_log(motor({'Power/Motors/rio-29/ConfigValid': [(0, False)],
                                        'Power/Motors/rio-29/SupplyLimitEnabled': [(0, False)]})))
    assert r['motors'][0]['configuration']['SupplyLimitEnabled'] is None


def test_match_window_spans_auto_through_teleop():
    r = battery.analyze(make_log({'DriverStation/Enabled': [(0, False), (1, True), (3, False), (4, True), (8, False)],
                                  'DriverStation/Autonomous': [(0, True), (3.5, False)]}))
    assert [(w['lo'], w['hi']) for w in r['windows'] if w['label'].startswith('Match')] == [(1, 8)]


def test_plain_wpilib_competition_log_battery_signals():
    """FRC_*.wpilog from DataLogManager: no SystemStats/, no DriverStation/ -- mode from the FMS control
    word, voltage and threshold from SmartDashboard, Pickup supply current under its SmartDashboard name."""
    r = battery.analyze(Log(pathlib.Path('FRC_20260416_174046_NYTR_P9.wpilog'), {
        'End': [(10, 0)],
        'NT:/FMSInfo/FMSControlData': [(0, 0x30), (1, 0x33), (3, 0x32), (4, 0x31), (8, 0x30)],
        'NT:/SmartDashboard/Battery/BatteryVoltage': [(0, 12.5), (5, 6.5), (5.5, 11.0)],
        'NT:/SmartDashboard/Battery/BrownoutVoltage': [(0, 6.75)],
        'NT:/SmartDashboard/Intake/PickupSupplyCurrent': [(0, 2.0)],
    }))
    assert r['mode_spans'][1][2] == 'auto' and r['mode_spans'][3][2] == 'teleop'
    assert r['summary']['min_voltage'] == 6.5
    assert r['provenance']['voltage'] == 'NT:/SmartDashboard/Battery/BatteryVoltage'
    assert r['summary']['brownout_count'] == 1                # 6.5 V is below the 6.75 V threshold: a brownout
    assert 'Pickup' in [m['name'] for m in r['motors']]


def competition_log():
    """A plain WPILib match log: mode from the FMS control word, SmartDashboard telemetry, game periods."""
    return Log(pathlib.Path('FRC_20260416_174046_NYTR_P9.wpilog'), {
        'End': [(30, 0)],
        'NT:/FMSInfo/FMSControlData': [(0, 0x30), (2, 0x33), (6, 0x32), (8, 0x31), (26, 0x30)],
        'NT:/FMSInfo/EventName': [(0, 'NYTR')], 'NT:/FMSInfo/MatchNumber': [(0, 9)], 'NT:/FMSInfo/MatchType': [(0, 1)],
        'NT:/FMSInfo/IsRedAlliance': [(0, False)], 'NT:/FMSInfo/StationNumber': [(0, 3)],
        'NT:/GamePeriod/Period': [(8, 'Shift 1'), (20, 'End Game')],
        'NT:/SmartDashboard/Battery/BatteryVoltage': [(0, 12.6), (12, 7.5), (12.3, 11.5), (12.8, 7.8), (13.0, 11.5),
                                                      (22, 6.6), (22.4, 11.0), (28, 12.3)],
        'NT:/SmartDashboard/Battery/BrownoutVoltage': [(0, 6.75)],
        'NT:/SmartDashboard/Shooter/Motor1TorqueCurrent': [(0, 0.0), (11.8, 60.0), (13.5, 5.0)],
        'NT:/SmartDashboard/SwerveDrive/DriveMotor_SupplyCurrent_0': [(0, 0.0), (21.9, 45.0), (22.6, 2.0)],
        'NT:/SmartDashboard/Shooter/CumulativeStatorCurrent': [(0, 0.0), (12, 200.0)],      # a sum, not a load
    })


def test_insights_episodes_attribute_dips_to_the_loads_drawing_at_the_time():
    ins = battery.analyze(competition_log())['insights']
    assert ins['context']['event'] == 'NYTR' and ins['context']['match'] == 'Practice 9' and ins['context']['alliance'] == 'Blue 3'
    assert ins['context']['log_kind'] == 'WPILib DataLogManager'
    eps = ins['episodes']
    assert len(eps) == 2                                        # 12.0 and 12.8 are within 1 s: one episode
    assert eps[0]['period'] == 'Shift 1' and not eps[0]['brownout'] and eps[0]['min_voltage'] == 7.5
    assert eps[0]['contributors'][0]['name'] == 'Shooter/Motor1TorqueCurrent' and eps[0]['contributors'][0]['kind'] == 'torque'
    assert eps[1]['period'] == 'End Game' and eps[1]['brownout'] and eps[1]['min_voltage'] == 6.6
    assert eps[1]['contributors'][0]['name'] == 'SwerveDrive/DriveMotor_SupplyCurrent_0'
    assert 'voltage' in eps[1]['evidence'] and 'SwerveDrive/DriveMotor_SupplyCurrent_0' in eps[1]['evidence']
    assert ins['brownouts']['count'] == 1 and ins['low_voltage']['count'] == 2
    assert ins['voltage']['resting_before'] == 12.6
    assert all('Cumulative' not in l['name'] for l in ins['loads'])
    assert any('1 brownout' in f for f in ins['findings'])
    assert any('Shooter torque current' in f for f in ins['findings'])


def test_page_timeline_keeps_only_changes():
    r = battery.analyze(competition_log())
    for key, series in r['spec']['data'].items():
        assert series['n'] < 60, key                          # not one value per power-signal change


def recovering_log():
    """Disabled 20 s at 12.6 V, a 20 s match at 10 V, then 200 s of recovery with a 30 s time constant."""
    import math
    volts = [(t / 2, 12.6) for t in range(0, 40)] + [(20 + t / 2, 10.0) for t in range(0, 40)]
    volts += [(40 + t / 2, 12.4 - 0.5 * math.exp(-(t / 2) / 30)) for t in range(0, 400)]
    return Log(pathlib.Path('FRC_rec.wpilog'), {
        'End': [(240, 0)],
        'NT:/FMSInfo/FMSControlData': [(0, 0x30), (20, 0x31), (40, 0x30)],
        'NT:/SmartDashboard/Battery/BatteryVoltage': volts,
    })


def test_recovery_after_the_match_is_measured_at_checkpoints_and_fitted():
    v = battery.analyze(recovering_log())['insights']['voltage']
    rec = v['recovery']
    assert v['resting_before'] == 12.6
    assert [p['after_s'] for p in rec['points']] == [10, 30, 60, 120]
    assert rec['drop_measured_after_s'] == 120 and rec['drop_v'] == pytest.approx(12.6 - (12.4 - 0.5 * math.exp(-4)), abs=0.02)
    assert rec['tau_s'] == pytest.approx(30, rel=0.1) and rec['projected_rest_v'] == pytest.approx(12.4, abs=0.02)
    findings = battery.analyze(recovering_log())['insights']['findings']
    assert any('drop, measured 2 min after' in f for f in findings)
    assert any('time constant of about 30 s' in f or 'time constant of about 29 s' in f or 'time constant of about 31 s' in f
               for f in findings)


def test_a_short_wait_after_the_match_says_the_drop_is_overstated():
    log = recovering_log()
    log.signals['NT:/SmartDashboard/Battery/BatteryVoltage'] = [p for p in log.signals['NT:/SmartDashboard/Battery/BatteryVoltage'] if p[0] < 55]
    log.signals['End'] = [(55, 0)]
    ins = battery.analyze(log)['insights']
    assert ins['voltage']['recovery']['drop_measured_after_s'] == 10 and ins['voltage']['recovery']['tau_s'] is None
    assert any('still recovering' in f for f in ins['findings'])
