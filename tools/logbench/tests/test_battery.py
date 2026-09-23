import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import paths  # noqa: F401
import battery
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
    html = battery.render_html(r)
    assert '<script>alert(1)' not in html
    assert '&lt;script&gt;' in html


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
    r = battery.analyze(make_log({'SystemStats/BrownedOut': [(5, False)]}), (0, 2))
    assert r['summary']['brownout_count'] is None
    assert r['summary']['brownout_coverage'] == 0


def test_channels_are_not_added_to_whole_robot_draw():
    r = battery.analyze(make_log({'PowerDistribution/ChannelCurrent': [(0, [10.0, 10.0])]}))
    assert r['summary']['average'] == 20
    assert len(r['channels']) == 2
    assert r['channels'][0]['stats']['average'] == 10


def test_failed_configuration_masks_enable_flags_as_unknown():
    r = battery.analyze(make_log(motor({'Power/Motors/rio-29/ConfigValid': [(0, False)],
                                        'Power/Motors/rio-29/SupplyLimitEnabled': [(0, False)]})))
    assert r['motors'][0]['configuration']['SupplyLimitEnabled'] is None
