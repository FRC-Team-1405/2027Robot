"""Evaluating health checks against a signal source -- a finished log or a live NetworkTables view.

Two sources, one engine:

  LogSource      the parsed .wpilog (every signal is a sample-and-hold series). A check's `measure`
                 collapses the part of the log selected by its `window` (auto, teleop, enabled, ...)
                 to one number.
  SnapshotSource the latest value of every live topic, each with the age of its last update. A live
                 check just looks at the current value; measures that need history (seconds_above,
                 changes, delta) have nothing to look at and are reported as log-only.

Everything the page needs comes back in one plain-dict report: sections -> groups -> checks, each
carrying a status, a display value, the rule that was applied in words, and any detail worth
reading (when the worst value happened, what an alert said). Roll-ups take the worst child.
"""
import math
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from core import signals as sig

from .config import CheckSpec, HISTORY_MEASURES, SAMPLE_MEASURES

OK, WARN, FAIL, NODATA, NA = 'ok', 'warn', 'fail', 'nodata', 'na'
# na (does not apply here) < ok < nodata (could not tell) < warn < fail
RANK = {NA: -1, OK: 0, NODATA: 1, WARN: 2, FAIL: 3}

# A log's keys may carry AdvantageKit's RealOutputs/ prefix, or be a mirrored NetworkTables topic.
_PREFIXES = ('', 'RealOutputs/', 'NT:/')


_MISSING = {'nodata': NODATA, 'ok': OK, 'warn': WARN, 'fail': FAIL}


def worst(statuses: Iterable[str], default: str = NA) -> str:
    best = default
    for s in statuses:
        if RANK[s] > RANK[best]:
            best = s
    return best


# ── key matching ──────────────────────────────────────────────────────────────────────────────

def _pattern_regex(pattern: str) -> 're.Pattern':
    return re.compile('^' + '([^/]+)'.join(re.escape(part) for part in pattern.strip('/').split('*')) + '$')


class _Keys:
    """canonical key (no leading '/', no RealOutputs/ or NT:/ prefix) -> the real key in the source."""

    def __init__(self, real_keys: Iterable[str]):
        self.real: Dict[str, str] = {}
        for prefix in _PREFIXES:
            for key in real_keys:
                k = key.lstrip('/')
                if prefix and not k.startswith(prefix):
                    continue
                canonical = k[len(prefix):]
                self.real.setdefault(canonical, key)

    def match(self, pattern: str) -> List[Tuple[str, Tuple[str, ...]]]:
        """[(canonical key, captures)] in a stable order."""
        if '*' not in pattern:
            key = pattern.strip('/')
            return [(key, ())] if key in self.real else []
        rx = _pattern_regex(pattern)
        out = []
        for canonical in sorted(self.real):
            m = rx.match(canonical)
            if m:
                out.append((canonical, m.groups()))
        return out


# ── reduced values ────────────────────────────────────────────────────────────────────────────

class Reduced:
    """One check's measurement. `value` is a number, bool or string; None means no data."""

    def __init__(self, value: Any, at: Optional[float] = None, age: Optional[float] = None,
                 sample: Optional[str] = None, history_needed: bool = False):
        self.value = value
        self.at = at                  # seconds after log start of the extreme, when meaningful
        self.age = age                # live: seconds since the topic last updated
        self.sample = sample          # text worth showing (an alert's message)
        self.history_needed = history_needed


def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)) and math.isfinite(v):
        return float(v)
    return None


def _text(v: Any) -> Optional[str]:
    if isinstance(v, str):
        return v if v else None
    if isinstance(v, (list, tuple)):
        parts = [str(x) for x in v if str(x)]
        return '; '.join(parts) if parts else None
    return None


def _scalar(v: Any) -> Any:
    """A value as the check will judge and show it: bools stay bools, numbers must be finite
    (NaN means 'could not measure' and reads as no data), lists become their text."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    if isinstance(v, (list, tuple)):
        return _text(v) or ''
    return v


def _matches(v: Any, wanted: Any) -> bool:
    """Whether a sample equals the `equals` value of a check, comparing like with like."""
    if isinstance(wanted, bool):
        return isinstance(v, bool) and v == wanted or (not isinstance(v, str) and bool(v) == wanted and _num(v) is not None)
    if isinstance(wanted, (int, float)):
        n = _num(v)
        return n is not None and abs(n - float(wanted)) < 1e-9
    return str(v) == str(wanted)


def _length(v: Any) -> float:
    return float(len(v)) if isinstance(v, (str, list, tuple)) else 0.0


class LogSource:
    kind = 'log'

    def __init__(self, signals: Dict, spans: Sequence[Tuple[float, float, str]], t0: Optional[float] = None,
                 t1: Optional[float] = None):
        """`spans` are mode windows [(rel_start, rel_end, 'disabled'|'auto'|'teleop')] relative to
        the log's first record, as Log.mode_spans() gives them."""
        self.signals = signals
        lo, hi = sig.bounds(signals)
        self.t0 = lo if t0 is None else t0
        self.t1 = hi if t1 is None else t1
        self.spans = [(self.t0 + a, self.t0 + b, m) for a, b, m in spans]
        self.keys = _Keys(signals.keys())

    def match(self, pattern):
        return self.keys.match(pattern)

    def text(self, canonical: str) -> Optional[str]:
        series = self.signals.get(self.keys.real.get(canonical, ''))
        if not series:
            return None
        for _t, v in reversed(series):
            t = _text(v)
            if t is not None:
                return t
        return None

    def _window(self, window: str) -> Optional[List[Tuple[float, float]]]:
        if window == 'all':
            return [(self.t0, self.t1)]
        if not self.spans:
            return None
        wanted = {'enabled': ('auto', 'teleop'), 'auto': ('auto',), 'teleop': ('teleop',),
                  'disabled': ('disabled',)}[window]
        return sig.merge_spans(sorted((a, b) for a, b, m in self.spans if m in wanted))

    def reduce(self, canonical: str, spec: CheckSpec) -> Optional[Reduced]:
        series = self.signals.get(self.keys.real.get(canonical, ''))
        if not series:
            return None
        spans = self._window(spec.window)
        if spans is None:
            r = Reduced(None)
            r.sample = 'this log has no driver-station mode data, so "%s" cannot be selected' % spec.window
            return r
        if spec.measure in SAMPLE_MEASURES:
            # a record exactly at a window's end belongs to the next mode, as in the spans themselves
            values = [x for t, v in series if spec.window == 'all' or any(a <= t < b for a, b in spans)
                      for x in (_num(v),) if x is not None]
            return _reduce_samples(values, spec)
        pieces = sig.hold_intervals(series, self.t0, self.t1)
        if spec.window != 'all':
            pieces = sig.clip_to_spans(pieces, spans)
        if not pieces:
            return None
        return _reduce_pieces(pieces, spec, self.t0)


def _reduce_samples(values: List[float], spec: CheckSpec) -> Optional[Reduced]:
    """One number from the records inside the window, each record counted once."""
    if not values:
        return None
    if spec.measure == 'sample_mean':
        return Reduced(sum(values) / len(values))
    if spec.measure == 'share_above':
        return Reduced(sum(x > spec.above for x in values) / len(values))
    ordered = sorted(values)                     # percentile: nearest rank
    rank = max(1, math.ceil(spec.q / 100 * len(ordered)))
    return Reduced(ordered[rank - 1])


def _reduce_pieces(pieces: List[sig.Piece], spec: CheckSpec, t0: float) -> Reduced:
    measure = spec.measure
    total = sum(b - a for a, b, _ in pieces)
    nums = [(a, b, _num(v)) for a, b, v in pieces]
    nums = [(a, b, x) for a, b, x in nums if x is not None]

    def text_sample() -> Optional[str]:
        for _a, _b, v in reversed(pieces):
            t = _text(v)
            if t is not None:
                return t
        return None

    if measure == 'last':
        return Reduced(_scalar(pieces[-1][2]), sample=text_sample())
    if measure == 'first':
        return Reduced(_scalar(pieces[0][2]))
    if measure in ('max', 'min'):
        if not nums:
            return Reduced(None)
        pick = max if measure == 'max' else min
        a, _b, x = pick(nums, key=lambda p: p[2])
        return Reduced(x, at=a - t0)
    if measure == 'mean':
        pieces_n = [(a, b, x) for a, b, x in nums]
        value = sig.time_weighted_mean(pieces_n)
        return Reduced(value)
    if measure == 'seconds_above':
        return Reduced(sum(b - a for a, b, x in nums if x > spec.above))
    if measure == 'seconds_below':
        return Reduced(sum(b - a for a, b, x in nums if x < spec.below))
    if measure in ('seconds_true', 'fraction_true', 'seconds_false', 'fraction_false'):
        want = measure.endswith('true')
        secs = sum(b - a for a, b, v in pieces if bool(v) == want)
        return Reduced(secs / total if measure.startswith('fraction') and total > 0 else secs)
    if measure in ('seconds_equals', 'fraction_equals'):
        secs = sum(b - a for a, b, v in pieces if _matches(v, spec.equals))
        return Reduced(secs / total if measure == 'fraction_equals' and total > 0 else secs)
    if measure == 'any_true':
        return Reduced(any(bool(v) for _a, _b, v in pieces))
    if measure == 'all_true':
        return Reduced(all(bool(v) for _a, _b, v in pieces))
    if measure == 'changes':
        changes = 0
        for (_a1, _b1, v1), (_a2, _b2, v2) in zip(pieces, pieces[1:]):
            same = v1 == v2 or (isinstance(v1, float) and isinstance(v2, float) and v1 != v1 and v2 != v2)
            changes += 0 if same else 1
        return Reduced(float(changes))
    if measure == 'delta':
        if len(nums) < 1:
            return Reduced(None)
        return Reduced(nums[-1][2] - nums[0][2])
    if measure == 'max_len':
        return Reduced(max(_length(v) for _a, _b, v in pieces), sample=text_sample())
    if measure == 'last_len':
        return Reduced(_length(pieces[-1][2]), sample=text_sample())
    raise ValueError(measure)


class SnapshotSource:
    kind = 'live'

    def __init__(self, data: Dict[str, Tuple[Any, Optional[float]]]):
        """data: topic path -> (latest value, seconds since it last updated). Paths may carry a
        leading '/' and an AdvantageKit root; the page strips the root before building this."""
        self.data = data
        self.keys = _Keys(data.keys())

    def match(self, pattern):
        return self.keys.match(pattern)

    def text(self, canonical: str) -> Optional[str]:
        entry = self.data.get(self.keys.real.get(canonical, ''))
        return _text(entry[0]) if entry else None

    def reduce(self, canonical: str, spec: CheckSpec) -> Optional[Reduced]:
        entry = self.data.get(self.keys.real.get(canonical, ''))
        if entry is None:
            return None
        v, age = entry
        if spec.measure in HISTORY_MEASURES:
            return Reduced(None, age=age, history_needed=True)
        if spec.measure in ('any_true', 'all_true'):
            return Reduced(bool(v), age=age)
        if spec.measure in ('fraction_true', 'fraction_false'):
            return Reduced(1.0 if bool(v) == spec.measure.endswith('true') else 0.0, age=age)
        if spec.measure == 'fraction_equals':
            return Reduced(1.0 if _matches(v, spec.equals) else 0.0, age=age)
        if spec.measure in ('max_len', 'last_len'):
            return Reduced(_length(v), age=age, sample=_text(v))
        return Reduced(_scalar(v), age=age, sample=_text(v))


# ── formatting ────────────────────────────────────────────────────────────────────────────────

def _fmt_number(x: float, decimals: Optional[int]) -> str:
    if decimals is not None:
        return f'{x:.{decimals}f}'
    if x == int(x) and abs(x) < 1e6:
        return str(int(x))
    if abs(x) >= 100:
        return f'{x:.0f}'
    if abs(x) >= 10:
        return f'{x:.1f}'
    return f'{x:.2f}'


def display(value: Any, unit: str, decimals: Optional[int]) -> str:
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'yes' if value else 'no'
    if isinstance(value, (int, float)):
        text = _fmt_number(float(value), decimals)
        return f'{text} {unit}'.strip() if unit else text
    return str(value)


def rule_text(spec: CheckSpec) -> str:
    parts = []
    u = f' {spec.unit}' if spec.unit else ''
    if spec.warn_above is not None:
        parts.append(f'warn above {_fmt_number(spec.warn_above, None)}{u}')
    if spec.fail_above is not None:
        parts.append(f'fail above {_fmt_number(spec.fail_above, None)}{u}')
    if spec.warn_below is not None:
        parts.append(f'warn below {_fmt_number(spec.warn_below, None)}{u}')
    if spec.fail_below is not None:
        parts.append(f'fail below {_fmt_number(spec.fail_below, None)}{u}')
    if spec.has_expect:
        shown = ('yes' if spec.expect else 'no') if isinstance(spec.expect, bool) else spec.expect
        parts.append(f'expect {shown} ({"warn" if spec.severity == "warn" else "fail"} otherwise)')
    if spec.expect_in:
        parts.append('expect ' + ' or '.join(spec.expect_in) + f' ({spec.severity} otherwise)')
    if spec.stale_after is not None:
        parts.append(f'fail if silent over {_fmt_number(spec.stale_after, None)} s')
    return ', '.join(parts) if parts else 'info only'


_PLACEHOLDER = re.compile(r'\{(\d+|[A-Za-z_]\w*)\}')


def _fill(template: str, captures: Tuple[str, ...], lookups: Dict[str, str]) -> str:
    def sub(m):
        k = m.group(1)
        if k.isdigit():
            i = int(k) - 1
            return captures[i] if 0 <= i < len(captures) else m.group(0)
        return lookups.get(k, m.group(0))
    return _PLACEHOLDER.sub(sub, template)


# ── judging one value ─────────────────────────────────────────────────────────────────────────

def judge(spec: CheckSpec, reduced: Reduced) -> Tuple[str, Any, List[str]]:
    """(status, scaled value, detail strings) for a measurement that has data."""
    value = reduced.value
    status = OK
    detail: List[str] = []
    x = value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        x = float(value) * spec.scale
        if spec.fail_above is not None and x > spec.fail_above:
            status = FAIL
        elif spec.warn_above is not None and x > spec.warn_above:
            status = WARN
        if spec.fail_below is not None and x < spec.fail_below:
            status = FAIL
        elif spec.warn_below is not None and x < spec.warn_below and status != FAIL:
            status = WARN
    elif isinstance(value, bool) and spec.scale != 1.0:
        x = float(value) * spec.scale
    if spec.has_expect:
        if isinstance(spec.expect, bool):
            ok = bool(value) == spec.expect
        elif isinstance(spec.expect, (int, float)) and _num(value) is not None:
            ok = abs(_num(value) - spec.expect) < 1e-9
        else:
            ok = str(value) == str(spec.expect)
        if not ok:
            status = worst([status, FAIL if spec.severity == 'fail' else WARN], OK)
    if spec.expect_in and str(value) not in spec.expect_in:
        status = worst([status, FAIL if spec.severity == 'fail' else WARN], OK)
    if spec.stale_after is not None and reduced.age is not None and reduced.age > spec.stale_after:
        status = FAIL
        detail.append(f'last updated {reduced.age:.0f} s ago')
    if reduced.at is not None and status in (WARN, FAIL):
        detail.append(f'at {reduced.at:.1f} s into the log')
    if reduced.sample and not isinstance(value, str):
        detail.append(reduced.sample[:160])
    return status, x, detail


# ── latching (live) ───────────────────────────────────────────────────────────────────────────

class Latch:
    """Remembers, per check item, the worst status and most extreme value seen since the last reset,
    so a pit check that goes red for two seconds while the robot is enabled is not forgotten by the
    time you look at the screen."""

    def __init__(self):
        self.worst: Dict[str, str] = {}
        self.peak: Dict[str, float] = {}

    def reset(self):
        self.worst.clear()
        self.peak.clear()

    def update(self, key: str, status: str, value: Any, spec: CheckSpec) -> Tuple[str, Optional[float]]:
        if RANK[status] > RANK.get(self.worst.get(key, NA), -1):
            self.worst[key] = status
        self.worst.setdefault(key, status)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            upward = spec.warn_above is not None or spec.fail_above is not None
            downward = spec.warn_below is not None or spec.fail_below is not None
            if upward or downward:
                prev = self.peak.get(key)
                if prev is None or (upward and value > prev) or (not upward and downward and value < prev):
                    self.peak[key] = value
        return self.worst[key], self.peak.get(key)


# ── the report ────────────────────────────────────────────────────────────────────────────────

def _row(spec: CheckSpec, key: str, labels: Tuple[str, str, str], status: str, value: Any,
         detail: List[str]) -> Dict[str, Any]:
    label, group, subject = labels
    return {
        'id': spec.id, 'key': key, 'section': spec.section, 'group': group, 'subject': subject, 'label': label,
        'status': status, 'value': value if not isinstance(value, float) or math.isfinite(value) else None,
        'display': display(value, spec.unit, spec.decimals), 'unit': spec.unit,
        'rule': rule_text(spec), 'detail': '; '.join(detail), 'help': spec.help,
    }


def make_row(*, id: str, section: str, group: str, label: str, status: str, value: Any, display: str,
             unit: str = '', rule: str = '', detail: str = '', help: str = '', subject: str = '',
             key: Optional[str] = None) -> Dict[str, Any]:
    """A report row for something computed outside the TOML checks (the vision recording's coverage,
    which needs the bundle's files as well as the log). Same shape the checks produce."""
    return {'id': id, 'key': key or f'{id}|{group}', 'section': section, 'group': group, 'subject': subject,
            'label': label, 'status': status, 'value': value, 'display': display, 'unit': unit,
            'rule': rule, 'detail': detail, 'help': help}


def evaluate(specs: Sequence[CheckSpec], source, latch: Optional[Latch] = None,
             extra_rows: Sequence[Dict[str, Any]] = ()) -> Dict[str, Any]:
    """Run every check against `source`; returns the report dict. `extra_rows` (see make_row) are
    added to the report after the configured checks."""
    rows: List[Dict[str, Any]] = []
    for spec in specs:
        matches = source.match(spec.signal)
        if spec.mode != 'both' and spec.mode != source.kind:
            only = 'a live robot' if spec.mode == 'live' else 'a log'
            for key, caps in (matches or [(spec.signal, ())]):
                rows.append(_row(spec, key, _labels(spec, caps, source, key), NA, None,
                                 [f'only applies to {only}']))
            continue
        if not matches:
            status = _MISSING[spec.missing]
            rows.append(_row(spec, spec.signal, _labels(spec, (), source, spec.signal), status, None,
                             [_missing_reason(spec, source)]))
        for key, caps in matches:
            labels = _labels(spec, caps, source, key)
            reduced = source.reduce(key, spec)
            if reduced is not None and reduced.history_needed:
                rows.append(_row(spec, key, labels, NA, None,
                                 ['needs a log (looks at how the value changed over time)']))
                continue
            if reduced is None or reduced.value is None:
                status = _MISSING[spec.missing]
                note = (reduced.sample if reduced is not None and reduced.sample else
                        _missing_reason(spec, source, found=True))
                rows.append(_row(spec, key, labels, status, None, [note]))
                continue
            status, x, detail = judge(spec, reduced)
            rows.append(_row(spec, key, labels, status, x, detail))
        if spec.expect_items and '*' in spec.signal and matches:
            # Only when some items reported: a log with none of this kind of data at all (a plain
            # WPILib log has no vision signals) cannot say that an expected one is missing.
            have = {caps[0] for _k, caps in matches if caps}
            for name in spec.expect_items:
                if name in have:
                    continue
                status = {'nodata': FAIL, 'warn': WARN, 'fail': FAIL}[spec.missing]
                rows.append(_row(spec, spec.signal.replace('*', name, 1),
                                 _labels(spec, (name,), source, spec.signal), status, None,
                                 [f'expected {name} but it is not reporting']))
    rows.extend(extra_rows)
    if latch is not None:
        specs_by_id = {s.id: s for s in specs}
        for row in rows:
            if row['status'] == NA:
                continue
            k = row['id'] + '|' + row['key']
            w, peak = latch.update(k, row['status'], row['value'], specs_by_id[row['id']])
            row['worst'] = w
            if peak is not None and peak != row['value']:
                row['peak'] = peak
                row['peak_display'] = display(peak, row['unit'], specs_by_id[row['id']].decimals)
    return _assemble(rows, source)


def _missing_reason(spec: CheckSpec, source, found: bool = False) -> str:
    if spec.missing == 'ok':
        return 'none reported'
    if found:
        return 'no samples in the selected part of the log' if source.kind == 'log' else 'no value yet'
    if source.kind == 'log':
        return f'not in this log ({spec.signal})'
    return f'topic not published ({spec.signal})'


_UNRESOLVED = re.compile(r'\{[^}]*\}')


def _labels(spec: CheckSpec, caps: Tuple[str, ...], source, key: str) -> Tuple[str, str, str]:
    """(label, group, subject). Placeholders that nothing filled (a `*` check with no matches) read
    as '...', and such rows go to a shared 'No data' group instead of one per unfilled template."""
    lookups: Dict[str, str] = {}
    for name, pattern in spec.lookup:
        text = source.text(_fill(pattern, caps, {}).strip('/'))
        if text:
            lookups[name] = text
    label = _fill(spec.label, caps, lookups)
    group = _fill(spec.group, caps, lookups)
    subject = _fill(spec.subject, caps, lookups)
    if _UNRESOLVED.search(group + subject + label):
        group = 'No data' if _UNRESOLVED.search(group) else group
        label = _UNRESOLVED.sub('...', label)
        subject = _UNRESOLVED.sub('...', subject)
    return label, group, subject


def _assemble(rows: List[Dict[str, Any]], source) -> Dict[str, Any]:
    sections: List[Dict[str, Any]] = []
    by_section: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        sec = by_section.get(row['section'])
        if sec is None:
            sec = {'id': row['section'], 'label': row['section'], 'groups': [], '_by_group': {}}
            by_section[row['section']] = sec
            sections.append(sec)
        grp = sec['_by_group'].get(row['group'])
        if grp is None:
            grp = {'label': row['group'], 'subjects': [], '_by_subject': {}}
            sec['_by_group'][row['group']] = grp
            sec['groups'].append(grp)
        sub = grp['_by_subject'].get(row['subject'])
        if sub is None:
            sub = {'label': row['subject'], 'checks': []}
            grp['_by_subject'][row['subject']] = sub
            grp['subjects'].append(sub)
        sub['checks'].append(row)
    counts = {OK: 0, WARN: 0, FAIL: 0, NODATA: 0, NA: 0}
    for sec in sections:
        del sec['_by_group']
        for grp in sec['groups']:
            del grp['_by_subject']
            for sub in grp['subjects']:
                sub['status'] = worst(c['status'] for c in sub['checks'])
                sub['counts'] = _counts(sub['checks'])
            grp['status'] = worst(s['status'] for s in grp['subjects'])
            grp['counts'] = _counts(c for s in grp['subjects'] for c in s['checks'])
        sec['status'] = worst(g['status'] for g in sec['groups'])
        sec['counts'] = _counts(c for g in sec['groups'] for s in g['subjects'] for c in s['checks'])
    for row in rows:
        counts[row['status']] += 1
    overall = worst(r['status'] for r in rows)
    verdict = {FAIL: 'fail', WARN: 'warn', NODATA: 'incomplete'}.get(overall, 'ok' if rows else 'empty')
    return {'kind': source.kind, 'verdict': verdict, 'counts': counts, 'sections': sections}


def _counts(rows: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    out = {OK: 0, WARN: 0, FAIL: 0, NODATA: 0, NA: 0}
    for r in rows:
        out[r['status']] += 1
    return out
