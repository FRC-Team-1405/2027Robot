"""Finding data that is logged more than once.

Every entry lands in at most one bucket, in this order (see docs/wpilog-janitor-plan.md, "Duplicates"):

  1. constant           one distinct value for the whole window. Reported on its own, never as duplicates
                        of each other -- 200+ of an AdvantageKit log's ~300 entries are constants (zeroed
                        joystick axes, empty alert arrays) and they would all hash-match.
  2. exact duplicate    same type, identical sequence of values. `identical` if the timestamps match too,
                        `values` if the same data was logged at different instants.
  3. near duplicate     same type and record count, >= NEAR_THRESHOLD of the values equal position by position.

A group is `weak` when a member changed fewer than MIN_CHANGES times: two booleans that each flip once will
match by coincidence all the time. Weak groups are still returned (the UI tucks them away), never hidden.

Names only ever *propose* a pair: `/Pickup/VelocityRPS` and `/RealOutputs/Pickup/VelocityRPS` share a "name
key", but they are only reported as duplicates if their values match. A shared name with different values
is reported separately, as `Twin`s -- often more interesting than a duplicate.

Nothing here decides anything: it suggests a keeper and how much a group would recover; the user chooses.
"""
import re
from collections import defaultdict
from dataclasses import dataclass, field, replace
from typing import Collection, Dict, List, Optional, Sequence, Set, Tuple

from . import classify as cl
from .content import EntryStats, Range, collect_sequences

NEAR_THRESHOLD = 0.999
MIN_CHANGES = 6              # a match between series that changed fewer times than this is weak evidence
NEAR_MAX_BUCKET = 12          # do not compare more than this many candidates against each other
_NAME_KEY_PREFIX = re.compile(r'^(RealOutputs|ReplayOutputs|NT:[^/]*)/')


@dataclass
class DupGroup:
    id: str
    kind: str                       # 'identical' | 'values' | 'near'
    type: str
    members: List[int]              # entry ids
    keeper: int
    recoverable_bytes: int          # bytes of every member except the keeper
    evidence: str
    blocked: List[int] = field(default_factory=list)   # non-keepers that the chosen protection profiles cover
    weak: bool = False              # some member changed fewer than MIN_CHANGES times: two short series match by chance


@dataclass
class Twin:
    key: str
    members: List[int]
    relation: str                   # 'identical' | 'near' | 'different' | 'different-length'
    note: str


def name_key(name: str) -> str:
    """`/RealOutputs/Pickup/VelocityRPS` and `/Pickup/VelocityRPS` -> `Pickup/VelocityRPS`."""
    return _NAME_KEY_PREFIX.sub('', name.lstrip('/'), count=1)


def _rank(st: EntryStats) -> Tuple:
    """Lower is a better keeper: the replay-input side beats an output copy, then the shorter (less nested)
    name, then alphabetical."""
    cls = cl.classify(st.name, st.type)
    order = {cl.REPLAY_INPUT: 0, cl.STRUCTURAL: 0, cl.JANITOR: 0, cl.OUTPUT: 1}[cls]
    return (order, len(st.name), st.name)


def choose_keeper(ids: Sequence[int], stats: Dict[int, EntryStats]) -> int:
    return min(ids, key=lambda i: _rank(stats[i]))


def _blocked(ids: Sequence[int], keeper: int, stats: Dict[int, EntryStats], protect: Collection[str]) -> List[int]:
    return [i for i in ids if i != keeper and cl.protection(stats[i].name, stats[i].type, protect)]


def with_protection(groups: Sequence[DupGroup], stats: Dict[int, EntryStats], protect: Collection[str]) -> List[DupGroup]:
    """The same groups with `blocked` recomputed for another protection setting (grouping itself does not depend on it)."""
    return [replace(g, blocked=_blocked(g.members, g.keeper, stats, protect)) for g in groups]


def _group(kind: str, ids: List[int], stats: Dict[int, EntryStats], protect: Collection[str], evidence: str, n: int) -> DupGroup:
    keeper = choose_keeper(ids, stats)
    others = [i for i in ids if i != keeper]
    blocked = _blocked(ids, keeper, stats, protect)
    return DupGroup(
        id=f'{kind}-{n}', kind=kind, type=stats[keeper].type, members=sorted(ids, key=lambda i: _rank(stats[i])),
        keeper=keeper, recoverable_bytes=sum(stats[i].bytes for i in others), evidence=evidence, blocked=blocked,
        weak=min(stats[i].n_changes for i in ids) < MIN_CHANGES)


def constants(stats: Dict[int, EntryStats]) -> List[int]:
    return [i for i, s in stats.items() if s.constant]


def exact_groups(stats: Dict[int, EntryStats], protect: Collection[str]) -> List[DupGroup]:
    """Non-constant entries with identical value sequences."""
    by: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for i, s in stats.items():
        if s.n_records >= 2 and not s.constant:
            by[(s.type, s.seq_hash)].append(i)
    out: List[DupGroup] = []
    for (typ, _h), ids in by.items():
        if len(ids) < 2:
            continue
        same_times = len({stats[i].time_hash for i in ids}) == 1
        n = stats[ids[0]].n_records
        out.append(_group(
            'identical' if same_times else 'values', ids, stats, protect,
            f'all {n:,} values match' + (', at the same instants' if same_times else ', logged at different instants'),
            len(out)))
    out.sort(key=lambda g: -g.recoverable_bytes)
    return out


def _equal_fraction(a: List[int], b: List[int]) -> float:
    return sum(x == y for x, y in zip(a, b)) / len(a) if a and len(a) == len(b) else 0.0


def near_groups_and_twins(
    raw: bytes, header_end: int, stats: Dict[int, EntryStats], exact: List[DupGroup], protect: Collection[str],
    ranges: Optional[Sequence[Range]] = None,
) -> Tuple[List[DupGroup], List[Twin]]:
    """Near-duplicates, and entries that share a name key but not their data. One extra pass over the file, and
    only if there is something to compare."""
    in_exact: Dict[int, DupGroup] = {i: g for g in exact for i in g.members}
    by_key: Dict[str, List[int]] = defaultdict(list)
    for i, s in stats.items():
        by_key[name_key(s.name)].append(i)
    twin_sets = [(k, ids) for k, ids in by_key.items() if len(ids) > 1]

    buckets: Dict[Tuple, List[int]] = defaultdict(list)
    for i, s in stats.items():
        if s.n_records >= 2 and not s.constant and i not in in_exact:
            buckets[(s.type, s.n_records, s.distinct)].append(i)
    buckets = {k: v for k, v in buckets.items() if 2 <= len(v) <= NEAR_MAX_BUCKET}

    wanted: Set[int] = {i for v in buckets.values() for i in v}
    for _k, ids in twin_sets:
        wanted.update(i for i in ids if stats[i].n_records >= 2 and not stats[i].constant)
    seqs = collect_sequences(raw, header_end, wanted, ranges) if wanted else {}

    near: List[DupGroup] = []
    seen_pairs: Set[Tuple[int, int]] = set()
    for ids in buckets.values():
        parent = {i: i for i in ids}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        fractions: Dict[Tuple[int, int], float] = {}
        for a in range(len(ids)):
            for b in range(a + 1, len(ids)):
                f = _equal_fraction(seqs[ids[a]], seqs[ids[b]])
                fractions[(ids[a], ids[b])] = f
                seen_pairs.add((ids[a], ids[b]))
                if f >= NEAR_THRESHOLD:
                    parent[find(ids[a])] = find(ids[b])
        comps: Dict[int, List[int]] = defaultdict(list)
        for i in ids:
            comps[find(i)].append(i)
        for comp in comps.values():
            if len(comp) < 2:
                continue
            worst = min(f for (x, y), f in fractions.items() if x in comp and y in comp)
            n = stats[comp[0]].n_records
            near.append(_group('near', comp, stats, protect, f'{worst * 100:.2f}% of {n:,} values match', len(near)))
    near.sort(key=lambda g: -g.recoverable_bytes)

    twins: List[Twin] = []
    for key, ids in twin_sets:
        ids = sorted(ids, key=lambda i: _rank(stats[i]))
        a, b = ids[0], ids[1]
        sa, sb = stats[a], stats[b]
        if sa.seq_hash == sb.seq_hash and sa.type == sb.type and sa.n_records:
            rel, note = 'identical', 'same name and the same values'
        elif sa.n_records != sb.n_records or sa.type != sb.type:
            rel, note = 'different-length', f'{sa.n_records:,} vs {sb.n_records:,} records' + ('' if sa.type == sb.type else f' ({sa.type} vs {sb.type})')
        elif a in seqs and b in seqs:
            f = _equal_fraction(seqs[a], seqs[b])
            rel, note = ('near', f'{f * 100:.2f}% of values match') if f >= NEAR_THRESHOLD else ('different', f'only {f * 100:.1f}% of values match')
        else:
            rel, note = 'different', 'the values differ'
        twins.append(Twin(key, ids, rel, note))
    twins.sort(key=lambda t: (t.relation == 'identical', -sum(stats[i].bytes for i in t.members)))
    return near, twins
