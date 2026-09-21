"""Where the bytes are: rollups of a LogIndex's per-entry sizes by path prefix."""
from dataclasses import dataclass
from typing import Dict, List

from wpilog_utils.index import LogIndex


@dataclass
class Rollup:
    prefix: str          # e.g. '/Vision/Left' ('/' = whole log)
    bytes: int
    records: int
    entries: int


def rollup(index: LogIndex, depth: int) -> List[Rollup]:
    """Group entries by their first `depth` path components, largest first. Entries shallower than
    `depth` are grouped under their own full name."""
    groups: Dict[str, Rollup] = {}
    for e in index.entries.values():
        parts = [p for p in e.name.split('/') if p]
        key = '/' + '/'.join(parts[:depth])
        g = groups.setdefault(key, Rollup(key, 0, 0, 0))
        g.bytes += e.bytes
        g.records += e.n_records
        g.entries += 1
    return sorted(groups.values(), key=lambda g: g.bytes, reverse=True)


def top_entries(index: LogIndex, n: int):
    return sorted(index.entries.values(), key=lambda e: e.bytes, reverse=True)[:n]


def human(n: float) -> str:
    for unit in ('B', 'KB', 'MB', 'GB'):
        if abs(n) < 1024 or unit == 'GB':
            return f'{n:.0f} {unit}' if unit == 'B' else f'{n:.1f} {unit}'
        n /= 1024
    return f'{n} B'
