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

export interface ImportResult {
  log: string;
  imported: string[];
}
