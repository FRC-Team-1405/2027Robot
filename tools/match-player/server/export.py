"""Produces a self-contained .html player with one log's data baked in.

The output has no external references at all -- no CDN, no fetch, no separate .js. That
matters for two reasons: the Streamlit calibration tab embeds this string directly in an
iframe (so playback never touches the Streamlit server), and a competition venue's wifi
cannot be relied on, so a replay you want to show someone in the pit has to work from a
file on a USB stick.

The bundle it injects into is built by `npm run build:single` in web/ and committed at
assets/player.singlefile.html, so running the calibration app does not require Node.
"""
import json
import pathlib

_ASSET = pathlib.Path(__file__).resolve().parent / 'assets' / 'player.singlefile.html'

_BUILD_HINT = (
    'Run:  cd tools/match-player/web && npm install && npm run build:single'
)


class BundleMissing(RuntimeError):
    pass


def bundle_path() -> pathlib.Path:
    return _ASSET


def bundle_exists() -> bool:
    return _ASSET.exists()


def _json_for_script(payload: dict) -> str:
    """JSON safe to embed inside a <script> block.

    Three hazards, all of which come from data the robot wrote (Reason strings,
    track labels) rather than from us, so none can be assumed away:
      - a literal "</script>" would close the tag early and break the whole page;
      - U+2028/U+2029 are valid in JSON but are line terminators in JavaScript, so
        they would turn a valid string literal into a syntax error.
    Escaping every < and > is blunt but keeps the check obvious.

    The escapes are built from chr(92) rather than written as backslash literals so
    that a copy/paste or re-encode of this file cannot silently turn them into the
    characters they are supposed to be escaping (which would make this a no-op).
    """
    text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    for ch, code in ((chr(60), "u003c"), (chr(62), "u003e"),
                     (chr(0x2028), "u2028"), (chr(0x2029), "u2029")):
        text = text.replace(ch, chr(92) + code)
    return text


def render_single_file(payload: dict) -> str:
    """payload: the dict from encode.spec_to_dict (or the parsed /api/spec response)."""
    if not bundle_exists():
        raise BundleMissing(
            'the single-file player bundle is missing at %s. %s' % (_ASSET, _BUILD_HINT)
        )
    html = _ASSET.read_text(encoding='utf-8')
    script = '<script>window.__MATCH_SPEC__=%s;</script>' % _json_for_script(payload)

    # Must land before the bundle executes, so useSpec() finds it on first render.
    # Every Vite build has a </head>; prepending is a last resort that still produces a
    # working page rather than a player silently missing its data.
    if '</head>' in html:
        return html.replace('</head>', script + '</head>', 1)
    return script + html


def render_from_log(log_path: str, spec_name: str = None) -> str:
    """Convenience: parse a .wpilog and return the standalone player for it."""
    import paths  # noqa: F401

    import specs
    from encode import spec_to_dict

    from vision_analyzer.parser import parse_wpilog

    builder = specs.get(spec_name or specs.DEFAULT)
    signals = parse_wpilog(log_path)
    spec, data = builder.build(signals, title=pathlib.Path(log_path).name)
    return render_single_file(spec_to_dict(spec, data))


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('log')
    ap.add_argument('--out', help='default: replay-<logname>.html beside the log')
    ap.add_argument('--spec', default=None)
    args = ap.parse_args(argv)

    src = pathlib.Path(args.log)
    out = pathlib.Path(args.out) if args.out else src.with_name('replay-%s.html' % src.stem)
    html = render_from_log(str(src), args.spec)
    out.write_text(html, encoding='utf-8')
    print('wrote %s  (%.2f MB)' % (out, len(html.encode()) / 1e6))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
