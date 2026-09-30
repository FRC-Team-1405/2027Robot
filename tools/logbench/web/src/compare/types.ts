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

// availability / quality / context are the three kinds of question a metric can answer
// (docs/adr/0001, D1). 'overall' is the optional availability x quality product and 'legacy'
// is the composites that predate the split and mix categories.
export type CategoryId = 'availability' | 'quality' | 'context' | 'overall' | 'legacy';

export interface CategoryDef {
  id: 'availability' | 'quality' | 'context';
  label: string;
  question: string;
  low_means: string;
  scored: boolean;
}

export interface MetricDescriptor {
  id: string;
  label: string;
  unit: string | null;
  lowerIsBetter: boolean;
  kind: 'metric' | 'composite';
  category: CategoryId;
  // False for a whole-run fact (robot speed): compare returns one 'All' row for it.
  perCamera: boolean;
  description: string;
}

export interface MetricCatalog {
  defaults: string[];
  categories: CategoryDef[];
  metrics: MetricDescriptor[];
}

// 'context' = a context metric: shown, never judged (less range is neither better nor worse).
export type Verdict = 'improved' | 'regressed' | 'neutral' | 'n/a' | 'context';

export interface MetricDelta {
  id: string;
  label: string;
  unit: string | null;
  camera: string;
  a: number | null;
  b: number | null;
  delta: number | null;
  verdict: Verdict;
  category: CategoryId;
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
