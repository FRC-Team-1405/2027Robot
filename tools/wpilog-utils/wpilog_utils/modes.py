"""
Driver-station mode spans (disabled / auto / teleop) and time-window filtering of parsed signals.

Moved verbatim from vision_analyzer.metrics (see docs/wpilog-janitor-plan.md, M0); the leading
underscores were dropped from the names. Operates on the {name: [(t, value), ...]} dict that
`wpilog_utils.decode.parse_wpilog` returns.
"""
from typing import Dict, List, Optional, Tuple

# Where a log's driver-station mode can come from, most direct first. Our robot code has written three
# different shapes of log:
#   * AdvantageKit (akit_*.wpilog):  DriverStation/Enabled, DriverStation/Autonomous (booleans).
#   * WPILib DataLogManager (FRC_*.wpilog) with DriverStation.startDataLog(): DS:enabled, DS:autonomous.
#   * WPILib DataLogManager without it (e.g. every Albany 2026 log from Apr 16): no DS entries at all, but
#     NetworkTables is mirrored under NT:, including the control word DriverStation publishes to
#     /FMSInfo/FMSControlData on every change -- see FMS_CONTROL_BITS.
# The FMS only renames FRC_*.wpilog to FRC_<date>_<time>_<event>_<match>.wpilog; the contents are the same.
AKIT_ENABLED, AKIT_AUTO = 'DriverStation/Enabled', 'DriverStation/Autonomous'
WPILIB_ENABLED, WPILIB_AUTO = 'DS:enabled', 'DS:autonomous'
FMS_CONTROL_DATA = 'NT:/FMSInfo/FMSControlData'
# HAL_ControlWord bit layout (as DriverStation's MatchDataSender publishes it).
FMS_CONTROL_BITS = {'enabled': 0x01, 'autonomous': 0x02, 'test': 0x04, 'estop': 0x08,
                    'fms_attached': 0x10, 'ds_attached': 0x20}
# Every signal any source reads -- what a streaming reader (index.build_index) has to keep.
MODE_SIGNAL_NAMES = (AKIT_ENABLED, AKIT_AUTO, WPILIB_ENABLED, WPILIB_AUTO, FMS_CONTROL_DATA)


def mode_signals(signals: Dict) -> Tuple[List, List, Optional[str]]:
    """(enabled samples, autonomous samples, source name) from the first source this log has, or
    ([], [], None). Samples are [(t, bool), ...] in time order."""
    def bools(name: str) -> List:
        return sorted((t, bool(v)) for t, v in signals.get(name, []) if v is not None)

    if signals.get(AKIT_ENABLED):
        return bools(AKIT_ENABLED), bools(AKIT_AUTO), AKIT_ENABLED
    if signals.get(WPILIB_ENABLED):
        return bools(WPILIB_ENABLED), bools(WPILIB_AUTO), WPILIB_ENABLED
    words = sorted((t, int(v)) for t, v in signals.get(FMS_CONTROL_DATA, [])
                   if isinstance(v, (int, float)) and not isinstance(v, bool))
    if words:
        return ([(t, bool(w & FMS_CONTROL_BITS['enabled'])) for t, w in words],
                [(t, bool(w & FMS_CONTROL_BITS['autonomous'])) for t, w in words], FMS_CONTROL_DATA)
    return [], [], None

def filter_signals_by_time(signals: Dict, t_lo: float, t_hi: float) -> Dict:
    """
    Return signals containing only samples within [t_lo, t_hi], with one
    addition: if a signal has no sample inside the window but does have one
    before it, that last pre-window sample is carried forward and re-stamped
    to t_lo. WPILog only logs a value when it changes, so "no sample in this
    window" usually means "value held steady from before the window" (e.g. a
    Connected flag that goes true once and is never re-logged) rather than
    "value unknown" — without this, narrowing the time range can make a
    perfectly fine signal look like it has no data at all in that window.
    """
    out: Dict = {}
    for name, samples in signals.items():
        inwindow = [(t, v) for t, v in samples if t_lo <= t <= t_hi]
        if inwindow:
            out[name] = inwindow
            continue
        before = [(t, v) for t, v in samples if t < t_lo]
        out[name] = [(t_lo, before[-1][1])] if before else []
    return out


def compute_mode_spans(
    signals: Dict, start_t: float, end_t: Optional[float] = None
) -> List[Tuple[float, float, str]]:
    """
    Return [(rel_start, rel_end, mode), ...] where mode is 'disabled', 'auto', or 'teleop'.
    Times are seconds relative to start_t. The mode comes from whichever source `mode_signals` finds.

    WPILog only writes a new sample when a value changes, so the mode in
    effect after the *last* enabled sample persists until the
    log actually ends — it is not "unknown". The final span's end is
    therefore extended to `end_t` (the true end of the log, across all
    signals) rather than just the timestamp of that last sample. Otherwise a
    steady disabled tail (e.g. the DS app closing while robot code keeps
    running and logging other signals) looks like it ends early and gets
    excluded from mode-driven trimming, even though it's genuinely disabled
    the whole way to the end.
    """
    import bisect as _bisect

    enabled_sig, auto_sig, _source = mode_signals(signals)

    if not enabled_sig:
        return []

    auto_by_time   = {t: v for t, v in auto_sig}
    auto_ts_sorted = sorted(auto_by_time.keys())

    def get_auto(t: float) -> bool:
        if not auto_ts_sorted:
            return False
        idx = _bisect.bisect_right(auto_ts_sorted, t) - 1
        return bool(auto_by_time[auto_ts_sorted[max(0, idx)]])

    spans: List[Tuple[float, float, str]] = []
    current_mode: Optional[str] = None
    span_start:   Optional[float] = None

    # Re-evaluate at every change of either signal: sources that log only on change (DS:*) can switch
    # auto -> teleop with no new enabled sample. Autonomous samples before the first enabled one are moot.
    en_ts = [t for t, _ in enabled_sig]
    changes = sorted(set(en_ts) | {t for t in auto_ts_sorted if t > en_ts[0]})
    for t in changes:
        enabled = enabled_sig[_bisect.bisect_right(en_ts, t) - 1][1]
        auto = get_auto(t)
        if enabled and auto:
            mode = 'auto'
        elif enabled:
            mode = 'teleop'
        else:
            mode = 'disabled'

        if mode != current_mode:
            if current_mode is not None and span_start is not None:
                spans.append((span_start - start_t, t - start_t, current_mode))
            current_mode = mode
            span_start   = t

    final_end = (end_t - start_t) if end_t is not None else (enabled_sig[-1][0] - start_t)
    if current_mode is not None and span_start is not None:
        spans.append((span_start - start_t, final_end, current_mode))

    return spans
