"""Puts the sibling vision-analyzer tool on sys.path.

logbench reuses vision_analyzer's stdlib-only .wpilog parser and field constants
rather than vendoring a second copy. This mirrors the bridge camera_calibration does in
its logger.py -- same rationale, same relative-path shape -- so all three tools agree on
how a log is decoded.

Import this before importing anything from vision_analyzer.
"""
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
_VA_PATH = _HERE.parents[1] / 'vision-analyzer'


def ensure_vision_analyzer_on_path() -> pathlib.Path:
    if str(_VA_PATH) not in sys.path:
        sys.path.insert(0, str(_VA_PATH))
    return _VA_PATH


def ensure_server_on_path() -> pathlib.Path:
    """Lets `from model import ...` work when logbench is imported as a library
    from another tool (the Streamlit calibration app) rather than run from this dir."""
    if str(_HERE) not in sys.path:
        sys.path.insert(0, str(_HERE))
    return _HERE


ensure_server_on_path()
ensure_vision_analyzer_on_path()
