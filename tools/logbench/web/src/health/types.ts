// Shape of GET /api/health/log and /api/health/live (server/health/engine.py's report).

export type Status = 'ok' | 'warn' | 'fail' | 'nodata' | 'na';
export type Verdict = 'ok' | 'warn' | 'fail' | 'incomplete' | 'empty';

export interface Counts {
  ok: number;
  warn: number;
  fail: number;
  nodata: number;
  na: number;
}

export interface CheckRow {
  id: string;
  key: string;
  section: string;
  group: string;
  subject: string;
  label: string;
  status: Status;
  value: number | string | boolean | null;
  display: string;
  unit: string;
  /** The rule that was applied, in words: "warn above 70 %, fail above 90 %". */
  rule: string;
  detail: string;
  help: string;
  /** Live only: the worst status seen since the last reset. */
  worst?: Status;
  peak?: number;
  peak_display?: string;
}

export interface Subject {
  label: string;
  status: Status;
  counts: Counts;
  checks: CheckRow[];
}

export interface Group {
  label: string;
  status: Status;
  counts: Counts;
  subjects: Subject[];
}

export interface Section {
  id: string;
  label: string;
  status: Status;
  counts: Counts;
  groups: Group[];
}

export interface HealthReport {
  kind: 'live' | 'log';
  verdict: Verdict;
  counts: Counts;
  sections: Section[];
  config_errors?: string[];
  /** Live only: false until the NetworkTables client is connected. */
  connected?: boolean;
  meta?: {
    log?: string;
    duration?: number;
    modes?: { mode: string; start: number; end: number }[];
    topics?: number;
    robot?: 'disabled' | 'auto' | 'teleop' | null;
  };
}
