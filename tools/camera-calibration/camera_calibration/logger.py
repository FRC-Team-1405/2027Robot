"""
Central logging configuration for camera_calibration.

One timestamped log file is created per process (one Streamlit session) under
tools/camera-calibration/logs/. The root 'camera_calibration' logger writes
DEBUG and above to the file; WARNING and above to the console.

camera_calibration reuses parser/metrics code straight out of the sibling
vision_analyzer tool (see app.py, tabs/*.py) via a sys.path insert rather than
an installed dependency. Importing vision_analyzer triggers its own
setup_logging(), which writes to its own log file under
tools/vision-analyzer/logs/ — that's left in place so the vision-analyzer app
is unaffected when run standalone. This module additionally attaches its file
handler to the 'vision_analyzer' logger, so every parser/metrics log line
(including the loud warnings parser.py now emits for parsing anomalies) also
lands in the calibration session's own log file — one place to look when
debugging a calibration run instead of two.

Import this module before calling logging.getLogger() so child loggers in
every sibling module propagate to an already-configured parent.
"""
import logging
import pathlib
import sys
from datetime import datetime

_LOG_DIR = pathlib.Path(__file__).parent.parent / 'logs'
_VA_PATH = pathlib.Path(__file__).parents[2] / 'vision-analyzer'
_MP_PATH = pathlib.Path(__file__).parents[2] / 'logbench' / 'server'

# Cached so callers can surface the path in the UI.
_log_file: pathlib.Path | None = None


def setup_logging() -> pathlib.Path:
    """
    Configure the 'camera_calibration' root logger and bridge in
    'vision_analyzer' logging. Idempotent — subsequent calls return the same
    log-file path without adding duplicate handlers.
    """
    global _log_file

    logger = logging.getLogger('camera_calibration')
    if logger.handlers:
        assert _log_file is not None
        return _log_file

    logger.setLevel(logging.DEBUG)
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    _log_file = _LOG_DIR / f'camera_calibration_{timestamp}.log'

    fmt = logging.Formatter(
        '%(asctime)s  %(levelname)-8s  %(name)s  %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    fh = logging.FileHandler(_log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    logger.info('camera_calibration session started — log: %s', _log_file)

    _bridge_vision_analyzer(fh)
    _bridge_logbench()

    return _log_file


def _bridge_vision_analyzer(fh: logging.FileHandler) -> None:
    """Make sibling-tool (vision_analyzer) log lines also land in this file."""
    if str(_VA_PATH) not in sys.path:
        sys.path.insert(0, str(_VA_PATH))
    import vision_analyzer  # noqa: F401  (import runs its own setup_logging())

    va_logger = logging.getLogger('vision_analyzer')
    if fh not in va_logger.handlers:
        va_logger.addHandler(fh)
        va_logger.info(
            'Bridged into camera_calibration session log: %s', _log_file,
        )


def _bridge_logbench() -> None:
    """Put the sibling logbench tool's server package on sys.path.

    Same rationale as _bridge_vision_analyzer: Tab 6 renders its replay with the
    logbench front end rather than rebuilding Plotly figures server-side, and reusing
    the sibling tool by path keeps one implementation of the player instead of two.
    Imported lazily by tabs/replay.py -- only the path insert happens here.
    """
    if str(_MP_PATH) not in sys.path:
        sys.path.insert(0, str(_MP_PATH))


def get_log_file() -> pathlib.Path | None:
    """Return the current log-file path (None before setup_logging runs)."""
    return _log_file


# Run on import so sibling module loggers propagate to an already-configured
# parent, and so vision-analyzer's package (and its sys.path entry) is
# available to every camera_calibration module without each one re-deriving
# the relative path to it.
setup_logging()
