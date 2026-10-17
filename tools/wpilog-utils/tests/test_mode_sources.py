"""Mode spans from each log shape modes.mode_signals knows: AdvantageKit, WPILib DS:*, and the
NT-mirrored FMS control word (plain DataLogManager logs, e.g. Albany 2026)."""
from wpilog_utils.modes import compute_mode_spans, mode_signals

EN, AUTO, FMS, DS = 0x01, 0x02, 0x10, 0x20


def test_fms_control_word_bits_give_the_mode():
    sigs = {'NT:/FMSInfo/FMSControlData': [(0.0, 0), (5.0, FMS | DS | AUTO), (10.0, FMS | DS | AUTO | EN),
                                            (25.0, FMS | DS), (28.0, FMS | DS | EN), (40.0, 0)]}
    assert compute_mode_spans(sigs, 0.0, 50.0) == [
        (0.0, 10.0, 'disabled'), (10.0, 25.0, 'auto'), (25.0, 28.0, 'disabled'),
        (28.0, 40.0, 'teleop'), (40.0, 50.0, 'disabled')]
    assert mode_signals(sigs)[2] == 'NT:/FMSInfo/FMSControlData'


def test_wpilib_ds_entries_give_the_mode():
    sigs = {'DS:enabled': [(1.0, False), (2.0, True), (4.0, False)], 'DS:autonomous': [(1.0, True), (3.0, False)]}
    assert compute_mode_spans(sigs, 1.0, 6.0) == [
        (0.0, 1.0, 'disabled'), (1.0, 2.0, 'auto'), (2.0, 3.0, 'teleop'), (3.0, 5.0, 'disabled')]


def test_the_most_direct_source_wins():
    sigs = {'DriverStation/Enabled': [(0.0, True)], 'DriverStation/Autonomous': [(0.0, False)],
            'DS:enabled': [(0.0, False)], 'NT:/FMSInfo/FMSControlData': [(0.0, EN | AUTO)]}
    assert mode_signals(sigs)[2] == 'DriverStation/Enabled'
    assert compute_mode_spans(sigs, 0.0, 1.0) == [(0.0, 1.0, 'teleop')]
    del sigs['DriverStation/Enabled']
    assert mode_signals(sigs)[2] == 'DS:enabled'


def test_no_source_means_no_spans():
    assert compute_mode_spans({'NT:/SmartDashboard/x': [(0.0, 1.0)]}, 0.0, 1.0) == []
    assert mode_signals({})[2] is None
