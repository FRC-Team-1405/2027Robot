"""
vision_analyzer — FRC vision log analysis package.

Modules:
    constants       — field geometry, tag positions, colors
    parser          — WPILog binary parser
    metrics         — signal discovery, metric computation, chart helpers
    robot           — roboRIO SSH download
    app             — Streamlit application
    cli             — CLI (probe + legacy HTML)
    tabs            — tab module registry
"""
# The shared .wpilog library lives in the sibling tools/wpilog-utils (not installed; same
# sys.path-bridge convention as logbench/camera-calibration use for this package).
import pathlib as _pathlib
import sys as _sys

_WU_PATH = str(_pathlib.Path(__file__).resolve().parents[2] / 'wpilog-utils')
if _WU_PATH not in _sys.path:
    _sys.path.insert(0, _WU_PATH)

# logger must be imported first so the 'vision_analyzer' root logger is
# configured before any sibling module calls logging.getLogger(__name__).
from . import logger as _logger  # noqa: F401
