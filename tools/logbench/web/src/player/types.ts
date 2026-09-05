// Mirrors server/model.py and the wire format produced by server/encode.py.
// Keep the two in step: the Python tests in tests/test_encode.py pin the shapes below.

export type TrackKind = 'scalar' | 'bool' | 'string' | 'enum' | 'pose2d' | 'intset';
export type PanelType = 'timeseries' | 'field' | 'readout' | 'events' | 'tracktoggle';

export interface Group {
  id: string;
  label: string;
  color: string;
}

export interface Track {
  id: string;
  label: string;
  kind: TrackKind;
  group: string | null;
  unit: string | null;
  color: string | null;
  domain: [number, number] | null;
  hidden: boolean;
}

export interface Panel {
  id: string;
  type: PanelType;
  title: string;
  tracks: string[];
  options: Record<string, unknown>;
}

/** Encoded form, straight off the wire. */
export interface WireSeries {
  dt: number[];
  n: number;
  decimated?: boolean;
  enc?: 'rle' | 'dict-rle';
  vocab?: string[];
  v?: unknown;
  x?: number[];
  y?: number[];
  rot?: number[];
}

export interface SeverityBand {
  min: number;
  color: string;
  label: string;
}

export interface FieldStatic {
  length: number;
  width: number;
  tags: Record<string, [number, number]>;
}

export interface WireSpec {
  title: string;
  t0: number;
  t1: number;
  duration: number;
  groups: Group[];
  tracks: Track[];
  panels: Panel[];
  layout: string[][];
  static: {
    field?: FieldStatic;
    severity?: SeverityBand[];
    staleness_sec?: number;
  };
  warnings: string[];
  data: Record<string, WireSeries>;
}

// ── Decoded, in-memory form ────────────────────────────────────────────────────
// Times are Float64Array of RELATIVE seconds (t - t0). Everything user-facing works
// in relative time; absolute log time is only needed to tie a moment back to the log.

export interface ScalarSeries {
  kind: 'scalar';
  t: Float64Array;
  /** NaN marks a sample the robot could not measure (encoded as null on the wire). */
  v: Float64Array;
  min: number;
  max: number;
  decimated: boolean;
}

export interface PoseSeries {
  kind: 'pose2d';
  t: Float64Array;
  x: Float64Array;
  y: Float64Array;
  rot: Float64Array;
}

export interface StringSeries {
  kind: 'string';
  t: Float64Array;
  v: string[];
}

export interface BoolSeries {
  kind: 'bool';
  t: Float64Array;
  v: Uint8Array;
}

export interface IntSetSeries {
  kind: 'intset';
  t: Float64Array;
  v: number[][];
}

export type Series = ScalarSeries | PoseSeries | StringSeries | BoolSeries | IntSetSeries;

export interface Spec extends Omit<WireSpec, 'data'> {
  series: Record<string, Series>;
  trackById: Record<string, Track>;
  groupById: Record<string, Group>;
}
