// Pure geometry for the timeline canvas: no DOM, so it can be unit-tested.

export interface View {
  t0: number; // seconds visible at the left edge
  t1: number; // seconds visible at the right edge
}

export const MIN_VIEW_SPAN = 0.5; // never zoom in past half a second across the whole canvas

export function timeToX(t: number, v: View, width: number): number {
  return ((t - v.t0) / (v.t1 - v.t0)) * width;
}

export function xToTime(x: number, v: View, width: number): number {
  return v.t0 + (x / width) * (v.t1 - v.t0);
}

/** Zoom by `factor` (>1 zooms in) keeping the time under the cursor fixed. Clamped to [0, total]. */
export function zoomAt(v: View, t: number, factor: number, total: number): View {
  const span = v.t1 - v.t0;
  const newSpan = Math.min(total, Math.max(Math.min(MIN_VIEW_SPAN, total), span / factor));
  const frac = span > 0 ? (t - v.t0) / span : 0.5;
  return clampView({ t0: t - frac * newSpan, t1: t - frac * newSpan + newSpan }, total);
}

export function panBy(v: View, dt: number, total: number): View {
  return clampView({ t0: v.t0 + dt, t1: v.t1 + dt }, total);
}

/** Shift a view back inside [0, total] without changing its span. */
export function clampView(v: View, total: number): View {
  const span = Math.min(v.t1 - v.t0, total);
  let t0 = v.t0;
  if (t0 < 0) t0 = 0;
  if (t0 + span > total) t0 = total - span;
  return { t0, t1: t0 + span };
}

/** Ticks on a 1-2-5 grid, at most about `maxTicks` of them, inside the view. */
export function niceTicks(v: View, maxTicks: number): number[] {
  const span = v.t1 - v.t0;
  if (!(span > 0) || maxTicks < 1) return [];
  const raw = span / maxTicks;
  const pow = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 5, 10].map((m) => m * pow).find((s) => s >= raw) ?? raw;
  const decimals = Math.max(0, -Math.floor(Math.log10(step)) + 1);
  const out: number[] = [];
  // Multiply an integer index by the step (instead of adding the step repeatedly) and round away the
  // float noise, so ticks come out as 36.3 rather than 36.300000000000004.
  for (let k = Math.ceil(v.t0 / step - 1e-9); k * step <= v.t1 + 1e-9; k++) out.push(Number((k * step).toFixed(decimals)));
  return out;
}

export interface SpanLike {
  start: number;
  end: number;
  mode: string;
}

export function spanAt<T extends SpanLike>(spans: T[], t: number): T | null {
  return spans.find((s) => t >= s.start && t < s.end) ?? (spans.length && t >= spans[spans.length - 1].end ? spans[spans.length - 1] : null);
}

/** Bytes in the 1 s bucket containing `t`. `hist[i]` covers [i, i+1). */
export function histAt(hist: number[], t: number): number {
  const i = Math.floor(t);
  return i >= 0 && i < hist.length ? hist[i] : 0;
}

export interface EdgeHit {
  id: string;
  edge: 'start' | 'end';
}

/** Which segment edge (if any) lies within `tolPx` of pixel `x`. The nearer edge wins; ties go to the later segment. */
export function hitEdge(
  segs: { id: string; start: number; end: number }[],
  x: number,
  v: View,
  width: number,
  tolPx: number,
): EdgeHit | null {
  let best: { hit: EdgeHit; d: number } | null = null;
  for (const s of segs) {
    for (const edge of ['start', 'end'] as const) {
      const d = Math.abs(timeToX(s[edge], v, width) - x);
      if (d <= tolPx && (best === null || d <= best.d)) best = { hit: { id: s.id, edge }, d };
    }
  }
  return best ? best.hit : null;
}
