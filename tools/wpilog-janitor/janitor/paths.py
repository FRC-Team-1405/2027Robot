"""Puts the sibling wpilog-utils library on sys.path (same bridge convention as logbench/paths.py).

Import this before importing anything from wpilog_utils. wpilog-utils has a pyproject.toml, so
`pip install -e tools/wpilog-utils` also works and makes this a no-op.
"""
import pathlib
import sys

_WU_PATH = pathlib.Path(__file__).resolve().parents[2] / 'wpilog-utils'


def ensure_wpilog_utils_on_path() -> pathlib.Path:
    if str(_WU_PATH) not in sys.path:
        sys.path.insert(0, str(_WU_PATH))
    return _WU_PATH


ensure_wpilog_utils_on_path()
