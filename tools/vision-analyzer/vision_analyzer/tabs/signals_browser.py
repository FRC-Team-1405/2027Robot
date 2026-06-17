"""Signals browser tab: searchable index of all signals in the log."""
from collections import defaultdict
from typing import Any, List, Tuple

LABEL = "Signals"


def _truncate(value: Any, maxlen: int = 60) -> str:
    s = str(value)
    return s if len(s) <= maxlen else s[:maxlen - 3] + '...'


def render(ctx: dict) -> None:
    import streamlit as st

    signals = ctx['signals']

    st.caption('Raw signal index — for debugging')

    query = st.text_input('Filter signals', placeholder='e.g. Vision/Left or Accepted')
    q = query.strip().lower()

    # Group by top-level namespace
    by_ns: dict = defaultdict(list)
    for name, samples in sorted(signals.items()):
        ns = name.split('/')[0] if '/' in name else '(root)'
        typ = type(samples[0][1]).__name__ if samples else '?'
        count = len(samples)
        first_val = _truncate(samples[0][1]) if samples else ''
        last_val  = _truncate(samples[-1][1]) if samples else ''
        by_ns[ns].append({
            'Signal': name,
            'Type': typ,
            'Samples': count,
            'First value': first_val,
            'Last value': last_val,
        })

    # If a query is active, find which namespace has the first match
    first_match_ns = None
    if q:
        for ns in sorted(by_ns.keys()):
            rows = by_ns[ns]
            if any(q in row['Signal'].lower() for row in rows):
                first_match_ns = ns
                break

    for ns in sorted(by_ns.keys()):
        rows = by_ns[ns]

        # Filter rows if query is set
        if q:
            filtered = [r for r in rows if q in r['Signal'].lower()]
            if not filtered:
                continue
        else:
            filtered = rows

        expanded = (ns == first_match_ns) if q else False
        with st.expander(f'**{ns}** — {len(filtered)} signal{"s" if len(filtered) != 1 else ""}',
                         expanded=expanded):
            st.dataframe(
                filtered,
                width='stretch',
                hide_index=True,
            )
