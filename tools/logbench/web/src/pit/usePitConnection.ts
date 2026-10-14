// Owns the connect/poll/disconnect lifecycle against /api/live/*. HTTP polling rather
// than a WebSocket -- see server/main.py's live_snapshot() docstring for why; this hook
// is the client half of that same decision.
import { useEffect, useRef, useState } from 'react';

import type { LiveSnapshot } from './types';

const POLL_MS = 400;

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

export function usePitConnection() {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [error, setError] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<LiveSnapshot | null>(null);
  const pollRef = useRef<number | null>(null);

  const stopPolling = () => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => stopPolling, []);

  const connect = async (server: string, rootTable: string) => {
    setStatus('connecting');
    setError(null);
    try {
      const params = new URLSearchParams({ server, root_table: rootTable });
      const r = await fetch(`/api/live/connect?${params.toString()}`, { method: 'POST' });
      if (!r.ok) throw new Error((await r.json()).detail ?? `${r.status}`);
      setStatus('connected');
      stopPolling();
      pollRef.current = window.setInterval(async () => {
        try {
          const res = await fetch('/api/live/snapshot');
          if (res.ok) setSnapshot(await res.json());
        } catch {
          // Transient poll failure -- keep showing the last good snapshot rather than
          // flashing an error every 400ms on a flaky pit wifi connection.
        }
      }, POLL_MS);
    } catch (e) {
      setStatus('error');
      setError(String((e as Error).message ?? e));
    }
  };

  const disconnect = async () => {
    stopPolling();
    setSnapshot(null);
    setStatus('disconnected');
    try {
      await fetch('/api/live/disconnect', { method: 'POST' });
    } catch {
      // Best-effort -- the poll loop is already stopped either way.
    }
  };

  return { status, error, snapshot, connect, disconnect };
}
