"""An actual WPILog roundtrip, also usable as a clearly labeled browser fixture."""
import pathlib
import sys
import json

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'wpilog-utils' / 'tests'))
import paths  # noqa: F401
from wpilog_builder import LogBuilder, double, boolean
from core.log import Log
import battery


def write_fixture(path):
    b = LogBuilder()
    signals = {
        '/SystemStats/BatteryVoltage': [(0, 12.5), (4, 7.0), (6, 11.5)],
        '/SystemStats/BrownedOut': [(0, False), (5, True), (6, False)],
        '/SystemStats/BrownoutVoltage': [(0, 6.75)],
        '/PowerDistribution/Voltage': [(0, 12.5), (4, 7.0), (6, 11.5)],
        '/PowerDistribution/TotalCurrent': [(0, 15.0), (2, 80.0), (4, 180.0), (6, 70.0)],
        '/DriverStation/Enabled': [(0, False), (1, True), (11, False)],
        '/DriverStation/Autonomous': [(0, False)],
        '/Power/Distribution/BatteryId': [(0, 'SYNTHETIC — not a real battery')],
        '/Power/Distribution/Valid': [(0, True)],
        '/RealOutputs/Power/State/Active': [(0, 'Unassigned'), (3, 'Scoring'), (10, 'Unassigned')],
        '/RealOutputs/Power/State/Definitions/Scoring/Shooter': [(0, 0.0)],
        '/RealOutputs/Power/State/Definitions/Scoring/Drivetrain': [(0, 1.0)],
        '/RealOutputs/Power/Allocation/Drivetrain/Mode': [(0, 'off'), (3, 'shadow'), (6, 'enforced')],
        '/RealOutputs/Power/Allocation/Drivetrain/ProposedLimitAmps': [(0, 45.0), (3, 25.0)],
        '/RealOutputs/Power/Allocation/Drivetrain/AppliedLimitAmps': [(0, 45.0), (6, 25.0)],
        '/RealOutputs/Power/Allocation/Drivetrain/ApplicationStatus': [(0, 'Baseline'), (3, 'Not applied: shadow'), (6, 'OK')],
        '/RealOutputs/Power/Allocation/Drivetrain/PolicyVersion': [(0, 'SYNTHETIC-v1')],
        '/End': [(12, 0.0)],
    }
    for name, subsystem, identity in [('Drive 0', 'Drivetrain', 'rio-1'), ('Shooter Motor1', 'Shooter', 'rio-41')]:
        prefix = '/Power/Motors/' + identity + '/'
        fields = {'Name': [(0, name)], 'Subsystem': [(0, subsystem)],
                  'SupplyCurrentAmps': [(0, 0.0), (2, 20.0), (4, 45.0), (6, 25.0)],
                  'StatorCurrentAmps': [(0, 0.0), (2, 50.0)],
                  'Valid': [(0, True), (8, False), (9, True)],
                  'SupplyLimited': [(0, False), (4, True), (7, False)],
                  'StatorLimited': [(0, False)], 'SupplyLimitEnabled': [(0, True)],
                  'SupplyLimitAmps': [(0, 45.0), (6, 25.0)], 'ConfigValid': [(0, True)],
                  'ConfigStatus': [(0, 'OK')], 'RequestedSetpoint': [(0, 0.0), (2, 70.0)],
                  'RequestUnits': [(0, 'rotations/s')], 'ControlMode': [(0, 'VelocityVoltage')],
                  'VelocityRPS': [(0, 0.0), (2, 60.0), (6, 68.0)],
                  'ClosedLoopError': [(0, 0.0), (2, 10.0), (6, 2.0)]}
        signals.update({prefix+k: v for k, v in fields.items()})
    records = []
    for key, samples in signals.items():
        value = samples[0][1]
        typ = 'boolean' if isinstance(value, bool) else 'string' if isinstance(value, str) else 'double'
        eid = b.entry(key, typ)
        for t, v in samples:
            payload = boolean(v) if typ == 'boolean' else v.encode() if typ == 'string' else double(v)
            records.append((int(t*1e6), eid, payload))
    for t, eid, payload in sorted(records):
        b.data(eid, t, payload)
    pathlib.Path(path).write_bytes(b.build())


def test_new_telemetry_survives_real_wpilog_parser(tmp_path):
    file = tmp_path / 'SYNTHETIC-power.wpilog'
    write_fixture(file)
    r = battery.analyze(Log.load(file))
    assert len(r['motors']) == 2
    assert r['motors'][0]['limiting_seconds']['SupplyLimited'] == 3
    assert r['summary']['brownout_count'] == 1
    assert r['summary']['brownout_seconds'] == 1
    assert r['summary']['low_voltage_seconds'] == 2
    assert 'Power/State/Active' in r['spec']['data']
    assert any(p['id'] == 'allocation-Drivetrain' for p in r['spec']['panels'])
    assert any('Configuration SupplyLimitAmps' in e['kind'] for e in r['events'])
    json.dumps(r, allow_nan=False)
