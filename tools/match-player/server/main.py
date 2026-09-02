"""FastAPI host for the match player: browse logs on disk, serve their specs, serve the
built front end.

    python -m server.main --logs ../../logs
    python server/main.py --logs ../../logs --port 8765

Parsing a large .wpilog takes a few seconds, so specs are cached by (path, mtime, spec
name) -- reopening a log you already looked at is instant, and editing the robot code and
re-recording invalidates the entry on its own.

This server is only one of three ways to run the player; the standalone export and the
Streamlit tab need nothing from this file (see export.py).
"""
import argparse
import json
import pathlib
import sys
from typing import Optional

import paths  # noqa: F401  (side effect: sys.path bridges)

import specs
from encode import spec_to_dict

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from vision_analyzer.parser import parse_wpilog

_HERE = pathlib.Path(__file__).resolve().parent
_DIST = _HERE.parent / 'web' / 'dist'

app = FastAPI(title='Match Player')
# The spec payload is mostly repeated small integers (see encode.py) and compresses
# roughly 4:1 -- a 26-minute log goes from 3.8 MB to 0.83 MB.
app.add_middleware(GZipMiddleware, minimum_size=1024)

# Set by main(); a module-level default keeps `uvicorn server.main:app` usable.
LOG_ROOT: pathlib.Path = pathlib.Path.cwd()

_spec_cache: dict = {}


def _resolve(rel: str) -> pathlib.Path:
    """Resolve a client-supplied path against LOG_ROOT, refusing anything that escapes
    it. The tool is meant for a laptop on a robot bench, but path traversal is cheap to
    close and there is no reason to leave it open."""
    p = (LOG_ROOT / rel).resolve()
    try:
        p.relative_to(LOG_ROOT.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail='path outside the log directory')
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail='no such log: %s' % rel)
    return p


@app.get('/api/logs')
def list_logs() -> dict:
    root = LOG_ROOT.resolve()
    out = []
    for p in sorted(root.rglob('*.wpilog')):
        stat = p.stat()
        out.append({
            'path': p.relative_to(root).as_posix(),
            'name': p.name,
            'size': stat.st_size,
            'mtime': stat.st_mtime,
        })
    return {'root': str(root), 'logs': out, 'specs': specs.listing()}


@app.get('/api/spec')
def get_spec(
    log: str = Query(..., description='log path relative to the log root'),
    spec: str = Query(specs.DEFAULT),
) -> JSONResponse:
    path = _resolve(log)
    key = (str(path), path.stat().st_mtime, spec)
    if key not in _spec_cache:
        try:
            builder = specs.get(spec)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        signals = parse_wpilog(str(path))
        player_spec, data = builder.build(signals, title=path.name)
        # Cache one log at a time: these are megabytes each, and the workflow is
        # "look at one log closely", not "flip between twenty".
        _spec_cache.clear()
        _spec_cache[key] = spec_to_dict(player_spec, data)
    return JSONResponse(_spec_cache[key])


@app.get('/api/export')
def export(log: str = Query(...), spec: str = Query(specs.DEFAULT)) -> HTMLResponse:
    """The standalone single-file player for this log, as a download."""
    from export import render_single_file

    path = _resolve(log)
    payload = get_spec(log=log, spec=spec).body
    html = render_single_file(json.loads(payload))
    return HTMLResponse(
        html,
        headers={'Content-Disposition': 'attachment; filename="replay-%s.html"' % path.stem},
    )


if _DIST.exists():
    app.mount('/', StaticFiles(directory=str(_DIST), html=True), name='web')
else:
    @app.get('/')
    def _needs_build() -> HTMLResponse:
        return HTMLResponse(
            '<pre style="font:13px ui-monospace;padding:24px">'
            'The front end has not been built yet.\n\n'
            '  cd tools/match-player/web &amp;&amp; npm install &amp;&amp; npm run build\n\n'
            'Or run the Vite dev server (npm run dev) and use http://localhost:5173 '
            'instead -- it proxies /api here.</pre>',
            status_code=503,
        )


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--logs', default='.', help='directory to search for .wpilog files')
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--host', default='127.0.0.1')
    args = ap.parse_args(argv)

    global LOG_ROOT
    LOG_ROOT = pathlib.Path(args.logs).resolve()
    if not LOG_ROOT.is_dir():
        print('not a directory: %s' % LOG_ROOT, file=sys.stderr)
        return 2

    import uvicorn

    print('log root: %s' % LOG_ROOT)
    print('open:     http://%s:%d/' % (args.host, args.port))
    uvicorn.run(app, host=args.host, port=args.port, log_level='warning')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
