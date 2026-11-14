"""PhotonVision settings: the friendly names a plan uses, and how to compare what we asked for with what
the Pi publisher reports.

This is the one place that knows how our names map onto PhotonVision's (see
coprocessor/orangepi-nt-publisher.py PV_PIPELINE_FIELDS, which uses PhotonVision's own JSON field names).
If a PhotonVision release renames a field, it changes here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Field:
    friendly: str       # the name in a plan
    pv: str             # PhotonVision's pipeline/camera JSON field (what the websocket message carries)
    topic: str          # the Pi publisher's NetworkTables topic under /OrangePi/<Pi>/PhotonVision/<camera>/
    kind: type          # int | float | bool


FIELDS: dict[str, Field] = {f.friendly: f for f in (
    Field("decimate", "decimate", "Decimate", int),
    Field("threads", "threads", "Threads", int),
    Field("low_latency", "blockForFrames", "LowLatencyMode", bool),
    Field("multitag", "doMultiTarget", "MultiTag", bool),
    Field("refine_edges", "refineEdges", "RefineEdges", bool),
    Field("blur", "blur", "Blur", float),
    Field("decision_margin", "decisionMargin", "DecisionMargin", int),
    Field("pose_iterations", "numIterations", "PoseIterations", int),
    Field("hamming", "hammingDist", "HammingDist", int),
    Field("auto_exposure", "cameraAutoExposure", "AutoExposure", bool),
    Field("exposure", "cameraExposureRaw", "Exposure", float),
    Field("brightness", "cameraBrightness", "Brightness", int),
    Field("gain", "cameraGain", "Gain", int),
)}
# The camera mode is special: set by index into the camera's mode list, confirmed by the real mode string.
MODE_KEY = "camera_mode"
SETTING_KEYS = tuple(FIELDS) + (MODE_KEY,)
MODE_TOPIC = "Video/video0/Mode"          # under /OrangePi/<Pi>/ ; e.g. "800x600 MJPG @100"

_MODE = re.compile(r"^\s*(\d+)\s*x\s*(\d+)\s+([A-Za-z0-9]+)\s*@\s*(\d+(?:\.\d+)?)\s*$")


class SettingsError(ValueError):
    pass


def parse_mode(text: str) -> tuple[int, int, str, float]:
    """'800x600 MJPG @100' -> (800, 600, 'MJPG', 100.0)."""
    m = _MODE.match(str(text))
    if not m:
        raise SettingsError(f"camera_mode {text!r}: write it like '800x600 MJPG @100'")
    return int(m.group(1)), int(m.group(2)), m.group(3).upper(), float(m.group(4))


def same_mode(a: str, b: str) -> bool:
    try:
        wa, ha, fa, ra = parse_mode(a)
        wb, hb, fb, rb = parse_mode(b)
    except SettingsError:
        return str(a).strip() == str(b).strip()
    return (wa, ha, ra) == (wb, hb, rb) and (fa == fb or {fa, fb} <= {"MJPG", "MJPEG"})


def validate(settings: dict[str, Any], where: str) -> dict[str, Any]:
    """Check names and types of one settings table; returns it with values coerced."""
    out: dict[str, Any] = {}
    for key, value in settings.items():
        if key == MODE_KEY:
            parse_mode(value)
            out[key] = str(value)
            continue
        if key not in FIELDS:
            raise SettingsError(f"{where}: unknown setting {key!r} (known: {', '.join(SETTING_KEYS)})")
        kind = FIELDS[key].kind
        if kind is bool:
            if not isinstance(value, bool):
                raise SettingsError(f"{where}: {key} must be true or false")
            out[key] = value
        elif kind is int:
            if isinstance(value, bool) or not isinstance(value, int):
                raise SettingsError(f"{where}: {key} must be a whole number")
            out[key] = value
        else:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise SettingsError(f"{where}: {key} must be a number")
            out[key] = float(value)
    return out


def equal(key: str, want: Any, got: Any) -> bool:
    if got is None:
        return False
    if key == MODE_KEY:
        return same_mode(want, got)
    kind = FIELDS[key].kind
    if kind is float:
        return abs(float(want) - float(got)) < 1e-6 * max(1.0, abs(float(want))) + 1e-9
    return kind(want) == kind(got)


def differences(want: dict[str, Any], got: dict[str, Any]) -> list[tuple[str, Any, Any]]:
    """[(key, wanted, actual)] for every wanted setting the readback does not match."""
    return [(k, v, got.get(k)) for k, v in want.items() if not equal(k, v, got.get(k))]


def describe(diffs: list[tuple[str, Any, Any]]) -> str:
    return ", ".join(f"{k} wanted {w!r} but is {g!r}" for k, w, g in diffs)
