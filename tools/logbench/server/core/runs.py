"""Run: a Log windowed to [lo, hi] seconds, with a memoized metric/composite cache.

This is the one unit every consumer -- CLI, comparison, single-log views -- operates on.
A "single log" view is just a Run spanning the whole log; a "compare two autonomous
windows" view is two Runs, each trimmed to its own log's auto span.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import composites as composites_mod
from . import metrics as metrics_mod
from .log import Log


@dataclass
class Window:
    lo: float  # absolute log seconds
    hi: float  # absolute log seconds

    @property
    def duration(self) -> float:
        return max(self.hi - self.lo, 0.0)


@dataclass
class Run:
    log: Log
    window: Window
    label: str = ''
    cache: Dict = field(default_factory=dict, repr=False)

    @classmethod
    def whole(cls, log: Log, label: str = '') -> 'Run':
        lo, hi = log.bounds()
        return cls(log=log, window=Window(lo, hi), label=label or log.path.name)

    def in_window(self, series: List[Tuple[float, object]]) -> List[Tuple[float, object]]:
        """Filter a (t, v) series to this run's window (absolute-time domain, same as
        every series the parser produces)."""
        lo, hi = self.window.lo, self.window.hi
        return [(t, v) for t, v in series if lo <= t <= hi]

    def metric(self, metric_id: str, camera: Optional[str] = None):
        key = ('metric', metric_id, camera)
        if key not in self.cache:
            self.cache[key] = metrics_mod.METRICS[metric_id].compute(self, camera)
        return self.cache[key]

    def composite(self, composite_id: str, camera: Optional[str] = None):
        key = ('composite', composite_id, camera)
        if key not in self.cache:
            self.cache[key] = composites_mod.resolve(self, composite_id, camera)
        return self.cache[key]

    def value(self, id_: str, camera: Optional[str] = None):
        """Look up a metric or a composite by id, whichever is registered under it."""
        if id_ in composites_mod.COMPOSITES:
            return self.composite(id_, camera)
        return self.metric(id_, camera)
