// Shapes returned by server/main.py's /api/log-info, /api/metric-catalog, /api/compare.
// Kept separate from player/types.ts (the replay wire format) -- this page never touches
// a PlayerSpec at all, it only talks to these three endpoints.

export interface LogEntry {
  path: string;
  name: string;
  size: number;
  mtime: number;
}

export interface LogListing {
  root: string;
  logs: LogEntry[];
}

export interface ModeSpan {
  lo: number;
  hi: number;
  mode: string;
}

export interface LogInfo {
  path: string;
  bounds: [number, number];
  duration: number;
  cameras: string[];
  mode_spans: ModeSpan[];
}

export interface MetricDescriptor {
  id: string;
  label: string;
  unit: string | null;
  lowerIsBetter: boolean;
  kind: 'metric' | 'composite';
}

export interface MetricCatalog {
  defaults: string[];
  metrics: MetricDescriptor[];
}

export type Verdict = 'improved' | 'regressed' | 'neutral' | 'n/a';

export interface MetricDelta {
  id: string;
  label: string;
  unit: string | null;
  camera: string;
  a: number | null;
  b: number | null;
  delta: number | null;
  verdict: Verdict;
}

export interface CompareResult {
  a: { log: string; window: { lo: number; hi: number } };
  b: { log: string; window: { lo: number; hi: number } };
  cameras: string[];
  deltas: MetricDelta[];
}

export type Mode = 'whole' | 'auto' | 'teleop' | 'disabled';

export interface ManualWindow {
  enabled: boolean;
  lo: number;
  hi: number;
}
