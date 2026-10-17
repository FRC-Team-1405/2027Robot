// Operations on the list of kept segments. Immutable, pure, unit-tested.

export interface Seg {
  id: string;
  start: number; // seconds from the log's first record
  end: number;
  label: string; // 'auto' | 'teleop' | 'disabled' | 'manual'
  padPre: number; // ms
  padPost: number; // ms
}

export interface Span {
  start: number;
  end: number;
  mode: string;
}

export const MIN_SEG = 0.05; // seconds; below this a segment would usually contain no cycles at all

let counter = 0;
export function newId(): string {
  counter += 1;
  return `s${Date.now().toString(36)}${counter}`;
}

export const sortSegs = (segs: Seg[]): Seg[] => [...segs].sort((a, b) => a.start - b.start || a.end - b.end);

export function sameSpan(seg: Seg, span: Span, tol = 0.05): boolean {
  return Math.abs(seg.start - span.start) <= tol && Math.abs(seg.end - span.end) <= tol;
}

export function spanSelected(segs: Seg[], span: Span): boolean {
  return segs.some((s) => sameSpan(s, span));
}

/** Add the span as a segment, or remove the segment that already is that span. */
export function toggleSpan(segs: Seg[], span: Span): Seg[] {
  if (spanSelected(segs, span)) return segs.filter((s) => !sameSpan(s, span));
  return sortSegs([...segs, { id: newId(), start: span.start, end: span.end, label: span.mode, padPre: 0, padPost: 0 }]);
}

/** Select every span of these modes (keeping anything else already selected). If they are all
 *  selected already, deselect them instead — so the same button toggles. */
export function toggleModes(segs: Seg[], spans: Span[], modes: string[]): Seg[] {
  const wanted = spans.filter((s) => modes.includes(s.mode));
  if (wanted.length === 0) return segs;
  if (wanted.every((s) => spanSelected(segs, s))) return segs.filter((g) => !wanted.some((s) => sameSpan(g, s)));
  let out = segs;
  for (const s of wanted) if (!spanSelected(out, s)) out = toggleSpan(out, s);
  return out;
}

export function addRange(segs: Seg[], a: number, b: number, total: number): Seg[] {
  const start = Math.max(0, Math.min(a, b));
  const end = Math.min(total, Math.max(a, b));
  if (end - start < MIN_SEG) return segs;
  return sortSegs([...segs, { id: newId(), start, end, label: 'manual', padPre: 0, padPost: 0 }]);
}

/** Move one edge (the segment is then a 'manual' range, no longer exactly a mode span). The edge stops MIN_SEG short of the other one and stays inside [0, total]; it does
 *  not stop at neighbouring segments (overlaps just merge when the plan is resolved). */
export function setEdge(segs: Seg[], id: string, edge: 'start' | 'end', t: number, total: number): Seg[] {
  return segs.map((s) => {
    if (s.id !== id) return s;
    if (edge === 'start') return { ...s, start: Math.max(0, Math.min(t, s.end - MIN_SEG)), label: 'manual' };
    return { ...s, end: Math.min(total, Math.max(t, s.start + MIN_SEG)), label: 'manual' };
  });
}

export const removeSeg = (segs: Seg[], id: string): Seg[] => segs.filter((s) => s.id !== id);

export function updateSeg(segs: Seg[], id: string, patch: Partial<Omit<Seg, 'id'>>): Seg[] {
  return segs.map((s) => (s.id === id ? { ...s, ...patch } : s));
}

/** Drop segments that no longer fit a log of this length (e.g. a plan restored for a different file). */
export function fitToDuration(segs: Seg[], total: number): Seg[] {
  return segs
    .filter((s) => s.start < total && s.end > 0)
    .map((s) => ({ ...s, start: Math.max(0, s.start), end: Math.min(total, s.end) }))
    .filter((s) => s.end - s.start >= MIN_SEG);
}

export function toRequestSegments(segs: Seg[]) {
  return sortSegs(segs).map((s) => ({
    start: s.start,
    end: s.end,
    label: s.label,
    pad_pre_ms: s.padPre,
    pad_post_ms: s.padPost,
  }));
}
