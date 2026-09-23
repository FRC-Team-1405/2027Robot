// Fetches /api/remote/sessions once on mount. Mirrors compare/useLogInfo.ts's shape
// (status + data + error, no polling -- this list only changes when someone plugs in a
// RIO/Pi, so a manual refetch button is enough).
import { useCallback, useEffect, useRef, useState } from 'react';

import type { RemoteJob, RemoteSessions } from './types';

export type RemoteSessionsStatus = 'loading' | 'ready' | 'error';

export function useRemoteSessions() {
  const [status, setStatus] = useState<RemoteSessionsStatus>('loading');
  const [data, setData] = useState<RemoteSessions | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<RemoteJob | null>(null);
  const jobId = useRef<string | null>(null);

  const refetch = useCallback(async () => {
    setStatus('loading');
    setError(null);
    setProgress(null);
    try {
      const started = await fetch('/api/remote/sessions/jobs', { method: 'POST' });
      const start = await started.json();
      if (!started.ok) throw new Error(start.detail ?? `${started.status}`);
      if (!start.configured) {
        setData({ configured: false });
        setStatus('ready');
        return;
      }
      jobId.current = start.job_id;
      while (jobId.current === start.job_id) {
        const r = await fetch(`/api/remote/jobs/${start.job_id}`);
        const job = await r.json() as RemoteJob;
        if (!r.ok) throw new Error(job.error ?? `${r.status}`);
        setProgress(job);
        if (job.status === 'complete') {
          setData(job.result as RemoteSessions);
          setStatus('ready');
          return;
        }
        if (job.status === 'error' || job.status === 'cancelled') {
          throw new Error(job.error ?? (job.status === 'cancelled' ? 'Loading cancelled.' : 'Remote listing failed.'));
        }
        await new Promise((resolve) => window.setTimeout(resolve, 250));
      }
    } catch (e) {
      setError(String((e as Error).message ?? e));
      setStatus('error');
    }
  }, []);

  useEffect(() => { void refetch(); }, [refetch]);

  const cancel = useCallback(async () => {
    const id = jobId.current;
    if (id) await fetch(`/api/remote/jobs/${id}`, { method: 'DELETE' });
  }, []);

  return { status, data, error, progress, refetch, cancel };
}
