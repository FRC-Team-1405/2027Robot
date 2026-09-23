"""File logging for the Logbench server.

Each server run gets its own file so an on-robot investigation stays together.  The
directory is deliberately local-only; :func:`configure` retains the ten newest runs.
"""
import logging
import pathlib
import sys
from datetime import datetime

LOG_DIR = pathlib.Path(__file__).resolve().parents[1] / 'logs'
KEEP_RUNS = 10


def configure() -> pathlib.Path:
    """Configure Logbench's file and console loggers once and return this run's file."""
    logger = logging.getLogger('logbench')
    if getattr(logger, '_logbench_configured', False):
        return logger._logbench_path

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / ('logbench-%s.log' % datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d %(levelname)-8s %(name)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')

    handler = logging.FileHandler(path, encoding='utf-8')
    handler.setFormatter(formatter)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)

    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.addHandler(console)
    logger.propagate = False
    logger._logbench_configured = True
    logger._logbench_path = path

    old = sorted(LOG_DIR.glob('logbench-*.log'), key=lambda item: item.stat().st_mtime,
                 reverse=True)[KEEP_RUNS:]
    for item in old:
        try:
            item.unlink()
        except OSError:
            logger.warning('could not remove old log file %s', item, exc_info=True)
    logger.info('logging to %s (retaining %d runs)', path, KEEP_RUNS)
    return path
