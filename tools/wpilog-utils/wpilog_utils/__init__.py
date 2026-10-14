"""
wpilog_utils -- shared, stdlib-only tools for reading and rewriting .wpilog files.

Modules:
    records   -- header, record walker (with byte ranges), record encoder
    decode    -- payload decoding, parse_wpilog -> {signal: [(t, value), ...]}
    modes     -- driver-station mode spans, time-window filtering of parsed signals
    index     -- one-pass LogIndex: entries, bytes, cycles, mode spans
    trim      -- trimming to time windows: legacy single window + the multi-segment engine

Used by wpilog-janitor, logbench, vision-analyzer and camera-calibration. Nothing here knows about
vision, the UI, or which entries are worth keeping. See docs/wpilog-janitor-plan.md.

Logging: this package logs to the 'wpilog_utils' logger and configures nothing itself. Tools that
own a log file (vision_analyzer, camera_calibration) attach their handlers to it.
"""
import logging as _logging

__version__ = '0.1.0'

_logging.getLogger(__name__).addHandler(_logging.NullHandler())
