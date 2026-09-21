// Typed client for janitor/server/main.py. Field names mirror the server's JSON.

export interface LogEntry {
  path: string;
  name: string;
  size: number;
  mtime: number;
}

export interface SpanInfo {
  start: number;
  end: number;
  mode: 'disabled' | 'auto' | 'teleop';
  bytes: number;
}

export interface LogInfo {
  log: string;
  root: string;
  name: string;
  size: number;
  mtime: number;
  duration_s: number;
  n_records: number;
  n_entries: number;
  n_cycles: number;
  cycle_period_ms: number;
  header: string;
  time_ordered: boolean;
  has_cycle_marker: boolean;
  data_bytes: number;
  control_bytes: number;
  spans: SpanInfo[];
  byte_hist: number[];
  warnings: string[];
  time_mirrors: string[];
}

export interface SegmentReq {
  start: number;
  end: number;
  label: string;
  pad_pre_ms: number;
  pad_post_ms: number;
}

export interface PlanReq {
  log: string;
  segments: SegmentReq[];
  gap_ms: number;
  gap_policy: 'compact' | 'preserve';
  exclude: string[];
  exclude_prefixes: string[];
}

export interface SegmentPreview {
  label: string;
  orig_first: number;
  orig_last: number;
  new_first: number;
  new_last: number;
  n_cycles: number;
  bytes: number;
}

export interface Seam {
  dropped_cycles: number;
  real_cycles_kept_before: number;
  real_cycles_kept_after: number;
}

export interface Preview {
  exact: boolean;
  source_bytes: number;
  output_bytes: number;
  saved_bytes: number;
  saved_pct: number;
  n_cycles_out: number;
  n_cycles_source: number;
  segments: SegmentPreview[];
  ranges: { first: number; last: number; n_cycles: number; bytes: number }[];
  seams: Seam[];
  gap_cycles: number;
  cycle_period_ms: number;
  warnings: string[];
  n_excluded_entries: number;
  // exact only
  n_carried?: number;
  n_excluded_records?: number;
  control_records_dropped?: number;
}

export interface ExportResult {
  path: string;
  abs_path: string;
  name: string;
  bytes: number;
  source_bytes: number;
  saved_bytes: number;
  saved_pct: number;
  verify: { ok: boolean; issues: string[]; n_issues: number } | null;
  verify_skipped: boolean;
  warnings: string[];
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e;
    throw new ApiError('Cannot reach the janitor server. Is `python -m janitor serve` still running?', 0);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (typeof body.detail === 'string') detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join('; ');
    } catch {
      /* not JSON */
    }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

const post = (body: unknown, signal?: AbortSignal): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
  signal,
});

export const api = {
  logs: () => request<{ root: string; logs: LogEntry[] }>('/api/logs'),
  index: (log: string, signal?: AbortSignal) => request<LogInfo>(`/api/index?log=${encodeURIComponent(log)}`, { signal }),
  preview: (plan: PlanReq, signal?: AbortSignal) => request<Preview>('/api/preview', post(plan, signal)),
  previewExact: (plan: PlanReq, signal?: AbortSignal) => request<Preview>('/api/preview/exact', post(plan, signal)),
  exportSave: (plan: PlanReq, filename: string | undefined, verify: boolean) =>
    request<ExportResult>('/api/export', post({ ...plan, mode: 'save', filename, verify })),
  /** Returns the file as a Blob plus the name the server suggested. */
  exportDownload: async (plan: PlanReq, filename: string | undefined) => {
    const res = await fetch('/api/export', post({ ...plan, mode: 'download', filename }));
    if (!res.ok) throw new ApiError((await res.json().catch(() => ({ detail: res.statusText }))).detail, res.status);
    const cd = res.headers.get('Content-Disposition') ?? '';
    const name = /filename="([^"]+)"/.exec(cd)?.[1] ?? 'trimmed.wpilog';
    return { blob: await res.blob(), name };
  },
};
