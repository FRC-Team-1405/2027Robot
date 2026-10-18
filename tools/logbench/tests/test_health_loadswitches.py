"""The CAN-load / loop-time checks used to A/B the FeatureSwitches (see docs/can-bus-load-ab-test.md).

Idle (disabled) CAN utilization is the baseline the status-signal switches move; the mean loop time and
the LOG_SUBSYSTEM_TIMINGS breakdown say where the loop goes. Synthetic logs, real health_checks.toml.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401

from health import config, engine

SHIPPED = pathlib.Path(__file__).resolve().parents[1] / 'server' / 'health_checks.toml'
SPECS, ERRORS = config.load(SHIPPED)

T0 = 10.0
SPANS = [(0, 20, 'disabled'), (20, 30, 'auto'), (30, 40, 'disabled'), (40, 90, 'teleop'), (90, 100, 'disabled')]


def ts(*pairs):
    return [(T0 + t, v) for t, v in pairs]


def rows(signals):
    report = engine.evaluate(SPECS, engine.LogSource(signals, SPANS))
    out = {}
    for sec in report['sections']:
        for g in sec['groups']:
            for sub in g['subjects']:
                for c in sub['checks']:
                    out.setdefault(c['id'], []).append(c)
    return out


def bus(idle, enabled):
    # utilization is 0-1 in the log; idle while disabled, `enabled` from 20 s to 90 s
    return {'Anchor': ts((0, 0), (100, 0)),
            'SystemStats/CANBus/Utilization': ts((0, idle), (20, enabled), (30, idle), (40, enabled), (90, idle))}


def test_the_shipped_config_has_no_errors_for_these_checks():
    assert not ERRORS
    ids = {s.id for s in SPECS}
    assert {'rio.can_util_idle', 'rio.can_util_enabled', 'rio.loop_mean', 'rio.loop_usercode_mean',
            'rio.timing_breakdown'} <= ids


def test_a_busy_idle_bus_is_flagged_and_a_quiet_one_is_not():
    busy = rows(bus(0.65, 0.77))
    assert busy['rio.can_util_idle'][0]['status'] == 'warn'
    assert round(busy['rio.can_util_idle'][0]['value']) == 65
    quiet = rows(bus(0.25, 0.45))
    assert quiet['rio.can_util_idle'][0]['status'] == 'ok'
    assert quiet['rio.can_util_enabled'][0]['status'] == 'ok'


def test_idle_baseline_ignores_the_enabled_part_of_the_match():
    r = rows(bus(0.25, 0.95))
    assert r['rio.can_util_idle'][0]['status'] == 'ok'
    assert r['rio.can_util_enabled'][0]['status'] == 'fail'


def test_mean_loop_time_is_measured_over_enabled_time_only():
    sig = {'Anchor': ts((0, 0), (100, 0)),
           'RealOutputs/LoggedRobot/FullCycleMS': ts((0, 90.0), (20, 38.0), (30, 90.0), (40, 38.0), (90, 90.0)),
           'RealOutputs/LoggedRobot/UserCodeMS': ts((0, 5.0), (20, 35.0), (30, 5.0), (40, 35.0), (90, 5.0))}
    r = rows(sig)
    assert abs(r['rio.loop_mean'][0]['value'] - 38.0) < 0.5
    assert r['rio.loop_mean'][0]['status'] == 'warn'
    assert r['rio.loop_usercode_mean'][0]['status'] == 'warn'


def test_timing_breakdown_gives_one_row_per_logged_section():
    sig = {'Anchor': ts((0, 0), (100, 0)),
           'RealOutputs/Timing/ShooterMs': ts((0, 3.0)),
           'RealOutputs/Timing/VisionMs': ts((0, 16.0))}
    labels = sorted(c['label'] for c in rows(sig)['rio.timing_breakdown'])
    assert any('ShooterMs' in l for l in labels) and any('VisionMs' in l for l in labels)
