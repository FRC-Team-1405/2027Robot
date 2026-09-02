// Sample lookup for a monotonically advancing playhead.
//
// This is the piece that replaces the old replay tab's per-tick full-series scan
// (tabs/replay.py `_pose_and_trail` walked every pose sample three times per tick, just
// to find a 3-second trail window). Playback time almost always moves forward by one
// frame, so the right data structure is a remembered index that steps forward a sample
// or two -- O(1) amortized -- with a binary search only for the rare discontinuity
// (a scrub, a reset, a jump backwards).

/** Index of the last sample at or before `time`, or -1 if `time` precedes all samples. */
export function binarySearch(t: Float64Array, time: number): number {
  let lo = 0;
  let hi = t.length - 1;
  if (hi < 0 || time < t[0]) return -1;
  if (time >= t[hi]) return hi;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (t[mid] <= time) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}

/**
 * A remembered position in one series. Create once per (series, consumer) and reuse it
 * across frames -- the whole point is the memory between calls.
 */
export class Cursor {
  /** Index of the last sample at or before the last queried time. -1 = before the start. */
  index = -1;
  private lastTime = -Infinity;

  constructor(private readonly t: Float64Array) {}

  /** Advance (or seek) to `time`, returning the new index. */
  seek(time: number): number {
    const t = this.t;
    if (t.length === 0) return -1;

    if (time >= this.lastTime) {
      // Forward: walk. Bounded by a small step count so a large forward jump (4x speed
      // over a sparse track, or a scrub to the right) degrades to a search rather than
      // to a long linear walk.
      let i = this.index;
      let steps = 0;
      while (i + 1 < t.length && t[i + 1] <= time) {
        i++;
        if (++steps > 64) {
          i = binarySearch(t, time);
          break;
        }
      }
      this.index = i;
    } else {
      this.index = binarySearch(t, time);
    }

    this.lastTime = time;
    return this.index;
  }

  reset(): void {
    this.index = -1;
    this.lastTime = -Infinity;
  }
}

/**
 * A sliding [time - window, time] range over one series, tracked with two cursors so a
 * trail costs O(1) per frame instead of a full scan.
 *
 * Returns index bounds rather than a copied array: the canvas draws straight out of the
 * underlying typed arrays, so no per-frame allocation happens at all.
 */
export class WindowCursor {
  private readonly head: Cursor;
  private readonly tail: Cursor;

  constructor(private readonly t: Float64Array) {
    this.head = new Cursor(t);
    this.tail = new Cursor(t);
  }

  /** [startIndex, endIndex] inclusive; endIndex < startIndex means the window is empty. */
  range(time: number, window: number): [number, number] {
    const end = this.head.seek(time);
    if (end < 0) return [0, -1];
    // `tail` lands on the last sample at or before the window's start; the first sample
    // INSIDE the window is the one after it.
    const start = this.tail.seek(time - window) + 1;
    return [Math.min(start, end), end];
  }

  reset(): void {
    this.head.reset();
    this.tail.reset();
  }

  get length(): number {
    return this.t.length;
  }
}

/**
 * Value of a scalar series at `time`, honoring a staleness limit.
 *
 * Mirrors vision_analyzer.metrics.nearest_value: a sample further than `maxAge` from the
 * playhead is not a stale reading to display, it is an absence of data. Returns NaN for
 * both "no sample" and "sample the robot could not measure", which the readout renders
 * as n/a either way.
 */
export function sampleAt(
  t: Float64Array,
  v: Float64Array,
  cursor: Cursor,
  time: number,
  maxAge: number,
): number {
  const i = cursor.seek(time);
  if (i < 0) {
    // Nothing at or before `time`; the first sample may still be within tolerance.
    return t.length > 0 && t[0] - time <= maxAge ? v[0] : NaN;
  }
  if (time - t[i] <= maxAge) return v[i];
  // Past sample is too old -- but a future one may be nearer (matching nearest_value's
  // "closest sample within tolerance" behavior rather than "last sample only").
  if (i + 1 < t.length && t[i + 1] - time <= maxAge) return v[i + 1];
  return NaN;
}
