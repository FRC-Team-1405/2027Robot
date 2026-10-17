"""Launcher so the janitor runs from any working directory without PYTHONPATH:

    python tools/wpilog-janitor/run.py serve --logs logs
    python tools/wpilog-janitor/run.py trim logs/match.wpilog --modes auto

Same as `python -m janitor ...` run from tools/wpilog-janitor.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from janitor.cli import main  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(main())
