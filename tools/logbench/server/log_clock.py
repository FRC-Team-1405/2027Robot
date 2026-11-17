"""Which roboRIO boot a .wpilog belongs to, and how long it really is.

One streaming pass over the file that decodes only the few clock entries (not the whole log), so it
is cheap enough to run on a freshly downloaded 100 MB log. See pairing.py for what the epoch is for.

The epoch (wall clock at log t=0) comes from, best first:
  RealOutputs/RobotTime/EpochMs   the AdvantageKit log, written on change by WallClockEpoch.java
  NT:/RobotTime/EpochMs           the same value as mirrored into the plain WPILib log
  NT:/RobotTime/WallClockMs       the robot's wall clock, republished every loop; the epoch is the value
                                  minus the sample's own log time (older logs have only this)
A log with none of them (an AdvantageKit log from before WallClockEpoch.java) has no epoch.

The Driver Station sync steps the wall clock from a stale date to the right one, so a log can hold two
different epochs; `epochs` lists them newest first and the first is the one to trust.
"""
import dataclasses
import datetime as dt
import pathlib
import struct
from typing import Dict, List, Optional, Tuple

import paths  # noqa: F401  (side effect: wpilog_utils on sys.path)
from wpilog_utils.decode import decode_payload, handle_control
from wpilog_utils.records import iter_records, wpilog_header_end

EPOCH_MS_NAMES = ('RealOutputs/RobotTime/EpochMs', 'NT:/RobotTime/EpochMs')
WALL_CLOCK_NAMES = ('NT:/RobotTime/WallClockMs',)
BOOT_ID_NAMES = ('RealOutputs/RobotTime/BootId', 'NT:/RobotTime/BootId')

# A record timestamp beyond this is a bogus stamp some plain WPILib logs carry, not robot time.
MAX_LOG_T_SEC = 1e6
_WANTED = set(EPOCH_MS_NAMES + WALL_CLOCK_NAMES + BOOT_ID_NAMES)
# Wall clocks outside this are not a real date (0 before any value was published).
_MIN_MS, _MAX_MS = 1.5e12, 4.1e12    # 2017 .. 2100
# Epochs closer than this are the same boot (WallClockMs jitters by a few ms per sample).
_SAME_EPOCH_SEC = 2.0


@dataclasses.dataclass
class LogClock:
    epochs: List[dt.datetime]            # newest recorded first; [] when the log has none
    boot_id: Optional[str]
    t_min: Optional[float]               # first / last record time, seconds
    t_max: Optional[float]
    source: Optional[str] = None         # which entry the epoch came from

    @property
    def epoch(self) -> Optional[dt.datetime]:
        return self.epochs[0] if self.epochs else None

    @property
    def duration_sec(self) -> Optional[float]:
        return None if self.t_min is None or self.t_max is None else self.t_max - self.t_min

    @property
    def t_range(self) -> Optional[Tuple[float, float]]:
        return None if self.t_min is None or self.t_max is None else (self.t_min, self.t_max)


def _epoch(ms: float, t_sec: float, absolute: bool) -> Optional[dt.datetime]:
    if not (_MIN_MS <= ms <= _MAX_MS):
        return None
    ms = ms if absolute else ms - t_sec * 1000.0
    return dt.datetime.fromtimestamp(ms / 1000.0, dt.timezone.utc)


def read(raw: bytes) -> LogClock:
    """Scan raw .wpilog bytes. Never raises on a damaged log: whatever was read before the damage is used."""
    entries: Dict[int, dict] = {}
    wanted: Dict[int, Tuple[str, str]] = {}      # entry id -> (name, kind)
    first: Dict[str, Tuple[float, object]] = {}
    last: Dict[str, Tuple[float, object]] = {}
    t_min = t_max = None
    try:
        for entry_id, ts, payload, _s, _e in iter_records(raw, wpilog_header_end(raw)):
            if entry_id == 0:
                handle_control(payload, entries)
                if len(payload) >= 5 and payload[0] == 0:
                    new_id = struct.unpack_from('<I', payload, 1)[0]
                    info = entries.get(new_id)
                    if info and info['name'] in _WANTED:
                        wanted[new_id] = (info['name'], info['type'])
                continue
            if ts < MAX_LOG_T_SEC:
                if t_min is None or ts < t_min:
                    t_min = ts
                if t_max is None or ts > t_max:
                    t_max = ts
            want = wanted.get(entry_id)
            if want is None or ts >= MAX_LOG_T_SEC:
                continue
            value = decode_payload(payload, want[1])
            if value is None:
                continue
            first.setdefault(want[0], (ts, value))
            last[want[0]] = (ts, value)
    except (ValueError, IndexError):
        pass

    boot = next((str(last[n][1]) for n in BOOT_ID_NAMES if n in last), None)
    for names, absolute in ((EPOCH_MS_NAMES, True), (WALL_CLOCK_NAMES, False)):
        for name in (n for n in names if n in last):
            found: List[dt.datetime] = []
            for ts, value in (last[name], first[name]):      # newest first
                try:
                    epoch = _epoch(float(value), ts, absolute)
                except (TypeError, ValueError):
                    continue
                if epoch is not None and all(abs((epoch - e).total_seconds()) > _SAME_EPOCH_SEC for e in found):
                    found.append(epoch)
            if found:
                return LogClock(found, boot, t_min, t_max, name)
    return LogClock([], boot, t_min, t_max)


def read_file(path) -> LogClock:
    return read(pathlib.Path(path).read_bytes())
