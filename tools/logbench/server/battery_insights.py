"""Battery Insights: the conclusions, and the evidence behind them.

battery.analyze() measures (step-held integrals, per-motor accounting, the timeline the page draws). This
module turns a log into what a person or an LLM wants from a match: the match context, how the battery
held up, every dip below the brownout threshold or the warning level, and what was drawing current when
it happened. It works on legacy logs too: current signals are found by name, whatever subsystem wrote
them and whether they are supply, stator or torque current -- so the plain WPILib competition logs
(FRC_*.wpilog, SmartDashboard values mirrored under NT:) get the same insights as AdvantageKit logs.

Everything here is small on purpose: the exports carry these insights plus a little evidence around each
dip, never the whole log.
"""
import bisect
import math
import re
import statistics

SCHEMA = 'logbench.battery-insights/v2'
DEFAULT_BROWNOUT_V = 6.75          # roboRIO 2 default, used when the log does not record its threshold
EPISODE_MERGE_S = 1.0              # dips closer than this are one episode
CONTRIBUTOR_LEAD_S = 0.5           # what drove a dip is looked for from this long before it starts
STALE_S = 0.5                      # a reading older than this at the moment of a dip is marked as old
EVIDENCE_PAD_S = 1.0               # evidence kept either side of an episode
EVIDENCE_MAX_POINTS = 60           # per signal, per episode
VOLTAGE_LEVELS = (10.0, 9.0, 8.0, 7.0)
RECOVERY_CHECKPOINTS_S = (10, 30, 60, 120)   # voltage after the match, each a 5 s median around the checkpoint
RECOVERY_FIT_MAX_S = 300                     # recovery curve fitted over at most this long after the match
RECOVERY_FIT_MIN_S = 30                      # ... and only with at least this much of it
TOP_CONTRIBUTORS = 5
MIN_CONTRIBUTOR_A = 5.0

_CURRENT = re.compile(r'(supply|stator|torque)?current(amps)?(_\d+)?$', re.I)
_NOT_A_LOAD = re.compile(r'cumulative|total|limit|requested|threshold|setpoint|reference', re.I)
_PREFIXES = ('NT:/SmartDashboard/', 'SmartDashboard/', 'RealOutputs/', 'NT:/')
_MATCH_TYPES = {0: None, 1: 'Practice', 2: 'Qualification', 3: 'Elimination'}


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


class _Series:
    def __init__(self, samples):
        self.samples = sorted((p for p in samples), key=lambda p: p[0])
        self.times = [p[0] for p in self.samples]

    def index_at(self, t):
        return bisect.bisect_right(self.times, t) - 1

    def at(self, t):
        i = self.index_at(t)
        return self.samples[i][1] if i >= 0 else None

    def between(self, a, b):
        i, j = bisect.bisect_left(self.times, a), bisect.bisect_right(self.times, b)
        return self.samples[i:j]


def _clean(key):
    for p in _PREFIXES:
        if key.startswith(p):
            return key[len(p):].lstrip('/')
    return key.lstrip('/')


def _last(signals, *keys):
    for k in keys:
        for _t, v in reversed(signals.get(k, [])):
            if v not in (None, ''):
                return v
    return None


def current_signals(signals):
    """Every numeric current signal in the log, found by name: [{key, name, group, kind, series}]."""
    out, seen = [], set()
    for key in sorted(signals):
        name = _clean(key)
        leaf = name.rsplit('/', 1)[-1]
        if not _CURRENT.search(leaf) or _NOT_A_LOAD.search(leaf) or name in seen:
            continue
        samples = [(t, float(v)) for t, v in signals[key] if _number(v)]
        if not samples:
            continue
        seen.add(name)
        kind = next((k for k in ('supply', 'stator', 'torque') if k in leaf.lower()), 'current')
        group = name.split('/', 1)[0]
        m = re.match(r'^Power/Motors/([^/]+)/', name)
        if m:                                   # new-schema motors carry their own name and subsystem
            base = key[:key.index('Power/Motors/')] + f'Power/Motors/{m.group(1)}/'
            motor = _last(signals, base + 'Name') or m.group(1)
            group = _last(signals, base + 'Subsystem') or 'Unknown'
            name = f'{motor} · {leaf}'
        out.append({'key': key, 'name': name, 'group': str(group), 'kind': kind, 'series': _Series(samples)})
    return out


def _true_spans(series_at, times, intervals):
    """[(a, b)] inside intervals where series_at(t) is True, step-held between the given change times."""
    spans = []
    for a, b in intervals:
        points = sorted({a, b, *(t for t in times if a < t < b)})
        for lo, hi in zip(points, points[1:]):
            if series_at(lo) is True:
                if spans and spans[-1][1] == lo and spans[-1][2] == a:
                    spans[-1][1] = hi
                else:
                    spans.append([lo, hi, a])
    return spans


def _merge(spans, gap):
    """Merge spans closer than `gap`, never across a trim seam (spans carry their interval start)."""
    out = []
    for lo, hi, seg in spans:
        if out and out[-1][2] == seg and lo - out[-1][1] < gap:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi, seg])
    return [(lo, hi) for lo, hi, _ in out]


def _resting(voltage, spans, t0, before):
    """Median voltage while disabled right before the first enabled period (last 10 s of it) or after
    the last one (from 3 s after disabling, up to 20 s). None when the log has no such period."""
    enabled = [(lo, hi) for lo, hi, m in spans if m in ('auto', 'teleop')]
    if not enabled:
        return None
    if before:
        disabled = [(lo, hi) for lo, hi, m in spans if m == 'disabled' and hi <= enabled[0][0] + 1e-6]
        if not disabled:
            return None
        lo, hi = disabled[-1]
        a, b = max(lo, hi - 10), hi
    else:
        disabled = [(lo, hi) for lo, hi, m in spans if m == 'disabled' and lo >= enabled[-1][1] - 1e-6]
        if not disabled:
            return None
        lo, hi = disabled[0]
        a, b = lo + 3, min(hi, lo + 23)
    values = [v for _t, v in voltage.between(t0 + a, t0 + b) if _number(v) and v > 0]
    return statistics.median(values) if values else None


def _recovery(voltage, spans, t0):
    """How the battery recovered after the last enabled period, while disabled: the voltage when the load
    stopped, the bounce in the first seconds, the voltage at fixed checkpoints, and a fitted recovery curve
    V(t) = V_rest - A*exp(-t/tau). None when the log has no disabled time after the match.

    The fit is exploratory: internal resistance is the established battery-health measure, but how fast a
    battery recovers may also say something about its charge and health, so it is recorded to compare
    across batteries and matches."""
    enabled = [(a, b) for a, b, m in spans if m in ('auto', 'teleop')]
    if not enabled:
        return None
    end = enabled[-1][1]
    after = next(((a, b) for a, b, m in spans if m == 'disabled' and a >= end - 1e-6), None)
    if after is None:
        return None
    te = t0 + end
    samples = [(t - te, v) for t, v in voltage.between(te, t0 + after[1])]
    if not samples:
        return None
    observed = samples[-1][0]

    def med(a, b):
        vs = [v for t, v in samples if a <= t < b]
        return statistics.median(vs) if vs else None

    before = [v for _t, v in voltage.between(te - 1, te)]
    load_end = statistics.median(before) if before else None
    points = [{'after_s': c, 'voltage': _r(med(c - 2.5, c + 2.5))} for c in RECOVERY_CHECKPOINTS_S
              if c + 2.5 <= observed and med(c - 2.5, c + 2.5) is not None]
    early = med(2, 4)
    fit = _fit_recovery([(t, v) for t, v in samples if 2 <= t <= RECOVERY_FIT_MAX_S])
    return {'load_end_v': _r(load_end), 'rebound_3s_v': _r(early - load_end) if early is not None and load_end is not None else None,
            'points': points, 'observed_s': _r(observed, 1), **fit}


def _fit_recovery(samples):
    """Least-squares V(t) = V_rest - A*exp(-t/tau) over 1 s medians; tau by a log-spaced search. Unreliable
    fits (too little data, not recovering, or tau at the edge of the search) report None."""
    none = {'tau_s': None, 'projected_rest_v': None, 'fit_rms_v': None}
    if not samples or samples[-1][0] - samples[0][0] < RECOVERY_FIT_MIN_S:
        return none
    buckets = {}
    for t, v in samples:
        buckets.setdefault(int(t), []).append(v)
    pts = [(k + 0.5, statistics.median(vs)) for k, vs in sorted(buckets.items())]
    best = None
    taus = [2 * (300 / 2) ** (i / 59) for i in range(60)]          # 2 s .. 300 s
    for tau in taus:
        xs = [math.exp(-t / tau) for t, _v in pts]
        n = len(pts)
        mx, my = sum(xs) / n, sum(v for _t, v in pts) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        if sxx <= 0:
            continue
        slope = sum((x - mx) * (v - my) for x, (_t, v) in zip(xs, pts)) / sxx
        c0 = my - slope * mx
        sse = sum((c0 + slope * x - v) ** 2 for x, (_t, v) in zip(xs, pts))
        if best is None or sse < best[0]:
            best = (sse, tau, c0, -slope, n)
    if best is None:
        return none
    sse, tau, rest, amp, n = best
    if amp <= 0 or tau in (taus[0], taus[-1]):
        return none
    return {'tau_s': _r(tau, 1), 'projected_rest_v': _r(rest), 'fit_rms_v': _r(math.sqrt(sse / n), 3)}


def _decimate(points, limit):
    if len(points) <= limit:
        return points
    step = len(points) / limit
    picked = [points[int(i * step)] for i in range(limit)]
    lowest = min(points, key=lambda p: p[1])          # never lose the dip itself
    if lowest not in picked:
        picked.append(lowest)
    return sorted(picked)


def _load(kind, v):
    """How much load a reading represents. Stator and torque current carry a direction (motoring vs braking),
    so their size is the load; supply current is signed, and negative supply is current returned to the battery."""
    return v if kind == 'supply' else abs(v)


def _changes(samples):
    out = []
    for t, v in samples:
        if not out or out[-1][1] != v:
            out.append((t, v))
    return out


def _r(x, n=2):
    return round(x, n) if _number(x) else None


def build(log, lo, hi, intervals, voltage_samples, voltage_source, threshold_samples, flag_samples, warning,
          measured=None):
    """The insights for [lo, hi] (seconds from log start). `intervals` are the valid absolute-time pieces
    (trim seams and heartbeat gaps removed); the rest are raw [(t, value)] from the log."""
    s = log.signals
    t0 = log.bounds()[0]
    spans = log.mode_spans()
    voltage = _Series([(t, v) for t, v in voltage_samples if _number(v) and v > 0])
    threshold = _Series([(t, v) for t, v in threshold_samples if _number(v)])
    flag = _Series([(t, v) for t, v in flag_samples if isinstance(v, bool)])
    thr_logged = bool(threshold.samples)

    def thr(t):
        v = threshold.at(t)
        return v if _number(v) else (threshold.samples[0][1] if thr_logged else DEFAULT_BROWNOUT_V)

    def below_warning(t):
        v = voltage.at(t)
        return (v < warning) if _number(v) else None

    def browned_out(t):
        v = voltage.at(t)
        if flag.at(t) is True or (_number(v) and v < thr(t)):
            return True
        return False if (_number(v) or flag.at(t) is False) else None

    change_times = sorted(set(voltage.times + threshold.times + flag.times))
    duration = sum(b - a for a, b in intervals)
    covered = sum(b - a for a, b, _ in _true_spans(lambda t: _number(voltage.at(t)) or flag.at(t) is not None,
                                                   change_times, intervals))
    brown_spans = _true_spans(browned_out, change_times, intervals)
    low_spans = _true_spans(below_warning, change_times, intervals)
    brownouts = _merge(brown_spans, EPISODE_MERGE_S)
    lows = _merge(low_spans, EPISODE_MERGE_S)
    below = {}
    for level in VOLTAGE_LEVELS:
        below[f'{level:g}'] = sum(b - a for a, b, _ in _true_spans(
            lambda t, level=level: (voltage.at(t) < level) if _number(voltage.at(t)) else None, voltage.times, intervals))

    in_window = [(t, v) for a, b in intervals for t, v in voltage.between(a, b)]
    t_min, v_min = min(in_window, key=lambda p: p[1]) if in_window else (None, None)

    period = _Series(s.get('NT:/GamePeriod/Period') or s.get('GamePeriod/Period') or [])

    def period_at(t):
        label = period.at(t)
        if isinstance(label, str) and label:
            return label
        rel = t - t0
        return next((m for a, b, m in spans if a <= rel < b), None)

    loads = current_signals(s)

    def contributors(a, b, t_ref):
        rows = []
        for ld in loads:
            ser = ld['series']
            held = ser.at(a - CONTRIBUTOR_LEAD_S)
            values = [_load(ld['kind'], v) for _t, v in ser.between(a - CONTRIBUTOR_LEAD_S, b + 0.1)]
            if _number(held):
                values.append(_load(ld['kind'], held))
            if not values:
                continue
            peak = max(values)
            if peak < MIN_CONTRIBUTOR_A:
                continue
            i = ser.index_at(t_ref)
            age = t_ref - ser.times[i] if i >= 0 else None
            rows.append({'name': ld['name'], 'kind': ld['kind'], 'group': ld['group'], 'peak_a': _r(peak, 1),
                         'reading_age_s': _r(age), 'stale': age is None or age > STALE_S, 'key': ld['key']})
        rows.sort(key=lambda r: -r['peak_a'])
        return rows[:TOP_CONTRIBUTORS]

    def episode(a, b):
        pts = voltage.between(a, b) or [(a, voltage.at(a))]
        tm, vm = min(((t, v) for t, v in pts if _number(v)), key=lambda p: p[1], default=(a, None))
        brown_s = sum(min(hi, b) - max(lo, a) for lo, hi, _ in brown_spans if lo < b and hi > a)
        contrib = contributors(a, b, tm)
        ev = {'voltage': [[_r(t - t0, 3), _r(v)] for t, v in
                          _decimate(_changes(voltage.between(a - EVIDENCE_PAD_S, b + EVIDENCE_PAD_S)), EVIDENCE_MAX_POINTS)]}
        for c in contrib[:3]:
            ser = next(ld['series'] for ld in loads if ld['key'] == c['key'])
            ev[c['name']] = [[_r(t - t0, 3), _r(_load(c['kind'], v), 1)] for t, v in
                             _decimate(_changes(ser.between(a - EVIDENCE_PAD_S, b + EVIDENCE_PAD_S)), EVIDENCE_MAX_POINTS)]
        for c in contrib:
            del c['key']
        return {'start': _r(a - t0, 3), 'end': _r(b - t0, 3), 'duration_s': _r(b - a, 3),
                'min_voltage': _r(vm), 'at': _r(tm - t0, 3), 'brownout': brown_s > 0, 'brownout_s': _r(brown_s, 3),
                'period': period_at(tm), 'contributors': contrib, 'evidence': ev}

    episodes = [episode(a, b) for a, b in lows]

    # per-signal load table, with the peak each reached during the dips
    load_rows = []
    for ld in loads:
        ser = ld['series']
        vals = [_load(ld['kind'], v) for a, b in intervals for _t, v in ser.between(a, b)]
        if not vals:
            continue
        area = total = 0.0
        for a, b in intervals:
            pts = sorted({a, b, *(t for t in ser.times if a < t < b)})
            for p, q in zip(pts, pts[1:]):
                v = ser.at(p)
                if _number(v):
                    area += _load(ld['kind'], v) * (q - p)
                    total += q - p
        during = [_load(ld['kind'], v) for a, b in lows for _t, v in ser.between(a - CONTRIBUTOR_LEAD_S, b + 0.1)]
        load_rows.append({'name': ld['name'], 'group': ld['group'], 'kind': ld['kind'],
                          'peak_a': _r(max(vals), 1), 'average_a': _r(area / total if total else None, 1),
                          'peak_during_dips_a': _r(max(during), 1) if during else None,
                          'samples_per_s': _r(len(vals) / duration if duration else None, 1), 'source': ld['key']})
    load_rows.sort(key=lambda r: -r['peak_a'])

    # 1 s minimum-voltage profile: enough to draw the match and to reason about it, a few hundred numbers
    # (None where the log has no valid data: a trim seam or a telemetry gap is not held flat)
    # Every voltage sample counts here, inside the analysed periods or not: a log trimmed with the match
    # context kept still shows the battery before and after.
    profile = []
    if voltage.samples:
        for k in range(int(math.ceil(hi - lo))):
            vs = [v for _t, v in voltage.between(t0 + lo + k, t0 + lo + k + 1)]
            profile.append(_r(min(vs)) if vs else None)

    context = _context(s, log)
    resting_before = _resting(voltage, spans, t0, True)
    recovery = _recovery(voltage, spans, t0)
    latest = recovery['points'][-1] if recovery and recovery['points'] else None
    resting_after = latest['voltage'] if latest else None
    if recovery is not None:
        recovery['drop_v'] = _r(resting_before - resting_after) if resting_before is not None and resting_after is not None else None
        recovery['drop_measured_after_s'] = latest['after_s'] if latest else None

    def edge(a, b):
        vs = [v for _t, v in voltage.between(a, b)]
        return statistics.median(vs) if vs else None
    at_start = edge(t0 + lo, t0 + lo + 2) if intervals else None
    at_end = edge(t0 + hi - 2, t0 + hi) if intervals else None
    # Disabled stretches between two enabled periods (e.g. an A-Stop, or a gap between auto and teleop):
    # how long, and what the battery recovered to with nothing drawing.
    enabled = [(a, b) for a, b, m in spans if m in ('auto', 'teleop')]
    pauses = []
    for a, b, m in spans:
        if m == 'disabled' and b - a >= 3 and enabled and enabled[0][1] <= a and b <= enabled[-1][0] and lo <= a and b <= hi:
            vs = [v for _t, v in voltage.between(t0 + a + 1, t0 + b)]
            pauses.append({'start': _r(a, 3), 'end': _r(b, 3), 'seconds': _r(b - a, 1),
                           'resting_voltage': _r(statistics.median(vs)) if vs else None})
    result = {
        'schema': SCHEMA,
        'context': {**context, 'window': [_r(lo, 3), _r(hi, 3)],
                    'periods': _periods(period, spans, t0, lo, hi)},
        'voltage': {'source': voltage_source, 'resting_before': _r(resting_before), 'resting_after': _r(resting_after),
                    'recovery': recovery,
                    'window_start': _r(at_start), 'window_end': _r(at_end), 'disabled_pauses': pauses,
                    'minimum': _r(v_min), 'minimum_at': _r(t_min - t0, 3) if t_min is not None else None,
                    'seconds_below': {k: _r(v, 2) for k, v in below.items()},
                    'brownout_threshold': _r(thr(t0 + lo)), 'brownout_threshold_logged': thr_logged,
                    'warning': warning, 'coverage': _r(covered / duration if duration else 0, 3),
                    'profile_1s_min': profile},
        'brownouts': {'count': len(brownouts), 'seconds': _r(sum(b - a for a, b, _ in brown_spans), 3)} if covered else
                     {'count': None, 'seconds': None},
        'low_voltage': {'count': len(lows), 'seconds': _r(sum(b - a for a, b, _ in low_spans), 3)} if voltage.samples else
                       {'count': None, 'seconds': None},
        'episodes': episodes,
        'loads': load_rows,
        'measured_motor_draw': measured,
    }
    result['findings'] = _findings(result)
    return result


def _context(s, log):
    event = _last(s, 'NT:/FMSInfo/EventName', 'DriverStation/EventName')
    number = _last(s, 'NT:/FMSInfo/MatchNumber', 'DriverStation/MatchNumber')
    mtype = _last(s, 'NT:/FMSInfo/MatchType', 'DriverStation/MatchType')
    if isinstance(mtype, (int, float)):
        mtype = _MATCH_TYPES.get(int(mtype))
    red = _last(s, 'NT:/FMSInfo/IsRedAlliance')
    station = _last(s, 'NT:/FMSInfo/StationNumber')
    alliance = _last(s, 'DriverStation/AllianceStation')
    if alliance is None and red is not None:
        alliance = ('Red' if red else 'Blue') + (f' {int(station)}' if _number(station) else '')
    akit = any(k.startswith(('RealOutputs/', 'DriverStation/')) for k in s)
    kind = 'AdvantageKit' if akit else 'WPILib DataLogManager' if any(k.startswith('NT:') for k in s) else 'Unknown'
    return {'log': log.path.name, 'log_kind': kind, 'event': event or None,
            'match': f'{mtype} {int(number)}' if mtype and _number(number) and number else None,
            'alliance': alliance}


def _periods(period, spans, t0, lo, hi):
    out = [{'label': m, 'start': _r(a, 3), 'end': _r(b, 3)} for a, b, m in spans if b > lo and a < hi]
    for (t, label), nxt in zip(period.samples, period.samples[1:] + [(None, None)]):
        end = (nxt[0] - t0) if nxt[0] is not None else hi
        if isinstance(label, str) and label and end > lo and t - t0 < hi:
            out.append({'label': label, 'start': _r(t - t0, 3), 'end': _r(end, 3)})
    return out


def _ago(seconds):
    return f'{seconds / 60:g} min' if seconds >= 60 and seconds % 60 == 0 else f'{seconds:g} s'


def _findings(r):
    v, out = r['voltage'], []
    rec = v.get('recovery')
    if v['resting_before'] is not None or v['resting_after'] is not None:
        parts = []
        if v['resting_before'] is not None:
            parts.append(f"{v['resting_before']:.2f} V at rest before the match")
        if rec and rec['points']:
            parts.append('after it ' + ', '.join(f"{p['voltage']:.2f} V at {_ago(p['after_s'])}" for p in rec['points']))
        line = '; '.join(parts) + '.'
        if rec and rec.get('drop_v') is not None:
            after = rec['drop_measured_after_s']
            line += f" A {rec['drop_v']:.2f} V drop, measured {_ago(after)} after"
            line += (' (it was still recovering then, so this overstates the drop; keep more time after the match to '
                     'measure it settled).' if after < 60 else '.')
        out.append(line[0].upper() + line[1:])
    elif v['window_start'] is not None and v['window_end'] is not None:
        out.append(f"Voltage {v['window_start']:.2f} V at the start of this window and {v['window_end']:.2f} V at the end "
                   '(no disabled time before or after the enabled period to measure the battery at rest).')
    if rec and rec.get('tau_s') is not None:
        line = 'After the match the battery recovered with a time constant of about '
        line += f"{rec['tau_s']:.0f} s toward {rec['projected_rest_v']:.2f} V"
        if rec.get('load_end_v') is not None and rec.get('rebound_3s_v') is not None:
            line += (f" (from {rec['load_end_v']:.2f} V under the last load and "
                     f"{rec['load_end_v'] + rec['rebound_3s_v']:.2f} V 3 s after it came off)")
        out.append(line + '. Exploratory: compare it across batteries and matches.')
    for p in v['disabled_pauses']:
        out.append(f"Disabled for {p['seconds']:.1f} s between enabled periods ({p['start']:.1f}–{p['end']:.1f} s)"
                   + (f"; the battery recovered to {p['resting_voltage']:.2f} V with nothing drawing" if p['resting_voltage'] else '')
                   + '.')
    eps = r['episodes']
    b = r['brownouts']
    if b['count'] is None:
        out.append('Brownouts: unknown (no battery voltage or brownout flag in this window).')
    elif b['count'] == 0:
        out.append(f"No brownouts (nothing below the {v['brownout_threshold']:.2f} V threshold)."
                   + (f" Lowest voltage {v['minimum']:.2f} V at {v['minimum_at']:.1f} s." if v['minimum'] is not None else ''))
    else:
        worst = min((e for e in eps if e['brownout']), key=lambda e: e['min_voltage'] or 99, default=None)
        out.append(f"{b['count']} brownout{'s' if b['count'] != 1 else ''} ({b['seconds']:.2f} s below the "
                   f"{v['brownout_threshold']:.2f} V threshold)"
                   + (f"; the worst reached {worst['min_voltage']:.2f} V at {worst['at']:.1f} s"
                      + (f" ({worst['period']})" if worst['period'] else '') if worst else '') + '.')
    lv = r['low_voltage']
    if lv['count']:
        by_period = {}
        for e in eps:
            by_period[e['period'] or 'unknown'] = by_period.get(e['period'] or 'unknown', 0) + 1
        top = max(by_period.items(), key=lambda kv: kv[1])
        out.append(f"{lv['count']} dip{'s' if lv['count'] != 1 else ''} below the {v['warning']:g} V warning level "
                   f"({lv['seconds']:.1f} s in total)"
                   + (f", {top[1]} of them in {top[0]}" if len(by_period) > 1 and top[1] > 1 else '') + '.')
        tally = {}                              # (group, kind) -> [episodes, peak, signals]
        for e in eps:
            seen = set()
            for c in e['contributors'][:3]:
                key = (c['group'], c['kind'])
                t = tally.setdefault(key, [0, 0.0, set()])
                if key not in seen:
                    t[0] += 1
                    seen.add(key)
                t[1] = max(t[1], c['peak_a'])
                t[2].add(c['name'])
        if tally:
            ranked = sorted(tally.items(), key=lambda kv: (-kv[1][0], -kv[1][1]))[:4]
            out.append('Drawing the most during those dips: ' + '; '.join(
                f"{group} {kind} current{f' ({len(names)} signals)' if len(names) > 1 else ''}: in {n} of {len(eps)}, "
                f"up to {peak:.0f} A{' per motor' if len(names) > 1 else ''}"
                for (group, kind), (n, peak, names) in ranked) + '.')
    elif lv['count'] == 0:
        out.append(f"Voltage stayed above the {v['warning']:g} V warning level.")
    m = r.get('measured_motor_draw')
    if m and m.get('peak') is not None:
        out.append(f"Measured motor supply current ({m['motors']} motor{'s' if m['motors'] != 1 else ''}, a lower bound "
                   f"on total draw): peak {m['peak']:.0f} A, average {m['average']:.1f} A.")
    stale = sum(1 for e in eps for c in e['contributors'] if c['stale'])
    if stale:
        out.append(f'{stale} of the readings behind these dips are more than {STALE_S:g} s old: that telemetry is logged '
                   'slowly, so treat those currents as approximate.')
    return out
