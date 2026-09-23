// Second top-level view (see App.tsx's ?view=compare switch): pick two logs, pick a
// window in each (a shared DS-mode span, resolved independently per log, or a manual
// per-log time slice), pick which metrics/composites matter, and see a delta/verdict
// table. This is the "did the change I just made actually help" page -- the CLI's
// `logbench compare` and this page hit the exact same /api/compare endpoint, so a result
// here should never disagree with a script's.
import { useEffect, useMemo, useState } from 'react';

import { CategoryPanels } from './CategoryPanels';
import { LogSide } from './LogSide';
import { LogRootButton } from '../loader/LogRootButton';
import type {
  CategoryId, CompareResult, LogEntry, ManualWindow, MetricCatalog, MetricDescriptor, Mode,
} from './types';

const MODES: Mode[] = ['whole', 'auto', 'teleop', 'disabled'];

// The order metric groups are listed in the picker, and their headings. The first three are the
// question categories from docs/adr/0001 (their wording comes from the server's catalog, so the
// page never restates it); 'overall' and 'legacy' only place the composites.
const PICKER_ORDER: CategoryId[] = ['availability', 'quality', 'context', 'overall', 'legacy'];
const PICKER_HEADING: Record<string, string> = {
  overall: 'Overall (optional)',
  legacy: 'Legacy composites',
};

function emptyManual(): ManualWindow {
  return { enabled: false, lo: 0, hi: 0 };
}

export function ComparePage() {
  const [logs, setLogs] = useState<LogEntry[] | null>(null);
  const [root, setRoot] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<MetricCatalog | null>(null);
  const [logA, setLogA] = useState<string | null>(null);
  const [logB, setLogB] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>('whole');
  const [manualA, setManualA] = useState<ManualWindow>(emptyManual());
  const [manualB, setManualB] = useState<ManualWindow>(emptyManual());
  const [metricIds, setMetricIds] = useState<Set<string> | null>(null);
  const [result, setResult] = useState<CompareResult | null>(null);
  // The query the shown result was computed from. Export links use this, not the live form
  // state, so a download always matches the table on screen even if the selectors changed
  // since the last Compare click.
  const [resultQuery, setResultQuery] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'loading' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);

  const loadLogs = () => {
    fetch('/api/logs')
      .then((r) => r.json())
      .then((d) => {
        setLogs(d.logs);
        setRoot(d.root);
      });
  };

  // A new folder means the old selections (and any result computed from them) are gone.
  const changeRoot = () => {
    setLogA(null);
    setLogB(null);
    setResult(null);
    setResultQuery(null);
    loadLogs();
  };

  useEffect(() => {
    loadLogs();
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

    const query = params.toString();
    fetch(`/api/compare?${query}`)
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json()).detail ?? `${r.status}`);
        return r.json() as Promise<CompareResult>;
      })
      .then((data) => {
        setResult(data);
        setResultQuery(query);
        setStatus('idle');
      })
      .catch((e) => {
        setError(String(e.message ?? e));
        setStatus('error');
      });
  };

  // The "autonomous routine check" use case: window to the auto span and pick the standard metric
  // set. That set (the server's defaults) scores availability and quality separately and shows
  // context beside them, and leaves out jitter and the legacy composites: jitter rises with motion
  // for reasons unrelated to camera quality. One click sets both the window and the metric
  // selection, rather than a second page duplicating this one's table/verdict logic.
  const applyAutoRoutinePreset = () => {
    setMode('auto');
    setManualA(emptyManual());
    setManualB(emptyManual());
    if (catalog) setMetricIds(new Set(catalog.defaults));
  };

  const toggleMetric = (id: string) => {
    setMetricIds((current) => {
      const next = new Set(current ?? []);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Metrics grouped by category, in picker order, each group with the heading the server gave
  // its category (or the fixed heading for overall/legacy).
  const pickerGroups = useMemo(() => {
    if (!catalog) return [];
    return PICKER_ORDER.map((id) => ({
      id,
      heading:
        PICKER_HEADING[id] ?? catalog.categories.find((c) => c.id === id)?.label ?? id,
      note: id === 'context' ? 'not scored' : '',
      members: catalog.metrics.filter((m: MetricDescriptor) => m.category === id),
    })).filter((g) => g.members.length > 0);
  }, [catalog]);

  return (
    <div className="compare-page">
      <div className="compare-page__head">
        <h1 className="compare-page__title">Compare two logs</h1>
      </div>
      <LogRootButton root={root} onChanged={changeRoot} />

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
          title="Window to the auto span in each log and select the standard metric set: availability and quality scored separately, context shown beside them (jitter and the legacy composites left out)"
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
            {pickerGroups.map((g) => (
              <div className={`compare-metrics__group compare-metrics__group--${g.id}`} key={g.id}>
                <strong>
                  {g.heading}
                  {g.note && <span className="cat-badge">{g.note}</span>}
                </strong>
                {g.members.map((m) => (
                  <label key={m.id} title={m.description}>
                    <input type="checkbox" checked={metricIds?.has(m.id) ?? false} onChange={() => toggleMetric(m.id)} />
                    {m.label}
                  </label>
                ))}
              </div>
            ))}
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

      {result && catalog && status !== 'error' && (
        <>
          <div className="compare-window-summary">
            <div>A: {result.a.log} — window [{result.a.window.lo.toFixed(1)}, {result.a.window.hi.toFixed(1)}]s</div>
            <div>B: {result.b.log} — window [{result.b.window.lo.toFixed(1)}, {result.b.window.hi.toFixed(1)}]s</div>
          </div>
          <div className="compare-export">
            <span>Export this comparison:</span>
            <a className="compare-export__link" href={`/api/compare/export?${resultQuery}&format=html`}>
              HTML (for people)
            </a>
            <a
              className="compare-export__link"
              href={`/api/compare/export?${resultQuery}&format=json`}
              title="One self-describing JSON document: file names, windows, metric definitions, per-camera values, deltas, verdicts and a reading guide"
            >
              JSON (for LLMs)
            </a>
          </div>
          <CategoryPanels result={result} catalog={catalog} />
        </>
      )}
    </div>
  );
}
