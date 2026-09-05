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
