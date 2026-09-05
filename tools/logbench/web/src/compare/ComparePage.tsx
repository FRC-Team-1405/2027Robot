// Second top-level view (see App.tsx's ?view=compare switch): pick two logs, pick a
// window in each (a shared DS-mode span, resolved independently per log, or a manual
// per-log time slice), pick which metrics/composites matter, and see a delta/verdict
// table. This is the "did the change I just made actually help" page -- the CLI's
// `logbench compare` and this page hit the exact same /api/compare endpoint, so a result
// here should never disagree with a script's.
import { useEffect, useMemo, useState } from 'react';

import { LogSide } from './LogSide';
import { ResultsTable } from './ResultsTable';
import type {
  CompareResult, LogEntry, ManualWindow, MetricCatalog, Mode,
} from './types';

const MODES: Mode[] = ['whole', 'auto', 'teleop', 'disabled'];

// The "motion autonomous routine check" use case: window to the auto span and look only
// at metrics that stay meaningful while the robot is commanded to move -- motion_score
// and its inputs deliberately exclude stillness/jitter (see core/composites.py), which
// are expected to look bad during motion for reasons that have nothing to do with camera
// health. One click sets both the window and the metric selection, rather than a second
// page duplicating this one's table/verdict logic.
const AUTO_ROUTINE_PRESET_METRICS = [
  'motion_score', 'area_pct', 'ambiguity_pct', 'fps_pct', 'acceptance_pct',
  'latency_pct', 'multitag_pct', 'acceptance_rate', 'fps_mean', 'fps_min',
];

function emptyManual(): ManualWindow {
  return { enabled: false, lo: 0, hi: 0 };
}

export function ComparePage() {
  const [logs, setLogs] = useState<LogEntry[] | null>(null);
  const [catalog, setCatalog] = useState<MetricCatalog | null>(null);
  const [logA, setLogA] = useState<string | null>(null);
  const [logB, setLogB] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>('whole');
  const [manualA, setManualA] = useState<ManualWindow>(emptyManual());
  const [manualB, setManualB] = useState<ManualWindow>(emptyManual());
  const [metricIds, setMetricIds] = useState<Set<string> | null>(null);
  const [result, setResult] = useState<CompareResult | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/logs')
      .then((r) => r.json())
      .then((d) => setLogs(d.logs));
    fetch('/api/metric-catalog')
      .then((r) => r.json())
      .then((d: MetricCatalog) => {
        setCatalog(d);
        setMetricIds(new Set(d.defaults));
      });
  }, []);

  const canCompare = Boolean(logA && logB && metricIds && metricIds.size > 0);

  const runCompare = () => {
    if (!logA || !logB || !metricIds) return;
    setStatus('loading');
    setError(null);
    const params = new URLSearchParams();
    params.set('log_a', logA);
    params.set('log_b', logB);
    params.set('mode', mode);
    if (manualA.enabled) params.set('window_a', `${manualA.lo},${manualA.hi}`);
    if (manualB.enabled) params.set('window_b', `${manualB.lo},${manualB.hi}`);
    for (const id of metricIds) params.append('metric', id);

    fetch(`/api/compare?${params.toString()}`)
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).detail ?? `${r.status}`);
        return r.json() as Promise<CompareResult>;
      })
      .then((data) => {
        setResult(data);
        setStatus('idle');
      })
      .catch((e) => {
        setError(String(e.message ?? e));
        setStatus('error');
      });
  };

  const applyAutoRoutinePreset = () => {
    setMode('auto');
    setManualA(emptyManual());
    setManualB(emptyManual());
    setMetricIds(new Set(AUTO_ROUTINE_PRESET_METRICS));
  };

  const toggleMetric = (id: string) => {
    setMetricIds((current) => {
      const next = new Set(current ?? []);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const metricsByKind = useMemo(() => {
    if (!catalog) return { metric: [], composite: [] };
    return {
      metric: catalog.metrics.filter((m) => m.kind === 'metric'),
      composite: catalog.metrics.filter((m) => m.kind === 'composite'),
    };
  }, [catalog]);

  return (
    <div className="compare-page">
      <div className="compare-page__head">
        <h1 className="compare-page__title">Compare two logs</h1>
        <div className="compare-page__head-links">
          <a href={window.location.pathname}>← Back to replay</a>
          <a href="?view=pit">Pit Check (live) →</a>
        </div>
      </div>

      <div className="compare-sides">
        <LogSide
          label="A"
          logs={logs ?? []}
          logPath={logA}
          onLogChange={setLogA}
          mode={mode}
          manual={manualA}
          onManualChange={setManualA}
        />
        <LogSide
          label="B"
          logs={logs ?? []}
          logPath={logB}
          onLogChange={setLogB}
          mode={mode}
          manual={manualB}
          onManualChange={setManualB}
        />
      </div>

      <div className="compare-presets">
        <button
          className="compare-mode__btn"
          onClick={applyAutoRoutinePreset}
          title="Window to the auto span in each log and select metrics that stay meaningful during commanded motion (excludes stillness/jitter)"
        >
          Autonomous routine preset
        </button>
      </div>

      <div className="compare-mode">
        <span>Window:</span>
        {MODES.map((m) => (
          <button
            key={m}
            className={`compare-mode__btn${mode === m ? ' compare-mode__btn--active' : ''}`}
            onClick={() => setMode(m)}
          >
            {m}
          </button>
        ))}
        <span className="compare-mode__hint">
          applies to whichever side doesn't have a custom time slice
        </span>
      </div>

      {catalog && (
        <details className="compare-metrics">
          <summary>Metrics ({metricIds?.size ?? 0} selected)</summary>
          <div className="compare-metrics__content">
            <div className="compare-metrics__group">
              <strong>Composites</strong>
              {metricsByKind.composite.map((m) => (
                <label key={m.id}>
                  <input type="checkbox" checked={metricIds?.has(m.id) ?? false} onChange={() => toggleMetric(m.id)} />
                  {m.label}
                </label>
              ))}
            </div>
            <div className="compare-metrics__group">
              <strong>Metrics</strong>
              {metricsByKind.metric.map((m) => (
                <label key={m.id}>
                  <input type="checkbox" checked={metricIds?.has(m.id) ?? false} onChange={() => toggleMetric(m.id)} />
                  {m.label}
                </label>
              ))}
            </div>
          </div>
        </details>
      )}

      <button className="compare-run" disabled={!canCompare || status === 'loading'} onClick={runCompare}>
        {status === 'loading' ? 'Comparing…' : 'Compare'}
      </button>

      {status === 'error' && (
        <div className="status status--error">
          <strong>Could not compare these logs.</strong>
          <pre>{error}</pre>
        </div>
      )}

      {result && status !== 'error' && (
        <>
          <div className="compare-window-summary">
            <div>A: {result.a.log} — window [{result.a.window.lo.toFixed(1)}, {result.a.window.hi.toFixed(1)}]s</div>
            <div>B: {result.b.log} — window [{result.b.window.lo.toFixed(1)}, {result.b.window.hi.toFixed(1)}]s</div>
          </div>
          <ResultsTable result={result} />
        </>
      )}
    </div>
  );
}
