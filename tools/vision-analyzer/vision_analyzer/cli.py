"""
CLI entry point: probe mode and legacy HTML generation.
"""
import argparse
import pathlib
import sys
from collections import defaultdict
from typing import Dict, List

from .parser import parse_wpilog
from .metrics import (
    discover_cameras,
    detect_format,
    find_drivetrain_speeds,
    compute_camera_metrics,
)


def probe_signals(path: str) -> None:
    signals = parse_wpilog(path)
    print(f"\n{'-' * 60}")
    print(f"Signals in {pathlib.Path(path).name}  ({len(signals)} entries)")
    print('-' * 60)
    by_ns: Dict[str, list] = defaultdict(list)
    for name in sorted(signals):
        ns = name.split('/')[0] if '/' in name else '(root)'
        sample = signals[name]
        typ = type(sample[0][1]).__name__ if sample else '?'
        count = len(sample)
        by_ns[ns].append(f'  {name}  [{typ}, {count} samples]')
    for ns, items in sorted(by_ns.items()):
        print(f'\n[{ns}]')
        for item in items:
            print(item)
    print()


def _load_log(path: str):
    """Parse a wpilog and compute metrics for all cameras. Returns (metrics, duration, meta, cameras)."""
    signals = parse_wpilog(path)
    cameras = discover_cameras(signals)
    all_ts  = [t for sig in signals.values() for t, _ in sig]
    start_t = min(all_ts) if all_ts else 0.0
    end_t   = max(all_ts) if all_ts else 0.0

    meta: Dict[str, str] = {}
    for key in ('RealMetadata/ProjectName', 'RealMetadata/GitHash', 'RealMetadata/RuntimeType'):
        if key in signals and signals[key]:
            meta[key.split('/')[-1]] = str(signals[key][-1][1])

    lin_key, omega_key = find_drivetrain_speeds(signals)
    linear_sig = signals[lin_key] if lin_key else None
    omega_sig  = signals[omega_key] if omega_key else None

    all_metrics = []
    for cam in cameras:
        fmt = detect_format(signals, cam)
        m = compute_camera_metrics(signals, cam, fmt, start_t, end_t, linear_sig, omega_sig)
        all_metrics.append(m)

    return all_metrics, end_t - start_t, meta, cameras


def _write_legacy_html(
    all_metrics: List[Dict],
    duration: float,
    meta: Dict,
    log_name: str,
    out_path: pathlib.Path,
) -> None:
    """Write a lightweight HTML that embeds the summary table and links to streamlit."""
    cameras = [m['camera'] for m in all_metrics]
    fmt = all_metrics[0]['format'] if all_metrics else 'old'

    def pct(v):
        return f'{v:.1f}%' if v is not None else '-'

    rows = [
        ('Acceptance rate',     [pct(m['acceptance_rate']) for m in all_metrics]),
        ('FPS (mean)',          [f'{m["fps_mean"]:.1f}' for m in all_metrics]),
        ('Connection uptime',   [pct(m['conn_uptime_pct']) for m in all_metrics]),
        ('Mean result latency', [f'{m["latency_mean_ms"]:.0f} ms' if m["latency_mean_ms"] else '-'
                                 for m in all_metrics]),
        ('Rejected (velocity)', [pct(m.get('rej_velocity_pct')) for m in all_metrics]),
        ('Rejected (boundary)', [pct(m.get('rej_boundary_pct')) for m in all_metrics]),
    ]
    if fmt == 'new':
        rows.append(('Rejected (ambiguity)', [pct(m.get('rej_ambiguity_pct')) for m in all_metrics]))

    thead = '<tr><th>Metric</th>' + ''.join(f'<th>{c}</th>' for c in cameras) + '</tr>'
    tbody = ''.join(
        '<tr><td>' + row[0] + '</td>' + ''.join(f'<td>{v}</td>' for v in row[1]) + '</tr>'
        for row in rows
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Vision Dashboard - {log_name}</title>
<style>
body{{background:#0f0f1a;color:#e0e0e0;font-family:system-ui,sans-serif;padding:20px}}
h1{{color:#90caf9}}
.note{{color:#aaa;font-size:0.9em;margin:10px 0 20px}}
table{{border-collapse:collapse;width:100%}}
th{{background:#16213e;color:#90caf9;padding:8px 12px;text-align:left}}
td{{padding:6px 12px;border-bottom:1px solid #2a2a4a}}
</style></head>
<body>
<h1>Vision Dashboard - {log_name}</h1>
<p class="note">{duration:.0f} s &nbsp;|&nbsp; cameras: {', '.join(cameras)}
&nbsp;|&nbsp; format: {'new (raw pre-filter)' if fmt == 'new' else 'old (post-filter)'}
{'&nbsp;|&nbsp;' + meta.get('ProjectName','') + ' @ ' + meta.get('GitHash','')[:7]
 if meta.get('ProjectName') else ''}</p>
<p class="note">For the full interactive dashboard run:
<code>streamlit run tools/vision-analyzer/analyze.py</code></p>
<table><thead>{thead}</thead><tbody>{tbody}</tbody></table>
</body></html>"""
    out_path.write_text(html, encoding='utf-8')


def _cli_main() -> None:
    parser = argparse.ArgumentParser(
        description='Vision Log Analyzer. Run with `streamlit run analyze.py` for the dashboard.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('paths', nargs='*', help='.wpilog file(s) or a directory')
    parser.add_argument('--output', '-o', metavar='DIR',
                        help='Output directory for HTML reports (legacy mode)')
    parser.add_argument('--probe', action='store_true',
                        help='Dump all signal names and types, then exit')
    args = parser.parse_args()

    if not args.paths:
        print('Usage: streamlit run analyze.py   (dashboard)')
        print('       python analyze.py --probe log.wpilog  (signal dump)')
        sys.exit(0)

    log_files: List[str] = []
    for p in args.paths:
        pp = pathlib.Path(p)
        if pp.is_dir():
            log_files.extend(str(f) for f in sorted(pp.glob('*.wpilog')))
        elif pp.suffix == '.wpilog':
            log_files.append(str(pp))
        else:
            print(f'Warning: {p} is not a .wpilog file or directory, skipping.',
                  file=sys.stderr)

    if not log_files:
        print('No .wpilog files found.', file=sys.stderr)
        sys.exit(1)

    if args.probe:
        for lf in log_files:
            probe_signals(lf)
        return

    # Legacy: write an HTML dashboard for backward compatibility
    for lf in log_files:
        try:
            print(f'Reading {lf} ...', end=' ', flush=True)
            all_metrics, duration, meta, cameras = _load_log(lf)
            print(f'{len(cameras)} cameras.')
            if not all_metrics:
                print('  No vision cameras found. Skipping.')
                continue
            for m in all_metrics:
                sq = m.get('stationary_quality')
                sq_str = f'{sq:.0f}%' if sq is not None else 'n/a'
                print(f'  {m["camera"]}: format={m["format"]}  '
                      f'acceptance={m["acceptance_rate"]:.0f}%  '
                      f'stationary_quality={sq_str}')
            # Generate a minimal HTML placeholder pointing to the Streamlit app
            out_dir  = pathlib.Path(args.output) if args.output else pathlib.Path(lf).parent
            out_dir.mkdir(parents=True, exist_ok=True)
            stem     = pathlib.Path(lf).stem
            out_path = out_dir / f'{stem}_vision_dashboard.html'
            _write_legacy_html(all_metrics, duration, meta, pathlib.Path(lf).name, out_path)
            print(f'  -> {out_path}')
        except Exception as e:
            print(f'Error processing {lf}: {e}', file=sys.stderr)
            import traceback; traceback.print_exc()
