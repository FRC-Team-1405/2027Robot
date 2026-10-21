import { useCallback, useEffect, useRef, useState } from 'react';
import { errorMessage, requestJson } from '../lib/request';
import { usePolling } from '../lib/usePolling';
import { parseHealthReport } from './healthData';
import type { HealthReport } from './types';

export function useLogReport(path: string | null) {
  const [data, setData] = useState<{ path: string; report: HealthReport } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const request = useRef<AbortController | null>(null);
  const load = useCallback(async () => {
    request.current?.abort();
    if (!path) { setLoading(false); setError(null); setWarnings([]); return; }
    const controller = new AbortController(); request.current = controller;
    setLoading(true); setError(null);
    try {
      const parsed = parseHealthReport(await requestJson(`/api/health/log?${new URLSearchParams({ path })}`, { signal: controller.signal }));
      if (parsed.value.kind !== 'log') throw new Error('The server returned a live report for a log.');
      if (!controller.signal.aborted) { setData({ path, report: parsed.value }); setWarnings(parsed.warnings); }
    } catch (e) { if (!controller.signal.aborted) setError(errorMessage(e)); }
    finally { if (!controller.signal.aborted) setLoading(false); }
  }, [path]);
  useEffect(() => {
    setData(null); setWarnings([]);
    void load();
    return () => request.current?.abort();
  }, [load]);
  return { report: data?.path === path ? data.report : null, error, warnings, loading, reload: load };
}

function parseLiveReport(body: unknown) {
  // This is the normal API response while the NT client waits/reconnects.
  if (body && typeof body === 'object' && 'connected' in body && body.connected === false) {
    const config = 'config_errors' in body && Array.isArray(body.config_errors)
      ? body.config_errors.filter((v): v is string => typeof v === 'string').join(' ') : '';
    throw new Error(`Waiting for the robot NetworkTables connection.${config ? ` ${config}` : ''}`);
  }
  const parsed = parseHealthReport(body);
  if (parsed.value.kind !== 'live') throw new Error('The server returned a log report for a live robot.');
  return parsed;
}

export function useLiveReport(active: boolean) {
  const poll = usePolling('/api/health/live', active, parseLiveReport, 1000);
  const [resetError, setResetError] = useState<string | null>(null);
  const request = useRef<AbortController | null>(null);
  useEffect(() => {
    setResetError(null);
    return () => request.current?.abort();
  }, [active]);
  const reset = useCallback(async () => {
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    try {
      await requestJson('/api/health/live/reset', { method: 'POST', signal: controller.signal });
      if (!controller.signal.aborted) setResetError(null);
    } catch (e) { if (!controller.signal.aborted) setResetError(`Reset failed: ${errorMessage(e)}`); }
  }, []);
  return { ...poll, report: poll.data, resetError, reset };
}
