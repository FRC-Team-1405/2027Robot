// Fetches /api/log-info for one log: bounds, cameras, DS-mode spans. Used twice by
// ComparePage (once per side) so it's a hook rather than inlined fetch logic.
import { useEffect, useState } from 'react';

import type { LogInfo } from './types';

export function useLogInfo(logPath: string | null): LogInfo | null {
  const [info, setInfo] = useState<LogInfo | null>(null);

  useEffect(() => {
    if (!logPath) {
      setInfo(null);
      return;
    }
    let cancelled = false;
    setInfo(null);
    fetch(`/api/log-info?log=${encodeURIComponent(logPath)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${r.status}`))))
      .then((data: LogInfo) => {
        if (!cancelled) setInfo(data);
      })
      .catch(() => {
        if (!cancelled) setInfo(null);
      });
    return () => {
      cancelled = true;
    };
  }, [logPath]);

  return info;
}
