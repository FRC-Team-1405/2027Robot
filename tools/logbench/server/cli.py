"""logbench CLI -- the tool's headless surface over core/.

The web UI and this CLI are two views over the same library: nothing in core/ knows
either exists. That means a metric or composite change can be validated here -- by a
human, a test, or an LLM -- with no browser and no npm involved, and the --json output is
meant to be asserted against directly rather than scraped.

    python cli.py metrics path/to/log.wpilog
    python cli.py metrics path/to/log.wpilog --mode auto --metric still_score --json
    python cli.py compare path/to/a.wpilog path/to/b.wpilog --mode auto
    python cli.py compare path/to/a.wpilog path/to/b.wpilog --window-a 0 15 --window-b 3 18
"""
import argparse
import dataclasses
import json
import sys
from typing import List, Optional

import paths  # noqa: F401  (side effect: sys.path bridges)

from core.compare import WindowSelector, compare, make_run
from core.log import Log

# A representative default set for a quick look: the robot's own composite, both
# logbench composites, then the raw per-camera factors and log-derived metrics that feed
# them, so `--json` output is useful without also passing --metric a dozen times.
DEFAULT_METRICS = [
    'score_pct', 'still_score', 'motion_score',
    'stillness_pct', 'area_pct', 'ambiguity_pct', 'fps_pct', 'jitter_pct',
    'acceptance_pct', 'latency_pct', 'multitag_pct',
    'acceptance_rate', 'fps_mean', 'fps_min', 'conn_uptime_pct', 'latency_mean_ms',
]


def _fmt(v: Optional[float]) -> str:
    return 'n/a' if v is None else f'{v:.2f}'


def _selector(mode: str, window: Optional[List[float]]) -> WindowSelector:
    if window is not None:
        lo, hi = window
        return WindowSelector(manual=(lo, hi))
    return WindowSelector(mode=mode)


def _metrics_cmd(args) -> int:
    log = Log.load(args.log)
    run = make_run(log, _selector(args.mode, args.window), label=args.log)
    cameras = args.camera or log.cameras()
    metric_ids = args.metric or DEFAULT_METRICS

    rows = [
        {'metric': metric_id, 'camera': camera, 'value': run.value(metric_id, camera)}
        for metric_id in metric_ids
        for camera in cameras
    ]

    if args.json:
        json.dump({
            'log': args.log,
            'window': dataclasses.asdict(run.window),
            'cameras': cameras,
            'metrics': rows,
        }, sys.stdout, indent=2)
        print()
    else:
        print(f'{args.log}  window=[{run.window.lo:.2f}, {run.window.hi:.2f}]s '
              f'({run.window.duration:.2f}s)  cameras={", ".join(cameras) or "(none found)"}')
        for row in rows:
            print(f"  {row['camera']:<10} {row['metric']:<20} {_fmt(row['value'])}")
    return 0


def _compare_cmd(args) -> int:
    log_a = Log.load(args.log_a)
    log_b = Log.load(args.log_b)
    sel_a = _selector(args.mode, args.window_a)
    sel_b = _selector(args.mode, args.window_b)
    run_a = make_run(log_a, sel_a, label=args.log_a)
    run_b = make_run(log_b, sel_b, label=args.log_b)

    cameras = args.camera or sorted(set(log_a.cameras()) | set(log_b.cameras()))
    metric_ids = args.metric or DEFAULT_METRICS
    deltas = compare(run_a, run_b, metric_ids, cameras)

    if args.json:
        json.dump({
            'a': {'log': args.log_a, 'window': dataclasses.asdict(run_a.window)},
            'b': {'log': args.log_b, 'window': dataclasses.asdict(run_b.window)},
            'cameras': cameras,
            'deltas': [dataclasses.asdict(d) for d in deltas],
        }, sys.stdout, indent=2)
        print()
    else:
        print(f'A: {args.log_a}  window=[{run_a.window.lo:.2f}, {run_a.window.hi:.2f}]s')
        print(f'B: {args.log_b}  window=[{run_b.window.lo:.2f}, {run_b.window.hi:.2f}]s')
        for d in deltas:
            print(f'  {d.camera:<10} {d.label:<26} A={_fmt(d.a):<8} B={_fmt(d.b):<8} '
                  f'delta={_fmt(d.delta):<8} {d.verdict}')
    return 0


def _add_window_args(p: argparse.ArgumentParser, *, per_log: bool) -> None:
    p.add_argument('--mode', choices=['auto', 'teleop', 'disabled', 'whole'], default='whole',
                    help="select this DS-mode span (default: whole log, i.e. no trim)")
    if per_log:
        p.add_argument('--window-a', type=float, nargs=2, metavar=('LO', 'HI'),
                        help='manual [lo, hi] seconds relative to log A start; overrides --mode for A only')
        p.add_argument('--window-b', type=float, nargs=2, metavar=('LO', 'HI'),
                        help='manual [lo, hi] seconds relative to log B start; overrides --mode for B only')
    else:
        p.add_argument('--window', type=float, nargs=2, metavar=('LO', 'HI'),
                        help='manual [lo, hi] seconds relative to log start; overrides --mode')


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='command', required=True)

    p_metrics = sub.add_parser('metrics', help='dump metrics/composites for one log')
    p_metrics.add_argument('log')
    p_metrics.add_argument('--camera', action='append',
                            help='repeatable; default: every camera discovered in the log')
    p_metrics.add_argument('--metric', action='append',
                            help='repeatable metric/composite id; default: a standard set')
    _add_window_args(p_metrics, per_log=False)
    p_metrics.add_argument('--json', action='store_true')
    p_metrics.set_defaults(func=_metrics_cmd)

    p_compare = sub.add_parser('compare', help='compare two logs metric-by-metric')
    p_compare.add_argument('log_a')
    p_compare.add_argument('log_b')
    p_compare.add_argument('--camera', action='append')
    p_compare.add_argument('--metric', action='append')
    _add_window_args(p_compare, per_log=True)
    p_compare.add_argument('--json', action='store_true')
    p_compare.set_defaults(func=_compare_cmd)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
