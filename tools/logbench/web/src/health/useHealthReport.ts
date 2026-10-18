// Fetching the two kinds of report. A log is fetched once (and again on demand); the live robot is
// polled about once a second while connected. Both keep the last good report on screen if a
// request fails, so a flaky pit wifi connection shows a note instead of blanking the page.
import { useCallback, useEffect, useRef, useState } from 'react';

import type { HealthReport } from './types';

const LIVE_POLL_MS = 1000;

async function readError(r: Response): Promise<string> {
  try {
    const body = await r.json();
    return typeof body.detail === 'string' ? body.detail : `${r.status}`;
  } catch {
    return `${r.status}`;
  }
}

export function useLogReport(path: string | null) {
  const [report, setReport] = useState<HealthReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const seq = useRef(0);

  const load = useCallback(async () => {
    if (!path) return;
    const mine = ++seq.current;
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`/api/health/log?${new URLSearchParams({ path })}`);
      if (!r.ok) throw new Error(await readError(r));
      const body = (await r.json()) as HealthReport;
      if (mine === seq.current) setReport(body);
    } catch (e) {
      if (mine === seq.current) {
        setReport(null);
        setError(String((e as Error).message ?? e));
      }
    } finally {
      if (mine === seq.current) setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    setReport(null);
    void load();
  }, [load]);

  return { report, error, loading, reload: load };
}

export function useLiveReport(active: boolean) {
  const [report, setReport] = useState<HealthReport | null>(null);
  const [stale, setStale] = useState(false);

  useEffect(() => {
    if (!active) {
      setReport(null);
      setStale(false);
      return;
    }
    let cancelled = false;
    const poll = async () => {
      try {
        const r = await fetch('/api/health/live');
        if (!r.ok) throw new Error(String(r.status));
        const body = (await r.json()) as HealthReport;
        if (!cancelled) {
          setReport(body);
          setStale(false);
        }
      } catch {
        if (!cancelled) setStale(true);
      }
    };
    void poll();
    const id = window.setInterval(poll, LIVE_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [active]);

  const reset = useCallback(async () => {
    try {
      await fetch('/api/health/live/reset', { method: 'POST' });
    } catch {
      // Best effort: the next poll shows whether it took.
    }
  }, []);

  return { report, stale, reset };
}
