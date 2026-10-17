"""Log: a parsed .wpilog plus the log-level facts every Run is windowed against.

Reuses vision_analyzer's parser and DS-mode-span detection rather than a second
implementation of either -- see the module docstring in core/__init__.py.
"""
import pathlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from vision_analyzer import metrics as va_metrics
from vision_analyzer.parser import parse_wpilog

from . import signals as sig


@dataclass
class Log:
    path: pathlib.Path
    signals: Dict = field(repr=False)
    # {'n_records', 'n_late', 'max_late_s'} from the parser: records written behind a newer one (a plain
    # WPILib log's NT mirroring). Harmless here -- every signal is read on its own -- but the WPILog
    # Janitor cannot trim such a log until it has made a time-ordered copy. None when not known.
    order_stats: Optional[Dict] = field(default=None, repr=False)

    @classmethod
    def load(cls, path) -> 'Log':
        p = pathlib.Path(path)
        stats: Dict = {}
        return cls(path=p, signals=parse_wpilog(str(p), stats), order_stats=stats)

    def bounds(self) -> Tuple[float, float]:
        """(earliest, latest) timestamp across every signal, absolute log seconds."""
        return sig.bounds(self.signals)

    def cameras(self) -> List[str]:
        return sig.discover_cameras(self.signals)

    def mode_spans(self) -> List[Tuple[float, float, str]]:
        """[(rel_start, rel_end, mode), ...] where mode is 'disabled', 'auto', or
        'teleop', relative to this log's own start (bounds()[0])."""
        t0, t1 = self.bounds()
        return va_metrics.compute_mode_spans(self.signals, t0, t1)
