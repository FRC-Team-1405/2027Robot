"""
Builds a flat, tidy summary of every tab/chart's headline numbers, for export
to .csv (machine/LLM friendly) and .md (human + LLM friendly) so a run can be
quickly compared against another without opening the dashboard.
No Streamlit dependency.
"""
import csv
import io
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

Row = Tuple[str, str, str, Any]  # (section, metric, camera, value)

_MOTION_BUCKETS = [
    ('stationary', 'Stationary'),
    ('slow', 'Slow translate'),
    ('rotating', 'Rotating'),
    ('fast', 'Full speed'),
]


def _stat_rows(rows: List[Row], section: str, label: str, cam: str,
                values: List[float], decimals: int = 3) -> None:
    if not values:
        return
    rows.append((section, f'{label} mean', cam, round(sum(values) / len(values), decimals)))
    rows.append((section, f'{label} min', cam, round(min(values), decimals)))
    rows.append((section, f'{label} max', cam, round(max(values), decimals)))


def build_export_rows(metrics: List[Dict], fmt: str) -> List[Row]:
    """One row per (section, metric, camera) — mirrors the headline number on
    each dashboard tab/chart. Long/tidy format so it loads cleanly in pandas
    or a spreadsheet, and is easy for an LLM to scan."""
    rows: List[Row] = []

    for m in metrics:
        cam = m['camera']

        # ── Summary tab ──────────────────────────────────────────────────
        rows.append(('Summary', 'Acceptance rate (%)', cam, round(m['acceptance_rate'], 2)))
        rows.append(('Summary', 'FPS mean', cam, round(m['fps_mean'], 2)))
        rows.append(('Summary', 'FPS min', cam, round(m['fps_min'], 2)))
        rows.append(('Summary', 'Connection uptime (%)', cam, round(m['conn_uptime_pct'], 2)))
        rows.append(('Summary', 'Mean result latency (ms)', cam, round(m['latency_mean_ms'], 1)))
        rows.append(('Summary', 'Rejected velocity (%)', cam, round(m.get('rej_velocity_pct', 0.0), 2)))
        rows.append(('Summary', 'Rejected boundary (%)', cam, round(m.get('rej_boundary_pct', 0.0), 2)))
        if fmt == 'new':
            rows.append(('Summary', 'Rejected ambiguity (%)', cam,
                          round(m.get('rej_ambiguity_pct', 0.0), 2)))
        sq = m.get('stationary_quality')
        rows.append(('Summary', 'Stationary quality (%)', cam, round(sq, 2) if sq is not None else None))

        # ── Acceptance tab (poses/sec throughput) ───────────────────────────
        total_accepted = m.get('total_accepted', 0)
        total_results  = m.get('total_results', 0)
        acc_ts = m.get('acc_ts', [])
        span = acc_ts[-1] - acc_ts[0] if len(acc_ts) > 1 else 0.0
        rows.append(('Acceptance', 'Total accepted poses', cam, total_accepted))
        rows.append(('Acceptance', 'Total raw results', cam, total_results))
        rows.append(('Acceptance', 'Accepted poses per second (avg)', cam,
                      round(total_accepted / span, 3) if span > 0 else None))

        # ── Health tab ────────────────────────────────────────────────────
        rows.append(('Health', 'Latency sample count', cam, len(m.get('latencies_ms', []))))
        if m.get('stddev_x_m'):
            _stat_rows(rows, 'Health', 'Pose stddev X, 100-sample window (mm)', cam,
                       [v * 1000.0 for v in m['stddev_x_m']])
            _stat_rows(rows, 'Health', 'Pose stddev Y, 100-sample window (mm)', cam,
                       [v * 1000.0 for v in m['stddev_y_m']])
            _stat_rows(rows, 'Health', 'Pose stddev theta, 100-sample window (deg)', cam,
                       m['stddev_theta_deg'], decimals=4)
        if m.get('stddev_1s_x_m'):
            _stat_rows(rows, 'Health', 'Pose stddev X, 1s window (mm)', cam,
                       [v * 1000.0 for v in m['stddev_1s_x_m']])
            _stat_rows(rows, 'Health', 'Pose stddev Y, 1s window (mm)', cam,
                       [v * 1000.0 for v in m['stddev_1s_y_m']])
            _stat_rows(rows, 'Health', 'Pose stddev theta, 1s window (deg)', cam,
                       m['stddev_1s_theta_deg'], decimals=4)

        # ── Motion tab ───────────────────────────────────────────────────
        for bkey, blabel in _MOTION_BUCKETS:
            bkt = m.get('velocity_buckets', {}).get(bkey)
            if bkt:
                rows.append(('Motion', f'{blabel} acceptance rate (%)', cam,
                              round(bkt['acceptance_rate'], 2)))
                rows.append(('Motion', f'{blabel} sample count', cam, bkt['count']))

        # ── Geometry tab ─────────────────────────────────────────────────
        _stat_rows(rows, 'Geometry', 'Distance (m)', cam, m.get('distances', []))
        if fmt == 'new':
            _stat_rows(rows, 'Geometry', 'Tag area (sum)', cam, m.get('areas', []))
            _stat_rows(rows, 'Geometry', 'Z height (m)', cam, m.get('z_heights', []))
            _stat_rows(rows, 'Geometry', 'Ambiguity (single-tag)', cam, m.get('ambiguities', []))
            mt = m.get('multi_tag_count', 0)
            st_ = m.get('single_tag_count', 0)
            total_tags = mt + st_
            rows.append(('Geometry', 'Multi-tag count', cam, mt))
            rows.append(('Geometry', 'Single-tag count', cam, st_))
            rows.append(('Geometry', 'Multi-tag rate (%)', cam,
                          round(100.0 * mt / total_tags, 2) if total_tags else None))
        else:
            _stat_rows(rows, 'Geometry', 'Weight scalar', cam, m.get('weights', []))

        # ── Field tab ────────────────────────────────────────────────────
        tag_freq = m.get('tag_freq', {})
        rows.append(('Field', 'Unique tags seen', cam, len(tag_freq)))
        rows.append(('Field', 'Total tag detections', cam, sum(tag_freq.values())))
        if fmt == 'new':
            rows.append(('Field', 'Rejected boundary poses (count)', cam,
                          len(m.get('rej_boundary_path_x', []))))
            rows.append(('Field', 'Rejected velocity poses (count)', cam,
                          len(m.get('rej_velocity_path_x', []))))
            rows.append(('Field', 'Rejected ambiguity poses (count)', cam,
                          len(m.get('rej_ambiguity_path_x', []))))

    return rows


def rows_to_csv(rows: List[Row]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['section', 'metric', 'camera', 'value'])
    for section, metric, cam, value in rows:
        writer.writerow([section, metric, cam, '' if value is None else value])
    return buf.getvalue()


def _fmt_md_val(v: Any) -> str:
    if v is None:
        return '-'
    if isinstance(v, float):
        return f'{v:g}'
    return str(v)


def rows_to_markdown(
    rows: List[Row],
    cameras: List[str],
    log_name: str,
    fmt: str,
    duration: float,
    meta: Optional[Dict[str, str]] = None,
    committed: Optional[Tuple[float, float]] = None,
) -> str:
    """Pivot the tidy rows into one Markdown table per section (metric rows x
    camera columns) — readable at a glance by a human or an LLM."""
    sections: "OrderedDict[str, OrderedDict[str, Dict[str, Any]]]" = OrderedDict()
    for section, metric, cam, value in rows:
        sections.setdefault(section, OrderedDict())
        sections[section].setdefault(metric, {})[cam] = value

    meta = meta or {}
    lines: List[str] = [f'# Vision Analysis Summary — {log_name}', '']
    lines.append(f'- Format: {"new (raw pre-filter)" if fmt == "new" else "old (post-filter)"}')
    lines.append(f'- Cameras: {", ".join(cameras)}')
    if committed is not None:
        lines.append(
            f'- Analyzed window: {committed[0]:.1f}s – {committed[1]:.1f}s '
            f'({committed[1] - committed[0]:.1f}s of {duration:.1f}s total)'
        )
    else:
        lines.append(f'- Duration: {duration:.1f}s')
    if meta.get('ProjectName'):
        lines.append(f'- Project: {meta["ProjectName"]} @ {meta.get("GitHash", "")[:7]}')
    lines.append('')

    for section, metric_map in sections.items():
        lines.append(f'## {section}')
        lines.append('')
        lines.append('| Metric | ' + ' | '.join(cameras) + ' |')
        lines.append('|---' * (len(cameras) + 1) + '|')
        for metric, cam_values in metric_map.items():
            lines.append(
                f'| {metric} | ' + ' | '.join(_fmt_md_val(cam_values.get(c)) for c in cameras) + ' |'
            )
        lines.append('')

    return '\n'.join(lines)
