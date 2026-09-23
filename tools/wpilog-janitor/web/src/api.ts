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
  /** Entry the mode bands come from: DriverStation/Enabled (AdvantageKit), DS:enabled or NT:/FMSInfo/FMSControlData (plain WPILib). */
  mode_source: string | null;
  has_cycle_marker: boolean;
  /** Records written behind a newer record (plain WPILib logs' NT mirroring). Nonzero: the log needs the Order page before trimming. */
  order: { n_late: number; max_late_ms: number; late_pct: number };
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
  /** Keep battery voltage and match info for the whole log, not just the kept periods (original timestamps only). */
  keep_context: boolean;
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
  /** Entries kept for the whole log (the match context), empty when off or when closing the gaps. */
  kept_everywhere: string[];
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

export interface OrderEntry {
  name: string;
  records: number;
  late: number;
  max_late_ms: number;
  backwards: number;
}

export interface OrderReport {
  log: string;
  name: string;
  size: number;
  default_name: string;
  ordered: boolean;
  n_records: number;
  n_late: number;
  late_pct: number;
  max_late_ms: number;
  lateness: { bucket: string; records: number }[];
  /** Records out of order within their own entry. 0 means reordering keeps every signal's sequence exactly. */
  n_backwards: number;
  n_entries_late: number;
  entries: OrderEntry[];
}

export interface ReorderResult {
  path: string;
  abs_path: string;
  name: string;
  bytes: number;
  source_bytes: number;
  n_moved: number;
  n_records: number;
  verify: { ok: boolean; issues: string[]; n_issues: number } | null;
  verify_skipped: boolean;
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
  /** Opens the OS folder dialog on the server's machine; blocks until it closes. */
  pickLogRoot: () => request<{ root: string; cancelled: boolean }>('/api/log-root/pick', { method: 'POST' }),
  index: (log: string, signal?: AbortSignal) => request<LogInfo>(`/api/index?log=${encodeURIComponent(log)}`, { signal }),
  preview: (plan: PlanReq, signal?: AbortSignal) => request<Preview>('/api/preview', post(plan, signal)),
  previewExact: (plan: PlanReq, signal?: AbortSignal) => request<Preview>('/api/preview/exact', post(plan, signal)),
  exportSave: (plan: PlanReq, filename: string | undefined, verify: boolean) =>
    request<ExportResult>('/api/export', post({ ...plan, mode: 'save', filename, verify })),
  order: (log: string, signal?: AbortSignal) => request<OrderReport>(`/api/order?log=${encodeURIComponent(log)}`, { signal }),
  reorderSave: (log: string, filename: string | undefined) => request<ReorderResult>('/api/reorder', post({ log, mode: 'save', filename, verify: true })),
  reorderDownload: async (log: string, filename: string | undefined) => {
    const res = await fetch('/api/reorder', post({ log, mode: 'download', filename }));
    if (!res.ok) throw new ApiError((await res.json().catch(() => ({ detail: res.statusText }))).detail, res.status);
    const name = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ?? 'ordered.wpilog';
    return { blob: await res.blob(), name };
  },
  /** Returns the file as a Blob plus the name the server suggested. */
  exportDownload: async (plan: PlanReq, filename: string | undefined) => {
    const res = await fetch('/api/export', post({ ...plan, mode: 'download', filename }));
    if (!res.ok) throw new ApiError((await res.json().catch(() => ({ detail: res.statusText }))).detail, res.status);
    const cd = res.headers.get('Content-Disposition') ?? '';
    const name = /filename="([^"]+)"/.exec(cd)?.[1] ?? 'trimmed.wpilog';
    return { blob: await res.blob(), name };
  },
};

// ── Content page ─────────────────────────────────────────────────────────────────────────────────

export type EntryClass = 'output' | 'replay-input' | 'structural' | 'janitor';
export type ProtectProfile = 'replay' | 'logbench';

export interface ContentEntry {
  id: number;
  name: string;
  type: string;
  bytes: number;
  records: number;
  hz: number;
  changes: number;
  distinct: number;
  distinct_capped: boolean;
  constant: boolean;
  cls: EntryClass;
  protected: string | null;
  first_s: number | null;
  last_s: number | null;
  sample: string | null;
  num: { min: number | null; max: number | null; mean: number | null } | null;
}

export interface DupGroup {
  id: string;
  kind: 'identical' | 'values' | 'near';
  type: string;
  members: number[];
  keeper: number;
  recoverable_bytes: number;
  evidence: string;
  blocked: number[];
  weak: boolean;
}

export interface Twin {
  key: string;
  members: number[];
  relation: 'near' | 'different' | 'different-length';
  note: string;
}

export interface ContentReq {
  log: string;
  segments: SegmentReq[];
  gap_ms: number;
  gap_policy: 'compact' | 'preserve';
  protect: ProtectProfile[];
}

export interface ContentResult {
  window: { whole_log: boolean; seconds: number; cycles: number; bytes: number };
  protect: ProtectProfile[];
  entries: ContentEntry[];
  constants: { count: number; bytes: number };
  groups: DupGroup[];
  twins: Twin[];
  took_s: number;
}

export const contentApi = {
  content: (req: ContentReq, signal?: AbortSignal) => request<ContentResult>('/api/content', post(req, signal)),
};
