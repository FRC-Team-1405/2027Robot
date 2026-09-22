import { useEffect, useMemo, useState } from 'react';
import { contentApi, type ContentReq, type ContentResult } from '../api';

/** Fetches the Content analysis for a request and keeps showing the previous result while a new one loads
 *  (changing the protection setting, or the window, should not blank the page). */
export function useContent(req: ContentReq | null) {
  const key = useMemo(() => JSON.stringify(req), [req]);
  const [data, setData] = useState<ContentResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!req) return;
    const ac = new AbortController();
    setLoading(true);
    contentApi
      .content(req, ac.signal)
      .then((d) => {
        setData(d);
        setError(null);
        setLoading(false);
      })
      .catch((e: Error) => {
        if (e.name === 'AbortError') return;
        setError(e.message);
        setLoading(false);
      });
    return () => ac.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return { data, error, loading };
}
