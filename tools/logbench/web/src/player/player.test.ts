// Guards the three invariants the player's usability rests on:
//   - the wire format decodes to exactly what server/encode.py encoded,
//   - the monotonic cursor always agrees with a plain binary search (this is the O(N)
//     scan fix; if it ever disagrees, the picture is silently wrong rather than slow),
//   - playback time tracks real elapsed time and speed.

import { describe, expect, it } from 'vitest';

import { PlayerClock } from './clock';
import { Cursor, WindowCursor, binarySearch, sampleAt } from './cursor';
import { decodeSpec } from './decode';
import type { WireSpec } from './types';

// ── decode.ts <-> server/encode.py ────────────────────────────────────────────

function wire(partial: Partial<WireSpec>): WireSpec {
  return {
    title: 't',
    t0: 100,
    t1: 110,
    duration: 10,
    groups: [],
    tracks: [],
    panels: [],
    layout: [],
    static: {},
    warnings: [],
    data: {},
    ...partial,
  };
}

describe('decode', () => {
  it('turns delta-encoded ms into relative seconds', () => {
    const spec = decodeSpec(
      wire({
        tracks: [
          { id: 'a', label: 'A', kind: 'scalar', group: null, unit: null, color: null, domain: null, hidden: false },
        ],
        data: { a: { dt: [0, 20, 20, 60], n: 4, v: [1, 2, 3, 4] } },
      }),
    );
    const s = spec.series.a;
    expect(Array.from(s.t)).toEqual([0, 0.02, 0.04, 0.1]);
  });

  it('maps null to NaN and keeps it out of min/max', () => {
    const spec = decodeSpec(
      wire({
        tracks: [
          { id: 'a', label: 'A', kind: 'scalar', group: null, unit: null, color: null, domain: null, hidden: false },
        ],
        data: { a: { dt: [0, 20, 20], n: 3, v: [50, null, 70] } },
      }),
    );
    const s = spec.series.a as { v: Float64Array; min: number; max: number };
    expect(Number.isNaN(s.v[1])).toBe(true);
    expect(s.min).toBe(50);
    expect(s.max).toBe(70);
  });

  it('expands dict+RLE strings', () => {
    const spec = decodeSpec(
      wire({
        tracks: [
          { id: 'r', label: 'R', kind: 'string', group: null, unit: null, color: null, domain: null, hidden: false },
        ],
        data: { r: { dt: [0, 20, 20, 20], n: 4, enc: 'dict-rle', vocab: ['stale', ''], v: [[0, 2], [1, 2]] } },
      }),
    );
    expect((spec.series.r as { v: string[] }).v).toEqual(['stale', 'stale', '', '']);
  });

  it('expands RLE int sets', () => {
    const spec = decodeSpec(
      wire({
        tracks: [
          { id: 'g', label: 'G', kind: 'intset', group: null, unit: null, color: null, domain: null, hidden: false },
        ],
        data: { g: { dt: [0, 20, 20], n: 3, enc: 'rle', v: [[[3, 10], 2], [[7], 1]] } },
      }),
    );
    expect((spec.series.g as { v: number[][] }).v).toEqual([[3, 10], [3, 10], [7]]);
  });

  it('drops payload entries with no matching track', () => {
    const spec = decodeSpec(wire({ data: { orphan: { dt: [0], n: 1, v: [1] } } }));
    expect(Object.keys(spec.series)).toEqual([]);
  });
});

// ── cursor.ts ─────────────────────────────────────────────────────────────────

const times = Float64Array.from({ length: 5000 }, (_, i) => i * 0.02);

describe('Cursor', () => {
  it('agrees with binary search while walking forward', () => {
    const c = new Cursor(times);
    for (let t = 0; t < 100; t += 0.016) {
      expect(c.seek(t)).toBe(binarySearch(times, t));
    }
  });

  it('agrees with binary search across random backward jumps (scrubbing)', () => {
    const c = new Cursor(times);
    let t = 0;
    for (let i = 0; i < 5000; i++) {
      t = i % 7 === 0 ? Math.random() * 100 : t + 0.016;
      if (t > 100) t = 0;
      expect(c.seek(t)).toBe(binarySearch(times, t));
    }
  });

  it('agrees after a large forward jump (the walk must fall back to a search)', () => {
    const c = new Cursor(times);
    c.seek(0);
    expect(c.seek(95)).toBe(binarySearch(times, 95));
  });

  it('reports -1 before the first sample', () => {
    expect(new Cursor(times).seek(-1)).toBe(-1);
  });

  it('handles an empty series', () => {
    expect(new Cursor(new Float64Array(0)).seek(5)).toBe(-1);
  });
});

describe('WindowCursor', () => {
  it('matches a brute-force scan of the trail window', () => {
    const w = new WindowCursor(times);
    let t = 0;
    for (let i = 0; i < 1500; i++) {
      t = i % 9 === 0 ? Math.random() * 100 : t + 0.016;
      if (t > 100) t = 0;
      const [a, b] = w.range(t, 3);
      const brute: number[] = [];
      for (let k = 0; k < times.length; k++) {
        if (times[k] >= t - 3 && times[k] <= t) brute.push(k);
      }
      const got = b >= a ? Array.from({ length: b - a + 1 }, (_, k) => a + k) : [];
      expect(got).toEqual(brute);
    }
  });
});

describe('sampleAt', () => {
  const t = Float64Array.from([0, 1, 10]);
  const v = Float64Array.from([5, 6, 7]);

  it('returns the sample at or before the time', () => {
    expect(sampleAt(t, v, new Cursor(t), 1.5, 1)).toBe(6);
  });

  it('returns NaN when the nearest sample is staler than the limit', () => {
    // 5s sits in the gap between t=1 and t=10; both are >1s away.
    expect(Number.isNaN(sampleAt(t, v, new Cursor(t), 5, 1))).toBe(true);
  });

  it('reaches forward to a nearer future sample within tolerance', () => {
    expect(sampleAt(t, v, new Cursor(t), 9.5, 1)).toBe(7);
  });
});

// ── clock.ts ──────────────────────────────────────────────────────────────────

describe('PlayerClock', () => {
  it('advances by real elapsed time scaled by speed', () => {
    // The old Streamlit tab added a fixed 200ms per tick regardless of how long the
    // tick actually took, so slow ticks silently desynced playback from the log.
    const c = new PlayerClock(600);
    c.setSpeed(2);
    for (let i = 0; i < 600; i++) c.advance(1 / 60); // 10s of wall clock at 2x
    expect(c.time).toBeCloseTo(20, 6);
  });

  it('never runs past the end', () => {
    const c = new PlayerClock(5);
    for (let i = 0; i < 1000; i++) c.advance(0.1);
    expect(c.time).toBe(5);
  });

  it('clamps seeks to the log', () => {
    const c = new PlayerClock(10);
    c.seek(-5);
    expect(c.time).toBe(0);
    c.seek(999);
    expect(c.time).toBe(10);
  });

  it('restarts from the top when play is pressed at the end', () => {
    const c = new PlayerClock(10);
    c.seek(10);
    c.play();
    expect(c.time).toBe(0);
    c.pause();
  });

  it('notifies frame listeners with the current time', () => {
    const c = new PlayerClock(10);
    const seen: number[] = [];
    c.onFrame((t) => seen.push(t));
    c.advance(1);
    c.advance(1);
    expect(seen).toEqual([1, 2]);
  });

  it('stops notifying after unsubscribe', () => {
    const c = new PlayerClock(10);
    const seen: number[] = [];
    const off = c.onFrame((t) => seen.push(t));
    c.advance(1);
    off();
    c.advance(1);
    expect(seen).toEqual([1]);
  });
});
