"""
Tab registry. TABS is the single source of truth for render order.
Adding a new tab: create a module with LABEL and render(ctx), then append it here.
"""
from . import summary, health, acceptance, geometry, field_coverage, motion, signals_browser, export

TABS = [
    summary,
    health,
    acceptance,
    geometry,
    field_coverage,
    motion,
    signals_browser,
    export,
]
