import { useEffect, useRef, useState } from 'react';
import { parseLiveSnapshot } from '../health/healthData';
import { errorMessage, requestJson } from '../lib/request';
import { usePolling } from '../lib/usePolling';

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

export function usePitConnection() {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [error, setError] = useState<string | null>(null);
  const request = useRef<AbortController | null>(null);
  const poll = usePolling('/api/live/snapshot', status === 'connected', parseLiveSnapshot, 400);
  useEffect(() => () => request.current?.abort(), []);

  const connect = async (server: string, rootTable: string) => {
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    setStatus('connecting'); setError(null);
    try {
      const params = new URLSearchParams({ server, root_table: rootTable });
      await requestJson(`/api/live/connect?${params}`, { method: 'POST', signal: controller.signal });
      if (!controller.signal.aborted) setStatus('connected');
    } catch (e) {
      if (!controller.signal.aborted) { setStatus('error'); setError(errorMessage(e)); }
    }
  };
  const disconnect = async () => {
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    setStatus('disconnected'); setError(null);
    try { await requestJson('/api/live/disconnect', { method: 'POST', signal: controller.signal }); }
    catch (e) { if (!controller.signal.aborted) setError(`Could not confirm disconnect: ${errorMessage(e)}`); }
  };
  return { status, error: error ?? poll.error, snapshot: poll.data, stale: poll.stale,
    warnings: poll.warnings, lastUpdated: poll.lastUpdated, connect, disconnect };
}
