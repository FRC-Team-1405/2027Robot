import { useEffect, useState } from 'react';
import { errorMessage, requestJson, type Parsed } from './request';

export const LIVE_UPDATE_GRACE_MS = 5000;
export const LIVE_STARTUP_GRACE_MS = 10000;
export const LIVE_RECOVERY_POLLS = 2;

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
    let watchdog: number | undefined;
    let degraded = false;
    let recoveryPolls = 0;
    let lastFailure: string | null = null;
    const armWatchdog = (delay: number) => {
      window.clearTimeout(watchdog);
      watchdog = window.setTimeout(() => {
        if (controller.signal.aborted) return;
        degraded = true;
        recoveryPolls = 0;
        setError(lastFailure ?? 'No live updates received. Waiting for the robot or server.');
      }, delay);
    };
    // A watchdog also catches a stalled request before its 10-second HTTP timeout.
    armWatchdog(LIVE_STARTUP_GRACE_MS);
    const poll = async () => {
      try {
        const parsed = parse(await requestJson(url, { signal: controller.signal }));
        if (!controller.signal.aborted) {
          setData(parsed.value); setWarnings(parsed.warnings); setLastUpdated(Date.now());
          lastFailure = null;
          if (!degraded || ++recoveryPolls >= LIVE_RECOVERY_POLLS) {
            degraded = false;
            recoveryPolls = 0;
            setError(null);
          }
          armWatchdog(LIVE_UPDATE_GRACE_MS);
        }
      } catch (e) {
        if (!controller.signal.aborted) {
          lastFailure = errorMessage(e);
          recoveryPolls = 0;
          // Single failures do not replace good data or flash the outage UI.
          if (degraded) setError(lastFailure);
        }
      } finally {
        // Schedule after completion: slow requests cannot overlap or overwrite newer data.
        if (!controller.signal.aborted) timer = window.setTimeout(poll, intervalMs);
      }
    };
    void poll();
    return () => { controller.abort(); window.clearTimeout(timer); window.clearTimeout(watchdog); };
  }, [url, active, parse, intervalMs]);
  return { data, error, warnings, stale: Boolean(error), lastUpdated };
}
