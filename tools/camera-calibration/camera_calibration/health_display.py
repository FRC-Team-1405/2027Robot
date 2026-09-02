"""Shared score-display helpers for Tab 5 (Live Health) and Tab 6 (Replay).

Both tabs show the same VisionHealth.java-computed 0-100 scores; this is the
one place their "what does this score mean visually" logic lives, so the two
views can't drift out of sync with each other.
"""
import math
from typing import Optional


def is_unmeasurable(score: float, reason: str) -> bool:
    """True if the robot couldn't compute a real score (reason non-empty), or we've never
    received/read a value at all (NaN). The robot itself never publishes NaN over NT (see
    VisionHealth.java) -- a real score is always a plain 0-100 number; NaN here means "no
    data," not "measured and it's zero"."""
    return bool(reason) or score is None or math.isnan(score)


def severity_word(pct: Optional[float]) -> str:
    """Maps to Streamlit's built-in markdown color directives (:word[text])."""
    if pct is None or math.isnan(pct):
        return 'gray'
    if pct >= 80:
        return 'green'
    if pct >= 40:
        return 'orange'
    return 'red'
