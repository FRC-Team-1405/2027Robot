"""What an experiment switch was set to while a log was recorded.

Experiment switches (src/main/java/frc/robot/constants/ExperimentSwitches.java) are AdvantageKit
LoggedNetworkBooleans, so every loop's value is in the log as
``NetworkInputs/Tuning/ExperimentSwitches/<NAME>/Value``. The experiment runner writes the switch before a run and
reads it back; an analysis uses this to check the LOG agrees (the runner's word is not the log's).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

Signals = Dict[str, List[Tuple[float, object]]]


def switch_series(signals: Signals, name: str) -> List[Tuple[float, bool]]:
    """[(t, value)] for one switch, or [] if the log never recorded it (the code had no such switch)."""
    needle = f"tuning/experimentswitches/{name}".lower()
    for key, series in signals.items():
        k = key.lower().replace("\\", "/")
        if needle in k and (k.endswith(needle) or k.endswith(needle + "/value")):
            return [(t, bool(v)) for t, v in series]
    return []


def switch_values(signals: Signals, name: str, window: Optional[Tuple[float, float]] = None) -> Set[bool]:
    """Every value the switch had during `window` (the value in effect when it opened, and any change inside).
    One element means it stayed put; an empty set means the log has no record of it."""
    series = switch_series(signals, name)
    if not series:
        return set()
    if window is None:
        return {v for _t, v in series}
    lo, hi = window
    values = {v for t, v in series if lo <= t <= hi}
    before = [v for t, v in series if t < lo]
    if before:
        values.add(before[-1])          # a log records changes only; the last one before the window still holds
    return values
