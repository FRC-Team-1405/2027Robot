import { describe, expect, it } from 'vitest';
import { fmtBytes, fmtDuration, fmtPct, fmtTime, stemOf } from './format';
import {
  addRange,
  fitToDuration,
  removeSeg,
  setEdge,
  sortSegs,
  spanSelected,
  toggleModes,
  toggleSpan,
  toRequestSegments,
  updateSeg,
  type Seg,
  type Span,
} from './segments';
import { clampView, hitEdge, histAt, niceTicks, panBy, spanAt, timeToX, xToTime, zoomAt } from './timeline';

const spans: Span[] = [
  { start: 0, end: 36.8, mode: 'disabled' },
  { start: 36.8, end: 52.7, mode: 'auto' },
  { start: 52.7, end: 120, mode: 'disabled' },
  { start: 120, end: 135, mode: 'auto' },
  { start: 135, end: 200, mode: 'teleop' },
];
const seg = (id: string, start: number, end: number, label = 'manual'): Seg => ({ id, start, end, label, padPre: 0, padPost: 0 });

describe('format', () => {
  it('formats bytes', () => {
    expect(fmtBytes(0)).toBe('0 B');
    expect(fmtBytes(1023)).toBe('1023 B');
    expect(fmtBytes(1536)).toBe('1.5 KB');
    expect(fmtBytes(9.3 * 1024 * 1024)).toBe('9.3 MB');
    expect(fmtBytes(140_414_976)).toBe('134 MB');
    expect(fmtBytes(-2048)).toBe('-2.0 KB');
    expect(fmtBytes(NaN)).toBe('—');
  });
  it('formats times and durations', () => {
    expect(fmtTime(3.456)).toBe('3.46 s');
    expect(fmtTime(36.8)).toBe('36.8 s');
    expect(fmtTime(125.3)).toBe('2:05.3');
    expect(fmtTime(60)).toBe('1:00.0');
    expect(fmtDuration(191.6)).toBe('3 min 12 s');
    expect(fmtDuration(3508.4)).toBe('58 min 28 s');
    expect(fmtDuration(12)).toBe('12.0 s');
  });
  it('formats percentages and file stems', () => {
    expect(fmtPct(90.94)).toBe('90.9%');
    expect(fmtPct(99.97)).toBe('100%');
    expect(stemOf('logs/offseason/9-1/akit_x.wpilog')).toBe('akit_x');
    expect(stemOf('plain')).toBe('plain');
  });
});

describe('timeline geometry', () => {
  const v = { t0: 10, t1: 30 };
  it('maps time <-> x', () => {
    expect(timeToX(10, v, 400)).toBe(0);
    expect(timeToX(30, v, 400)).toBe(400);
    expect(timeToX(20, v, 400)).toBe(200);
    expect(xToTime(100, v, 400)).toBe(15);
    expect(xToTime(timeToX(23.7, v, 640), v, 640)).toBeCloseTo(23.7);
  });
  it('zooms around a fixed point and clamps', () => {
    const z = zoomAt({ t0: 0, t1: 100 }, 25, 2, 100);
    expect(z.t1 - z.t0).toBeCloseTo(50);
    expect(z.t0 + 0.25 * 50).toBeCloseTo(25); // the time under the cursor did not move
    const out = zoomAt({ t0: 0, t1: 100 }, 50, 0.1, 100);
    expect(out).toEqual({ t0: 0, t1: 100 }); // cannot zoom out past the whole log
    const deep = zoomAt({ t0: 0, t1: 1 }, 0.5, 100, 100);
    expect(deep.t1 - deep.t0).toBeCloseTo(0.5); // and not in past MIN_VIEW_SPAN
  });
  it('pans and clamps at the ends', () => {
    expect(panBy({ t0: 10, t1: 20 }, 5, 100)).toEqual({ t0: 15, t1: 25 });
    expect(panBy({ t0: 10, t1: 20 }, -50, 100)).toEqual({ t0: 0, t1: 10 });
    expect(panBy({ t0: 10, t1: 20 }, 500, 100)).toEqual({ t0: 90, t1: 100 });
    expect(clampView({ t0: -5, t1: 500 }, 100)).toEqual({ t0: 0, t1: 100 });
  });
  it('picks 1-2-5 ticks', () => {
    expect(niceTicks({ t0: 0, t1: 100 }, 10)).toEqual([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]);
    expect(niceTicks({ t0: 0, t1: 3508 }, 8)).toEqual([0, 500, 1000, 1500, 2000, 2500, 3000, 3500]);
    expect(niceTicks({ t0: 36.1, t1: 36.6 }, 5)).toEqual([36.1, 36.2, 36.3, 36.4, 36.5, 36.6]);
    expect(niceTicks({ t0: 5, t1: 5 }, 5)).toEqual([]);
  });
  it('finds the mode and byte density at a time', () => {
    expect(spanAt(spans, 10)?.mode).toBe('disabled');
    expect(spanAt(spans, 36.8)?.mode).toBe('auto');
    expect(spanAt(spans, 200)?.mode).toBe('teleop'); // the very end belongs to the last span
    expect(spanAt([], 1)).toBeNull();
    expect(histAt([5, 7, 9], 1.9)).toBe(7);
    expect(histAt([5, 7, 9], 3.5)).toBe(0);
    expect(histAt([5, 7, 9], -1)).toBe(0);
  });
  it('hits the nearest segment edge within a tolerance', () => {
    const segs = [seg('a', 10, 20), seg('b', 20.2, 30)];
    const view = { t0: 0, t1: 40 };
    expect(hitEdge(segs, timeToX(10, view, 400) + 3, view, 400, 6)).toEqual({ id: 'a', edge: 'start' });
    expect(hitEdge(segs, timeToX(30, view, 400), view, 400, 6)).toEqual({ id: 'b', edge: 'end' });
    expect(hitEdge(segs, timeToX(20.15, view, 400), view, 400, 6)?.id).toBe('b'); // closer to b's start than a's end
    expect(hitEdge(segs, timeToX(15, view, 400), view, 400, 6)).toBeNull();
  });
});

describe('segment operations', () => {
  it('toggles a mode span on and off', () => {
    const on = toggleSpan([], spans[1]);
    expect(on).toHaveLength(1);
    expect(on[0]).toMatchObject({ start: 36.8, end: 52.7, label: 'auto' });
    expect(spanSelected(on, spans[1])).toBe(true);
    expect(toggleSpan(on, spans[1])).toEqual([]);
  });
  it('still recognises a span after tiny drift', () => {
    const drifted = [seg('x', 36.82, 52.69, 'auto')];
    expect(spanSelected(drifted, spans[1])).toBe(true);
    expect(toggleSpan(drifted, spans[1])).toEqual([]);
  });
  it('keeps segments sorted by start', () => {
    const s = toggleSpan(toggleSpan([], spans[3]), spans[1]);
    expect(s.map((x) => x.start)).toEqual([36.8, 120]);
    expect(sortSegs([seg('b', 5, 6), seg('a', 1, 2)]).map((x) => x.id)).toEqual(['a', 'b']);
  });
  it('selects and deselects all spans of a mode without touching others', () => {
    const teleop = toggleSpan([], spans[4]);
    const withAuto = toggleModes(teleop, spans, ['auto']);
    expect(withAuto.map((s) => s.label).sort()).toEqual(['auto', 'auto', 'teleop']);
    const back = toggleModes(withAuto, spans, ['auto']);
    expect(back.map((s) => s.label)).toEqual(['teleop']);
    expect(toggleModes([], spans, ['test'])).toEqual([]); // no such mode: nothing happens
  });
  it('adds a manual range in either drag direction, clamped, ignoring slivers', () => {
    expect(addRange([], 40, 30, 100)[0]).toMatchObject({ start: 30, end: 40, label: 'manual' });
    expect(addRange([], -5, 500, 100)[0]).toMatchObject({ start: 0, end: 100 });
    expect(addRange([], 10, 10.01, 100)).toEqual([]);
  });
  it('moves an edge, keeps a minimum length, and marks the segment manual', () => {
    const segs = [seg('a', 10, 20, 'auto')];
    expect(setEdge(segs, 'a', 'start', 12, 100)[0]).toMatchObject({ start: 12, end: 20, label: 'manual' });
    expect(setEdge(segs, 'a', 'start', 25, 100)[0].start).toBeCloseTo(19.95); // cannot cross the other edge
    expect(setEdge(segs, 'a', 'end', 999, 100)[0].end).toBe(100);
    expect(setEdge(segs, 'a', 'end', 5, 100)[0].end).toBeCloseTo(10.05);
    expect(setEdge(segs, 'a', 'start', -3, 100)[0].start).toBe(0);
    expect(setEdge(segs, 'zzz', 'start', 12, 100)).toEqual(segs);
  });
  it('removes, updates and fits segments', () => {
    const segs = [seg('a', 10, 20), seg('b', 90, 150)];
    expect(removeSeg(segs, 'a').map((s) => s.id)).toEqual(['b']);
    expect(updateSeg(segs, 'a', { padPre: 100 })[0].padPre).toBe(100);
    expect(fitToDuration(segs, 100).map((s) => [s.id, s.end])).toEqual([['a', 20], ['b', 100]]);
    expect(fitToDuration([seg('c', 300, 400)], 100)).toEqual([]);
  });
  it('builds the request body sorted, with snake_case pads', () => {
    const body = toRequestSegments([{ ...seg('b', 50, 60, 'auto'), padPre: 100 }, seg('a', 1, 2)]);
    expect(body).toEqual([
      { start: 1, end: 2, label: 'manual', pad_pre_ms: 0, pad_post_ms: 0 },
      { start: 50, end: 60, label: 'auto', pad_pre_ms: 100, pad_post_ms: 0 },
    ]);
  });
});
