import { useEffect, useMemo, useState } from 'react';
import { fmtBytes, fmtDate, fmtDuration } from '../lib/format';
import { fitToDuration, toggleModes, type Seg } from '../lib/segments';
import { exclusionsKey, loadJson, NO_EXCLUSIONS, planKey, saveJson, type Exclusions, type SavedPlan } from '../lib/storage';
import { ExportPanel } from './ExportPanel';
import { GapControls } from './GapControls';
import { usePreview, useLogInfo } from './hooks';
import { SavingsPanel } from './SavingsPanel';
import { SegmentTable } from './SegmentTable';
import { Timeline } from './Timeline';

export function TrimPage({ log, onChangeLog }: { log: string; onChangeLog: () => void }) {
  const { info, error, loading } = useLogInfo(log);
  const [segs, setSegs] = useState<Seg[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [gapMs, setGapMs] = useState(200);
  const [policy, setPolicy] = useState<'compact' | 'preserve'>('preserve');
  const [restoredFor, setRestoredFor] = useState<string | null>(null);

  // exclusions are chosen on the Content page; here they only feed the savings numbers
  const excl = useMemo<Exclusions>(() => loadJson(exclusionsKey(log), NO_EXCLUSIONS), [log]);

  // a plan belongs to one log: restore it once the log is indexed, and never write one log's plan under another's key
  useEffect(() => {
    setRestoredFor(null);
    setSegs([]);
    setSelectedId(null);
  }, [log]);
  useEffect(() => {
    if (!info || info.log !== log || restoredFor === log) return;
    const saved = loadJson<SavedPlan | null>(planKey(log), null);
    if (saved) {
      setSegs(fitToDuration(saved.segs ?? [], info.duration_s));
      setGapMs(saved.gapMs ?? 200);
      setPolicy(saved.timing === 'compact' ? 'compact' : 'preserve');
    } else {
      setGapMs(200);
      setPolicy('preserve');
    }
    setRestoredFor(log);
  }, [info, log, restoredFor]);
  useEffect(() => {
    if (restoredFor === log) saveJson(planKey(log), { segs, gapMs, timing: policy } satisfies SavedPlan);
  }, [segs, gapMs, policy, log, restoredFor]);

  const previewState = usePreview(log, restoredFor === log ? info : null, segs, gapMs, policy, excl);

  if (loading) {
    return (
      <div className="page">
        <p className="status" role="status">
          Reading <strong>{log}</strong>… the first open of a large log can take 15 s or more; after that it is instant.
        </p>
      </div>
    );
  }
  if (error || !info) {
    return (
      <div className="page">
        <p className="error" role="alert">
          {error ?? 'Could not load this log.'}
        </p>
        <button type="button" className="btn" onClick={onChangeLog}>
          Choose another log
        </button>
      </div>
    );
  }

  const modes = ['auto', 'teleop', 'disabled'] as const;
  const spans = info.spans;

  return (
    <div className="page">
      <section className="card log-head">
        <div className="title-row">
          <div>
            <h1 title={log}>{info.name}</h1>
            <p className="muted small">{log !== info.name ? log : `Modified ${fmtDate(info.mtime)}`}</p>
          </div>
          <button type="button" className="btn" onClick={onChangeLog}>
            Change log
          </button>
        </div>
        <dl className="facts">
          <div>
            <dt>Size</dt>
            <dd>{fmtBytes(info.size)}</dd>
          </div>
          <div>
            <dt>Duration</dt>
            <dd>{fmtDuration(info.duration_s)}</dd>
          </div>
          <div>
            <dt>Entries</dt>
            <dd>{info.n_entries.toLocaleString()}</dd>
          </div>
          <div>
            <dt>Records</dt>
            <dd>{info.n_records.toLocaleString()}</dd>
          </div>
          <div>
            <dt>Cycles</dt>
            <dd>
              {info.n_cycles.toLocaleString()} <span className="muted">@ {info.cycle_period_ms.toFixed(1)} ms</span>
            </dd>
          </div>
        </dl>
        {info.warnings.map((w) => (
          <p key={w} className="warn small" role="status">
            {w}
          </p>
        ))}
      </section>

      <section className="card">
        <div className="section-head">
          <h2>What to keep</h2>
          <div className="quick">
            {modes
              .filter((m) => spans.some((s) => s.mode === m))
              .map((m) => (
                <button key={m} type="button" className={`btn small mode-btn mode-${m}`} onClick={() => setSegs((cur) => toggleModes(cur, spans, [m]))}>
                  {m} ×{spans.filter((s) => s.mode === m).length}
                </button>
              ))}
            <button type="button" className="btn small" onClick={() => setSegs([])} disabled={segs.length === 0}>
              Clear
            </button>
          </div>
        </div>
        <Timeline
          duration={info.duration_s}
          spans={spans}
          hist={info.byte_hist}
          segments={segs}
          selectedId={selectedId}
          onSegments={setSegs}
          onSelect={setSelectedId}
        />
        <SegmentTable
          segments={segs}
          duration={info.duration_s}
          preview={previewState.preview}
          selectedId={selectedId}
          cyclePeriodMs={info.cycle_period_ms}
          onSegments={setSegs}
          onSelect={setSelectedId}
        />
      </section>

      <div className="two-col">
        <div className="col">
          <SavingsPanel state={previewState} hasSegments={segs.length > 0} sourceBytes={info.size} />
        </div>
        <div className="col">
          <section className="card">
            <h2>Timing</h2>
            <GapControls gapMs={gapMs} policy={policy} cyclePeriodMs={info.cycle_period_ms} onGap={setGapMs} onPolicy={setPolicy} />
          </section>
          <ExportPanel log={log} request={previewState.request} />
        </div>
      </div>
    </div>
  );
}
