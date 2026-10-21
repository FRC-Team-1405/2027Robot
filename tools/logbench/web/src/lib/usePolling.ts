import { useEffect, useState } from 'react';
import { errorMessage, requestJson, type Parsed } from './request';

export function usePolling<T>(url: string, active: boolean, parse: (body: unknown) => Parsed<T>, intervalMs: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  useEffect(() => {
    setData(null); setError(null); setWarnings([]); setLastUpdated(null);
    if (!active) return;
    const controller = new AbortController();
    let timer: number | undefined;
    const poll = async () => {
      try {
        const parsed = parse(await requestJson(url, { signal: controller.signal }));
        if (!controller.signal.aborted) {
          setData(parsed.value); setWarnings(parsed.warnings); setError(null); setLastUpdated(Date.now());
        }
      } catch (e) {
        if (!controller.signal.aborted) setError(errorMessage(e));
      } finally {
        // Schedule after completion: slow requests cannot overlap or overwrite newer data.
        if (!controller.signal.aborted) timer = window.setTimeout(poll, intervalMs);
      }
    };
    void poll();
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [url, active, parse, intervalMs]);
  return { data, error, warnings, stale: Boolean(error), lastUpdated };
}
