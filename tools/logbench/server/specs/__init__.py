"""Registry of spec builders.

A builder is `build(signals, title=...) -> (PlayerSpec, data)`. To add a new kind of
match playback, write a module beside camera_health.py exposing NAME, LABEL and build,
then register it here. Nothing else in the tool changes.
"""
from . import camera_health

BUILDERS = {
    camera_health.NAME: camera_health,
}

DEFAULT = camera_health.NAME


def get(name: str):
    if name not in BUILDERS:
        raise KeyError(
            'unknown spec %r (have: %s)' % (name, ', '.join(sorted(BUILDERS)))
        )
    return BUILDERS[name]


def listing() -> list:
    return [{'name': m.NAME, 'label': m.LABEL} for m in BUILDERS.values()]
