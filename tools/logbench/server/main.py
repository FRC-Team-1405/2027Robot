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
import inspect
import io
import json
import logging
import pathlib
import re
import sys
import time
import zipfile
from typing import List, Optional

import paths  # noqa: F401  (side effect: sys.path bridges)

import bundles
import app_logging
import compare_export
import live_nt
import pairing
import remote_config
import remote_fetch
from remote_jobs import RemoteJobs
import specs
from cli import DEFAULT_METRICS
from core import categories
from core.compare import WindowSelector, compare, make_run
from core.composites import COMPOSITES
from core.log import Log
from core.metrics import METRICS
from core.severity import BANDS as SEVERITY_BANDS
from encode import spec_to_dict

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

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
remote_jobs = RemoteJobs()
log = logging.getLogger('logbench.server')


@app.on_event('startup')
def _configure_app_logging() -> None:
    app_logging.configure()


@app.middleware('http')
async def _log_requests(request: Request, call_next):
    request_id = request.headers.get('X-Request-ID', '') or __import__('uuid').uuid4().hex[:8]
    started = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        log.exception('%s %s request=%s failed after %.3fs', request.method, request.url.path,
                      request_id, time.monotonic() - started)
        raise
    response.headers['X-Request-ID'] = request_id
    log.info('%s %s request=%s status=%d duration=%.3fs', request.method, request.url.path,
             request_id, response.status_code, time.monotonic() - started)
    return response


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
    desc = compare_export.DESCRIPTIONS
    return {
        'defaults': DEFAULT_METRICS,
        'severity': SEVERITY_BANDS,
        # The category definitions (question, what a low reading means, whether it is scored),
        # so the page lays out and explains categories from the server's own words.
        'categories': categories.describe(),
        'metrics': (
            [{'id': m.id, 'label': m.label, 'unit': m.unit, 'lowerIsBetter': m.lower_is_better,
              'kind': 'metric', 'category': m.category, 'perCamera': m.per_camera,
              'description': desc.get(m.id, '')} for m in METRICS.values()]
            + [{'id': c.id, 'label': c.label, 'unit': '%', 'lowerIsBetter': c.lower_is_better,
                'kind': 'composite', 'category': c.category, 'perCamera': True,
                'description': desc.get(c.id, '')} for c in COMPOSITES.values()]
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


def _run_comparison(log_a, log_b, mode, window_a, window_b, metric, camera):
    """The one place a comparison is computed, shared by /api/compare and its export so
    a downloaded report can never disagree with what the page just showed."""
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
    unknown = [m for m in metric_ids if m not in METRICS and m not in COMPOSITES]
    if unknown:
        raise HTTPException(status_code=400, detail='unknown metric id(s): %s' % ', '.join(unknown))
    deltas = compare(run_a, run_b, metric_ids, cameras)
    return run_a, run_b, cameras, metric_ids, deltas


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
    run_a, run_b, cameras, _, deltas = _run_comparison(
        log_a, log_b, mode, window_a, window_b, metric, camera)
    return {
        'a': {'log': log_a, 'window': dataclasses.asdict(run_a.window)},
        'b': {'log': log_b, 'window': dataclasses.asdict(run_b.window)},
        'cameras': cameras,
        'deltas': [dataclasses.asdict(d) for d in deltas],
    }


@app.get('/api/compare/export')
def export_comparison(
    log_a: str = Query(...),
    log_b: str = Query(...),
    format: str = Query('html', pattern='^(html|json)$',
                        description='html for people, json for LLMs (see compare_export.py)'),
    mode: str = Query('whole'),
    window_a: Optional[str] = Query(None),
    window_b: Optional[str] = Query(None),
    metric: Optional[List[str]] = Query(None),
    camera: Optional[List[str]] = Query(None),
) -> Response:
    """Same parameters as /api/compare, returned as a downloadable file."""
    run_a, run_b, cameras, metric_ids, deltas = _run_comparison(
        log_a, log_b, mode, window_a, window_b, metric, camera)
    report = compare_export.build_report(
        run_a, run_b, deltas, cameras, metric_ids,
        mode=mode, manual_a=bool(window_a), manual_b=bool(window_b))

    stem_a = pathlib.PurePosixPath(log_a.replace('\\', '/')).stem
    stem_b = pathlib.PurePosixPath(log_b.replace('\\', '/')).stem
    filename = re.sub(r'[^A-Za-z0-9._-]+', '_', 'compare-%s-vs-%s.%s' % (stem_a, stem_b, format))
    if format == 'json':
        body, media = compare_export.render_json(report), 'application/json'
    else:
        body, media = compare_export.render_html(report), 'text/html'
    return Response(body, media_type=media,
                    headers={'Content-Disposition': 'attachment; filename="%s"' % filename})


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
        build_kwargs = {'title': path.name}
        # Not every builder knows about vision bundles (only camera_health does) --
        # only pass log_path/log_root through to ones that declare them, so this stays
        # generic as more specs/*.py builders are added.
        build_params = inspect.signature(builder.build).parameters
        if 'log_path' in build_params:
            build_kwargs['log_path'] = path
        if 'log_root' in build_params:
            build_kwargs['log_root'] = LOG_ROOT
        player_spec, data = builder.build(signals, **build_kwargs)
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


# ── Remote fetch (RIO + Pi over SFTP) ───────────────────────────────────────────────
# Every endpoint below is guarded by "no remote_config.json found" -- see
# remote_config.py. Absence isn't an error: a laptop that only browses locally-copied
# logs never needs this file, so /api/remote/sessions reports {'configured': False}
# instead of a 4xx/5xx, and the Fetch Bundle tab shows a setup message for that case
# while every other tab is unaffected.

class PiSessionRef(BaseModel):
    camera: str
    name: str


class BundleRequest(BaseModel):
    rio_log: str
    pi_sessions: List[PiSessionRef] = []
    # Echoed back, not otherwise interpreted here -- the manual/auto distinction only
    # matters to the client (whether to keep showing an auto-suggested pairing or one
    # the user picked by hand); fetching happens identically either way.
    manual: bool = False


def _iso(d) -> Optional[str]:
    return d.isoformat() if d is not None else None


def _remote_sessions_result(cfg, rio_raw: list[dict], pi_raw: list[dict]) -> dict:
    """Build the stable wire shape shared by the legacy and tracked list endpoints."""
    rio_infos = [pairing.RioLogInfo(name=r['name'], wall_clock=r['wall_clock']) for r in rio_raw]
    pi_infos = [pairing.PiSessionInfo(camera=s['camera'], name=s['name'], wall_clock=s['wall_clock'])
                for s in pi_raw]
    suggestions = pairing.suggest_pairings(rio_infos, pi_infos)

    root = LOG_ROOT.resolve()
    rio_out = [{
        'name': r['name'], 'size': r['size'], 'mtime': r['mtime'],
        'wall_clock': _iso(r['wall_clock']),
        'status': bundles.local_status(root / r['name']),
    } for r in rio_raw]
    pi_out = [{'camera': s['camera'], 'name': s['name'], 'wall_clock': _iso(s['wall_clock'])}
              for s in pi_raw]
    pairings_out = [{
        'rio_log': p.rio_log,
        'pi_sessions': [{'camera': s.camera, 'name': s.name} for s in p.pi_sessions],
        'confidence': p.confidence,
        'reason': p.reason,
    } for p in suggestions]
    return {'configured': True, 'rio_logs': rio_out, 'pi_sessions': pi_out, 'pairings': pairings_out}


def _job_or_404(job_id: str) -> dict:
    snapshot = remote_jobs.snapshot(job_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail='remote job not found or has expired')
    return snapshot


@app.post('/api/remote/sessions/jobs', status_code=202)
def start_remote_sessions_job() -> dict:
    """Start remote metadata discovery; polling exposes real connection/list phases."""
    cfg = remote_config.load_remote_config()
    if cfg is None:
        return {'configured': False}

    def work(job_id: str) -> dict:
        from concurrent.futures import ThreadPoolExecutor
        remote_jobs.set_phase(job_id, 'Connecting to roboRIO and Orange Pi')
        # These independent hosts are intentionally listed in parallel.  On a weak
        # robot network this removes the avoidable serial wait from page load.
        with ThreadPoolExecutor(max_workers=2) as executor:
            rio_future = executor.submit(remote_fetch.list_rio_logs, cfg.rio)
            pi_future = executor.submit(remote_fetch.list_pi_sessions, cfg.pi)
            remote_jobs.set_phase(job_id, 'Reading remote log and vision directories')
            rio_raw = rio_future.result()
            pi_raw = pi_future.result()
        if remote_jobs.cancelled(job_id):
            raise RuntimeError('cancelled by user')
        remote_jobs.set_phase(job_id, 'Matching logs and sessions')
        result = _remote_sessions_result(cfg, rio_raw, pi_raw)
        log.info('remote session job %s found %d RIO logs and %d Pi sessions', job_id,
                 len(rio_raw), len(pi_raw))
        return result

    job_id = remote_jobs.start('list-sessions', work)
    return {'configured': True, 'job_id': job_id}


@app.get('/api/remote/jobs/{job_id}')
def remote_job_status(job_id: str) -> dict:
    return _job_or_404(job_id)


@app.delete('/api/remote/jobs/{job_id}', status_code=202)
def cancel_remote_job(job_id: str) -> dict:
    _job_or_404(job_id)
    return {'cancelled': remote_jobs.cancel(job_id)}


@app.post('/api/remote/bundle/jobs', status_code=202)
def start_remote_bundle_job(body: BundleRequest) -> dict:
    """Start a bundled download and expose byte/file/throughput progress by polling."""
    cfg = remote_config.load_remote_config()
    if cfg is None:
        raise HTTPException(status_code=400, detail='no remote_config.json configured -- see remote_config.json.example')

    def work(job_id: str) -> dict:
        remote_jobs.set_phase(job_id, 'Inspecting selected remote files')
        rio_size = remote_fetch.rio_log_size(cfg.rio, body.rio_log)
        pi_files: list[tuple[PiSessionRef, list[dict]]] = []
        inventory = [(body.rio_log, rio_size)]
        for ref in body.pi_sessions:
            files = remote_fetch.pi_session_files(cfg.pi, ref.camera, ref.name)
            pi_files.append((ref, files))
            inventory.extend((f'{ref.camera or "vision"}/{ref.name}/{item["name"]}', item['size'])
                             for item in files)
        remote_jobs.set_inventory(job_id, inventory)
        log.info('bundle job %s inventory: %d files, %d bytes', job_id, len(inventory),
                 sum(size for _, size in inventory))

        def rio_progress(name: str, done: int, total: int) -> None:
            remote_jobs.file_progress(job_id, name, done, total)

        remote_jobs.set_phase(job_id, 'Downloading RoboRIO log', body.rio_log)
        local_log = remote_fetch.fetch_rio_log(
            cfg.rio, body.rio_log, LOG_ROOT, progress=rio_progress,
            idle_timeout_seconds=cfg.transfer_idle_timeout_seconds)
        remote_jobs.file_complete(job_id, body.rio_log)

        fetched: List[dict] = []
        if body.pi_sessions:
            vision_dir = bundles.vision_dir_for(local_log)
            for ref, files in pi_files:
                remote_jobs.set_phase(job_id, 'Downloading Orange Pi vision session', ref.name)

                def pi_progress(name: str, done: int, total: int, ref=ref) -> None:
                    filename = name.rsplit('/', 1)[-1]
                    remote_jobs.file_progress(job_id, f'{ref.camera or "vision"}/{ref.name}/{filename}', done, total)

                session_dir = remote_fetch.fetch_pi_session(
                    cfg.pi, ref.camera, ref.name, vision_dir, progress=pi_progress,
                    idle_timeout_seconds=cfg.transfer_idle_timeout_seconds)
                # Empty files do not produce an SFTP byte callback; mark every file
                # idempotently so the completed count stays accurate in that case too.
                for item in files:
                    remote_jobs.file_complete(job_id,
                                              f'{ref.camera or "vision"}/{ref.name}/{item["name"]}')
                fetched.append({'camera': ref.camera, 'name': ref.name,
                                'path': session_dir.relative_to(LOG_ROOT.resolve()).as_posix()})
        remote_jobs.set_phase(job_id, 'Finalizing bundle')
        return {'log': local_log.relative_to(LOG_ROOT.resolve()).as_posix(),
                'pi_sessions': fetched, 'manual': body.manual}

    job_id = remote_jobs.start('bundle', work)
    return {'job_id': job_id}


@app.get('/api/remote/sessions')
def remote_sessions() -> dict:
    """RIO logs + Pi sessions + suggested pairings + each RIO log's local bundle status
    (bundles.local_status, via LOG_ROOT/<name>.vision), so the Fetch Bundle page can
    render its two lists and the pairing rows in one round trip."""
    cfg = remote_config.load_remote_config()
    if cfg is None:
        return {'configured': False}

    try:
        rio_raw = remote_fetch.list_rio_logs(cfg.rio)
        pi_raw = remote_fetch.list_pi_sessions(cfg.pi)
    except remote_fetch.RemoteFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return _remote_sessions_result(cfg, rio_raw, pi_raw)


@app.post('/api/remote/bundle')
def remote_bundle(body: BundleRequest) -> dict:
    """Fetches one RIO log and its paired Pi session(s) into LOG_ROOT, following
    bundles.py's <name>.vision/<camera>/<session>/ convention -- what "Bundle & Open"
    calls before navigating to the newly-local log."""
    cfg = remote_config.load_remote_config()
    if cfg is None:
        raise HTTPException(status_code=400, detail='no remote_config.json configured -- see remote_config.json.example')

    try:
        local_log = remote_fetch.fetch_rio_log(cfg.rio, body.rio_log, LOG_ROOT)
        fetched: List[dict] = []
        if body.pi_sessions:
            vision_dir = bundles.vision_dir_for(local_log)
            for ref in body.pi_sessions:
                session_dir = remote_fetch.fetch_pi_session(cfg.pi, ref.camera, ref.name, vision_dir)
                fetched.append({'camera': ref.camera, 'name': ref.name,
                                 'path': session_dir.relative_to(LOG_ROOT.resolve()).as_posix()})
    except remote_fetch.RemoteFetchError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return {
        'log': local_log.relative_to(LOG_ROOT.resolve()).as_posix(),
        'pi_sessions': fetched,
        'manual': body.manual,
    }


@app.get('/api/remote/bundle-zip')
def remote_bundle_zip(log: str = Query(..., description='log path relative to the log root')):
    """Zips the wpilog + its .vision/ dir (if any) on the fly -- the shareable download
    for a teammate without SSH access, re-imported elsewhere via /api/import/zip."""
    path = _resolve(log)
    vision_dir = bundles.vision_dir_for(path)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(path, arcname=path.name)
        if vision_dir.is_dir():
            for f in sorted(vision_dir.rglob('*')):
                if f.is_file():
                    arcname = pathlib.Path(vision_dir.name) / f.relative_to(vision_dir)
                    zf.write(f, arcname=str(arcname))
    buf.seek(0)

    return StreamingResponse(buf, media_type='application/zip', headers={
        'Content-Disposition': 'attachment; filename="%s-bundle.zip"' % path.stem,
    })


@app.post('/api/import/zip')
async def import_zip(file: UploadFile = File(...)) -> dict:
    """Multipart upload for teammates without SSH access to the RIO/Pi. Validates the
    zip has exactly one top-level .wpilog (+ optionally that log's own <name>.vision/
    tree, matching what /api/remote/bundle-zip produces) and extracts it into LOG_ROOT.
    409s on a name collision so the client can prompt for a rename rather than silently
    overwriting someone's existing log."""
    contents = await file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(contents))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail='not a valid zip file')

    names = [n for n in zf.namelist() if not n.endswith('/')]
    top_level_logs = [n for n in names if n.endswith('.wpilog') and '/' not in n]
    if len(top_level_logs) != 1:
        raise HTTPException(
            status_code=400,
            detail='zip must contain exactly one top-level .wpilog file (found %d)' % len(top_level_logs),
        )
    wpilog_name = top_level_logs[0]
    vision_prefix = pathlib.Path(wpilog_name).stem + bundles.VISION_SUFFIX + '/'
    for n in names:
        if n != wpilog_name and not n.startswith(vision_prefix):
            raise HTTPException(
                status_code=400,
                detail='unexpected entry in zip: %r (expected only %r and %r*)' % (n, wpilog_name, vision_prefix),
            )

    dest_log = LOG_ROOT / wpilog_name
    if dest_log.exists():
        raise HTTPException(status_code=409, detail='%s already exists in the log root' % wpilog_name)

    zf.extractall(LOG_ROOT, members=names)
    return {'log': wpilog_name, 'imported': names}


def _register_static_mounts() -> None:
    """The front end bundle and /vision-video, both mounted here (rather than at import
    time) so /vision-video always serves the real LOG_ROOT the server was started
    against, never the module-level default. Called once from main().

    /vision-video MUST be registered before the '/' front-end mount: Starlette matches
    mounted routes in registration order by prefix, and a StaticFiles mount at '/'
    matches every path underneath it -- registering it first would swallow every
    /vision-video/* request before this one ever got a chance to match."""
    app.mount('/vision-video', StaticFiles(directory=str(LOG_ROOT)), name='vision-video')

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

    _register_static_mounts()

    import uvicorn

    print('log root: %s' % LOG_ROOT)
    print('open:     http://%s:%d/' % (args.host, args.port))
    uvicorn.run(app, host=args.host, port=args.port, log_level='warning')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
