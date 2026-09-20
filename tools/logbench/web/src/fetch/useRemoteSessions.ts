// Fetches /api/remote/sessions once on mount. Mirrors compare/useLogInfo.ts's shape
// (status + data + error, no polling -- this list only changes when someone plugs in a
// RIO/Pi, so a manual refetch button is enough).
import { useCallback, useEffect, useState } from 'react';

import type { RemoteSessions } from './types';

export type RemoteSessionsStatus = 'loading' | 'ready' | 'error';

export function useRemoteSessions() {
  const [status, setStatus] = useState<RemoteSessionsStatus>('loading');
  const [data, setData] = useState<RemoteSessions | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(() => {
    setStatus('loading');
    setError(null);
    fetch('/api/remote/sessions')
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).detail ?? `${r.status}`);
        return r.json() as Promise<RemoteSessions>;
      })
      .then((d) => {
        setData(d);
        setStatus('ready');
      })
      .catch((e) => {
        setError(String(e.message ?? e));
        setStatus('error');
      });
  }, []);

  useEffect(() => refetch(), [refetch]);

  return { status, data, error, refetch };
}
