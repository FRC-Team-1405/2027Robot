"""CLI: turn a .wpilog into a player spec JSON, and report what came out.

This is the tool's headless surface. It exists so the whole server-side half can be
exercised -- and its payload size checked against budget -- with no browser, no npm,
and no Streamlit involved.

    python dump_spec.py path/to/log.wpilog --out spec.json
    python dump_spec.py path/to/log.wpilog --stats
"""
import argparse
import gzip
import json
import pathlib
import sys

import paths  # noqa: F401  (side effect: sys.path bridge)

import specs
from encode import spec_to_dict

from vision_analyzer.parser import parse_wpilog


def build_spec_dict(log_path: str, spec_name: str = specs.DEFAULT, title: str = None) -> dict:
    signals = parse_wpilog(log_path)
    builder = specs.get(spec_name)
    spec, data = builder.build(signals, title=title or pathlib.Path(log_path).name)
    return spec_to_dict(spec, data)


def _stats(payload: dict) -> str:
    raw = json.dumps(payload, separators=(',', ':')).encode()
    gz = gzip.compress(raw, 6)
    lines = [
        'title      %s' % payload['title'],
        'duration   %.1fs  (t0=%.3f t1=%.3f)' % (payload['duration'], payload['t0'], payload['t1']),
        'groups     %s' % ', '.join(g['id'] for g in payload['groups']),
        'panels     %s' % ', '.join('%s(%s)' % (p['id'], p['type']) for p in payload['panels']),
        'layout     %s' % payload['layout'],
        'tracks     %d' % len(payload['tracks']),
        'samples    %d' % sum(s['n'] for s in payload['data'].values()),
        'payload    %.2f MB raw / %.2f MB gzip' % (len(raw) / 1e6, len(gz) / 1e6),
    ]
    for w in payload['warnings']:
        lines.append('WARNING    %s' % w)
    lines.append('')
    lines.append('%-28s %-8s %7s  %s' % ('track', 'kind', 'n', 'label'))
    for t in payload['tracks']:
        s = payload['data'][t['id']]
        flag = ' [decimated]' if s.get('decimated') else ''
        lines.append('%-28s %-8s %7d  %s%s' % (t['id'], t['kind'], s['n'], t['label'], flag))
    return '\n'.join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('log', help='path to a .wpilog file')
    ap.add_argument('--out', help='write spec JSON here (default: stdout unless --stats)')
    ap.add_argument('--spec', default=specs.DEFAULT,
                    help='spec builder name (default: %(default)s)')
    ap.add_argument('--title', help='override the spec title')
    ap.add_argument('--stats', action='store_true',
                    help='print a human summary instead of the JSON')
    ap.add_argument('--indent', type=int, default=None, help='pretty-print the JSON')
    args = ap.parse_args(argv)

    if not pathlib.Path(args.log).exists():
        print('not found: %s' % args.log, file=sys.stderr)
        return 2

    payload = build_spec_dict(args.log, args.spec, args.title)

    if args.out:
        pathlib.Path(args.out).write_text(
            json.dumps(payload, indent=args.indent,
                       separators=None if args.indent else (',', ':')),
            encoding='utf-8',
        )
        print('wrote %s' % args.out, file=sys.stderr)
    if args.stats or args.out:
        print(_stats(payload))
    elif not args.out:
        json.dump(payload, sys.stdout, separators=(',', ':'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
