"""0-100 severity bands for coloring any percentage-scored composite or metric.

Mirrors camera_calibration/health_display.severity_word. Duplicated rather than shared
because the dependency between the two tools only runs one way -- camera-calibration
imports logbench, not the reverse -- so logbench cannot import health_display without
creating a cycle. If the bands change, change both. specs/camera_health.py used to keep
its own second copy of these same three numbers on top of that; it now imports BANDS from
here instead, so there are two copies in the codebase rather than three.
"""
BANDS = [
    {'min': 80, 'color': '#2ecc71', 'label': 'good'},
    {'min': 40, 'color': '#e67e22', 'label': 'marginal'},
    {'min': 0, 'color': '#e74c3c', 'label': 'bad'},
]
