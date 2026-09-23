"""Battery Insights exports: the insights, not the data.

JSON is for LLMs and scripts: the match context, the findings as sentences, the numbers behind them with
units, every dip episode with what was drawing current and a little evidence around it, and what the log
could not tell. HTML is for people: the same, laid out to read in a minute, with a voltage chart and a
close-up of the worst dips. Neither carries the page's timeline -- the log itself is the full data.
"""
import html
import json
import math

import battery_insights

SCHEMA = 'logbench.battery-insights/v2'
COMPARISON_SCHEMA = 'logbench.battery-insights-comparison/v2'
TOP_LOADS = 20

HOW_TO_READ = {
    'brownouts': 'Times the battery voltage fell below the brownout threshold (or the roboRIO reported a brownout). '
                 f'Dips closer than {battery_insights.EPISODE_MERGE_S:g} s are counted as one.',
    'low_voltage': 'Episodes below the configurable warning level: the margin kept above a brownout.',
    'episodes': 'Each dip below the warning level, with the current signals peaking from '
                f'{battery_insights.CONTRIBUTOR_LEAD_S:g} s before it to its end. Stator and torque current are motor-side '
                'magnitudes (they include braking); supply current is what the battery delivers. A reading older than '
                f'{battery_insights.STALE_S:g} s at the lowest point is marked stale: that telemetry was logged slowly.',
    'loads': 'Every current signal found in the log, by peak. Signals of different kinds are not added together.',
    'measured_motor_draw': 'Sum of motor supply currents that are logged: a lower bound on total battery current.',
    'times': 'Seconds from the start of the log.',
}


def _r(x, n=2):
    return round(x, n) if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) else None


def export_json(report):
    """The insight export of one battery.analyze() report."""
    ins = report['insights']
    s = report['summary']
    motors = [{'name': m['name'], 'subsystem': m['subsystem'],
               'supply_peak_a': _r(m['stats']['peak'], 1), 'supply_average_a': _r(m['stats']['average'], 1),
               'supply_ah': _r(m['stats']['ah'], 3), 'stator_peak_a': _r(m['stator_stats']['peak'], 1),
               'supply_limited_s': _r(m['limiting_seconds'].get('SupplyLimited')),
               'stator_limited_s': _r(m['limiting_seconds'].get('StatorLimited')),
               'coverage': _r(m['stats']['coverage'], 3)} for m in report['motors']]
    return {
        'schema': SCHEMA,
        'log': report['log'],
        'window_s': report['window'],
        'context': ins['context'],
        'findings': ins['findings'],
        'summary': {
            'brownouts': ins['brownouts'], 'low_voltage': ins['low_voltage'],
            'min_voltage_v': _r(s['min_voltage']), 'seconds_below_v': ins['voltage']['seconds_below'],
            'pdh_total_current': {'peak_a': _r(s['peak'], 1), 'average_a': _r(s['average'], 1), 'ah': _r(s['ah'], 3),
                                  'wh': _r(s['wh'], 2), 'coverage': _r(s['coverage'], 3)},
            'measured_motor_draw': ins['measured_motor_draw'],
        },
        'voltage': ins['voltage'],
        'episodes': ins['episodes'],
        'loads': ins['loads'][:TOP_LOADS],
        'loads_total': len(ins['loads']),
        'motors': motors,
        'notes': report['warnings'],
        'how_to_read': HOW_TO_READ,
    }


def comparison(a, b):
    """Two reports side by side, as insight exports, with B − A for the headline numbers."""
    ea, eb = export_json(a), export_json(b)

    def num(e, *path):
        v = e['summary']
        for p in path:
            v = v.get(p) if isinstance(v, dict) else None
        return v

    rows = {'brownouts': ('brownouts', 'count'), 'brownout_seconds': ('brownouts', 'seconds'),
            'low_voltage_dips': ('low_voltage', 'count'), 'low_voltage_seconds': ('low_voltage', 'seconds'),
            'min_voltage_v': ('min_voltage_v',), 'pdh_average_a': ('pdh_total_current', 'average_a'),
            'pdh_ah': ('pdh_total_current', 'ah'), 'measured_motor_peak_a': ('measured_motor_draw', 'peak'),
            'measured_motor_average_a': ('measured_motor_draw', 'average')}
    deltas = {}
    for key, path in rows.items():
        x, y = num(ea, *path), num(eb, *path)
        deltas[key] = _r(y - x, 3) if isinstance(x, (int, float)) and isinstance(y, (int, float)) else None
    return {'schema': COMPARISON_SCHEMA, 'a': ea, 'b': eb, 'deltas': deltas,
            'interpretation': 'Observed B minus A. Different battery, driving, robot state and match can confound these '
                              'changes; they are not causal savings.'}


# ── HTML ────────────────────────────────────────────────────────────────────────────────────────────────

_CSS = """
:root{--bg:#fff;--fg:#1d2330;--muted:#5c6577;--line:#d9dde3;--panel:#f4f5f7;--bad:#c0392b;--warn:#b7791f;--v:#2557d6;
--c1:#2557d6;--c2:#23874f;--c3:#b7791f;--band:#eef1f6}
@media (prefers-color-scheme:dark){:root{--bg:#0f141c;--fg:#e2e8f0;--muted:#98a2b3;--line:#2c3e55;--panel:#16202e;
--bad:#f87171;--warn:#fbbf24;--v:#60a5fa;--c1:#60a5fa;--c2:#34d399;--c3:#fbbf24;--band:#182231}}
body{font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--fg);max-width:1040px;margin:0 auto;padding:24px 16px}
h1{font-size:26px;margin:0 0 4px}h2{font-size:18px;margin:28px 0 8px}h3{font-size:15px;margin:18px 0 6px}
.muted{color:var(--muted)}.small{font-size:13px}
ul.findings{background:var(--panel);border-left:4px solid var(--v);padding:12px 12px 12px 32px;margin:16px 0}
ul.findings li{margin:4px 0}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:16px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 12px}
.card b{display:block;font-size:22px;font-variant-numeric:tabular-nums}.card span{font-size:12px;color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;color:var(--muted);font-weight:600}td.r,th.r{text-align:right;font-variant-numeric:tabular-nums}
.wrap{overflow-x:auto}.bad{color:var(--bad);font-weight:600}svg{width:100%;height:auto;display:block}
svg text{fill:var(--muted);font:11px system-ui,sans-serif}
"""


def _e(x):
    return html.escape('' if x is None else str(x))


def _fmt(v, unit='', digits=2):
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
        return 'Unknown'
    return f'{v:.{digits}f}{" " + unit if unit else ""}'


def _ticks(lo, hi, n=5):
    """Round tick values covering [lo, hi] (1/2/5 × 10^k steps)."""
    span = (hi - lo) or 1
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 5, 10) if m * mag >= raw)
    first = math.ceil(lo / step) * step
    out, v = [], first
    while v <= hi + 1e-9:
        out.append(round(v, 6))
        v += step
    return out, step


def _tick_label(v, step, unit):
    digits = 0 if step >= 1 else 1 if step >= 0.1 else 2
    return f'{v:.{digits}f}{unit}'


def _chart(width, height, x0, x1, y0, y1, series, hlines=(), bands=(), dots=(), unit=''):
    """A small SVG line chart. series: [(label, color, [[x, y], ...], step)]; a None y breaks the line."""
    pad_l, pad_r, pad_t, pad_b = 44, 8, 14, 20
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    span_x = (x1 - x0) or 1
    span_y = (y1 - y0) or 1

    def X(x):
        return pad_l + (x - x0) / span_x * w

    def Y(y):
        return pad_t + (1 - (y - y0) / span_y) * h

    out = [f'<svg viewBox="0 0 {width} {height}" role="img">']
    for a, b, label in bands:
        a, b = max(a, x0), min(b, x1)
        if b > a:
            fits = X(b) - X(a) >= 6.5 * len(str(label)) + 6         # skip labels that would run into the next band
            out.append(f'<rect x="{X(a):.1f}" y="{pad_t}" width="{X(b) - X(a):.1f}" height="{h}" fill="var(--band)" '
                       f'stroke="var(--line)" stroke-width="0.5"><title>{_e(label)}</title></rect>'
                       + (f'<text x="{X(a) + 3:.1f}" y="{pad_t - 3}">{_e(label)}</text>' if fits else ''))
    yt, ys = _ticks(y0, y1, 4)
    for yv in yt:
        out.append(f'<line x1="{pad_l}" x2="{pad_l + w}" y1="{Y(yv):.1f}" y2="{Y(yv):.1f}" stroke="var(--line)" stroke-width="0.5"/>'
                   f'<text x="{pad_l - 4}" y="{Y(yv) + 4:.1f}" text-anchor="end">{_tick_label(yv, ys, _e(unit))}</text>')
    xt, xs = _ticks(x0, x1, 6)
    for xv in xt:
        out.append(f'<text x="{X(xv):.1f}" y="{height - 4}" text-anchor="middle">{_tick_label(xv, xs, "s")}</text>')
    for yv, color, label in hlines:
        if y0 <= yv <= y1:
            out.append(f'<line x1="{pad_l}" x2="{pad_l + w}" y1="{Y(yv):.1f}" y2="{Y(yv):.1f}" stroke="{color}" '
                       f'stroke-dasharray="5 4" stroke-width="1"/><text x="{pad_l + w - 2}" y="{Y(yv) - 3:.1f}" '
                       f'text-anchor="end" style="fill:{color}">{_e(label)}</text>')
    for label, color, pts, step in series:
        runs, run = [], []
        for x, y in pts:
            if x is None or y is None:
                if run:
                    runs.append(run)
                run = []
            else:
                run.append((x, y))
        if run:
            runs.append(run)
        for run in runs:
            coords = []
            for i, (x, y) in enumerate(run):
                if step and i:
                    coords.append(f'{X(x):.1f},{Y(run[i - 1][1]):.1f}')
                coords.append(f'{X(x):.1f},{Y(y):.1f}')
            out.append(f'<polyline fill="none" stroke="{color}" stroke-width="1.5" points="{" ".join(coords)}">'
                       f'<title>{_e(label)}</title></polyline>')
    for x, y, color, label in dots:
        out.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="3.5" fill="{color}"><title>{_e(label)}</title></circle>')
    out.append('</svg>')
    return ''.join(out)


def _voltage_chart(ex):
    v, ctx = ex['voltage'], ex['context']
    lo, hi = ex['window_s']
    prof = v['profile_1s_min']
    if not any(p is not None for p in prof):
        return '<p class="muted">No battery voltage in this window.</p>'
    pts = [[lo + i + 0.5, p] for i, p in enumerate(prof)]          # None breaks the line: no data there
    vals = [p for p in prof if p is not None]
    y0 = math.floor(min(vals + [v['brownout_threshold'] or 7]) - 0.5)
    y1 = math.ceil(max(vals) + 0.3)
    periods = [p for p in ctx['periods'] if p['label'] not in ('disabled',)]
    game = [p for p in periods if p['label'] not in ('auto', 'teleop')]
    bands = [(p['start'], p['end'], p['label']) for p in (game or periods)]
    dots = [(e['at'], e['min_voltage'], 'var(--bad)' if e['brownout'] else 'var(--warn)',
             f"{e['min_voltage']} V at {e['at']:.1f} s{' — brownout' if e['brownout'] else ''}")
            for e in ex['episodes'] if e['at'] is not None and e['min_voltage'] is not None]
    hl = [(v['brownout_threshold'], 'var(--bad)', f"brownout {v['brownout_threshold']:g} V")] if v['brownout_threshold'] else []
    hl.append((v['warning'], 'var(--warn)', f"warning {v['warning']:g} V"))
    return (_chart(1000, 240, lo, hi, y0, y1, [('Lowest voltage each second', 'var(--v)', pts, False)], hl, bands, dots, 'V')
            + '<p class="muted small">Lowest battery voltage in each second. Dots mark dips below the warning level '
              '(red: brownout). Shaded bands are game periods.</p>')


def _episode_chart(ep, v):
    ev = ep['evidence']
    volt = ev.get('voltage') or []
    xs = [p[0] for pts in ev.values() for p in pts]
    if not xs:
        return ''
    x0, x1 = min(xs), max(xs)
    vv = [p[1] for p in volt if p[1] is not None]
    top = _chart(480, 150, x0, x1, math.floor(min(vv + [v['brownout_threshold'] or 7]) - 0.3), math.ceil(max(vv or [12]) + 0.2),
                 [('Battery voltage', 'var(--v)', volt, True)],
                 [(v['brownout_threshold'], 'var(--bad)', 'brownout'), (v['warning'], 'var(--warn)', 'warning')], unit='V')
    colors = ['var(--c2)', 'var(--c3)', 'var(--bad)']
    cur = [(name, colors[i % 3], pts, True) for i, (name, pts) in enumerate((k, p) for k, p in ev.items() if k != 'voltage')]
    amps = [y for _n, _c, pts, _s in cur for _x, y in pts if y is not None]
    bottom = _chart(480, 150, x0, x1, 0, max(10, math.ceil(max(amps or [10]) / 20) * 20), cur, unit='A') if cur else ''
    legend = ' · '.join(f'<span style="color:{c}">■</span> {_e(n)}' for n, c, _p, _s in cur)
    return top + bottom + (f'<p class="muted small">{legend}</p>' if legend else '')


def _contributors(ep):
    parts = []
    for c in ep['contributors'][:3]:
        old = f" <span class='muted'>(reading {c['reading_age_s']:.1f} s old)</span>" if c['stale'] and c['reading_age_s'] is not None else ''
        parts.append(f"{_e(c['name'])} <b>{c['peak_a']:.0f} A</b> <span class='muted'>{_e(c['kind'])}</span>{old}")
    return '<br>'.join(parts) or '<span class="muted">No current signal above 5 A</span>'


def _report_html(ex):
    ctx, v, sm = ex['context'], ex['voltage'], ex['summary']
    head = ' · '.join(_e(x) for x in (ctx.get('event'), ctx.get('match'), ctx.get('alliance') and f"{ctx['alliance']} alliance",
                                        ctx.get('log_kind')) if x)
    out = [f"<h1>Battery Insights</h1><p><b>{_e(ex['log'])}</b></p>",
           f"<p class='muted'>{head}{' · ' if head else ''}window {ex['window_s'][0]:.1f}–{ex['window_s'][1]:.1f} s</p>"]
    out.append('<ul class="findings">' + ''.join(f'<li>{_e(f)}</li>' for f in ex['findings']) + '</ul>')
    b, lv, m = sm['brownouts'], sm['low_voltage'], sm['measured_motor_draw'] or {}
    cards = [('Brownouts', b['count'] if b['count'] is not None else 'Unknown'),
             (f"Dips below {v['warning']:g} V", lv['count'] if lv['count'] is not None else 'Unknown'),
             ('Lowest voltage', _fmt(sm['min_voltage_v'], 'V')),
             (f"Time below {v['warning']:g} V", _fmt(lv['seconds'], 's', 1)),
             ('Peak measured motor draw', _fmt(m.get('peak'), 'A', 0)),
             ('Average measured motor draw', _fmt(m.get('average'), 'A', 1))]
    out.append('<div class="cards">' + ''.join(f'<div class="card"><span>{_e(k)}</span><b>{_e(val)}</b></div>' for k, val in cards) + '</div>')
    out.append('<h2>Voltage over the window</h2>' + _voltage_chart(ex))
    rec = v.get('recovery')
    if v.get('resting_before') is not None or rec:
        rows = [('At rest before the match', _fmt(v.get('resting_before'), 'V'))]
        if rec:
            rows.append(('Under the last load', _fmt(rec.get('load_end_v'), 'V')))
            rows += [(f"{p['after_s']:g} s after", _fmt(p['voltage'], 'V')) for p in rec['points']]
            if rec.get('drop_v') is not None:
                rows.append((f"Drop (measured {rec['drop_measured_after_s']:g} s after)", _fmt(rec['drop_v'], 'V')))
            rows.append(('Recovery time constant (exploratory)', _fmt(rec.get('tau_s'), 's', 0)))
            rows.append(('Projected resting voltage', _fmt(rec.get('projected_rest_v'), 'V')))
        out.append('<h2>Battery at rest and recovery</h2><div class="wrap"><table>' + ''.join(
            f'<tr><th>{_e(k)}</th><td class="r">{_e(val)}</td></tr>' for k, val in rows) + '</table></div>'
            '<p class="muted small">Measured while disabled (radio, roboRIO and CAN still draw a little). The drop is most '
            'honest measured late: the battery keeps recovering for a minute or two after the match. The recovery time '
            'constant comes from fitting V(t) = V_rest − A·e^(−t/τ) to the voltage after the match.</p>')
    below = v['seconds_below']
    out.append('<p class="small">Time below: ' + ' · '.join(f'{k} V: {_fmt(s, "s", 1)}' for k, s in below.items()) + '</p>')
    eps = ex['episodes']
    out.append(f"<h2>Dips below {v['warning']:g} V ({len(eps)})</h2>")
    if eps:
        rows = ''.join(
            f"<tr><td class='r'>{i + 1}</td><td class='r'>{e['start']:.1f} s</td><td class='r'>{e['duration_s']:.2f} s</td>"
            f"<td class='r{' bad' if e['brownout'] else ''}'>{_fmt(e['min_voltage'], 'V')}</td>"
            f"<td>{'<span class=bad>Brownout</span>' if e['brownout'] else ''}</td><td>{_e(e['period'] or '')}</td>"
            f"<td>{_contributors(e)}</td></tr>" for i, e in enumerate(eps))
        out.append('<div class="wrap"><table><tr><th class="r">#</th><th class="r">At</th><th class="r">Length</th>'
                   '<th class="r">Lowest</th><th></th><th>Period</th><th>Drawing the most (peak)</th></tr>' + rows + '</table></div>')
        worst = sorted(eps, key=lambda e: e['min_voltage'] if e['min_voltage'] is not None else 99)[:3]
        out.append('<h2>Closest look: the worst dips</h2>')
        for e in worst:
            out.append(f"<h3>{e['start']:.1f} s{' — ' + _e(e['period']) if e['period'] else ''}: lowest {_fmt(e['min_voltage'], 'V')}"
                       f"{' (brownout)' if e['brownout'] else ''}</h3>" + _episode_chart(e, v))
    else:
        out.append('<p>None.</p>')
    loads = ex['loads']
    out.append(f"<h2>Current by signal</h2><p class='muted small'>Every current signal in the log ({ex['loads_total']}), "
               'largest first. Stator and torque current are motor-side sizes and include braking; supply current is what '
               'the battery delivers. Signals of different kinds are not added together.</p>')
    if loads:
        out.append('<div class="wrap"><table><tr><th>Signal</th><th>Kind</th><th class="r">Peak</th><th class="r">Average</th>'
                   '<th class="r">Peak during dips</th><th class="r">Samples/s</th></tr>' + ''.join(
                       f"<tr><td>{_e(l['name'])}</td><td>{_e(l['kind'])}</td><td class='r'>{_fmt(l['peak_a'], 'A', 0)}</td>"
                       f"<td class='r'>{_fmt(l['average_a'], 'A', 1)}</td><td class='r'>{_fmt(l['peak_during_dips_a'], 'A', 0)}</td>"
                       f"<td class='r'>{_fmt(l['samples_per_s'], '', 1)}</td></tr>" for l in loads) + '</table></div>')
    else:
        out.append('<p>No current signals in this log.</p>')
    if ex['motors']:
        out.append('<h2>Motors with supply current</h2><div class="wrap"><table><tr><th>Motor</th><th>Subsystem</th>'
                   '<th class="r">Peak</th><th class="r">Average</th><th class="r">Charge</th><th class="r">Coverage</th></tr>' + ''.join(
                       f"<tr><td>{_e(mo['name'])}</td><td>{_e(mo['subsystem'])}</td><td class='r'>{_fmt(mo['supply_peak_a'], 'A', 0)}</td>"
                       f"<td class='r'>{_fmt(mo['supply_average_a'], 'A', 1)}</td><td class='r'>{_fmt(mo['supply_ah'], 'Ah', 3)}</td>"
                       f"<td class='r'>{_fmt((mo['coverage'] or 0) * 100, '%', 0)}</td></tr>" for mo in ex['motors']) + '</table></div>')
    if ex['notes']:
        out.append('<h2>Notes on the data</h2><ul class="small">' + ''.join(f'<li>{_e(n)}</li>' for n in ex['notes']) + '</ul>')
    out.append('<p class="muted small">Battery voltage from ' + _e(v['source']) + '. '
               + _e(HOW_TO_READ['episodes']) + '</p>')
    return ''.join(out)


def render_html(report):
    """A readable, self-contained page: findings first, then the evidence. Everything from the log is escaped."""
    if 'insights' in report:
        body = _report_html(export_json(report))
    else:                                       # a comparison() result
        rows = ''.join(f'<tr><td>{_e(k)}</td><td class="r">{_e(v)}</td></tr>' for k, v in report['deltas'].items())
        body = ('<h1>Battery Insights — comparison</h1><p>' + _e(report['interpretation']) + '</p>'
                '<h2>B − A</h2><table><tr><th>Measure</th><th class="r">Change</th></tr>' + rows + '</table>'
                '<hr><h2>A</h2>' + _report_html(report['a']) + '<hr><h2>B</h2>' + _report_html(report['b']))
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Battery Insights</title><style>{_CSS}</style><body>{body}</body></html>')


def dumps(obj):
    return json.dumps(obj, allow_nan=False, separators=(',', ':'))
