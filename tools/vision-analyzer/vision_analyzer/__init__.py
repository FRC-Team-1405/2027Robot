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
# logger must be imported first so the 'vision_analyzer' root logger is
# configured before any sibling module calls logging.getLogger(__name__).
from . import logger as _logger  # noqa: F401
