"""
wpilog-janitor -- make .wpilog files smaller on purpose.

Trim a log to the periods you care about (re-timed so it still plays cleanly in AdvantageScope),
drop entries you don't need, and see what that saves. The file-format work lives in the shared
wpilog-utils library; this package is the tool on top of it. See docs/wpilog-janitor-plan.md.
"""
from . import paths as _paths  # noqa: F401  (side effect: wpilog_utils importable)

__version__ = '0.1.0'
