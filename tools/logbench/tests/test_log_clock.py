"""log_clock.py: the boot epoch and true duration read from a .wpilog, and bundle_pairing.refine, which
uses them to re-pick a downloaded log's Pi sessions. Logs are built byte by byte (wpilog_builder)."""
import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'wpilog-utils' / 'tests'))

import paths  # noqa: F401
import wpilog_builder as wb

import bundle_pairing
import log_clock

UTC = dt.timezone.utc
BOOT = dt.datetime(2026, 10, 17, 12, 30, 0, tzinfo=UTC)
STALE_MS = 1_775_000_000_000            # the roboRIO's date before the Driver Station syncs it


def ms(t):
    return int(t.timestamp() * 1000)


def us(sec):
    return int(sec * 1e6)


def frc_log(sync_at=300.0, end=500.0, wall_samples=None):
    """A plain WPILib log: the robot's wall clock mirrored from NetworkTables every ~second."""
    b = wb.LogBuilder(extra='')
    b.entry('NT:/RobotTime/WallClockMs', 'int64', us(1))
    for t in wall_samples if wall_samples is not None else range(2, int(end), 1):
        wall = STALE_MS + t * 1000 if t < sync_at else ms(BOOT) + int(t * 1000)
        b.data('NT:/RobotTime/WallClockMs', us(t), wb.int64(wall))
    return b.build()


def akit_log(epoch_samples, boot_id=None, end=500.0):
    b = wb.LogBuilder()
    b.entry('/Timestamp', 'int64', us(1))
    b.entry('/RealOutputs/RobotTime/EpochMs', 'int64', us(1))
    if boot_id:
        b.entry('/RealOutputs/RobotTime/BootId', 'string', us(1))
        b.data('/RealOutputs/RobotTime/BootId', us(2), boot_id.encode())
    for t, epoch_ms in epoch_samples:
        b.data('/RealOutputs/RobotTime/EpochMs', us(t), wb.int64(epoch_ms))
    b.data('/Timestamp', us(end), wb.int64(us(end)))
    return b.build()


def test_wpilib_log_epoch_is_the_synced_wall_clock_minus_its_time_in_the_log():
    clock = log_clock.read(frc_log())
    assert abs((clock.epoch - BOOT).total_seconds()) < 0.01
    assert clock.source == 'NT:/RobotTime/WallClockMs'
    assert clock.t_range == (2.0, 499.0)


def test_the_stale_pre_sync_clock_is_listed_after_the_real_one():
    clock = log_clock.read(frc_log())
    assert len(clock.epochs) == 2
    assert abs((clock.epochs[0] - BOOT).total_seconds()) < 0.01       # newest first
    assert abs((clock.epochs[1] - BOOT).total_seconds()) > 3600         # the April epoch


def test_an_advantagekit_log_records_the_epoch_directly_and_the_boot_id():
    log = akit_log([(2.0, STALE_MS - 2000), (300.0, ms(BOOT))], boot_id='3f2a-run')
    clock = log_clock.read(log)
    assert clock.source == 'RealOutputs/RobotTime/EpochMs'
    assert clock.epoch == BOOT
    assert clock.boot_id == '3f2a-run'


def test_an_advantagekit_log_from_before_the_robot_recorded_its_clock_has_no_epoch():
    log, _ = wb.ds_log([('disabled', 5), ('auto', 3)])
    clock = log_clock.read(log)
    assert clock.epoch is None and clock.epochs == []
    assert clock.duration_sec is not None and clock.duration_sec > 7        # the duration is still known


def test_duration_ignores_a_bogus_late_timestamp():
    b = wb.LogBuilder(extra='')
    b.entry('NT:/RobotTime/WallClockMs', 'int64', us(1))
    b.data('NT:/RobotTime/WallClockMs', us(10), wb.int64(ms(BOOT) + 10_000))
    b.data('NT:/RobotTime/WallClockMs', us(400), wb.int64(ms(BOOT) + 400_000))
    b.entry('NT:/Junk', 'int64', us(2))
    b.data('NT:/Junk', 3_000_000_000_000, wb.int64(1))               # some plain logs carry these
    clock = log_clock.read(b.build())
    assert clock.t_max == 400.0


def test_a_truncated_log_still_yields_what_was_read():
    log = frc_log()
    clock = log_clock.read(log[:-7])
    assert abs((clock.epoch - BOOT).total_seconds()) < 0.01


def test_jitter_in_the_wall_clock_is_one_epoch_not_many():
    samples = list(range(310, 330))
    log = frc_log(sync_at=0, wall_samples=samples)
    assert len(log_clock.read(log).epochs) == 1


# ── bundle_pairing.refine ───────────────────────────────────────────────────────────────────

def pi(camera, name, epoch, t0, t1, pi_name='LeftPi'):
    return {'camera': camera, 'name': name, 'pi': pi_name, 'wall_clock': epoch, 'epoch': epoch,
            't_first': t0, 't_last': t1}


def test_refine_replaces_the_file_name_guess_with_the_boot_clock_match(tmp_path):
    log = tmp_path / 'akit_26-10-17_12-35-00_nyroc1_q1.wpilog'
    log.write_bytes(akit_log([(300.0, ms(BOOT))], end=900.0))
    listing = [pi('LeftCam', 'boot0003-a', BOOT, 600, 640), pi('LeftCam', 'boot0003-b', BOOT, 700, 760),
               pi('LeftCam', 'boot0002-old', BOOT - dt.timedelta(hours=1), 600, 640),   # another boot
               pi('LeftCam', 'boot0003-late', BOOT, 5000, 5100)]                         # past the log's end
    requested = [{'camera': 'LeftCam', 'name': 'boot0003-a', 'pi': 'LeftPi'},
                 {'camera': 'LeftCam', 'name': 'boot0002-old', 'pi': 'LeftPi'}]          # the filename guess
    out = bundle_pairing.refine(log, requested, listing)
    assert out.method == 'epoch'
    assert [s['name'] for s in out.sessions] == ['boot0003-a', 'boot0003-b']
    assert '1 added' in out.note and '1 dropped' in out.note


def test_refine_keeps_requested_sessions_that_have_no_clock_to_compare(tmp_path):
    log = tmp_path / 'x.wpilog'
    log.write_bytes(akit_log([(300.0, ms(BOOT))], end=900.0))
    clockless = {'camera': 'RightCam', 'name': 'boot0003-bare', 'pi': 'RightPi', 'wall_clock': BOOT, 'epoch': None,
                 't_first': None, 't_last': None}
    listing = [pi('LeftCam', 'boot0003-a', BOOT, 600, 640), clockless]
    requested = [{'camera': 'RightCam', 'name': 'boot0003-bare', 'pi': 'RightPi'}]
    out = bundle_pairing.refine(log, requested, listing)
    assert {s['name'] for s in out.sessions} == {'boot0003-a', 'boot0003-bare'}


def test_refine_explains_itself_and_keeps_the_request_when_the_log_has_no_clock(tmp_path):
    log = tmp_path / 'x.wpilog'
    log.write_bytes(wb.ds_log([('disabled', 5), ('auto', 3)])[0])
    requested = [{'camera': 'LeftCam', 'name': 'boot0003-a', 'pi': 'LeftPi'}]
    out = bundle_pairing.refine(log, requested, [pi('LeftCam', 'boot0003-a', BOOT, 600, 640)])
    assert out.method == 'requested' and out.sessions == requested and 'file name' in out.note


def test_refine_keeps_the_request_when_no_session_shares_the_boot(tmp_path):
    log = tmp_path / 'x.wpilog'
    log.write_bytes(akit_log([(300.0, ms(BOOT))]))
    requested = [{'camera': 'LeftCam', 'name': 'boot0009-z', 'pi': 'LeftPi'}]
    other = pi('LeftCam', 'boot0002-old', BOOT - dt.timedelta(hours=2), 0, 50)
    out = bundle_pairing.refine(log, requested, [other])
    assert out.method == 'requested' and out.sessions == requested
