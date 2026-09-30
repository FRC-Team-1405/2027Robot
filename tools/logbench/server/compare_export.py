"""Exports one comparison as a standalone HTML page (for people) or a self-describing JSON
document (for LLMs).

Both are rendered from the same report dict, so they cannot disagree with each other or with
the compare page: the numbers come from core.compare.compare(), the very call /api/compare
and the CLI make. Pure functions over already-computed Runs -- no I/O, no FastAPI -- so tests
and the CLI can use them directly.

Why one .json document rather than .jsonl: a comparison is one small, cohesive unit, and an
LLM reasons better when the log identities, windows, metric definitions and verdict rule sit
next to the numbers in a single object than when it has to stitch them from a stream of
lines. .jsonl earns its keep for many records, which this is not.

Only file *names* are ever written (never directory paths): the export gets shared, and a
laptop's directory layout is neither useful to a reader nor something to leak.
"""
import html
import json
import pathlib
from datetime import datetime, timezone
from typing import Dict, List, Optional

from core import categories as categories_mod
from core import composites as composites_mod
from core import metrics as metrics_mod
from core.compare import CONTEXT_VERDICT, VERDICT_THRESHOLD

SCHEMA = 'logbench.compare/v2'

VERDICTS = ('improved', 'regressed', 'neutral', 'n/a', CONTEXT_VERDICT)

# One line per registered id, so an LLM that has never seen this repo can tell what a number
# means. tests/test_compare_export.py fails if a metric is registered without an entry here.
# The *_pct factors are scored on the robot by VisionHealth.java and merely averaged over the
# window here; the log-derived ones are computed from the raw log by vision_analyzer.
DESCRIPTIONS: Dict[str, str] = {
    'health_score': 'Optional convenience number: availability_score x quality_score / 100. '
                    'Context is never part of it. Prefer reading the two scores it is made of, '
                    'because a product hides which one moved.',
    'availability_score': 'Availability: does usable data arrive when it should? Product of '
                          'tag_in_view_pct, fps_pct and latency_pct. A low value points at the '
                          'connection, mount / field of view, exposure or lighting, USB or network.',
    'quality_score': 'Quality: when a tag is seen, how good is the solution? Product of area_pct, '
                     'ambiguity_pct, acceptance_pct and multitag_pct, each measured only over the '
                     'times a tag was in view. Jitter is excluded (it rises with motion). Area is '
                     'still range-dependent until range normalisation lands (docs/adr/0001, D3), so '
                     'read it next to Median range to tags. A low value points at calibration, '
                     'focus, the detection threshold or decimate.',
    'tag_in_view_pct': 'Availability: percent of the window during which a tag-bearing result was '
                       "in view (derived from the robot's Health/Reason gate, or from the raw "
                       'pose array on older logs). Depends on the route: a robot facing away from '
                       'the tags lowers it without any camera fault.',
    'longest_gap_ms': 'Availability: the longest unbroken stretch with no tag in view, in '
                      'milliseconds. Lower is better. Tells apart many 20 ms blips from one long '
                      'hole, which the fraction above cannot. Loops are 20 ms, so differences of '
                      'a loop or two are noise.',
    'range_median_m': 'Context (not scored): median distance from the camera to the tags used in '
                      'each result. Tag area and multi-tag depend heavily on this, so a change '
                      'here explains changes there.',
    'speed_mean_mps': 'Context (not scored): time-weighted mean chassis speed over the window. '
                      'Whole-run, so it appears once (camera "All").',
    'score_pct': 'Legacy. Robot-reported overall camera health (0-100), the product of every '
                 'factor including stillness, averaged over time WITHOUT excluding loops the robot '
                 'zeroed for no tag. A calibration diagnostic for a robot held still, not a '
                 'match-accuracy score.',
    'stillness_pct': 'Context (not scored): health factor from instantaneous chassis velocity; '
                     'high when the robot is still. Expected to be low during autonomous motion, '
                     'so it describes the run, not the camera.',
    'area_pct': 'Quality: health factor from total tag image area (0.5s median), averaged over '
                'times a tag was in view. Higher = tags nearer or better oriented. '
                'Range-dependent: a closer route raises it with no change to the camera (read it '
                'next to Median range to tags).',
    'ambiguity_pct': 'Quality: health factor from single-tag PnP ambiguity (0.5s median, '
                     'inverted). Multi-tag solves score 100.',
    'fps_pct': 'Availability: health factor from 1s mean camera FPS relative to the target FPS.',
    'jitter_pct': 'Quality: health factor from 1s pose standard deviation, inverted. Higher = '
                  'less pose scatter. Physically rises with motion, so it is excluded from '
                  'quality_score and is not judged well by a moving run.',
    'acceptance_pct': 'Quality: health factor from accepted / raw pose results over 1s.',
    'latency_pct': 'Availability: health factor from newest-result latency (1s median), '
                   'inverted. Stale data is unavailable data.',
    'multitag_pct': 'Quality (provisionally): health factor from the fraction of accepted results '
                    'in the previous second that used 2+ tags. Partly reflects route geometry '
                    '(whether two tags were in view at all).',
    'acceptance_rate': 'Percent of raw vision pose results accepted by the filter pipeline in '
                       'the window (computed from the log). The most direct measure of filter '
                       'changes.',
    'fps_mean': 'Mean camera FPS over the window (computed from the log). 0 if no FPS samples.',
    'fps_min': 'Minimum camera FPS over the window (computed from the log). 0 if no FPS samples.',
    'conn_uptime_pct': 'Percent of connection samples in the window reporting the camera '
                       'connected. 0 if no samples.',
    'latency_mean_ms': 'Mean camera pipeline latency in milliseconds (computed from the log). '
                       'Lower is better.',
    'stationary_quality': 'Acceptance rate restricted to moments the robot was stationary '
                          '(computed from the log). Null if the log has no drivetrain speed data.',
    'still_score': 'Legacy composite: product of all eight health factors, with jitter blended '
                   'by stillness. Mixes availability, quality and context (stillness), so it '
                   'cannot say which moved. Designed for a "hold the robot still" check.',
    'motion_score': 'Legacy composite: product of area, ambiguity, fps, acceptance, latency and '
                    'multi-tag factors. Mixes availability and quality into one number, so it '
                    'cannot say which moved. Superseded by availability_score and quality_score.',
}

HOW_TO_READ = [
    'Every metric has a category (see "categories" and the "category" on each metric): "availability" '
    '(does usable data arrive?), "quality" (when a tag is seen, how good is it?) or "context" '
    '(the conditions of the run: speed, range). Read availability and quality separately. '
    'Context is never part of a score and gets verdict "context" instead of a judgement: it '
    'explains why the other numbers moved, e.g. a shorter range raises tag area with no change '
    'to the camera. Composites in category "legacy" mix categories and are kept only for '
    'continuity.',
    'A metric with camera "All" describes the whole run and is the same for every camera.',
    'Each entry in "comparisons" is one metric for one camera, computed over each log\'s '
    'window. "delta" is b - a and "pct_change" is (b - a) / |a| * 100 (null when a is 0 or '
    'either side is null).',
    'Each log is scored only inside its own window (see logs.<a|b>.window). Windows chosen '
    'with selection "mode:<x>" are that DS mode\'s longest span in each log independently, so '
    'the two windows can differ in length.',
    'Verdict compares b to a: a metric whose ratio b/a moves by more than verdict_rule.'
    'threshold_ratio in the good direction is "improved", in the bad direction "regressed", '
    'otherwise "neutral". "n/a" means a value was missing on either side. Direction comes '
    'from "lower_is_better" in "metrics".',
    'A null value means the log had no data for that metric/camera. Some log-derived metrics '
    '(fps_mean, fps_min, conn_uptime_pct, latency_mean_ms, acceptance_rate) report exactly 0 '
    'instead of null when there were no samples, so a 0 there can mean "no data" rather than a '
    'measured zero -- check the other metrics for the same camera before concluding.',
    'A single comparison of two logs is weak evidence: verdicts inside the noise band are '
    'neutral by design, and differing routes, lighting or driving between logs confound '
    'vision metrics. Prefer changes that show up across several metrics and both cameras.',
]


def _file_name(label: str) -> str:
    """A client-supplied log path ('offseason/6-13/x.wpilog', either separator) -> 'x.wpilog'."""
    return pathlib.PurePosixPath(label.replace('\\', '/')).name


def _round(v: Optional[float], digits: int = 4) -> Optional[float]:
    return None if v is None else round(v, digits)


def _describe_metric(metric_id: str) -> dict:
    if metric_id in composites_mod.COMPOSITES:
        c = composites_mod.COMPOSITES[metric_id]
        out = {'id': c.id, 'label': c.label, 'kind': 'composite', 'category': c.category,
               'unit': '%', 'lower_is_better': c.lower_is_better, 'depends_on': list(c.deps)}
    else:
        m = metrics_mod.METRICS[metric_id]
        out = {'id': m.id, 'label': m.label, 'kind': 'metric', 'category': m.category,
               'unit': m.unit, 'lower_is_better': m.lower_is_better}
    out['description'] = DESCRIPTIONS.get(metric_id, '')
    return out


def _log_section(run, selection: str) -> dict:
    t0, t1 = run.log.bounds()
    return {
        'file': _file_name(run.label),
        'duration_s': _round(t1 - t0, 2),
        'cameras': run.log.cameras(),
        'ds_mode_spans': [
            {'mode': mode, 'start_s': _round(lo, 2), 'end_s': _round(hi, 2)}
            for lo, hi, mode in run.log.mode_spans()
        ],
        'window': {
            'selection': selection,
            # Absolute log seconds are what the compare page prints; relative-to-log-start is
            # what ds_mode_spans and manual windows use. Both are given so neither reader
            # has to know which convention applies where.
            'start_s': _round(run.window.lo, 2),
            'end_s': _round(run.window.hi, 2),
            'start_rel_s': _round(run.window.lo - t0, 2),
            'end_rel_s': _round(run.window.hi - t0, 2),
            'duration_s': _round(run.window.duration, 2),
        },
    }


def _category_of(metric_id: str) -> str:
    if metric_id in composites_mod.COMPOSITES:
        return composites_mod.COMPOSITES[metric_id].category
    return metrics_mod.METRICS[metric_id].category


def _tally(deltas) -> dict:
    counts = {v: 0 for v in VERDICTS}
    for d in deltas:
        counts[d.verdict] += 1
    return counts


def build_report(run_a, run_b, deltas: List, cameras: List[str], metric_ids: List[str], *,
                 mode: str, manual_a: bool, manual_b: bool,
                 generated_at: Optional[datetime] = None) -> dict:
    """run_a/run_b/deltas/cameras/metric_ids are exactly what core.compare produced;
    mode/manual_* record how the windows were chosen so the report is reproducible."""
    generated_at = generated_at or datetime.now(timezone.utc)

    comparisons = []
    for d in deltas:
        pct = None
        if d.delta is not None and d.a not in (None, 0):
            pct = _round(100.0 * d.delta / abs(d.a), 2)
        comparisons.append({
            'metric': d.id, 'camera': d.camera, 'a': _round(d.a), 'b': _round(d.b),
            'delta': _round(d.delta), 'pct_change': pct, 'verdict': d.verdict,
        })

    metric_category = {m: _category_of(m) for m in metric_ids}
    return {
        'schema': SCHEMA,
        'generated_at': generated_at.isoformat(timespec='seconds'),
        'how_to_read': HOW_TO_READ,
        'verdict_rule': {'threshold_ratio': VERDICT_THRESHOLD},
        'logs': {
            'a': _log_section(run_a, 'manual' if manual_a else f'mode:{mode}'),
            'b': _log_section(run_b, 'manual' if manual_b else f'mode:{mode}'),
        },
        'cameras': cameras,
        'categories': categories_mod.describe(),
        'metrics': [_describe_metric(m) for m in metric_ids],
        'comparisons': comparisons,
        'summary': {
            'overall': _tally(deltas),
            'by_camera': {c: _tally([d for d in deltas if d.camera == c]) for c in cameras},
            'by_category': {
                cid: _tally([d for d in deltas if metric_category[d.id] == cid])
                for cid in categories_mod.ALL_IDS
                if any(metric_category[d.id] == cid for d in deltas)
            },
        },
    }


def render_json(report: dict) -> str:
    return json.dumps(report, indent=2, ensure_ascii=False) + '\n'


# ─── HTML ──────────────────────────────────────────────────────────────────────────────

def _fmt(v: Optional[float], unit: Optional[str]) -> str:
    """Same rule as web/src/compare/ResultsTable.tsx's fmt(), so the export reads identically
    to the page."""
    if v is None:
        return 'n/a'
    digits = 2 if abs(v) < 10 else 1
    return f'{v:.{digits}f}' + (f' {unit}' if unit else '')


_CSS = """
:root{--bg:#0b0f17;--panel:#111827;--border:#1f2937;--text:#e5e7eb;--muted:#98a2b3;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:13px/1.45 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:980px;margin:24px auto;padding:0 16px 40px;display:flex;flex-direction:column;gap:14px}
h1{font-size:16px;margin:0}
.meta,.summary{color:var(--muted);font-size:11px;display:flex;flex-direction:column;gap:2px}
.results{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:12px}
th{text-align:left;color:var(--muted);font-weight:600;padding:6px 10px;border-bottom:1px solid var(--border)}
td{padding:6px 10px;border-bottom:1px solid var(--border)}
td.num{font-variant-numeric:tabular-nums;text-align:right}
.verdict{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600}
.verdict--improved{background:#123b28;color:#6ee7a8}
.verdict--regressed{background:#3b1414;color:#f2b8b5}
.verdict--neutral{background:#1c2534;color:var(--muted)}
.verdict--na{background:transparent;color:#4b5563}
.verdict--context{background:transparent;color:var(--muted);border:1px dashed var(--border)}
.cat{display:flex;flex-direction:column;gap:4px}
h2{font-size:13px;margin:6px 0 0}
.q{color:var(--text);font-size:12px}.low{color:var(--muted);font-size:11px}
.badge{font-size:10px;font-weight:600;color:var(--muted);border:1px dashed var(--border);border-radius:8px;padding:1px 6px;margin-left:6px;vertical-align:middle}
.cat--context table{opacity:.85}
details{background:var(--panel);border:1px solid var(--border);border-radius:6px;padding:8px 12px}
summary{cursor:pointer;color:var(--muted)}
dt{font-weight:600;margin-top:8px}dd{margin:2px 0 0;color:var(--muted)}
@media print{:root{--bg:#fff;--panel:#fff;--border:#ccc;--text:#111;--muted:#555;color-scheme:light}
.verdict--improved{background:#d8f5e5;color:#0b6b3a}.verdict--regressed{background:#fbdcdc;color:#8a1c1c}.verdict--neutral{background:#eee;color:#555}}
"""


def _window_line(side: str, log: dict) -> str:
    w = log['window']
    return (f'{side}: {html.escape(log["file"])} — window '
            f'[{w["start_s"]:.1f}, {w["end_s"]:.1f}]s')


def render_html(report: dict) -> str:
    """Standalone page: no scripts, no external references, works from a file or an email."""
    a, b = report['logs']['a'], report['logs']['b']
    by_id = {m['id']: m for m in report['metrics']}

    rows_by_category: dict = {}
    for c in report['comparisons']:
        m = by_id[c['metric']]
        unit = m['unit']
        verdict = c['verdict']
        rows_by_category.setdefault(m['category'], []).append(
            '<tr>'
            f'<td>{html.escape(m["label"])}</td>'
            f'<td>{html.escape(c["camera"])}</td>'
            f'<td class="num">{_fmt(c["a"], unit)}</td>'
            f'<td class="num">{_fmt(c["b"], unit)}</td>'
            f'<td class="num">{_fmt(c["delta"], unit)}</td>'
            f'<td><span class="verdict verdict--{verdict.replace("/", "")}">{verdict}</span></td>'
            '</tr>'
        )

    # One section per category, in the order the compare page lays them out: the optional
    # overall number, the two scored categories, context (visibly not scored), then legacy.
    cat_info = {c['id']: c for c in report['categories']}
    cat_info[categories_mod.OVERALL] = {
        'label': categories_mod.OVERALL_LABEL, 'scored': True,
        'question': 'Availability x quality. Context is never part of it.', 'low_means': ''}
    cat_info[categories_mod.LEGACY] = {
        'label': categories_mod.LEGACY_LABEL, 'scored': False,
        'question': 'Predate the availability / quality / context split and mix categories.',
        'low_means': ''}
    section_order = [categories_mod.OVERALL, categories_mod.AVAILABILITY, categories_mod.QUALITY,
                     categories_mod.CONTEXT, categories_mod.LEGACY]
    sections = []
    for cid in section_order:
        if cid not in rows_by_category:
            continue
        info = cat_info[cid]
        note = '' if info['scored'] or cid == categories_mod.LEGACY else ' <span class="badge">not scored</span>'
        low = f'<div class="low">{html.escape(info["low_means"])}</div>' if info['low_means'] else ''
        sections.append(
            f'<section class="cat cat--{cid}"><h2>{html.escape(info["label"])}{note}</h2>'
            f'<div class="q">{html.escape(info["question"])}</div>{low}'
            '<div class="results"><table><thead><tr><th>Metric</th><th>Camera</th><th>A</th>'
            '<th>B</th><th>&Delta;</th><th>Verdict</th></tr></thead><tbody>'
            + ''.join(rows_by_category[cid]) + '</tbody></table></div></section>'
        )

    defs = ''.join(
        f'<dt>{html.escape(m["label"])} <code>{html.escape(m["id"])}</code></dt>'
        f'<dd>{html.escape(m["description"])}'
        f'{" Lower is better." if m["lower_is_better"] else ""}</dd>'
        for m in report['metrics']
    )
    tally = report['summary']['overall']
    title = f'Compare: {a["file"]} vs {b["file"]}'

    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{html.escape(title)}</title><style>{_CSS}</style></head><body><main>'
        '<h1>Compare two logs</h1>'
        f'<div class="meta"><div>{_window_line("A", a)}</div><div>{_window_line("B", b)}</div></div>'
        + ''.join(sections) +
        f'<div class="summary"><div>{tally["improved"]} improved · {tally["regressed"]} regressed · '
        f'{tally["neutral"]} neutral · {tally["n/a"]} n/a · {tally["context"]} context (not judged). '
        f'Verdict band: ±'
        f'{report["verdict_rule"]["threshold_ratio"] * 100:.0f}% (b vs a).</div>'
        f'<div>Window selection — A: {html.escape(a["window"]["selection"])}, '
        f'B: {html.escape(b["window"]["selection"])}. Generated {html.escape(report["generated_at"])}.</div></div>'
        f'<details><summary>Metric definitions</summary><dl>{defs}</dl></details>'
        '</main></body></html>\n'
    )
