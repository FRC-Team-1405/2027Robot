"""Camera mount calibration tool."""
# logger must be imported first so the 'camera_calibration' root logger is
# configured — and the vision_analyzer sibling package imported + bridged in
# — before any sibling module calls logging.getLogger(__name__) or imports
# from vision_analyzer.
from . import logger as _logger  # noqa: F401
