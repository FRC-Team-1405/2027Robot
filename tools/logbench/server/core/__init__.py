"""Generic metric/composite-score library over a parsed .wpilog.

Knows nothing about the web UI or the CLI — both are consumers of this package, not the
other way around (see server/cli.py and server/main.py). Vision is the primary use case
today (see the registrations at the bottom of metrics.py), but nothing in this package
name-checks "vision" or "camera": a future subsystem just registers its own Metric and
Composite entries.

Layers, bottom to top:
  signals.py     -- raw (t, value) series lookup helpers, shared with specs/.
  log.py         -- Log: a parsed .wpilog, plus DS-mode-span detection.
  runs.py        -- Run: a Log windowed to [lo, hi], with a memoized metric/composite cache.
  metrics.py     -- Metric: a named (run, camera) -> value function, registered by id.
  composites.py  -- Composite: a named function of other metrics/composites, registered
                     by id and resolved recursively so composites can build on composites.
  compare.py     -- window selection (DS-mode span or manual slice) + two-Run comparison.

Import `paths` (server/paths.py) before importing anything from this package outside of
server/ itself -- it puts vision_analyzer (whose parser and DS-mode-span logic this
package reuses rather than reimplementing) on sys.path.
"""
