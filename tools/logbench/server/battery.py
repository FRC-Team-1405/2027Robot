"""Battery Insights: step-held, coverage-aware power accounting over parsed logs.

No resampling is used for metrics. Motor phase currents never enter battery totals.
Unknown data is null, including limiting in logs that predate controller fault logging.
"""
import bisect
import html
import json
import math
import re

from model import PlayerSpec, Track, Panel
from encode import spec_to_dict

SCHEMA = 'logbench.battery/v1'
COLORS = ['#60a5fa', '#34d399', '#fbbf24', '#f472b6', '#a78bfa', '#fb923c']


class Series:
    def __init__(self, samples=(), source=None):
        self.samples = sorted(samples, key=lambda p: p[0])
        self.times = [p[0] for p in self.samples]
        self.source = source

    def at(self, t):
        i = bisect.bisect_right(self.times, t) - 1
        return self.samples[i][1] if i >= 0 else None


def number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def lookup(signals, *names):
    for name in names:
        for prefix in ('', 'RealOutputs/', 'NT:/SmartDashboard/', 'SmartDashboard/'):
            for variant in (name, name.lstrip('/')):
                key = prefix + variant
                if key in signals:
                    return Series(signals[key], key)
    return Series()


def segments(log):
    """Honor both compacted and original-time Janitor seams."""
    kept = [log.bounds()]
    raw = lookup(log.signals, '/Janitor/SegmentMap').samples
    if raw:
        try:
            data = json.loads(raw[-1][1])
            kept = [(s['new_first'], s['new_last']) for s in data['segments']]
            if not all(number(a) and number(b) and a <= b for a, b in kept):
                return []
        except (ValueError, KeyError, TypeError):
            # Unknown trim metadata cannot safely be integrated across seams.
            return []
    heartbeat = lookup(log.signals, 'Power/HeartbeatSeconds', 'Timestamp')
    if heartbeat.samples:
        start, end = log.bounds()
        out = []
        for previous, current in zip(heartbeat.times, heartbeat.times[1:]):
            if current - previous > 0.25:
                if start < previous:
                    out.append((start, previous))
                start = current
        if start < end:
            out.append((start, end))
        return [(max(a, c), min(b, d)) for a, b in kept for c, d in out if max(a, c) < min(b, d)]
    return kept


def windows(log):
    out = [{'label': 'Whole log', 'lo': 0, 'hi': log.bounds()[1] - log.bounds()[0]}]
    session = None
    for lo, hi, mode in log.mode_spans():
        if mode in ('auto', 'teleop', 'test'):
            out.append({'label': f'{mode.title()} {lo:.1f}–{hi:.1f}s', 'lo': lo, 'hi': hi})
            if session is None:
                session = {'label': 'Enabled session', 'lo': lo, 'hi': hi}
            else:
                session['hi'] = hi
        elif session:
            out.append(session)
            session = None
    if session:
        out.append(session)
    return out


def motor_sources(signals):
    ids = sorted(set(m.group(1) for key in signals
                     if (m := re.match(r'^(?:RealOutputs/)?Power/Motors/([^/]+)/SupplyCurrentAmps$', key))))
    result = []
    for identity in ids:
        prefix = f'Power/Motors/{identity}/'
        fields = {key.rsplit('/', 1)[-1]: lookup(signals, prefix + key.rsplit('/', 1)[-1])
                  for key in signals if key.startswith((prefix, 'RealOutputs/' + prefix))}
        result.append({'id': identity, 'name': fields.get('Name', Series()).at(float('inf')) or identity,
                       'subsystem': fields.get('Subsystem', Series()).at(float('inf')) or 'Unknown',
                       'fields': fields, 'aliases': [fields['Aliases'].at(float('inf'))] if 'Aliases' in fields else [], 'legacy': False})
    # Known historical physical inventory. Pickup and Intake/Pickup are the SAME motor.
    legacy = [('Intake', 'Deploy', 'Intake', 28), ('Pickup', '', 'Pickup', 29),
              ('Hopper', '', 'Hopper', 25), ('Indexer', '', 'Indexer', 40),
              ('Climber', 'Climber', 'Climber', 45), ('Climber', 'Grabber', 'Climber', 37)]
    legacy += [('Shooter', f'Motor{i}', 'Shooter', 0) for i in (1, 2, 3)]
    for base, part, group, can in legacy:
        # New registration supersedes its legacy alias; never count both.
        name = base + (f' {part}' if part else '')
        if any(m['name'] == name or (can and m['id'] == f'rio-{can}') for m in result):
            continue
        fields = {}
        aliases = []
        for field in ('SupplyCurrentAmps', 'StatorCurrentAmps', 'TorqueCurrentAmps',
                      'OutputVoltage', 'VelocityRPS', 'ClosedLoopError', 'ClosedLoopReference'):
            names = [f'{base}/{part}{field}']
            if base == 'Pickup':
                names.append('Intake/Pickup' + field)
            if base == 'Shooter' and field == 'OutputVoltage':
                names = [f'{base}/{part}OutputVoltage']
            if base == 'Shooter' and part == 'Motor1' and field in ('ClosedLoopError', 'ClosedLoopReference'):
                names.append(f'Shooter/{field}')
            fields[field] = lookup(signals, *names)
        if base == 'Pickup':
            aliases = ['Intake/Pickup', 'Pickup']
        if fields['SupplyCurrentAmps'].samples:
            result.append({'id': f'legacy-{base}-{part}', 'name': name, 'subsystem': group,
                           'fields': fields, 'aliases': aliases, 'legacy': True})
    for i in range(4):
        name = f'Drive {i}'
        if any(m['name'] == name for m in result):
            continue
        fields = {field: lookup(signals, f'SwerveDrive/DriveMotor_{old}_{i}') for field, old in
                  [('SupplyCurrentAmps', 'SupplyCurrent'), ('StatorCurrentAmps', 'StatorCurrent'),
                   ('OutputVoltage', 'OutputVoltage')]}
        if fields['SupplyCurrentAmps'].samples:
            result.append({'id': f'legacy-drive-{i}', 'name': name, 'subsystem': 'Drivetrain',
                           'fields': fields, 'aliases': [], 'legacy': True})
    return result


def summarize(samples, intervals, voltage=None):
    series = Series(samples)
    total = area = energy = energy_seconds = 0.0
    values = []
    for a, b in intervals:
        points = sorted({a, b, *(t for t in series.times if a < t < b),
                         *(t for t in (voltage.times if voltage else []) if a < t < b)})
        for lo, hi in zip(points, points[1:]):
            v = series.at(lo)
            if not number(v):
                continue
            dt = hi - lo
            total += dt
            area += v * dt
            values.append(v)
            volts = voltage.at(lo) if voltage else None
            if number(volts):
                energy += v * volts * dt
                energy_seconds += dt
    duration = sum(b-a for a, b in intervals)
    return {'minimum': min(values) if values else None, 'peak': max(values) if values else None,
            'average': area / total if total else None, 'ah': area / 3600 if total else None,
            'wh': energy / 3600 if energy_seconds else None,
            'coverage': total / duration if duration else 0,
            'energy_coverage': energy_seconds / duration if duration else 0,
            'valid_seconds': total}


def events(samples, intervals, kind, entity):
    series = Series(samples)
    out = []
    for a, b in intervals:
        points = sorted({a, b, *(t for t in series.times if a < t < b)})
        for lo, hi in zip(points, points[1:]):
            if series.at(lo) is not True:
                continue
            if out and out[-1]['end'] == lo and out[-1]['segment'] == a:
                out[-1]['end'] = hi
            else:
                out.append({'start': lo, 'end': hi, 'kind': kind, 'entity': entity, 'segment': a})
    return out


def analyze(log, window=None, low_voltage=8.0):
    t0, t1 = log.bounds()
    lo, hi = window or (0, t1-t0)
    if not all(number(x) for x in (lo, hi, low_voltage)) or not 0 <= lo < hi <= t1-t0 + 1e-6:
        raise ValueError('Window must be finite, inside the log, and have start < end')
    if not 0 < low_voltage < 16:
        raise ValueError('Low-voltage warning must be between 0 and 16 V')
    intervals = [(max(a, t0+lo), min(b, t0+hi)) for a, b in segments(log)
                 if max(a, t0+lo) < min(b, t0+hi)]
    s = log.signals
    rio = lookup(s, 'SystemStats/BatteryVoltage')
    pdv = lookup(s, 'PowerDistribution/Voltage')
    pdi = lookup(s, 'PowerDistribution/TotalCurrent')
    health = lookup(s, 'Power/Distribution/Valid')
    threshold = lookup(s, 'SystemStats/BrownoutVoltage')
    brown = lookup(s, 'SystemStats/BrownedOut')
    state = lookup(s, 'Power/State/Active')
    motors = motor_sources(s)
    warnings = []
    if not health.samples:
        warnings.append('Legacy acquisition health is unknown; plausible readings are lower-confidence evidence.')
    if not intervals:
        warnings.append('No valid acquisition intervals; trim metadata may be unsupported.')
    expected = {'Intake Deploy', 'Pickup', 'Hopper', 'Indexer', 'Climber Climber', 'Climber Grabber',
                *(f'Shooter Motor{i}' for i in (1, 2, 3)),
                *(f'{kind} {i}' for kind in ('Drive', 'Steer') for i in range(4))}
    missing_motors = sorted(expected - {m['name'] for m in motors})
    if missing_motors:
        warnings.append('No current telemetry for: ' + ', '.join(missing_motors) + '. These motors are not included in the instrumented sum.')
    if not threshold.samples:
        warnings.append('Brownout threshold is unavailable; the warning threshold is not a brownout detector.')
    # Build at actual sample/change boundaries, not an interpolated time grid.
    boundaries = {t0+lo, t0+hi}
    for a, b in intervals:
        boundaries.update((a, b))
    for key, samples in s.items():
        if any(term in key for term in ('Power/', 'PowerDistribution/', 'SystemStats/', 'Current', 'Voltage')):
            boundaries.update(t for t, _ in samples if t0+lo <= t <= t0+hi)
    times = sorted(boundaries)
    data = {k: [] for k in ('rio_voltage', 'pdh_voltage', 'total_current', 'motor_sum', 'difference',
                           'brownout_threshold', 'low_voltage_threshold', 'brownout', 'low_voltage', 'suspect_pdh')}
    motor_data = {m['id']: [] for m in motors}
    limit_data = {}
    for m in motors:
        for flag in ('SupplyLimited', 'StatorLimited'):
            limit_data[m['id'] + '/' + flag] = []
    for t in times:
        inside = any(a <= t < b for a, b in intervals)
        r, v, i = rio.at(t), pdv.at(t), pdi.at(t)
        suspect = number(r) and r > 4 and number(v) and v <= 0
        pd_ok = inside and health.at(t) is not False and not suspect and number(v) and v > 0
        r = r if inside and number(r) and r > 0 else None
        v = v if pd_ok else None
        i = i if pd_ok and number(i) else None
        currents = []
        for m in motors:
            f = m['fields']
            valid = inside and f.get('Valid', Series()).at(t) is not False
            current = f['SupplyCurrentAmps'].at(t)
            current = current if valid and number(current) else None
            motor_data[m['id']].append((t, current))
            if current is not None:
                currents.append(current)
            for flag in ('SupplyLimited', 'StatorLimited'):
                limit_data[m['id'] + '/' + flag].append((t, f.get(flag, Series()).at(t) if valid else None))
        # Require all registered motors to be valid for the measured motor sum.
        summed = sum(currents) if motors and len(currents) == len(motors) else None
        vals = [r, v, i, summed, i-summed if i is not None and summed is not None else None,
                threshold.at(t) if inside else None, low_voltage if inside else None,
                brown.at(t) if inside else None, r < low_voltage if r is not None else None,
                bool(suspect) if inside else None]
        for key, value in zip(data, vals):
            data[key].append((t, value))
    voltage = Series(data['pdh_voltage'])
    stats = summarize(data['total_current'], intervals, voltage)
    volts = summarize(data['rio_voltage'], intervals)
    ev = events(data['brownout'], intervals, 'Confirmed brownout', 'roboRIO')
    ev += events(data['low_voltage'], intervals, 'Low voltage', 'roboRIO')
    ev += events(data['suspect_pdh'], intervals, 'Suspect PDH telemetry', 'PDH')
    if any(v for _, v in data['suspect_pdh']):
        warnings.append('PDH zero-voltage samples conflict with roboRIO voltage and are excluded from power metrics.')
    rows = []
    groups = {}
    channels = lookup(s, 'PowerDistribution/ChannelCurrent')
    channel_rows = []
    channel_count = max((len(v) for _, v in channels.samples if isinstance(v, list)), default=0)
    pd_valid = Series(data['pdh_voltage'])
    for channel in range(channel_count):
        samples = []
        for t in times:
            currents = channels.at(t)
            value = currents[channel] if isinstance(currents, list) and channel < len(currents) and number(pd_valid.at(t)) else None
            samples.append((t, value))
        data[f'channel/{channel}'] = samples
        channel_rows.append({'channel': channel, 'mapping': 'Unmapped', 'stats': summarize(samples, intervals, voltage)})
    for m in motors:
        identity, fields = m['id'], m['fields']
        row = {k: m[k] for k in ('id', 'name', 'subsystem', 'aliases', 'legacy')}
        row['stats'] = summarize(motor_data[identity], intervals, voltage)
        def valid_field(field, absolute=False):
            source = fields.get(field, Series())
            points = sorted(set(times + source.times))
            return [(t, (abs(source.at(t)) if absolute else source.at(t))
                     if fields.get('Valid', Series()).at(t) is not False and number(source.at(t)) else None)
                    for t in points]
        row['stator_stats'] = summarize(valid_field('StatorCurrentAmps'), intervals)
        row['tracking_error'] = summarize(valid_field('ClosedLoopError', True), intervals)
        row['sources'] = {k: f.source for k, f in fields.items() if f.source}
        row['configuration'] = {k: f.at(t0+lo) for k, f in fields.items()
                                if 'Limit' in k or k in ('ConfigStatus', 'ConfigApplicationStatus', 'Follower', 'Bus', 'DeviceId')}
        if fields.get('ConfigValid', Series()).at(t0+lo) is False:
            for key in row['configuration']:
                if 'Limit' in key and not key.endswith('Limited'):
                    row['configuration'][key] = None
        row['limiting_seconds'] = {}
        for flag in ('SupplyLimited', 'StatorLimited'):
            samples = limit_data[identity + '/' + flag]
            detected = events(samples, intervals, flag, m['name'])
            ev += detected
            coverage = summarize([(t, int(v) if isinstance(v, bool) else None) for t, v in samples], intervals)
            row['limiting_seconds'][flag] = sum(e['end']-e['start'] for e in detected) if coverage['valid_seconds'] else None
            row['limiting_seconds'][flag + 'Coverage'] = coverage['coverage']
        rows.append(row)
        groups.setdefault(m['subsystem'], []).append(identity)
    # A duplicate legacy path is diagnostic evidence, never another motor.
    primary, alias = lookup(s, 'Pickup/SupplyCurrentAmps'), lookup(s, 'Intake/PickupSupplyCurrentAmps')
    if primary.samples and alias.samples:
        if any(number(primary.at(t)) and number(alias.at(t)) and abs(primary.at(t)-alias.at(t)) > 0.1 for t in times):
            warnings.append('Pickup and Intake/Pickup aliases disagree; Pickup is used once for CAN motor 29.')
    subsystem_rows = []
    for group, ids in groups.items():
        samples = []
        for j, t in enumerate(times):
            values = [motor_data[identity][j][1] for identity in ids]
            samples.append((t, sum(values) if all(number(v) for v in values) else None))
        data['subsystem/' + group] = samples
        subsystem_rows.append({'name': group, 'stats': summarize(samples, intervals, voltage)})
    # Full timeline data is shared with the existing player. Keep gaps as NaN for encoder.
    spec = PlayerSpec(title='Battery Insights — ' + log.path.name, t0=t0, t1=t1)
    spec.static['staleness_sec'] = t1-t0+1
    plots = [('voltage', 'Voltage (V)', ['rio_voltage', 'pdh_voltage', 'brownout_threshold', 'low_voltage_threshold']),
             ('current', 'PDH total, instrumented motor sum, and unaccounted difference (A)', ['total_current', 'motor_sum', 'difference']),
             ('subsystems', 'Subsystem supply current (A)', ['subsystem/' + g for g in groups])]
    for flag in ('SupplyLimited', 'StatorLimited'):
        data[flag + '_count'] = []
        for j, t in enumerate(times):
            flags = [limit_data[m['id'] + '/' + flag][j][1] for m in motors]
            known = [v for v in flags if isinstance(v, bool)]
            data[flag + '_count'].append((t, sum(known) if known else None))
    plots.append(('events', 'Reported events (1 = active); limiting counts include reporting motors only',
                  ['brownout', 'low_voltage', 'suspect_pdh', 'SupplyLimited_count', 'StatorLimited_count']))
    for m in motors:
        prefix = 'motor/' + m['id'] + '/'
        data[prefix + 'SupplyCurrentAmps'] = motor_data[m['id']]
        for field, series in m['fields'].items():
            if field == 'SupplyCurrentAmps':
                continue
            points = sorted({*(t for t in series.times if t0+lo <= t <= t0+hi),
                             *(x for interval in intervals for x in interval),
                             *m['fields'].get('Valid', Series()).times,
                             *m['fields'].get('StickyFaultsValid', Series()).times})
            data[prefix + field] = [(t, series.at(t) if any(a <= t < b for a, b in intervals)
                                     and m['fields'].get('Valid', Series()).at(t) is not False
                                     and not (field in ('StickySupplyLimited', 'StickyStatorLimited') and m['fields'].get('StickyFaultsValid', Series()).at(t) is False)
                                     else None)
                                    for t in points if t0+lo <= t <= t0+hi]
        for flag in ('SupplyLimited', 'StatorLimited'):
            data[prefix + flag] = limit_data[m['id'] + '/' + flag]
    for key, samples in s.items():
        canonical = key.removeprefix('RealOutputs/')
        if canonical.startswith(('Power/State/', 'Power/Allocation/')):
            source = Series(samples)
            points = sorted({*(t for t in source.times if t0+lo <= t <= t0+hi),
                             *(x for interval in intervals for x in interval)})
            data[canonical] = [(t, source.at(t) if any(a <= t < b for a, b in intervals) else None) for t in points]
            previous = None
            for t, value in samples:
                if value != previous and any(a <= t < b for a, b in intervals):
                    ev.append({'start': t, 'end': t, 'kind': f'{canonical}: {value}',
                               'entity': 'State / allocation', 'segment': 0})
                previous = value
    allocation_groups = sorted({key.split('/')[2] for key in data if key.startswith('Power/Allocation/') and key.endswith('Amps')})
    for group in allocation_groups:
        plots.append(('allocation-' + group, group + ' allocation: requested, granted, proposed and applied (A)',
                      [key for key in data if key.startswith('Power/Allocation/' + group + '/') and key.endswith('Amps')]))
    for m in motors:
        for field, series in m['fields'].items():
            if ('Limit' not in field and field not in ('ConfigStatus', 'ConfigApplicationStatus', 'ConfigValid')) or field.endswith('Limited'):
                continue
            for (prev_t, previous), (t, value) in zip(series.samples, series.samples[1:]):
                if previous != value and any(a <= t < b for a, b in intervals):
                    ev.append({'start': t, 'end': t, 'kind': f'Configuration {field}: {value}',
                               'entity': m['name'], 'segment': 0})
    for n, (key, samples) in enumerate(data.items()):
        example = next((v for _, v in samples if v is not None), None)
        # Scalar 0/1 preserves unknown gaps; the generic bool codec cannot encode null.
        kind = 'string' if isinstance(example, str) else 'scalar'
        if isinstance(example, (list, dict)):
            continue
        label = key.rsplit('/', 1)[-1] if key.startswith(('motor/', 'Power/')) else key.replace('subsystem/', '')
        label = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', label).replace('_', ' ')
        if key.startswith('Power/Allocation/'):
            label = key.split('/')[2] + ' · ' + label
        elif key.startswith('Power/State/Definitions/'):
            label = ' · '.join(key.split('/')[3:]) + ' priority'
        elif key == 'Power/State/Active':
            label = 'Active state'
        elif key == 'Power/State/Reason':
            label = 'State reason'
        unit = 'A' if key.endswith('Amps') or key in ('total_current', 'motor_sum', 'difference') or key.startswith(('subsystem/', 'channel/')) else 'V' if 'voltage' in key.lower() and 'seconds' not in key.lower() and key != 'low_voltage' else None
        spec.tracks.append(Track(key, label, kind, unit=unit, color=COLORS[n % len(COLORS)]))
    for identity, title, keys in plots:
        values = [v for key in keys for _, v in data[key] if number(v)]
        low = min(0, min(values)) if values else 0
        high = max(values) if values else 1
        spec.panels.append(Panel(identity, 'timeseries', title, keys,
                                 {'domain': [low, max(low+1, high*1.1)], 'step': True, 'view': [lo, hi]}))
        spec.layout.append([identity])
    kinds = {tr.id: tr.kind for tr in spec.tracks}
    encoded = {k: [(t, ('Unknown' if kinds[k] == 'string' else float('nan')) if v is None else v) for t, v in samples]
               for k, samples in data.items() if k in {tr.id for tr in spec.tracks}}
    brown_coverage = summarize([(t, int(v) if isinstance(v, bool) else None) for t, v in data['brownout']], intervals)
    summary = {**stats, 'min_voltage': volts['minimum'], 'voltage_coverage': volts['coverage'],
               'brownout_coverage': brown_coverage['coverage'],
               'brownout_count': len([e for e in ev if e['kind'] == 'Confirmed brownout']) if brown_coverage['valid_seconds'] else None,
               'brownout_seconds': sum(e['end']-e['start'] for e in ev if e['kind'] == 'Confirmed brownout') if brown_coverage['valid_seconds'] else None,
               'low_voltage_seconds': sum(e['end']-e['start'] for e in ev if e['kind'] == 'Low voltage') if volts['valid_seconds'] else None}
    for e in ev:
        e['start'] -= t0
        e['end'] -= t0
        del e['segment']
    report = {'schema': SCHEMA, 'log': log.path.name, 'window': [lo, hi], 'windows': windows(log),
            'mode_spans': log.mode_spans(), 'summary': summary, 'motors': rows, 'subsystems': subsystem_rows,
            'events': sorted(ev, key=lambda e: e['start']), 'warnings': warnings, 'channels': channel_rows,
            'missing_motors': missing_motors,
            'battery_id': lookup(s, 'Power/Distribution/BatteryId').at(t0+lo) or 'Unknown',
            'acquisition_basis': lookup(s, 'Power/Distribution/ValidityBasis').at(t0+lo) or 'Legacy / unavailable',
            'low_voltage_warning': low_voltage, 'intervals': [[a-t0, b-t0] for a, b in intervals],
            'provenance': {'total_current': pdi.source, 'voltage': rio.source, 'state': state.source},
            'spec': spec_to_dict(spec, encoded, allow_decimation=False)}
    return finite_json(report)


def comparison(a, b):
    keys = ('min_voltage', 'peak', 'average', 'ah', 'wh', 'brownout_count', 'brownout_seconds', 'low_voltage_seconds')
    return {'schema': 'logbench.battery-comparison/v1', 'a': a, 'b': b,
            'deltas': {k: b['summary'][k] - a['summary'][k]
                       if number(a['summary'][k]) and number(b['summary'][k]) else None for k in keys},
            'interpretation': 'Observed B minus A. Different battery, activity, state and policy can confound these changes; not causal savings.'}


def finite_json(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: finite_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_json(v) for v in value]
    return value


def render_html(report):
    """Portable report with exact analysis payload, escaped as text (never executable)."""
    def display(value):
        if value is None:
            return 'Unknown'
        if isinstance(value, float):
            return f'{value:.4g}'
        return html.escape(str(value))
    def table(items):
        return '<table>' + ''.join('<tr><th>' + html.escape(str(k)) + '</th><td>' +
                                  display(v) + '</td></tr>' for k, v in items.items()) + '</table>'
    def content(r):
        out = '<h2>' + html.escape(r['log']) + '</h2><p>Window: ' + html.escape(str(r['window'])) + ' seconds · Battery: ' + html.escape(r['battery_id']) + '</p>'
        out += '<h3>Summary</h3>' + table(r['summary'])
        out += '<p>Current: A; voltage: V; charge: Ah; energy: Wh; durations: seconds; coverage: fraction 0–1. Integrals cover valid samples only.</p>'
        out += '<h3>Coverage notes</h3>' + ''.join('<p>' + html.escape(w) + '</p>' for w in r['warnings'])
        out += '<h3>Subsystems</h3>'
        for group in r['subsystems']:
            out += '<h4>' + html.escape(group['name']) + '</h4>' + table(group['stats'])
        out += '<h3>Physical motors</h3>'
        for m in r['motors']:
            out += '<details><summary>' + html.escape(m['name']) + '</summary><h4>Supply current and energy</h4>' + table(m['stats'])
            out += '<h4>Limiting seconds and coverage</h4>' + table(m['limiting_seconds'])
            out += '<h4>Stator current</h4>' + table(m['stator_stats']) + '<h4>Absolute tracking error (native units)</h4>' + table(m['tracking_error'])
            out += '<h4>Configuration at interval start</h4>' + table(m['configuration']) + '<h4>Sources</h4>' + table(m['sources']) + '</details>'
        out += '<h3>Events and state / policy changes</h3><table><tr><th>Start (s)</th><th>End (s)</th><th>Evidence</th><th>Source</th></tr>'
        out += ''.join('<tr>' + ''.join('<td>' + display(e[k]) + '</td>' for k in ('start', 'end', 'kind', 'entity')) + '</tr>' for e in r['events']) + '</table>'
        out += '<details><summary>PDH channel measurements (not added to motor totals)</summary>'
        for channel in r['channels']:
            out += '<h4>Channel ' + str(channel['channel']) + ' — ' + html.escape(channel['mapping']) + '</h4>' + table(channel['stats'])
        return out + '</details>'
    sections = '<h1>Battery Insights</h1><p>Observed measurements only. Unrestricted current demand and causal savings are unknown.</p>'
    if report['schema'] == 'logbench.battery-comparison/v1':
        sections += '<h2>Observed B − A</h2><p>' + html.escape(report['interpretation']) + '</p>' + table(report['deltas'])
        sections += '<h2>Window A</h2>' + content(report['a']) + '<h2>Window B</h2>' + content(report['b'])
    else:
        sections += content(report)
    sections += '<details><summary>Complete report, configuration and timeline data</summary><pre>' + html.escape(json.dumps(report, indent=2, allow_nan=False)) + '</pre></details>'
    return '<!doctype html><meta charset="utf-8"><title>Battery Insights</title><style>body{font:16px system-ui;max-width:1000px;margin:40px auto;padding:20px}td,th{padding:5px 16px;text-align:left;border-bottom:1px solid #ddd}pre{white-space:pre-wrap}</style>' + sections
