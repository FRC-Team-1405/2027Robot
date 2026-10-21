"""Loading and validating health_checks.toml.

Strict on purpose: a misspelled field (`warn_abve = 70`) must be reported, not silently ignored,
or the check it was meant to guard would quietly never fire. A problem with one check never stops
the others: bad checks are skipped and listed in `errors`, which the page shows.

A check block (every field but id/section/label/signal is optional):

    [[check]]
    id = "rio.can_util"             # unique; used for latching and tests
    section = "roboRIO"             # the page's top-level heading
    group = "CAN bus"               # sub-heading inside the section; may use {1} {2} {name} ...
    subject = "{name}"              # optional: clusters rows about the same thing (one motor, one recorder)
    label = "CAN utilization"       # the row's name; same placeholders
    signal = "SystemStats/CANBus/Utilization"
    unit = "%"
    scale = 100                     # the value is multiplied by this for display and thresholds
    measure = "max"                 # how a log's samples collapse to one number (see MEASURES)
    q = 95                          # for percentile: which one (0-100)
    equals = "OK"                  # for seconds_equals / fraction_equals: the value that counts
    window = "enabled"              # which part of a log counts: all|enabled|auto|teleop|disabled
    warn_above = 70                 # numeric rules, applied to the scaled value
    fail_above = 90
    help = "Shown when you hover the row."

A `*` in `signal` matches one path segment, and one result is produced per match: `{1}` in the
group or label is what the first `*` matched, `{2}` the second. `lookup` pulls display text from
other signals of the same item:

    signal = "Power/Motors/*/SignalAgeSeconds"
    lookup = { name = "Power/Motors/{1}/Name", subsystem = "Power/Motors/{1}/Subsystem" }
    group  = "{subsystem}"
    label  = "{name}: signal age"

Rules (all optional; a check with none is informational and always OK):
    warn_above fail_above warn_below fail_below    numeric thresholds on the scaled value
    expect = true|false|<number>|"text"            the value must equal this
    expect_in = ["idle", "recording"]              the value must be one of these
    severity = "warn" | "fail"                     what an `expect` violation counts as (default fail)
    stale_after = 5                                live only: fail if the topic has not updated in N s
    missing = "nodata" | "ok" | "warn" | "fail"     what no data at all counts as (default nodata; use ok for
                                                   alerts, where nothing published means nothing wrong)
    expect_items = ["LeftCam", "RightCam"]         for `*` checks: these matches must exist
    mode = "both" | "live" | "log"                 where the check applies (default both)
"""
import dataclasses
import pathlib
from typing import Any, Dict, List, Optional, Tuple

try:  # tomllib is in the standard library from Python 3.11
    import tomllib
except ImportError:  # pragma: no cover - the project runs on 3.12+
    tomllib = None

MEASURES = (
    'last', 'first', 'max', 'min', 'mean',
    'seconds_above', 'seconds_below', 'seconds_true', 'seconds_false',
    'fraction_true', 'fraction_false', 'seconds_equals', 'fraction_equals', 'any_true', 'all_true',
    'changes', 'delta', 'max_len', 'last_len',
    'sample_mean', 'percentile', 'share_above',
)
# Measures over the records themselves, not sample-and-hold time: right for one-value-per-loop
# signals (loop time), where a time-weighted mean counts a 100 ms loop five times as much as a 20 ms one.
SAMPLE_MEASURES = ('sample_mean', 'percentile', 'share_above')
# Measures that need a log's history; in a live view they have nothing to measure.
HISTORY_MEASURES = ('seconds_above', 'seconds_below', 'seconds_true', 'seconds_false', 'seconds_equals',
                    'changes', 'delta') + SAMPLE_MEASURES
WINDOWS = ('all', 'enabled', 'auto', 'teleop', 'disabled')
MISSING = ('nodata', 'ok', 'warn', 'fail')
MODES = ('both', 'live', 'log')
SEVERITIES = ('warn', 'fail')

_NUMBER = (int, float)


@dataclasses.dataclass(frozen=True)
class CheckSpec:
    id: str
    section: str
    label: str
    signal: str
    group: str = ''
    subject: str = ''
    lookup: Tuple[Tuple[str, str], ...] = ()
    unit: str = ''
    scale: float = 1.0
    measure: str = 'last'
    window: str = 'all'
    above: Optional[float] = None
    q: Optional[float] = None
    below: Optional[float] = None
    equals: Any = None
    has_equals: bool = False
    warn_above: Optional[float] = None
    fail_above: Optional[float] = None
    warn_below: Optional[float] = None
    fail_below: Optional[float] = None
    expect: Any = None
    has_expect: bool = False
    expect_in: Tuple[str, ...] = ()
    severity: str = 'fail'
    stale_after: Optional[float] = None
    missing: str = 'nodata'
    expect_items: Tuple[str, ...] = ()
    mode: str = 'both'
    help: str = ''
    decimals: Optional[int] = None

    @property
    def has_rules(self) -> bool:
        return (any(getattr(self, f) is not None for f in ('warn_above', 'fail_above', 'warn_below', 'fail_below'))
                or self.has_expect or bool(self.expect_in) or self.stale_after is not None)


# field -> (accepted python types, validator or None)
_FIELDS: Dict[str, Tuple[tuple, Any]] = {
    'id': ((str,), None), 'section': ((str,), None), 'label': ((str,), None), 'signal': ((str,), None),
    'group': ((str,), None), 'subject': ((str,), None), 'lookup': ((dict,), None), 'unit': ((str,), None),
    'scale': (_NUMBER, None), 'measure': ((str,), MEASURES), 'window': ((str,), WINDOWS),
    'above': (_NUMBER, None), 'q': (_NUMBER, None), 'below': (_NUMBER, None), 'equals': ((bool, int, float, str), None),
    'warn_above': (_NUMBER, None), 'fail_above': (_NUMBER, None),
    'warn_below': (_NUMBER, None), 'fail_below': (_NUMBER, None),
    'expect': ((bool, int, float, str), None), 'expect_in': ((list,), None),
    'severity': ((str,), SEVERITIES), 'stale_after': (_NUMBER, None),
    'missing': ((str,), MISSING), 'expect_items': ((list,), None),
    'mode': ((str,), MODES), 'help': ((str,), None), 'decimals': ((int,), None),
}
_REQUIRED = ('id', 'section', 'label', 'signal')


def _build(raw: dict, defaults: dict) -> CheckSpec:
    """One check from its TOML table. Raises ValueError with a message naming the problem."""
    merged = {**defaults, **raw}
    ident = merged.get('id', '(no id)')
    for key in merged:
        if key not in _FIELDS:
            near = [f for f in _FIELDS if f.startswith(key[:4])] or list(_FIELDS)[:0]
            hint = f" (did you mean {', '.join(near[:3])}?)" if near else ''
            raise ValueError(f'{ident}: unknown field {key!r}{hint}')
    for key in _REQUIRED:
        if key not in merged:
            raise ValueError(f'{ident}: missing required field {key!r}')
    for key, value in merged.items():
        types, allowed = _FIELDS[key]
        if isinstance(value, bool) and bool not in types:
            raise ValueError(f'{ident}: {key} must not be true/false')
        if not isinstance(value, types):
            raise ValueError(f'{ident}: {key} has the wrong type ({type(value).__name__})')
        if isinstance(allowed, tuple) and value not in allowed:
            raise ValueError(f'{ident}: {key} must be one of {", ".join(allowed)} (got {value!r})')
    if merged.get('measure') == 'seconds_above' and 'above' not in merged:
        raise ValueError(f'{ident}: measure "seconds_above" needs an `above` value')
    if merged.get('measure') == 'share_above' and 'above' not in merged:
        raise ValueError(f'{ident}: measure "share_above" needs an `above` value')
    if merged.get('measure') == 'percentile' and not 0 <= merged.get('q', -1) <= 100:
        raise ValueError(f'{ident}: measure "percentile" needs `q` between 0 and 100')
    if merged.get('measure') == 'seconds_below' and 'below' not in merged:
        raise ValueError(f'{ident}: measure "seconds_below" needs a `below` value')
    if merged.get('measure') in ('seconds_equals', 'fraction_equals') and 'equals' not in merged:
        raise ValueError(f'{ident}: measure {merged["measure"]!r} needs an `equals` value')
    if 'expect' in merged and 'expect_in' in merged:
        raise ValueError(f'{ident}: use either expect or expect_in, not both')
    if merged.get('scale') == 0:
        raise ValueError(f'{ident}: scale must not be 0')
    if '*' not in merged['signal'] and merged.get('expect_items'):
        raise ValueError(f'{ident}: expect_items needs a `*` in signal')
    lookup = merged.get('lookup', {})
    for name, pattern in lookup.items():
        if not isinstance(pattern, str) or not name.isidentifier():
            raise ValueError(f'{ident}: lookup entries must be name = "signal path"')
    fields = {k: v for k, v in merged.items()
              if k not in ('lookup', 'expect', 'expect_in', 'expect_items', 'equals')}
    return CheckSpec(
        **fields,
        lookup=tuple(sorted(lookup.items())),
        expect=merged.get('expect'), has_expect='expect' in merged,
        equals=merged.get('equals'), has_equals='equals' in merged,
        expect_in=tuple(str(v) for v in merged.get('expect_in', ())),
        expect_items=tuple(str(v) for v in merged.get('expect_items', ())),
    )


def parse(text: str) -> Tuple[List[CheckSpec], List[str]]:
    """(valid checks, error messages) from TOML text."""
    if tomllib is None:
        return [], ['Python 3.11 or newer is needed to read health_checks.toml (tomllib is missing)']
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        return [], [f'health_checks.toml is not valid TOML: {exc}']
    errors: List[str] = []
    for key in data:
        if key not in ('defaults', 'check'):
            errors.append(f'unknown top-level entry {key!r} (only [defaults] and [[check]] are used)')
    defaults = data.get('defaults', {})
    if not isinstance(defaults, dict):
        errors.append('[defaults] must be a table')
        defaults = {}
    specs: List[CheckSpec] = []
    seen = set()
    for raw in data.get('check', []):
        try:
            spec = _build(raw, defaults)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if spec.id in seen:
            errors.append(f'{spec.id}: duplicate id')
            continue
        seen.add(spec.id)
        specs.append(spec)
    return specs, errors


_cache: Dict[str, Tuple[float, Tuple[List[CheckSpec], List[str]]]] = {}


def load(path) -> Tuple[List[CheckSpec], List[str]]:
    """parse() of a file, re-read whenever its modification time changes -- so editing the TOML
    takes effect on the next page refresh, with no server restart."""
    p = pathlib.Path(path)
    try:
        mtime = p.stat().st_mtime
    except OSError as exc:
        return [], [f'cannot read {p}: {exc}']
    hit = _cache.get(str(p))
    if hit and hit[0] == mtime:
        return hit[1]
    result = parse(p.read_text(encoding='utf-8'))
    _cache[str(p)] = (mtime, result)
    return result
