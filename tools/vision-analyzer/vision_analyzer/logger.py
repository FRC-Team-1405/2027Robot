"""
Central logging configuration for vision_analyzer.

One timestamped log file is created per process (one Streamlit session or one
CLI run) under tools/vision-analyzer/logs/. The root 'vision_analyzer' logger
writes DEBUG and above to the file; WARNING and above to the console.

Import this module before calling logging.getLogger() so child loggers in
every sibling module propagate to an already-configured parent.
"""
import logging
import pathlib
from datetime import datetime

_LOG_DIR = pathlib.Path(__file__).parent.parent / 'logs'

# Cached so callers can surface the path in the UI.
_log_file: pathlib.Path | None = None


def setup_logging() -> pathlib.Path:
    """
    Configure the 'vision_analyzer' root logger. Idempotent — subsequent calls
    return the same log-file path without adding duplicate handlers.
    """
    global _log_file

    logger = logging.getLogger('vision_analyzer')
    if logger.handlers:
        assert _log_file is not None
        return _log_file

    logger.setLevel(logging.DEBUG)
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    _log_file = _LOG_DIR / f'vision_analyzer_{timestamp}.log'

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

    logger.info('vision_analyzer session started — log: %s', _log_file)
    return _log_file


def get_log_file() -> pathlib.Path | None:
    """Return the current log-file path (None before setup_logging runs)."""
    return _log_file


# Run on import so sibling module loggers propagate to a configured parent.
setup_logging()
