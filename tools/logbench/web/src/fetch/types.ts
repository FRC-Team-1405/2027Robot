// Shapes returned by server/main.py's /api/remote/sessions, /api/remote/bundle and
// /api/import/zip. See main.py's PiSessionRef/BundleRequest and the handlers themselves
// for the authoritative wire format.

export interface RioLogEntry {
  name: string;
  size: number;
  mtime: number;
  wall_clock: string | null;
  status: 'none' | 'logs only' | 'logs and vision';
}

export interface PiSessionEntry {
  camera: string;
  name: string;
  wall_clock: string | null;
}

export interface PiSessionRef {
  camera: string;
  name: string;
}

export type Confidence = 'high' | 'low' | 'none';

export interface PairingSuggestion {
  rio_log: string;
  pi_sessions: PiSessionRef[];
  confidence: Confidence;
  reason: string;
}

export type RemoteSessions =
  | { configured: false }
  | {
      configured: true;
      rio_logs: RioLogEntry[];
      pi_sessions: PiSessionEntry[];
      pairings: PairingSuggestion[];
    };

export interface BundleResult {
  log: string;
  pi_sessions: (PiSessionRef & { path: string })[];
  manual: boolean;
}

export interface RemoteJob {
  id: string;
  kind: string;
  status: 'queued' | 'running' | 'complete' | 'error' | 'cancelled';
  phase: string;
  elapsed_seconds: number;
  bytes_done: number;
  bytes_total: number | null;
  files_done: number;
  files_total: number | null;
  active_file: string | null;
  bytes_per_second: number;
  eta_seconds: number | null;
  error: string | null;
  result: unknown;
}

export interface ImportResult {
  log: string;
  imported: string[];
}
