"""FastAPI host for the janitor web UI: browse logs on disk, index them, preview and export trims.

    python -m janitor serve --logs ../../logs            # then open http://127.0.0.1:8767/

Indexing a big log takes a while (~15 s for 130 MB), so the parsed log + index are kept in a small LRU
cache keyed by (path, mtime): reopening a log is instant, and re-recording invalidates itself.

The API is a thin layer over wpilog_utils -- every number the UI shows comes from `estimate_size`
(instant, from the index) or `dry_run` (exact, one pass over the file), and the file it writes comes
from the same writer as `dry_run`.
"""
import collections
import pathlib
import re
import threading
from typing import Dict, List, Literal, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import __version__, paths  # noqa: F401  (paths: side effect, wpilog_utils importable)
from wpilog_utils.index import LogIndex, build_index
from wpilog_utils.trim import (Segment, TrimPlan, dry_run, estimate_size, resolve_plan, trim_log)
from wpilog_utils.verify import verify_trim

DIST = pathlib.Path(__file__).resolve().parents[2] / 'web' / 'dist'
CACHE_SIZE = 2                       # parsed logs are big; keep only what you are actively working on
VERIFY_MAX_BYTES = 250 * 1024 * 1024


class SegmentIn(BaseModel):
    start: float = Field(..., description='seconds from the log start')
    end: float
    label: str = ''
    pad_pre_ms: float = 0.0
    pad_post_ms: float = 0.0


class PlanIn(BaseModel):
    log: str
    segments: List[SegmentIn]
    gap_ms: float = 200.0
    gap_policy: Literal['compact', 'preserve'] = 'compact'
    exclude: List[str] = []
    exclude_prefixes: List[str] = []


class ExportIn(PlanIn):
    mode: Literal['save', 'download'] = 'save'
    filename: Optional[str] = Field(None, description="save mode: file name (default <log>_trimmed.wpilog); never overwrites")
    verify: bool = True


def create_app(log_root: pathlib.Path, dist: Optional[pathlib.Path] = DIST) -> FastAPI:
    root = pathlib.Path(log_root).resolve()
    app = FastAPI(title='wpilog-janitor', version=__version__)
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    cache: 'collections.OrderedDict[Tuple[str, float], Tuple[bytes, LogIndex]]' = collections.OrderedDict()
    load_lock = threading.Lock()

    # ── helpers ──────────────────────────────────────────────────────────────────────────────────
    def resolve(rel: str) -> pathlib.Path:
        p = (root / rel).resolve()
        try:
            p.relative_to(root)
        except ValueError:
            raise HTTPException(400, 'path outside the log directory')
        if not p.is_file():
            raise HTTPException(404, f'no such log: {rel}')
        return p

    def load(rel: str) -> Tuple[pathlib.Path, bytes, LogIndex]:
        p = resolve(rel)
        key = (str(p), p.stat().st_mtime)
        with load_lock:                                   # a second request for the same log waits, then hits the cache
            if key in cache:
                cache.move_to_end(key)
                raw, ix = cache[key]
            else:
                raw = p.read_bytes()
                try:
                    ix = build_index(raw)
                except ValueError as exc:
                    raise HTTPException(422, f'{p.name} is not a readable .wpilog: {exc}')
                cache[key] = (raw, ix)
                while len(cache) > CACHE_SIZE:
                    cache.popitem(last=False)
        return p, raw, ix

    def to_plan(body: PlanIn, source_name: str) -> TrimPlan:
        return TrimPlan(
            segments=[Segment(s.start, s.end, s.label, s.pad_pre_ms, s.pad_post_ms) for s in body.segments],
            gap_ms=body.gap_ms, gap_policy=body.gap_policy, exclude=body.exclude,
            exclude_prefixes=body.exclude_prefixes, source_name=source_name)

    def resolved(ix: LogIndex, plan: TrimPlan):
        try:
            return resolve_plan(ix, plan)
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    # ── endpoints ────────────────────────────────────────────────────────────────────────────────
    @app.get('/api/logs')
    def list_logs() -> dict:
        logs = []
        for p in root.rglob('*.wpilog'):
            st = p.stat()
            logs.append({'path': p.relative_to(root).as_posix(), 'name': p.name, 'size': st.st_size, 'mtime': st.st_mtime})
        logs.sort(key=lambda d: d['mtime'], reverse=True)
        return {'root': str(root), 'logs': logs}

    @app.get('/api/index')
    def log_index(log: str = Query(..., description='log path relative to the log root')) -> dict:
        p, raw, ix = load(log)
        spans = [{'start': a, 'end': b, 'mode': m, 'bytes': ix.window_bytes(a, b)} for a, b, m in ix.mode_spans()]
        warnings: List[str] = []
        trailing = len(raw) - (ix.header_end + ix.control_bytes + ix.data_bytes)
        if trailing > 0:
            warnings.append(f'{trailing} trailing bytes are not a complete record (the log ended mid-write); they are dropped on trim')
        if not ix.time_ordered:
            warnings.append('records are not in time order; trimming is not supported for this log')
        if ix.n_unregistered_records:
            warnings.append(f'{ix.n_unregistered_records} data records belong to entries that were never started; they are dropped')
        if not spans:
            warnings.append('no DriverStation/Enabled data in this log: there are no mode bands, so pick times by dragging')
        if ix.cycle_entry_id is None:
            warnings.append('no /Timestamp entry: every distinct timestamp is treated as a cycle')
        return {
            'log': log, 'root': str(root), 'name': p.name, 'size': len(raw), 'mtime': p.stat().st_mtime,
            'duration_s': ix.duration_s, 'n_records': ix.n_records, 'n_entries': len(ix.entries),
            'n_cycles': len(ix.cycles_us), 'cycle_period_ms': ix.cycle_period_us() / 1000.0,
            'header': ix.extra_header.decode('utf-8', 'replace'), 'time_ordered': ix.time_ordered,
            'has_cycle_marker': ix.cycle_entry_id is not None,
            'data_bytes': ix.data_bytes, 'control_bytes': ix.control_bytes,
            'spans': spans, 'byte_hist': ix.byte_hist, 'warnings': warnings,
            'time_mirrors': sorted(e.name for e in ix.entries.values() if e.time_mirror),
        }

    def describe(ix: LogIndex, plan: TrimPlan, res) -> dict:
        cb = ix.cycle_bytes
        t0 = ix.t_min_us / 1e6
        return {
            'segments': [{
                'label': s.label, 'orig_first': s.orig_first_s, 'orig_last': s.orig_last_s,
                'new_first': s.new_first_s, 'new_last': s.new_last_s,
                'n_cycles': s.last_cycle - s.first_cycle + 1,
                'bytes': int(sum(cb[s.first_cycle:s.last_cycle + 1])),
            } for s in res.segments],
            'ranges': [{
                'first': (ix.cycles_us[r.first] / 1e6) - t0, 'last': (ix.cycles_us[r.last] / 1e6) - t0,
                'n_cycles': r.n_cycles, 'bytes': int(sum(cb[r.first:r.last + 1])),
            } for r in res.ranges],
            'seams': res.seams, 'gap_cycles': res.gap_cycles,
            'cycle_period_ms': res.nominal_period_us / 1000.0,
            'warnings': res.warnings, 'n_excluded_entries': len(res.excluded_ids),
        }

    @app.post('/api/preview')
    def preview(body: PlanIn) -> dict:
        """Instant: everything computed from the index, no pass over the file."""
        p, raw, ix = load(body.log)
        plan = to_plan(body, p.name)
        res = resolved(ix, plan)
        est = estimate_size(ix, plan, res)
        return {
            'exact': False, 'source_bytes': len(raw), 'output_bytes': est, 'saved_bytes': len(raw) - est,
            'saved_pct': 100.0 * (len(raw) - est) / max(1, len(raw)),
            'n_cycles_out': sum(r.n_cycles for r in res.ranges), 'n_cycles_source': len(ix.cycles_us),
            **describe(ix, plan, res),
        }

    @app.post('/api/preview/exact')
    def preview_exact(body: PlanIn) -> dict:
        """One pass over the file with the real writer, nothing built: the size export will produce."""
        p, raw, ix = load(body.log)
        plan = to_plan(body, p.name)
        res = resolved(ix, plan)
        st = dry_run(raw, ix, plan, res)
        return {
            'exact': True, 'source_bytes': st.source_bytes, 'output_bytes': st.bytes_out, 'saved_bytes': st.saved_bytes,
            'saved_pct': st.saved_pct, 'n_cycles_out': st.n_cycles_out, 'n_cycles_source': st.n_cycles_source,
            'n_carried': st.n_carried, 'n_excluded_records': st.n_excluded_records,
            'control_records_dropped': st.control_records_dropped,
            **describe(ix, plan, res),
        }

    def safe_name(name: str) -> str:
        base = pathlib.PurePath(name).name
        base = re.sub(r'[^A-Za-z0-9._ -]', '_', base).strip(' .')
        if not base:
            raise HTTPException(400, 'empty file name')
        return base if base.lower().endswith('.wpilog') else base + '.wpilog'

    @app.post('/api/export')
    def export(body: ExportIn) -> Response:
        p, raw, ix = load(body.log)
        plan = to_plan(body, p.name)
        res = resolved(ix, plan)
        out, st = trim_log(raw, ix, plan, res)
        stem = pathlib.PurePath(safe_name(body.filename)).stem if body.filename else p.stem + '_trimmed'
        if body.mode == 'download':
            return Response(out, media_type='application/octet-stream',
                            headers={'Content-Disposition': f'attachment; filename="{stem}.wpilog"'})

        dest = p.with_name(stem + '.wpilog')
        n = 2
        while dest.exists():                                  # never overwrite anything
            dest = p.with_name(f'{stem}_{n}.wpilog')
            n += 1
        dest.write_bytes(out)
        report = None
        if body.verify and len(raw) <= VERIFY_MAX_BYTES:
            r = verify_trim(out, raw, ix, plan, res)
            report = {'ok': r.ok, 'issues': r.issues[:25], 'n_issues': len(r.issues)}
        import json
        return Response(json.dumps({
            'path': dest.relative_to(root).as_posix(), 'abs_path': str(dest), 'name': dest.name, 'bytes': st.bytes_out,
            'source_bytes': st.source_bytes, 'saved_bytes': st.saved_bytes, 'saved_pct': st.saved_pct,
            'verify': report, 'verify_skipped': report is None,
            'warnings': res.warnings,
        }), media_type='application/json')

    if dist is not None and dist.exists():
        app.mount('/', StaticFiles(directory=str(dist), html=True), name='web')
    else:
        @app.get('/')
        def _needs_build() -> HTMLResponse:
            return HTMLResponse(
                '<pre style="font:13px ui-monospace;padding:24px">The janitor front end has not been built yet.\n\n'
                '  cd tools/wpilog-janitor/web &amp;&amp; npm install &amp;&amp; npm run build\n\n'
                'or run the Vite dev server (npm run dev) and use http://localhost:5174 -- it proxies /api here.</pre>',
                status_code=503)
    return app
