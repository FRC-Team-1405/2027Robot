import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api, type LogInfo, type PlanReq, type Preview } from '../api';
import { toRequestSegments, type Seg } from '../lib/segments';
import type { Exclusions } from '../lib/storage';

/** Above this size the exact (one pass over the file) preview is not run automatically. */
export const AUTO_EXACT_MAX_BYTES = 40 * 1024 * 1024;

export function useLogInfo(log: string) {
  const [state, setState] = useState<{ info: LogInfo | null; error: string | null; loading: boolean }>({
    info: null,
    error: null,
    loading: true,
  });
  useEffect(() => {
    const ac = new AbortController();
    setState({ info: null, error: null, loading: true });
    api
      .index(log, ac.signal)
      .then((info) => setState({ info, error: null, loading: false }))
      .catch((e: Error) => {
        if (e.name !== 'AbortError') setState({ info: null, error: e.message, loading: false });
      });
    return () => ac.abort();
  }, [log]);
  return state;
}

export interface PreviewState {
  /** The best number available for the current plan: exact if it has been computed, else the estimate. */
  preview: Preview | null;
  error: string | null;
  /** An estimate request is in flight. */
  pending: boolean;
  /** An exact request is in flight. */
  exactPending: boolean;
  canComputeExact: boolean;
  computeExact: () => void;
  request: PlanReq | null;
}

export function usePreview(
  log: string,
  info: LogInfo | null,
  segs: Seg[],
  gapMs: number,
  policy: 'compact' | 'preserve',
  excl: Exclusions,
): PreviewState {
  const request = useMemo<PlanReq | null>(
    () =>
      segs.length === 0
        ? null
        : {
            log,
            segments: toRequestSegments(segs),
            gap_ms: gapMs,
            gap_policy: policy,
            exclude: excl.exclude,
            exclude_prefixes: excl.exclude_prefixes,
          },
    [log, segs, gapMs, policy, excl],
  );
  const key = useMemo(() => JSON.stringify(request), [request]);

  const [est, setEst] = useState<{ key: string; preview: Preview } | null>(null);
  const [exact, setExact] = useState<{ key: string; preview: Preview } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [exactPending, setExactPending] = useState(false);
  const exactAbort = useRef<AbortController | null>(null);

  // instant estimate, debounced a touch so dragging an edge does not fire a request per pixel
  useEffect(() => {
    if (!request) {
      setEst(null);
      setError(null);
      setPending(false);
      return;
    }
    const ac = new AbortController();
    setPending(true);
    const t = setTimeout(() => {
      api
        .preview(request, ac.signal)
        .then((p) => {
          setEst({ key, preview: p });
          setError(null);
          setPending(false);
        })
        .catch((e: Error) => {
          if (e.name === 'AbortError') return;
          setError(e.message);
          setPending(false);
        });
    }, 90);
    return () => {
      clearTimeout(t);
      ac.abort();
    };
  }, [request, key]);

  const runExact = useCallback(() => {
    if (!request) return;
    exactAbort.current?.abort();
    const ac = new AbortController();
    exactAbort.current = ac;
    setExactPending(true);
    api
      .previewExact(request, ac.signal)
      .then((p) => {
        setExact({ key, preview: p });
        setExactPending(false);
      })
      .catch((e: Error) => {
        if (e.name === 'AbortError') return;
        setError(e.message);
        setExactPending(false);
      });
  }, [request, key]);

  // small logs: the exact number arrives on its own shortly after the estimate settles
  useEffect(() => {
    if (!request || !info || info.size > AUTO_EXACT_MAX_BYTES) return;
    const t = setTimeout(runExact, 600);
    return () => {
      clearTimeout(t);
      exactAbort.current?.abort();
      setExactPending(false);
    };
  }, [request, key, info, runExact]);

  const exactHere = exact && exact.key === key ? exact.preview : null;
  const estHere = est && est.key === key ? est.preview : null;
  return {
    preview: exactHere ?? estHere,
    error,
    pending,
    exactPending,
    canComputeExact: !!request && !exactHere && !exactPending,
    computeExact: runExact,
    request,
  };
}
