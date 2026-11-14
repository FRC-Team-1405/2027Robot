"""Defaults taken from the robot code, so the tool starts out matching the current robot.

Camera names and mounts come from VisionConstants.CONFIGS (parsed from the .java source each run,
so a change there is picked up without touching this tool). If the file can't be read or parsed,
the fallback below (the 2026 values) is used and `source` says so.
"""
from __future__ import annotations

import math
import pathlib
import re

_REPO = pathlib.Path(__file__).parents[3]
VISION_CONSTANTS = _REPO / 'src/main/java/frc/robot/subsystems/vision/VisionConstants.java'

# Used only if VisionConstants.java can't be parsed. Same numbers as the 2026 robot.
_FALLBACK = {
    'LeftCam':  {'x_in': 2.19, 'y_in':  10.91, 'z_in': 28.7, 'roll_deg': 0.0, 'pitch_deg': -25.0, 'yaw_deg': -10.0},
    'RightCam': {'x_in': 2.19, 'y_in': -10.91, 'z_in': 28.7, 'roll_deg': 0.0, 'pitch_deg': -25.0, 'yaw_deg':  10.0},
}

# Default calibration tag: the hub tag the CircleFacingTag test uses (hub pair 9 & 10).
DEFAULT_TAG_ID = 10


def _top_level_args(text: str) -> list[str]:
    """Split 'a, Math.toRadians(-25), b' at top-level commas."""
    args, depth, cur = [], 0, ''
    for ch in text:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            args.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        args.append(cur.strip())
    return args


def _angle_deg(arg: str) -> float:
    m = re.fullmatch(r'Math\.toRadians\(\s*(-?[\d.]+)\s*\)', arg)
    if m:
        return float(m.group(1))
    m = re.fullmatch(r'Units\.radiansToDegrees\(\s*(-?[\d.]+)\s*\)', arg)
    if m:
        return float(m.group(1))
    return math.degrees(float(arg))          # a bare number is radians (Rotation3d's unit)


def parse_vision_constants(text: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for m in re.finditer(r'new CameraConfig\(\s*"([^"]+)"\s*,', text):
        chunk = text[m.end():m.end() + 1500]
        inches = re.findall(r'Units\.inchesToMeters\(\s*(-?[\d.]+)\s*\)', chunk)[:3]
        r = chunk.find('new Rotation3d(')
        if len(inches) < 3 or r < 0:
            continue
        start = r + len('new Rotation3d(')
        depth, end = 1, start
        while end < len(chunk) and depth:
            depth += {'(': 1, ')': -1}.get(chunk[end], 0)
            end += 1
        args = _top_level_args(chunk[start:end - 1])
        if len(args) != 3:
            continue
        out[m.group(1)] = {
            'x_in': float(inches[0]), 'y_in': float(inches[1]), 'z_in': float(inches[2]),
            'roll_deg': _angle_deg(args[0]), 'pitch_deg': _angle_deg(args[1]), 'yaw_deg': _angle_deg(args[2]),
        }
    return out


def camera_defaults() -> tuple[dict[str, dict], str]:
    """({camera name: mount}, where it came from)."""
    try:
        parsed = parse_vision_constants(VISION_CONSTANTS.read_text(encoding='utf-8'))
        if parsed:
            return parsed, f'{VISION_CONSTANTS.name} (current robot code)'
    except OSError:
        pass
    return dict(_FALLBACK), 'built-in 2026 values (VisionConstants.java not found)'


def mount_for(name: str, defaults: dict[str, dict]) -> dict:
    """Mount for a camera name from a log: exact, case-insensitive, then Left/Right in the name."""
    if name in defaults:
        return defaults[name]
    low = {k.lower(): v for k, v in defaults.items()}
    if name.lower() in low:
        return low[name.lower()]
    for side in ('left', 'right'):
        if side in name.lower():
            for k, v in defaults.items():
                if side in k.lower():
                    return v
    return next(iter(defaults.values()))
