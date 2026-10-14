import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { SpanInfo } from '../api';
import { fmtBytes, fmtTime } from '../lib/format';
import { addRange, setEdge, toggleSpan, removeSeg, type Seg } from '../lib/segments';
import { clampView, hitEdge, histAt, niceTicks, panBy, spanAt, timeToX, xToTime, zoomAt, type View } from '../lib/timeline';

const AXIS_H = 22;
const BAND_TOP = 24;
const BAND_H = 40;
const DENS_TOP = 70;
const DENS_H = 70;
const HEIGHT = DENS_TOP + DENS_H + 6;
const EDGE_TOL = 7;
const DRAG_PX = 4;

interface Props {
  duration: number;
  spans: SpanInfo[];
  hist: number[];
  segments: Seg[];
  selectedId: string | null;
  onSegments: (next: Seg[]) => void;
  onSelect: (id: string | null) => void;
}

type Drag =
  | { kind: 'edge'; id: string; edge: 'start' | 'end' }
  | { kind: 'range'; x0: number; t0: number; moved: boolean }
  | { kind: 'pan'; x0: number; view0: View };

function cssVar(el: Element, name: string): string {
  return getComputedStyle(el).getPropertyValue(name).trim() || '#888';
}

export function Timeline({ duration, spans, hist, segments, selectedId, onSegments, onSelect }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(800);
  const [view, setView] = useState<View>({ t0: 0, t1: duration });
  const [hover, setHover] = useState<{ x: number; t: number } | null>(null);
  const [rubber, setRubber] = useState<{ a: number; b: number } | null>(null);
  const [cursor, setCursor] = useState('crosshair');
  const drag = useRef<Drag | null>(null);

  useEffect(() => setView({ t0: 0, t1: duration }), [duration]);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(Math.max(200, Math.floor(el.clientWidth))));
    ro.observe(el);
    setWidth(Math.max(200, Math.floor(el.clientWidth)));
    return () => ro.disconnect();
  }, []);

  const spansT = useMemo(() => spans.map((s) => ({ start: s.start, end: s.end, mode: s.mode })), [spans]);

  // ── drawing ────────────────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(HEIGHT * dpr);
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, HEIGHT);

    const col = {
      auto: cssVar(canvas, '--c-auto'),
      teleop: cssVar(canvas, '--c-teleop'),
      disabled: cssVar(canvas, '--c-disabled'),
      accent: cssVar(canvas, '--c-accent'),
      text: cssVar(canvas, '--c-text'),
      muted: cssVar(canvas, '--c-muted'),
      grid: cssVar(canvas, '--c-grid'),
      dens: cssVar(canvas, '--c-density'),
      bg: cssVar(canvas, '--c-surface'),
    };
    const X = (t: number) => timeToX(t, view, width);
    const modeColor = (m: string) => (m === 'auto' ? col.auto : m === 'teleop' ? col.teleop : col.disabled);

    // axis
    ctx.font = '11px system-ui, sans-serif';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = col.muted;
    ctx.strokeStyle = col.grid;
    ctx.lineWidth = 1;
    for (const t of niceTicks(view, Math.max(3, Math.floor(width / 90)))) {
      const x = Math.round(X(t)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(x, AXIS_H - 4);
      ctx.lineTo(x, DENS_TOP + DENS_H);
      ctx.stroke();
      ctx.fillText(fmtTime(t), x + 3, 10);
    }

    // mode bands
    for (const s of spansT) {
      const x0 = X(s.start);
      const x1 = X(s.end);
      if (x1 < 0 || x0 > width) continue;
      const a = Math.max(0, x0);
      const w = Math.max(1, Math.min(width, x1) - a);
      ctx.fillStyle = modeColor(s.mode);
      ctx.globalAlpha = s.mode === 'disabled' ? 0.55 : 0.9;
      ctx.fillRect(a, BAND_TOP, w, BAND_H);
      ctx.globalAlpha = 1;
      ctx.strokeStyle = col.bg;
      ctx.strokeRect(a + 0.5, BAND_TOP + 0.5, w, BAND_H - 1);
      if (w > 46) {
        ctx.fillStyle = s.mode === 'disabled' ? col.text : '#fff';
        ctx.fillText(`${s.mode}  ${fmtTime(s.end - s.start)}`, a + 6, BAND_TOP + BAND_H / 2, w - 10);
      }
    }
    if (spansT.length === 0) {
      ctx.fillStyle = col.muted;
      ctx.fillText('no DriverStation mode data in this log — drag on the timeline to pick a range', 8, BAND_TOP + BAND_H / 2);
    }

    // byte density (max within each pixel column so short spikes stay visible)
    let maxV = 1;
    const cols: number[] = new Array(Math.ceil(width)).fill(0);
    for (let x = 0; x < cols.length; x++) {
      const ta = xToTime(x, view, width);
      const tb = xToTime(x + 1, view, width);
      let m = 0;
      for (let i = Math.floor(ta); i <= Math.floor(tb); i++) m = Math.max(m, histAt(hist, i));
      cols[x] = m;
      maxV = Math.max(maxV, m);
    }
    ctx.fillStyle = col.dens;
    for (let x = 0; x < cols.length; x++) {
      const h = (cols[x] / maxV) * (DENS_H - 4);
      if (h > 0) ctx.fillRect(x, DENS_TOP + DENS_H - h, 1, h);
    }
    ctx.fillStyle = col.muted;
    ctx.fillText(`bytes / s   peak ${fmtBytes(maxV)}/s`, 6, DENS_TOP + 8);

    // selection
    for (const s of segments) {
      const x0 = X(s.start);
      const x1 = X(s.end);
      if (x1 < -10 || x0 > width + 10) continue;
      const sel = s.id === selectedId;
      const top = BAND_TOP - 2;
      const h = DENS_TOP + DENS_H - top;
      ctx.fillStyle = col.accent;
      ctx.globalAlpha = sel ? 0.24 : 0.16;
      ctx.fillRect(x0, top, x1 - x0, h);
      ctx.globalAlpha = 1;
      ctx.strokeStyle = col.accent;
      ctx.lineWidth = sel ? 2.5 : 1.5;
      ctx.strokeRect(x0, top, x1 - x0, h);
      ctx.fillStyle = col.accent;
      for (const x of [x0, x1]) ctx.fillRect(x - 3, top + h / 2 - 14, 6, 28);
    }
    ctx.lineWidth = 1;

    // rubber band while dragging out a new range
    if (rubber) {
      const a = X(Math.min(rubber.a, rubber.b));
      const b = X(Math.max(rubber.a, rubber.b));
      ctx.fillStyle = col.accent;
      ctx.globalAlpha = 0.25;
      ctx.fillRect(a, BAND_TOP - 2, b - a, DENS_TOP + DENS_H - BAND_TOP + 2);
      ctx.globalAlpha = 1;
      ctx.setLineDash([4, 3]);
      ctx.strokeStyle = col.accent;
      ctx.strokeRect(a, BAND_TOP - 2, b - a, DENS_TOP + DENS_H - BAND_TOP + 2);
      ctx.setLineDash([]);
    }

    // hover line
    if (hover) {
      ctx.strokeStyle = col.text;
      ctx.globalAlpha = 0.5;
      ctx.beginPath();
      ctx.moveTo(hover.x + 0.5, AXIS_H - 2);
      ctx.lineTo(hover.x + 0.5, DENS_TOP + DENS_H);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
  }, [width, view, spansT, hist, segments, selectedId, hover, rubber]);

  // ── interaction ────────────────────────────────────────────────────────────────────────────────
  const xy = (e: { clientX: number; clientY: number }) => {
    const r = canvasRef.current!.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };
  const tAt = useCallback((x: number) => Math.min(duration, Math.max(0, xToTime(x, view, width))), [view, width, duration]);

  const onPointerDown = (e: React.PointerEvent) => {
    const { x, y } = xy(e);
    canvasRef.current!.setPointerCapture(e.pointerId);
    canvasRef.current!.focus();
    if (e.button === 1 || e.altKey) {
      drag.current = { kind: 'pan', x0: e.clientX, view0: view };
      setCursor('grabbing');
      return;
    }
    const edge = hitEdge(segments, x, view, width, EDGE_TOL);
    if (edge) {
      drag.current = { kind: 'edge', ...edge };
      onSelect(edge.id);
      return;
    }
    drag.current = { kind: 'range', x0: x, t0: tAt(x), moved: false };
    void y;
  };

  const onPointerMove = (e: React.PointerEvent) => {
    const { x, y } = xy(e);
    const d = drag.current;
    setHover({ x, t: tAt(x) });
    if (!d) {
      if (hitEdge(segments, x, view, width, EDGE_TOL)) setCursor('col-resize');
      else setCursor(y >= BAND_TOP && y <= BAND_TOP + BAND_H ? 'pointer' : 'crosshair');
      return;
    }
    if (d.kind === 'pan') {
      const dt = -((e.clientX - d.x0) / width) * (d.view0.t1 - d.view0.t0);
      setView(panBy(d.view0, dt, duration));
    } else if (d.kind === 'edge') {
      onSegments(setEdge(segments, d.id, d.edge, tAt(x), duration));
    } else {
      if (Math.abs(x - d.x0) > DRAG_PX) d.moved = true;
      if (d.moved) setRubber({ a: d.t0, b: tAt(x) });
    }
  };

  const onPointerUp = (e: React.PointerEvent) => {
    const { x, y } = xy(e);
    const d = drag.current;
    drag.current = null;
    setRubber(null);
    setCursor('crosshair');
    if (!d || d.kind !== 'range') return;
    if (d.moved) {
      const next = addRange(segments, d.t0, tAt(x), duration);
      const known = new Set(segments.map((s) => s.id));
      onSegments(next);
      onSelect(next.find((s) => !known.has(s.id))?.id ?? null);
      return;
    }
    const t = tAt(x);
    if (y >= BAND_TOP && y <= BAND_TOP + BAND_H) {
      const span = spanAt(spansT, t);
      if (span) {
        const next = toggleSpan(segments, span);
        const known = new Set(segments.map((s) => s.id));
        onSegments(next);
        onSelect(next.find((s) => !known.has(s.id))?.id ?? null);
      }
    } else {
      onSelect(segments.find((s) => t >= s.start && t <= s.end)?.id ?? null);
    }
  };

  // wheel needs a non-passive listener to be able to stop the page scrolling
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = canvas.getBoundingClientRect();
      const x = e.clientX - r.left;
      if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        const dt = ((e.deltaX || e.deltaY) / width) * (view.t1 - view.t0);
        setView(panBy(view, dt, duration));
      } else {
        setView(zoomAt(view, xToTime(x, view, width), Math.exp(-e.deltaY * 0.0015), duration));
      }
    };
    canvas.addEventListener('wheel', onWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', onWheel);
  }, [view, width, duration]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    const span = view.t1 - view.t0;
    if (e.key === '+' || e.key === '=') setView(zoomAt(view, (view.t0 + view.t1) / 2, 1.5, duration));
    else if (e.key === '-') setView(zoomAt(view, (view.t0 + view.t1) / 2, 1 / 1.5, duration));
    else if (e.key === 'ArrowLeft') setView(panBy(view, -span * 0.2, duration));
    else if (e.key === 'ArrowRight') setView(panBy(view, span * 0.2, duration));
    else if (e.key === '0') setView({ t0: 0, t1: duration });
    else if ((e.key === 'Delete' || e.key === 'Backspace') && selectedId) onSegments(removeSeg(segments, selectedId));
    else return;
    e.preventDefault();
  };

  const zoomToSelection = () => {
    const sel = segments.find((s) => s.id === selectedId) ?? segments[0];
    if (!sel) return;
    const pad = Math.max(0.5, (sel.end - sel.start) * 0.1);
    setView(clampView({ t0: sel.start - pad, t1: sel.end + pad }, duration));
  };
  const zoomed = view.t0 > 0.001 || view.t1 < duration - 0.001;
  const tip = hover ? spanAt(spansT, hover.t) : null;

  return (
    <div className="timeline" ref={wrapRef}>
      <canvas
        ref={canvasRef}
        style={{ width, height: HEIGHT, cursor }}
        tabIndex={0}
        role="img"
        aria-label="Timeline of the log: driver-station mode bands over a bytes-per-second curve. Click a band to keep or drop that period; drag to keep an arbitrary range; drag a highlighted edge to adjust it."
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={() => !drag.current && setHover(null)}
        onDoubleClick={() => setView({ t0: 0, t1: duration })}
        onKeyDown={onKeyDown}
        onContextMenu={(e) => e.preventDefault()}
      />
      {hover && (
        <div className="tip" style={{ left: Math.min(width - 190, Math.max(0, hover.x + 12)), top: DENS_TOP + 4 }}>
          {fmtTime(hover.t)} · {tip?.mode ?? '—'} · {fmtBytes(histAt(hist, hover.t))}/s
        </div>
      )}
      <div className="timeline-tools">
        <span className="hint">
          click a band to keep it · drag to keep a range · drag an edge to adjust · wheel zooms · alt-drag pans · double-click resets
        </span>
        <span className="spacer" />
        <button type="button" className="btn small" onClick={zoomToSelection} disabled={segments.length === 0}>
          Zoom to selection
        </button>
        <button type="button" className="btn small" onClick={() => setView({ t0: 0, t1: duration })} disabled={!zoomed}>
          Reset zoom
        </button>
      </div>
    </div>
  );
}
