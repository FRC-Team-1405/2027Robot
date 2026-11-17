"""The shipped Pi diagnostics checks (reboot vs link flap vs camera loss) over synthetic match logs.

The Pi publishes BootId, NetCarrierChanges, UsbCameras and the recorder's NtDisconnects/NtDownSec;
the robot mirrors them into the log under RealOutputs/OrangePi/. These tests build such logs and run
the real health_checks.toml over them, so a change to the config or the engine that stopped a
scenario from being told apart shows up here.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401

from health import config, engine

SHIPPED = pathlib.Path(__file__).resolve().parents[1] / 'server' / 'health_checks.toml'
SPECS, ERRORS = config.load(SHIPPED)

T0 = 10.0
# 100 s log from t=10: disabled 0-20, auto 20-30, disabled 30-40, teleop 40-90, disabled 90-100
SPANS = [(0, 20, 'disabled'), (20, 30, 'auto'), (30, 40, 'disabled'), (40, 90, 'teleop'), (90, 100, 'disabled')]
BOARD = 'RealOutputs/OrangePi/RightPi'
REC = f'{BOARD}/Recorders/LeftCam'


def ts(*pairs):
    return [(T0 + t, v) for t, v in pairs]


def healthy():
    return {
        'Anchor': ts((0, 0), (100, 0)),
        f'{BOARD}/BootId': ts((0, 'boot-A')),
        f'{BOARD}/SystemUptimeSec': ts((0, 500.0), (99, 599.0)),
        f'{BOARD}/NetCarrierChanges': ts((0, 2)),
        f'{BOARD}/UsbCameras': ts((0, 2)),
        f'{REC}/NtDisconnects': ts((0, 0)),
        f'{REC}/NtDownSec': ts((0, 0.0)),
        f'{REC}/NtLongestOutageSec': ts((0, 0.0)),
        f'{REC}/CameraLostCount': ts((0, 0)),
    }


def rows(signals):
    source = engine.LogSource(signals, SPANS)
    report = engine.evaluate(SPECS, source)
    out = {}
    for sec in report['sections']:
        for g in sec['groups']:
            for sub in g['subjects']:
                for c in sub['checks']:
                    out[c['id']] = c
    return out


DIAGNOSTIC_IDS = ('pi.rebooted', 'pi.link_flaps', 'pi.usb_camera_loss', 'rec.nt_disconnects_match',
                  'rec.nt_down_match', 'rec.nt_longest', 'rec.camera_lost_match')


def test_the_shipped_config_is_valid_and_has_the_diagnostic_checks():
    assert ERRORS == []
    ids = {s.id for s in SPECS}
    assert set(DIAGNOSTIC_IDS) <= ids


def test_a_healthy_match_is_clean():
    r = rows(healthy())
    for ident in DIAGNOSTIC_IDS:
        assert r[ident]['status'] == 'ok', (ident, r[ident])
    assert r['pi.rebooted']['display'] == '0'


def test_a_reboot_is_told_apart_by_the_boot_id():
    s = healthy()
    s[f'{BOARD}/BootId'] = ts((0, 'boot-A'), (62, 'boot-B'))
    s[f'{BOARD}/SystemUptimeSec'] = ts((0, 500.0), (60, 560.0), (62, 3.0), (99, 40.0))
    r = rows(s)
    assert r['pi.rebooted']['status'] == 'fail' and r['pi.rebooted']['display'] == '1'
    # ...and nothing says the link or a camera was the cause
    assert r['pi.link_flaps']['status'] == 'ok' and r['pi.usb_camera_loss']['status'] == 'ok'


def test_a_link_flap_with_no_reboot_is_told_apart_by_the_carrier_count():
    s = healthy()
    s[f'{BOARD}/NetCarrierChanges'] = ts((0, 2), (45, 4), (60, 6))          # four link changes during teleop
    s[f'{REC}/NtDisconnects'] = ts((0, 0), (46, 3), (61, 5))
    s[f'{REC}/NtDownSec'] = ts((0, 0.0), (46, 8.0), (61, 19.0))
    s[f'{REC}/NtLongestOutageSec'] = ts((0, 0.0), (46, 7.0), (61, 11.0))
    r = rows(s)
    assert r['pi.rebooted']['status'] == 'ok'                                 # BootId never changed
    assert (r['pi.link_flaps']['status'], r['pi.link_flaps']['display']) == ('warn', '4')
    assert (r['rec.nt_disconnects_match']['status'], r['rec.nt_disconnects_match']['display']) == ('warn', '5')
    assert (r['rec.nt_down_match']['status'], r['rec.nt_down_match']['display']) == ('warn', '19 s')
    assert (r['rec.nt_longest']['status'], r['rec.nt_longest']['display']) == ('warn', '11 s')


def test_many_flaps_and_long_outages_are_problems():
    s = healthy()
    s[f'{BOARD}/NetCarrierChanges'] = ts((0, 2), (50, 9))
    s[f'{REC}/NtDisconnects'] = ts((0, 0), (50, 12))
    s[f'{REC}/NtDownSec'] = ts((0, 0.0), (50, 41.0))
    s[f'{REC}/NtLongestOutageSec'] = ts((0, 0.0), (50, 22.0), (70, 33.0))
    r = rows(s)
    assert r['pi.link_flaps']['status'] == 'fail'
    assert r['rec.nt_disconnects_match']['status'] == 'fail'
    assert r['rec.nt_down_match']['status'] == 'fail'
    assert r['rec.nt_longest']['status'] == 'fail'


def test_flaps_before_the_match_are_not_blamed_on_it():
    s = healthy()
    s[f'{BOARD}/NetCarrierChanges'] = ts((0, 2), (5, 8), (12, 12))          # all while disabled
    s[f'{REC}/NtDisconnects'] = ts((0, 0), (6, 9))
    r = rows(s)
    assert r['pi.link_flaps']['status'] == 'ok' and r['pi.link_flaps']['display'] == '0'
    assert r['rec.nt_disconnects_match']['status'] == 'ok'


def test_a_camera_falling_off_usb_is_told_apart_from_a_link_flap_or_reboot():
    s = healthy()
    s[f'{BOARD}/UsbCameras'] = ts((0, 2), (55, 1))
    r = rows(s)
    assert r['pi.usb_camera_loss']['status'] == 'warn'
    assert r['pi.rebooted']['status'] == 'ok' and r['pi.link_flaps']['status'] == 'ok'
    assert r['rec.nt_disconnects_match']['status'] == 'ok'


def test_photonvisions_camera_lost_card_fails_the_match_even_though_the_stream_looks_fine():
    # The 2026-10-24 practice log: LeftCam's USB camera dropped mid-teleop and never came back, while
    # PhotonVision kept streaming its 'Camera Lost' card (so StreamOk stayed true).
    s = healthy()
    s[f'{REC}/StreamOk'] = ts((0, True))
    s[f'{REC}/CameraLostCount'] = ts((0, 0), (55, 1))
    r = rows(s)
    assert (r['rec.camera_lost_match']['status'], r['rec.camera_lost_match']['display']) == ('fail', '1')
    assert r['pi.rebooted']['status'] == 'ok' and r['rec.nt_disconnects_match']['status'] == 'ok'


def test_a_camera_lost_in_the_pits_is_not_blamed_on_the_match():
    s = healthy()
    s[f'{REC}/CameraLostCount'] = ts((0, 0), (5, 1))                          # while disabled
    r = rows(s)
    assert r['rec.camera_lost_match']['status'] == 'ok'


def test_throttling_and_a_saturated_core_show_while_the_average_looks_fine():
    s = healthy()
    s[f'{BOARD}/CPU_Pct'] = ts((0, 20.0))                                     # the 8-core average
    s[f'{BOARD}/CpuCoreMaxPct'] = ts((0, 10.0), (20, 99.0), (90, 10.0))      # one core pegged while enabled
    s[f'{BOARD}/CpuThrottled'] = ts((0, False), (60, True), (75, False))     # capped for 15 of 70 s
    s[f'{BOARD}/TempMaxC'] = ts((0, 55.0), (60, 86.5))
    r = rows(s)
    assert r['pi.cpu']['status'] == 'ok'
    assert r['pi.core_max']['status'] == 'fail'
    assert r['pi.throttled']['status'] == 'fail'
    assert r['pi.temp_max']['status'] == 'fail'


def test_throttling_while_disabled_is_not_blamed_on_the_match():
    s = healthy()
    s[f'{BOARD}/CpuThrottled'] = ts((0, True), (15, False))
    s[f'{BOARD}/CpuCoreMaxPct'] = ts((0, 30.0))
    r = rows(s)
    assert r['pi.throttled']['status'] == 'ok'
    assert r['pi.core_max']['status'] == 'ok'


def test_a_log_recorded_before_the_mirror_existed_says_no_data_not_fine():
    r = rows({'Anchor': ts((0, 0), (100, 0))})
    for ident in DIAGNOSTIC_IDS:
        assert r[ident]['status'] == 'nodata', (ident, r[ident])


def test_the_live_rows_read_current_values():
    data = {
        'OrangePi/RightPi/SystemUptimeSec': (12.0, 0.2),
        'OrangePi/RightPi/NetOperState': ('down', 0.2),
        'OrangePi/RightPi/NetSpeedMbps': (100, 0.2),
        'OrangePi/RightPi/UsbCameras': (1, 0.2),
        'OrangePi/RightPi/Recorders/LeftCam/NtDisconnects': (12, 0.2),
        'OrangePi/RightPi/Recorders/LeftCam/UptimeSec': (900.0, 0.2),
    }
    report = engine.evaluate(SPECS, engine.SnapshotSource(data))
    by_id = {c['id']: c for sec in report['sections'] for g in sec['groups'] for sub in g['subjects']
             for c in sub['checks']}
    assert by_id['pi.uptime']['status'] == 'warn'                 # just booted
    assert by_id['pi.link_state']['status'] == 'fail'             # link is down
    assert by_id['pi.link_speed']['status'] == 'warn'             # negotiated 100 Mbit/s
    assert by_id['pi.usb_cameras']['display'] == '1'
    assert by_id['rec.nt_disconnects_live']['status'] == 'fail'
    assert by_id['rec.uptime']['status'] == 'ok'
    # the log-only rows do not apply to a live robot
    assert by_id['pi.rebooted']['status'] == 'na' and by_id['pi.link_flaps']['status'] == 'na'
