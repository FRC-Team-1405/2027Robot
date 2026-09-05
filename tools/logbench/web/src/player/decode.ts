// Inverse of server/encode.py. Runs exactly once per load, then never again -- the
// playback loop reads the typed arrays this produces and allocates nothing per frame.
//
// Everything lands in typed arrays (Float64Array) rather than JS arrays of objects:
// the cursor walk and the canvas draw loop both index these hot, and a Float64Array
// avoids the pointer chase and the GC pressure that `{t, v}[]` would add at 60fps.

import type {
  BoolSeries,
  IntSetSeries,
  PoseSeries,
  ScalarSeries,
  Series,
  Spec,
  StringSeries,
  WireSeries,
  WireSpec,
} from './types';

/** Delta-encoded integer milliseconds -> relative seconds. */
function decodeTimes(dt: number[]): Float64Array {
  const t = new Float64Array(dt.length);
  let acc = 0;
  for (let i = 0; i < dt.length; i++) {
    acc += dt[i];
    t[i] = acc / 1000;
  }
  return t;
}

function expandRle<T>(runs: [T, number][], total: number): T[] {
  const out: T[] = new Array(total);
  let i = 0;
  for (const [value, count] of runs) {
    for (let k = 0; k < count; k++) out[i++] = value;
  }
  return out;
}

function decodeSeries(w: WireSeries, kind: string): Series {
  const t = decodeTimes(w.dt);

  switch (kind) {
    case 'scalar': {
      const raw = w.v as (number | null)[];
      const v = new Float64Array(raw.length);
      let min = Infinity;
      let max = -Infinity;
      for (let i = 0; i < raw.length; i++) {
        // null on the wire means "the robot could not measure this". NaN carries that
        // through the typed array; every consumer must check Number.isNaN rather than
        // treating it as a value (see health_display.is_unmeasurable on the Python side).
        const x = raw[i];
        if (x === null) {
          v[i] = NaN;
        } else {
          v[i] = x;
          if (x < min) min = x;
          if (x > max) max = x;
        }
      }
      if (min === Infinity) {
        min = 0;
        max = 1;
      }
      return { kind: 'scalar', t, v, min, max, decimated: !!w.decimated } as ScalarSeries;
    }
    case 'pose2d':
      return {
        kind: 'pose2d',
        t,
        x: Float64Array.from(w.x!),
        y: Float64Array.from(w.y!),
        rot: Float64Array.from(w.rot!),
      } as PoseSeries;
    case 'string':
    case 'enum': {
      const idx = expandRle(w.v as [number, number][], w.n);
      const vocab = w.vocab!;
      return { kind: 'string', t, v: idx.map((i) => vocab[i]) } as StringSeries;
    }
    case 'bool':
      return {
        kind: 'bool',
        t,
        v: Uint8Array.from(expandRle(w.v as [number, number][], w.n)),
      } as BoolSeries;
    case 'intset':
      return {
        kind: 'intset',
        t,
        v: expandRle(w.v as [number[], number][], w.n),
      } as IntSetSeries;
    default:
      throw new Error(`unknown track kind: ${kind}`);
  }
}

export function decodeSpec(wire: WireSpec): Spec {
  const trackById: Record<string, (typeof wire.tracks)[number]> = {};
  for (const t of wire.tracks) trackById[t.id] = t;

  const groupById: Record<string, (typeof wire.groups)[number]> = {};
  for (const g of wire.groups) groupById[g.id] = g;

  const series: Record<string, Series> = {};
  for (const [id, w] of Object.entries(wire.data)) {
    const track = trackById[id];
    if (!track) continue;
    series[id] = decodeSeries(w, track.kind);
  }

  const { data: _data, ...rest } = wire;
  return { ...rest, series, trackById, groupById };
}
