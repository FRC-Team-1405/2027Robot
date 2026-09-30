"""Raw (t, value) series lookup helpers, shared by the metric library and by specs/.

Promoted out of specs/camera_health.py so the metric/composite library doesn't depend on
the player-spec layer (specs/ depends on core/, never the other way around). specs/camera_health.py
imports these rather than keeping its own copies.
"""
import math
import re
from typing import Any, Dict, List, Optional, Tuple


def find_signal(signals: Dict, base_key: str) -> Optional[List[Tuple[float, Any]]]:
    """Logs write these under a 'RealOutputs/' prefix (AdvantageKit) but older/NT-sourced
    ones don't, and at least one key differs in case from what was expected -- so try
    exact, prefixed, then case-insensitive before giving up."""
    for prefix in ('RealOutputs/', ''):
        k = prefix + base_key
        if k in signals:
            return signals[k]
    target = base_key.lower()
    for k in signals:
        kl = k.lower()
        if kl == target or kl == 'realoutputs/' + target:
            return signals[k]
    return None


def flatten_pose_signal(raw_signal: List[Tuple[float, Any]]) -> List[Tuple[float, dict]]:
    """Pose2d and Pose2d[] log entries both decode to (ts, list[dict]) -- the parser
    doesn't distinguish scalar vs array structs. For a scalar (Drivetrain/Pose) the list
    always has exactly one entry; for an array (Vision/*/AcceptedPoses, 0+ accepted poses
    per loop) take the most recent one that loop. Either way this produces one flat
    (ts, {'x','y','rot'}) series."""
    return [(t, poses[-1]) for t, poses in raw_signal if poses]


def discover_cameras(signals: Dict) -> List[str]:
    """Camera names, from whichever Vision/<name>/Health/ScorePercent keys exist.

    Falls back to AcceptedPoses so a log predating health scoring still yields its
    cameras."""
    found = set()
    for pattern in (
        r'^(?:RealOutputs/)?Vision/([^/]+)/Health/ScorePercent$',
        r'^(?:RealOutputs/)?Vision/([^/]+)/AcceptedPoses$',
    ):
        rx = re.compile(pattern, re.IGNORECASE)
        for key in signals:
            m = rx.match(key)
            if m:
                found.add(m.group(1))
        if found:
            break
    # CrossCameraAgreement lives at the same level but is not a camera.
    found.discard('CrossCameraAgreement')
    # Left/Right first if present, then anything else alphabetically, so the common
    # two-camera robot always lays out the same way.
    preferred = [c for c in ('Left', 'Right') if c in found]
    return preferred + sorted(found - set(preferred))


def bounds(signals: Dict) -> Tuple[float, float]:
    """(earliest, latest) timestamp across every signal in the log."""
    lo = math.inf
    hi = -math.inf
    for samples in signals.values():
        if samples:
            lo = min(lo, samples[0][0])
            hi = max(hi, samples[-1][0])
    if lo is math.inf:
        return 0.0, 0.0
    return lo, hi


# --- Time-weighted (sample-and-hold) helpers -------------------------------------------
#
# AdvantageKit writes a record only when a logged value *changes*, so a series is a step
# function, not a stream of equally-spaced samples: a value that held for 480 ms and one that
# held for 20 ms are one record each. Averaging records therefore weights by how often a
# value changed, not by how long it lasted -- on a strictly alternating 0/100 series the
# record-mean is 50 no matter how long the value sat at 100 (docs/adr/0001, Finding 2).
# Everything here integrates the step function over time instead.

Piece = Tuple[float, float, Any]  # (start, end, value), start < end


def hold_intervals(series: List[Tuple[float, Any]], lo: float, hi: float) -> List[Piece]:
    """The step function `series` describes, as (start, end, value) pieces clipped to
    [lo, hi]. The value from the last record at or before `lo` is carried in, so a signal that
    last changed before the window still counts for the whole window. A signal with no record
    yet at `lo` is undefined until its first record (no piece is emitted for that head)."""
    out: List[Piece] = []
    n = len(series)
    for i, (t, v) in enumerate(series):
        t_next = series[i + 1][0] if i + 1 < n else hi
        a, b = max(t, lo), min(t_next, hi)
        if b > a:
            out.append((a, b, v))
    return out


def merge_spans(spans: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Coalesce touching/overlapping (start, end) spans; input must be sorted by start."""
    out: List[Tuple[float, float]] = []
    for a, b in spans:
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def clip_to_spans(pieces: List[Piece], spans: List[Tuple[float, float]]) -> List[Piece]:
    """Keep only the parts of `pieces` that fall inside `spans` (both sorted, non-overlapping)."""
    out: List[Piece] = []
    j = 0
    for a, b, v in pieces:
        while j < len(spans) and spans[j][1] <= a:
            j += 1
        k = j
        while k < len(spans) and spans[k][0] < b:
            lo, hi = max(a, spans[k][0]), min(b, spans[k][1])
            if hi > lo:
                out.append((lo, hi, v))
            k += 1
    return out


def time_weighted_mean(pieces: List[Piece]) -> Optional[float]:
    """Duration-weighted mean of piece values; None if the pieces cover no time."""
    total = sum(b - a for a, b, _ in pieces)
    if total <= 0:
        return None
    return sum((b - a) * v for a, b, v in pieces) / total
