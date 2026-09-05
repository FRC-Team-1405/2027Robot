"""FastAPI host for logbench: browse logs on disk, serve their specs, serve the
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
import collections
import dataclasses
import json
import pathlib
import sys
from typing import List, Optional

import paths  # noqa: F401  (side effect: sys.path bridges)

import live_nt
import specs
from cli import DEFAULT_METRICS
from core.compare import WindowSelector, compare, make_run
from core.composites import COMPOSITES
from core.log import Log
from core.metrics import METRICS
from core.severity import BANDS as SEVERITY_BANDS
from encode import spec_to_dict

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from vision_analyzer.parser import parse_wpilog

_HERE = pathlib.Path(__file__).resolve().parent
_DIST = _HERE.parent / 'web' / 'dist'

app = FastAPI(title='Logbench')
# The spec payload is mostly repeated small integers (see encode.py) and compresses
# roughly 4:1 -- a 26-minute log goes from 3.8 MB to 0.83 MB.
app.add_middleware(GZipMiddleware, minimum_size=1024)

# Set by main(); a module-level default keeps `uvicorn server.main:app` usable.
LOG_ROOT: pathlib.Path = pathlib.Path.cwd()

_spec_cache: dict = {}

# Comparing two logs needs both parsed at once, unlike the single-log replay workflow
# _spec_cache is sized for -- an LRU keeps a handful of recently-opened logs around so
# switching which pair you're comparing doesn't re-parse one you already had loaded.
_LOG_CACHE_SIZE = 4
_log_cache: 'collections.OrderedDict[tuple, Log]' = collections.OrderedDict()


def _load_log(path: pathlib.Path) -> Log:
    key = (str(path), path.stat().st_mtime)
    if key in _log_cache:
        _log_cache.move_to_end(key)
        return _log_cache[key]
    log = Log.load(str(path))
    _log_cache[key] = log
    if len(_log_cache) > _LOG_CACHE_SIZE:
        _log_cache.popitem(last=False)
    return log


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


@app.get('/api/log-info')
def log_info(log: str = Query(..., description='log path relative to the log root')) -> dict:
    """Bounds, cameras, and DS-mode spans for one log -- what the compare page's window
    picker needs to render a mode dropdown with real numbers and sane manual-slice
    defaults, without shipping the whole parsed log to do it."""
    path = _resolve(log)
    parsed = _load_log(path)
    t0, t1 = parsed.bounds()
    return {
        'path': log,
        'bounds': [t0, t1],
        'duration': t1 - t0,
        'cameras': parsed.cameras(),
        'mode_spans': [
            {'lo': lo, 'hi': hi, 'mode': mode} for lo, hi, mode in parsed.mode_spans()
        ],
    }


@app.get('/api/metric-catalog')
def metric_catalog() -> dict:
    """Every registered Metric and Composite, so the compare page's metric picker never
    has to hardcode an id list that can drift from core/metrics.py and core/composites.py."""
    return {
        'defaults': DEFAULT_METRICS,
        'severity': SEVERITY_BANDS,
        'metrics': (
            [{'id': m.id, 'label': m.label, 'unit': m.unit, 'lowerIsBetter': m.lower_is_better,
              'kind': 'metric'} for m in METRICS.values()]
            + [{'id': c.id, 'label': c.label, 'unit': '%', 'lowerIsBetter': c.lower_is_better,
                'kind': 'composite'} for c in COMPOSITES.values()]
        ),
    }


def _parse_manual_window(raw: Optional[str]) -> Optional[tuple]:
    """'lo,hi' (seconds relative to the log's own start) -> (lo, hi), or None."""
    if not raw:
        return None
    try:
        lo_s, hi_s = raw.split(',')
        return float(lo_s), float(hi_s)
    except ValueError:
        raise HTTPException(status_code=400, detail='window must be "lo,hi" in seconds, got %r' % raw)


@app.get('/api/compare')
def compare_logs(
    log_a: str = Query(...),
    log_b: str = Query(...),
    mode: str = Query('whole', description="DS-mode span to select in each log when no manual window is given"),
    window_a: Optional[str] = Query(None, description='manual "lo,hi" seconds for log A; overrides mode for A only'),
    window_b: Optional[str] = Query(None, description='manual "lo,hi" seconds for log B; overrides mode for B only'),
    metric: Optional[List[str]] = Query(None, description='repeatable; default: a standard set'),
    camera: Optional[List[str]] = Query(None, description='repeatable; default: every camera in either log'),
) -> dict:
    path_a = _resolve(log_a)
    path_b = _resolve(log_b)
    log_obj_a = _load_log(path_a)
    log_obj_b = _load_log(path_b)

    sel_a = WindowSelector(manual=_parse_manual_window(window_a)) if window_a else WindowSelector(mode=mode)
    sel_b = WindowSelector(manual=_parse_manual_window(window_b)) if window_b else WindowSelector(mode=mode)
    try:
        run_a = make_run(log_obj_a, sel_a, label=log_a)
        run_b = make_run(log_obj_b, sel_b, label=log_b)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    cameras = camera or sorted(set(log_obj_a.cameras()) | set(log_obj_b.cameras()))
    metric_ids = metric or DEFAULT_METRICS
    deltas = compare(run_a, run_b, metric_ids, cameras)

    return {
        'a': {'log': log_a, 'window': dataclasses.asdict(run_a.window)},
        'b': {'log': log_b, 'window': dataclasses.asdict(run_b.window)},
        'cameras': cameras,
        'deltas': [dataclasses.asdict(d) for d in deltas],
    }


@app.post('/api/live/connect')
def live_connect(
    server: str = Query(..., description='team number or IP/hostname of the NT4 server'),
    root_table: str = Query(live_nt.DEFAULT_ROOT_TABLE),
) -> dict:
    """Connects (or reconnects, if settings changed) the process-wide NT4 client the Pit
    Check page polls. There is exactly one live connection at a time -- this tool runs on
    a laptop on a bench next to one robot, not a fleet."""
    try:
        live_nt.connect(server, root_table)
    except ModuleNotFoundError as exc:
        raise HTTPException(status_code=501, detail=(
            'ntcore is not installed in this environment (%s). Install pyntcore/robotpy '
            'to use the live Pit Check page -- log replay and Compare do not need it.' % exc
        ))
    return {'connected': live_nt.is_connected()}


@app.get('/api/live/snapshot')
def live_snapshot() -> dict:
    """The Pit Check page polls this a few times a second (see live_nt.read()'s
    docstring) -- simple HTTP polling rather than a WebSocket, matching the
    st.fragment(run_every=...) polling the camera-calibration tab this replaces already
    used, and easy to test with a plain fetch()."""
    return live_nt.read()


@app.post('/api/live/disconnect')
def live_disconnect() -> dict:
    live_nt.disconnect()
    return {'connected': False}


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
            '  cd tools/logbench/web &amp;&amp; npm install &amp;&amp; npm run build\n\n'
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
