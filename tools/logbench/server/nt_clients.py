"""Health Check row for a finished log: which NetworkTables clients were connected while enabled.

Every dashboard (AdvantageScope, Elastic, LogBench's live Health Check) costs the roboRIO's
NetworkTables server CPU, so a loop-time A/B is only fair between logs with the same clients
connected. WPILib logs each client as SystemStats/NTClients/<name>@<id>/Connected, with a new id
on every reconnect; this folds the ids back into one name per client, so it is one row, not one
per reconnect.
"""
import re
from typing import Dict, List, Sequence, Tuple

from core import signals as sig
from health import engine

_KEY = re.compile(r'^SystemStats/NTClients/(.+?)(?:@\d+)?/Connected$')
# A client connected for at least this share of the enabled time counts as connected for it.
CONNECTED_SHARE = 0.5


def connected_share(signals: Dict, enabled: Sequence[Tuple[float, float]]) -> Dict[str, float]:
    """client name -> share of the enabled time it was connected (its best id, if it reconnected)."""
    total = sum(b - a for a, b in enabled)
    lo, hi = sig.bounds(signals)
    out: Dict[str, float] = {}
    if total <= 0:
        return out
    for key, series in signals.items():
        m = _KEY.match(key.lstrip('/'))
        if not m or not series:
            continue
        pieces = sig.clip_to_spans(sig.hold_intervals(series, lo, hi), list(enabled))
        share = sum(b - a for a, b, v in pieces if bool(v)) / total
        out[m.group(1)] = max(out.get(m.group(1), 0.0), share)
    return out


def for_log(signals: Dict, mode_spans, t0: float) -> List[dict]:
    enabled = sig.merge_spans(sorted((t0 + a, t0 + b) for a, b, m in mode_spans if m in ('auto', 'teleop')))
    shares = connected_share(signals, enabled)
    if not shares:
        return []
    names = sorted((n for n, s in shares.items() if s >= CONNECTED_SHARE), key=str.casefold)
    return [engine.make_row(
        id='rio.nt_clients', section='roboRIO', group='NetworkTables clients',
        label='Clients connected while enabled', status=engine.OK, value=float(len(names)),
        display=str(len(names)), rule='info only', detail=', '.join(names) or 'none',
        help='Clients connected for at least half the enabled time, reconnects folded together. Each '
             'dashboard costs the roboRIO CPU: compare loop times only between logs with the same list. '
             'Bench 2026-10-20: every subsystem\'s time rose about 15 %% together when LogBench joined.')]
