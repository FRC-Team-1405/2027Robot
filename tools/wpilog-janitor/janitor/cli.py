"""
Command line for wpilog-janitor.

    python -m janitor analyze LOG [--depth 2] [--top 15]
    python -m janitor trim LOG [-o OUT] [--modes auto,teleop] [--only 0,2] [--range START:END ...]
                               [--gap-ms 200] [--pad-pre-ms N] [--pad-post-ms N] [--preserve]
                               [--exclude NAME ...] [--exclude-prefix PREFIX ...] [--dry-run] [--no-verify]
    python -m janitor segmap TRIMMED_LOG
    python -m janitor serve [--logs DIR] [--port 8767]      # web UI

Times are seconds from the log's first record (the same clock `analyze` prints).
"""
import argparse
import json
import pathlib
import sys
from typing import List, Optional

from . import paths  # noqa: F401  (side effect: wpilog_utils importable)
from .core import sizes
from wpilog_utils.decode import parse_wpilog_bytes
from wpilog_utils.index import LogIndex, build_index
from wpilog_utils.trim import (SEGMENT_MAP_ENTRY, Segment, TrimPlan, dry_run, mode_segments, resolve_plan,
                               trim_log)
from wpilog_utils.verify import verify_trim


class CliError(Exception):
    """A user-facing problem (bad path, not a log). main() prints it without a traceback and exits 2."""


def _list_logs(folder: pathlib.Path, limit: int = 25) -> str:
    logs = sorted(folder.rglob('*.wpilog'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        return f'{folder} contains no .wpilog files'
    lines = [f'{folder} is a folder, not a log. {len(logs)} .wpilog file(s) inside, newest first -- pass one of these:']
    for p in logs[:limit]:
        lines.append(f'  {sizes.human(p.stat().st_size):>9s}  {p}')
    if len(logs) > limit:
        lines.append(f'  ... and {len(logs) - limit} more')
    return '\n'.join(lines)


def _read_file(path: str) -> bytes:
    p = pathlib.Path(path)
    if p.is_dir():
        raise CliError(_list_logs(p))
    try:
        return p.read_bytes()
    except FileNotFoundError:
        raise CliError(f'no such file: {p}')
    except OSError as exc:
        raise CliError(f'cannot read {p}: {exc.strerror or exc}')


def _read(path: str):
    raw = _read_file(path)
    try:
        return raw, build_index(raw)
    except ValueError as exc:
        raise CliError(f'{path} is not a readable .wpilog: {exc}')


def cmd_analyze(args) -> int:
    raw, ix = _read(args.log)
    h = sizes.human
    print(f'{args.log}')
    print(f'  size        {h(len(raw))}   ({len(raw):,} bytes)')
    print(f'  duration    {ix.duration_s:.1f} s   records {ix.n_records:,}   entries {len(ix.entries)}')
    print(f'  cycles      {len(ix.cycles_us):,}   period {ix.cycle_period_us() / 1000:.1f} ms'
          f'   marker {ix.entry_by_name("/Timestamp") and "/Timestamp" or "none (every timestamp is a cycle)"}')
    print(f'  header      {ix.extra_header.decode("utf-8", "replace")!r}')
    tail = len(raw) - (ix.header_end + ix.control_bytes + ix.data_bytes)
    if tail > 0:
        print(f'  note        {tail} trailing bytes are not a complete record (log ended mid-write); they are dropped on trim')
    if not ix.time_ordered:
        print('  WARNING     records are not in time order; trimming is not supported for this log')
    if ix.n_unregistered_records:
        print(f'  WARNING     {ix.n_unregistered_records} data records belong to entries that were never started')

    spans = ix.mode_spans()
    print('\nModes (seconds from log start)')
    if not spans:
        print('  no DriverStation/Enabled data in this log; use --range to pick times')
    else:
        counts = {}
        for i, (a, b, m) in enumerate(spans):
            counts[m] = counts.get(m, -1) + 1
            nb = ix.window_bytes(a, b)
            print(f'  {m:9s} #{counts[m]}  {a:8.1f} -> {b:8.1f}   {b - a:7.1f} s   {h(nb):>9s}  {100 * nb / max(1, ix.data_bytes):5.1f}%')

    print(f'\nBytes by path (depth {args.depth})')
    for g in sizes.rollup(ix, args.depth)[:args.top]:
        print(f'  {g.prefix:34s} {h(g.bytes):>9s}  {100 * g.bytes / max(1, len(raw)):5.1f}%   {g.entries:4d} entries  {g.records:9,} records')

    print(f'\nLargest entries (top {args.top})')
    for e in sizes.top_entries(ix, args.top):
        print(f'  {e.name:50s} {e.type:16s} {h(e.bytes):>9s}  {100 * e.bytes / max(1, len(raw)):5.1f}%  {e.n_records:8,} rec')
    return 0


def _parse_range(text: str) -> Segment:
    try:
        a, b = text.split(':')
        return Segment(float(a), float(b), 'manual')
    except ValueError:
        raise argparse.ArgumentTypeError(f'--range wants START:END in seconds, got {text!r}')


def build_plan(args, ix: LogIndex) -> TrimPlan:
    segs: List[Segment] = []
    if args.modes:
        which = [int(x) for x in args.only.split(',')] if args.only else None
        segs += mode_segments(ix, [m.strip() for m in args.modes.split(',')], which, args.pad_pre_ms, args.pad_post_ms)
    for r in args.range or []:
        segs.append(Segment(r.start, r.end, r.label, args.pad_pre_ms, args.pad_post_ms))
    return TrimPlan(segs, gap_ms=args.gap_ms, gap_policy='preserve' if args.preserve else 'compact',
                    exclude=args.exclude or [], exclude_prefixes=args.exclude_prefix or [],
                    source_name=pathlib.Path(args.log).name)


def cmd_trim(args) -> int:
    raw, ix = _read(args.log)
    plan = build_plan(args, ix)
    if not plan.segments:
        if args.modes:
            present = sorted({m for *_, m in ix.mode_spans()}) or ['none: no DriverStation data']
            print(f'nothing selected: no span matches --modes {args.modes}'
                  + (f' --only {args.only}' if args.only else '')
                  + f' in this log (modes present: {", ".join(present)}); use --range for arbitrary times', file=sys.stderr)
        else:
            print('nothing selected: give --modes and/or --range (run `analyze` to see the modes)', file=sys.stderr)
        return 2
    try:
        res = resolve_plan(ix, plan)
    except ValueError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    for w in res.warnings:
        print(f'warning: {w}', file=sys.stderr)

    h = sizes.human
    for s in res.segments:
        print(f'  keep {s.label or "range":9s} {s.orig_first_s:8.2f} -> {s.orig_last_s:8.2f} s'
              f'   becomes {s.new_first_s:7.2f} -> {s.new_last_s:7.2f} s')
    for i, seam in enumerate(res.seams):
        print(f'  seam {i + 1}: {seam["dropped_cycles"]:,} cycles dropped, {seam["real_cycles_kept_before"] + seam["real_cycles_kept_after"]}'
              f' real cycles kept around the cut')

    if args.dry_run:
        st = dry_run(raw, ix, plan, res)
        _print_stats(st, h, None)
        return 0

    out, st = trim_log(raw, ix, plan, res)
    dest = pathlib.Path(args.output) if args.output else pathlib.Path(args.log).with_name(pathlib.Path(args.log).stem + '_trimmed.wpilog')
    dest.write_bytes(out)
    _print_stats(st, h, dest)

    if not args.no_verify:
        rep = verify_trim(out, raw, ix, plan, res)
        print(f'  verify: {rep}')
        return 0 if rep.ok else 1
    return 0


def _print_stats(st, h, dest) -> None:
    print(f'  {h(st.source_bytes)} -> {h(st.bytes_out)}   saved {h(st.saved_bytes)} ({st.saved_pct:.1f}%)'
          f'   cycles {st.n_cycles_out:,}/{st.n_cycles_source:,}   restated {st.n_carried} values'
          + (f'   excluded {st.n_excluded_records:,} records' if st.n_excluded_records else ''))
    if st.control_records_dropped:
        print(f'  note: {st.control_records_dropped} Finish/late-metadata control record(s) were not reproduced')
    if dest:
        print(f'  wrote {dest}')


def cmd_segmap(args) -> int:
    raw = _read_file(args.log)
    try:
        entries = parse_wpilog_bytes(raw).get(SEGMENT_MAP_ENTRY.lstrip('/'))
    except ValueError as exc:
        raise CliError(f'{args.log} is not a readable .wpilog: {exc}')
    if not entries:
        print(f'{args.log}: no {SEGMENT_MAP_ENTRY} entry -- not produced by wpilog-janitor', file=sys.stderr)
        return 1
    note = json.loads(entries[0][1])
    if args.json:
        print(json.dumps(note, indent=2))
        return 0
    print(f'{note["source_file"] or "(unnamed source)"}  {note["source_bytes"]:,} bytes, '
          f'{note["source_t_min"]:.3f} -> {note["source_t_max"]:.3f} s, gap {note["gap_ms"]} ms ({note["gap_policy"]})')
    print('  new = orig + offset')
    for s in note['segments']:
        print(f'  {s["kind"] or "range":9s} orig {s["orig_first"]:9.3f} -> {s["orig_last"]:9.3f}   '
              f'new {s["new_first"]:9.3f} -> {s["new_last"]:9.3f}   offset {s["offset"]:+10.3f}')
    if note['excluded_entries']:
        print(f'  excluded {len(note["excluded_entries"])} entries')
    return 0


def cmd_serve(args) -> int:
    root = pathlib.Path(args.logs).resolve()
    if not root.is_dir():
        print(f'error: not a directory: {root}', file=sys.stderr)
        return 2
    import uvicorn
    from .server.main import DIST, create_app
    print(f'log root: {root}')
    if not DIST.exists():
        print('note: the front end is not built yet: cd tools/wpilog-janitor/web && npm install && npm run build', file=sys.stderr)
    print(f'open:     http://{args.host}:{args.port}/')
    uvicorn.run(create_app(root), host=args.host, port=args.port, log_level='warning')
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog='janitor', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    a = sub.add_parser('analyze', help='modes, sizes and where the bytes are')
    a.add_argument('log')
    a.add_argument('--depth', type=int, default=2, help='path components to group by (default 2)')
    a.add_argument('--top', type=int, default=15)
    a.set_defaults(fn=cmd_analyze)

    t = sub.add_parser('trim', help='keep only the chosen periods and write a new log')
    t.add_argument('log')
    t.add_argument('-o', '--output', help='default: <log>_trimmed.wpilog next to the source')
    t.add_argument('--modes', help='comma list of disabled/auto/teleop: keep every span of these modes')
    t.add_argument('--only', help='with --modes: keep only these spans (0-based, among the matching ones), e.g. 0,2')
    t.add_argument('--range', type=_parse_range, action='append', help='START:END seconds from log start; repeatable')
    t.add_argument('--gap-ms', type=float, default=200.0, help='real time kept on each seam (default 200)')
    t.add_argument('--pad-pre-ms', type=float, default=0.0)
    t.add_argument('--pad-post-ms', type=float, default=0.0)
    t.add_argument('--preserve', action='store_true', help='keep original timestamps (leaves a hole instead of a short gap)')
    t.add_argument('--exclude', action='append', metavar='NAME', help='drop this entry; repeatable')
    t.add_argument('--exclude-prefix', action='append', metavar='PREFIX', help='drop this entry and everything under it')
    t.add_argument('--dry-run', action='store_true', help='print the exact output size without writing')
    t.add_argument('--no-verify', action='store_true')
    t.set_defaults(fn=cmd_trim)

    s = sub.add_parser('segmap', help='show the original-time map stored in a trimmed log')
    s.add_argument('log')
    s.add_argument('--json', action='store_true')
    s.set_defaults(fn=cmd_segmap)

    v = sub.add_parser('serve', help='start the web UI')
    v.add_argument('--logs', default='.', help='directory to search for .wpilog files (default: current directory)')
    v.add_argument('--port', type=int, default=8767)
    v.add_argument('--host', default='127.0.0.1')
    v.set_defaults(fn=cmd_serve)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except CliError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
