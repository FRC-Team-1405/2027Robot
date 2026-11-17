from wpilog_utils.switches import switch_series, switch_values


def sig():
    return {"NetworkInputs/Tuning/ExperimentSwitches/RIO_PROCESS_CPU_LOGGING/Value":
            [(0.0, False), (50.0, True), (90.0, False)]}


def test_series_found_by_name_with_or_without_value_suffix():
    assert switch_series(sig(), "RIO_PROCESS_CPU_LOGGING") == [(0.0, False), (50.0, True), (90.0, False)]
    s = {"NT:/AdvantageKit/NetworkInputs/Tuning/ExperimentSwitches/X": [(1.0, True)]}
    assert switch_series(s, "X") == [(1.0, True)]
    assert switch_series(sig(), "OTHER") == []


def test_values_in_a_window_include_the_one_in_effect_at_its_start():
    s = sig()
    assert switch_values(s, "RIO_PROCESS_CPU_LOGGING", (55.0, 80.0)) == {True}      # on since t=50
    assert switch_values(s, "RIO_PROCESS_CPU_LOGGING", (10.0, 40.0)) == {False}
    assert switch_values(s, "RIO_PROCESS_CPU_LOGGING", (40.0, 60.0)) == {False, True}   # flipped inside the window
    assert switch_values(s, "NOPE", (0, 1)) == set()
