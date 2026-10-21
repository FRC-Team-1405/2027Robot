// Health Check: one page that answers "is everything on the robot OK?" for the robot in the pits
// (live over NetworkTables) and for a finished match (a .wpilog). It replaced the Pit Check page,
// which only looked at AprilTag detection.
//
// What is checked, and the limits, comes from server/health_checks.toml -- this page just shows
// the report: every section, group and row with a status icon, the value, the rule that was applied
// in words, and any detail. Red/amber rows open by default; everything fine stays collapsed so the
// page can be scanned for icons that are not green.
import { useCallback, useEffect, useMemo, useState } from 'react';

import { errorMessage, requestJson } from '../lib/request';
import { HealthBoundary } from './HealthBoundary';
import { CameraCard } from '../pit/CameraCard';
import { usePitConnection } from '../pit/usePitConnection';
import type { SeverityBand } from '../lib/severity';
import {
  STATUS_ICON,
  STATUS_WORD,
  hideNotApplicable,
  latchNote,
  modesLine,
  onlyProblems,
  startsOpen,
  summarize,
  toggleKey,
  verdictView,
} from './healthView';
import type { CheckRow, Counts, HealthReport, Section, Status } from './types';
import { useLiveReport, useLogReport } from './useHealthReport';
import './health.css';

const DEFAULT_ROOT_TABLE = 'AdvantageKit';

interface LogEntry {
  path: string;
  name: string;
  mtime: number;
}

type Mode = 'live' | 'log';

export function HealthCheckPage() {
  return <HealthBoundary label="Health Check"><HealthCheckContent /></HealthBoundary>;
}

function HealthCheckContent() {
  const params = new URLSearchParams(window.location.search);
  const [mode, setMode] = useState<Mode>(params.get('log') ? 'log' : 'live');
  const [problemsOnly, setProblemsOnly] = useState(false);
  const [showNa, setShowNa] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [auxRetry, setAuxRetry] = useState(0);
  const [renderErrors, setRenderErrors] = useState<string[]>([]);
  const notify = useCallback((message: string) => {
    setRenderErrors((previous) => previous.includes(message) ? previous : [...previous.slice(-4), message]);
  }, []);
  useEffect(() => {
    const onError = (event: ErrorEvent) => notify(event.message || 'Unexpected page error.');
    const onRejection = (event: PromiseRejectionEvent) => notify(errorMessage(event.reason));
    window.addEventListener('error', onError);
    window.addEventListener('unhandledrejection', onRejection);
    return () => {
      window.removeEventListener('error', onError);
      window.removeEventListener('unhandledrejection', onRejection);
    };
  }, [notify]);

  // Live robot
  const pit = usePitConnection();
  const [server, setServer] = useState('');
  const [rootTable, setRootTable] = useState(DEFAULT_ROOT_TABLE);
  const live = useLiveReport(mode === 'live' && pit.status === 'connected');

  // Finished log
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logPath, setLogPath] = useState<string | null>(params.get('log'));
  const logReport = useLogReport(mode === 'log' ? logPath : null);

  useEffect(() => {
    const controller = new AbortController();
    setListError(null);
    void requestJson('/api/logs', { signal: controller.signal }).then((body) => {
      if (!body || typeof body !== 'object' || !('logs' in body) || !Array.isArray(body.logs)) throw new Error('Invalid log list.');
      const entries = body.logs.filter((item): item is LogEntry => item && typeof item.path === 'string' && typeof item.mtime === 'number' && Number.isFinite(item.mtime));
      if (controller.signal.aborted) return;
      if (entries.length !== body.logs.length) setListError('Some log-list entries were invalid and were omitted.');
      const sorted = [...entries].sort((a, b) => b.mtime - a.mtime);
      setLogs(sorted); setLogPath((current) => current ?? sorted[0]?.path ?? null);
    }).catch((error) => { if (!controller.signal.aborted) setListError(errorMessage(error)); });
    return () => controller.abort();
  }, [auxRetry]);

  const report = mode === 'live' ? live.report : logReport.report;
  const [bands, setBands] = useState<SeverityBand[]>([]);
  useEffect(() => {
    const controller = new AbortController();
    setCatalogError(null);
    void requestJson('/api/metric-catalog', { signal: controller.signal }).then((body) => {
      if (!body || typeof body !== 'object' || !('severity' in body) || !Array.isArray(body.severity)) throw new Error('Invalid score color settings.');
      const valid = body.severity.filter((band): band is SeverityBand => band && typeof band.min === 'number' && Number.isFinite(band.min) && typeof band.color === 'string');
      if (controller.signal.aborted) return;
      setBands(valid);
      if (valid.length !== body.severity.length) setCatalogError('Some score color settings were invalid.');
    }).catch((error) => { if (!controller.signal.aborted) setCatalogError(errorMessage(error)); });
    return () => controller.abort();
  }, [auxRetry]);

  const notices = [...new Set([
    ...(mode === 'live' ? [
      pit.error && `Live camera connection: ${pit.error}`,
      live.error && `Live health report: ${live.error}`,
      live.resetError,
      ...pit.warnings, ...live.warnings,
      (pit.stale || live.stale) && 'Live updates are stale. Any last good readings remain visible; automatic retries continue.',
      pit.stale && pit.lastUpdated && `Last camera snapshot received at ${new Date(pit.lastUpdated).toLocaleTimeString()}.`,
      live.stale && live.lastUpdated && `Last health report received at ${new Date(live.lastUpdated).toLocaleTimeString()}.`,
    ] : [logReport.error && `Log health report: ${logReport.error}${report ? ' Showing the last successful report for this log.' : ''}`, ...logReport.warnings]),
    listError && `Log list: ${listError}`, catalogError && `Score colors: ${catalogError}`,
    ...(report?.config_errors ?? []), ...renderErrors,
  ].filter((message): message is string => typeof message === 'string' && message.length > 0))];

  const cameras = pit.snapshot ? Object.entries(pit.snapshot.cameras) : [];
  const shownSections = useMemo(() => {
    if (!report) return [];
    const base = problemsOnly ? onlyProblems(report.sections) : report.sections;
    return showNa ? base : hideNotApplicable(base);
  }, [report, problemsOnly, showNa]);

  return (
    <div className="health">
      <div className="health__head">
        <h1 className="health__title">Health Check</h1>
        <div className="health__modes" role="tablist" aria-label="What to check">
          <button
            role="tab"
            aria-selected={mode === 'live'}
            className={`health__mode${mode === 'live' ? ' health__mode--on' : ''}`}
            onClick={() => setMode('live')}
          >
            Live robot
          </button>
          <button
            role="tab"
            aria-selected={mode === 'log'}
            className={`health__mode${mode === 'log' ? ' health__mode--on' : ''}`}
            onClick={() => setMode('log')}
          >
            Match log
          </button>
        </div>
      </div>
      {notices.length > 0 && <div className="health__notification" role="alert">
        <strong>Health Check needs attention</strong>
        <ul>{notices.map((message) => <li key={message}>{message}</li>)}</ul>
        {(listError || catalogError) && <button className="health__btn" onClick={() => setAuxRetry((v) => v + 1)}>Retry page data</button>}
        {renderErrors.length > 0 && <button className="health__btn" onClick={() => setRenderErrors([])}>Dismiss page errors</button>}
      </div>}
      <p className="health__hint">
        {mode === 'live'
          ? 'Connect to the robot in the pits and scan for anything that is not green. Enable and disable the robot to see how it behaves under load: a row that goes red keeps a note even after it recovers, until you press Reset.'
          : 'Run the same checks over a finished match and see what stands out. Rows show the worst reading in the log, and when it happened.'}
      </p>

      {mode === 'live' ? (
        <div className="health__connect">
          <input
            className="health__input"
            placeholder="Team number or IP address"
            value={server}
            onChange={(e) => setServer(e.target.value)}
            disabled={pit.status === 'connected' || pit.status === 'connecting'}
          />
          <input
            className="health__input"
            placeholder="NT root table"
            value={rootTable}
            onChange={(e) => setRootTable(e.target.value)}
            disabled={pit.status === 'connected' || pit.status === 'connecting'}
          />
          {pit.status === 'connected' ? (
            <>
              <button className="health__btn" onClick={pit.disconnect}>
                Disconnect
              </button>
              <button className="health__btn" onClick={() => void live.reset()} title="Forget what was worst so far">
                Reset
              </button>
            </>
          ) : (
            <button
              className="health__btn health__btn--primary"
              disabled={!server || pit.status === 'connecting'}
              onClick={() => pit.connect(server, rootTable)}
            >
              {pit.status === 'connecting' ? 'Connecting…' : 'Connect'}
            </button>
          )}
          <span className={`health__chip health__chip--${pit.status}`}>
            {pit.status === 'connected' &&
              (pit.snapshot?.nt_connected
                ? `connected${live.report?.meta?.robot ? ` · robot ${live.report.meta.robot}` : ''}`
                : 'client started, waiting for the robot…')}
            {pit.status === 'connecting' && 'connecting…'}
            {pit.status === 'disconnected' && 'not connected'}
            {pit.status === 'error' && 'error'}
          </span>
          {live.stale && <span className="health__chip health__chip--error">health updates unavailable</span>}
        </div>
      ) : (
        <div className="health__connect">
          <select
            className="health__input health__input--wide"
            value={logPath ?? ''}
            onChange={(e) => setLogPath(e.target.value)}
            aria-label="Log to check"
          >
            {logs.length === 0 && <option value="">No logs in the log folder</option>}
            {logs.map((l) => (
              <option key={l.path} value={l.path}>
                {l.path}
              </option>
            ))}
          </select>
          <button className="health__btn" onClick={() => void logReport.reload()} disabled={!logPath || logReport.loading}>
            {logReport.loading ? 'Checking…' : 'Check again'}
          </button>
          {logPath && (
            <a className="health__link" href={`?log=${encodeURIComponent(logPath)}`}>
              Open in Vision Logs
            </a>
          )}
        </div>
      )}

      {mode === 'live' && pit.status !== 'connected' && !report && (
        <div className="health__empty">Connect to the robot to see its health.</div>
      )}
      {mode === 'log' && !report && !logReport.error && logReport.loading && (
        <div className="health__empty">Reading the log and running the checks…</div>
      )}

      {report && report.sections.length > 0 && (
        <>
          <HealthBoundary label="Health summary" resetKey={report} onError={notify}><Verdict report={report} problemsOnly={problemsOnly} onToggleProblems={setProblemsOnly} showNa={showNa} onToggleNa={setShowNa} /></HealthBoundary>
          <Legend showNa={showNa} />
          <div className="health__sections">
            {shownSections.map((section) => (
              <HealthBoundary key={section.id} label={section.label || 'Health section'} resetKey={section} onError={notify}><SectionCard section={section} /></HealthBoundary>
            ))}
            {problemsOnly && shownSections.length === 0 && (
              <div className="health__empty">Nothing to show: no warnings or problems.</div>
            )}
          </div>
        </>
      )}

      {mode === 'live' && cameras.length > 0 && (
        <details className="health__detail">
          <summary>Tag detection detail (hold the robot still with a tag in view)</summary>
          <p className="health__hint">
            The same VisionHealth.java score the robot already computes, broken into its eight factors. A calibration
            diagnostic, not a match-accuracy score.
          </p>
          {pit.snapshot && (Math.abs(pit.snapshot.lin_speed ?? 0) > 0.06 || Math.abs(pit.snapshot.ang_speed ?? 0) > 0.06) && (
            <p className="health__warn">The robot is moving. Hold it still for a clean reading.</p>
          )}
          <div className="pit-cards">
            {cameras.map(([name, reading]) => (
              <HealthBoundary key={name} label={`Camera ${name}`} resetKey={reading} onError={notify}><CameraCard name={name} reading={reading} bands={bands} /></HealthBoundary>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

function Verdict({
  report,
  problemsOnly,
  onToggleProblems,
  showNa,
  onToggleNa,
}: {
  report: HealthReport;
  problemsOnly: boolean;
  onToggleProblems: (v: boolean) => void;
  showNa: boolean;
  onToggleNa: (v: boolean) => void;
}) {
  const view = verdictView(report.verdict, report.kind);
  const modes = report.kind === 'log' ? modesLine(report) : '';
  return (
    <div className={`health__verdict health__verdict--${view.tone}`}>
      <span className="health__verdict-icon" aria-hidden>
        {STATUS_ICON[view.tone as Status]}
      </span>
      <div className="health__verdict-text">
        <strong>{view.headline}</strong>
        <span>{summarize(report.counts)}</span>
        <span className="health__verdict-hint">
          {view.hint}
          {modes ? ` (${modes})` : ''}
        </span>
      </div>
      <div className="health__toggles">
        <label className="health__toggle">
          <input type="checkbox" checked={problemsOnly} onChange={(e) => onToggleProblems(e.target.checked)} /> Problems only
        </label>
        <label className="health__toggle" title="Checks that only make sense live (or only on a log) are hidden by default">
          <input type="checkbox" checked={showNa} onChange={(e) => onToggleNa(e.target.checked)} /> Show not applicable
        </label>
      </div>
    </div>
  );
}

function Legend({ showNa }: { showNa: boolean }) {
  const items: Status[] = showNa ? ['ok', 'warn', 'fail', 'nodata', 'na'] : ['ok', 'warn', 'fail', 'nodata'];
  return (
    <div className="health__legend" aria-label="Legend">
      {items.map((s) => (
        <span key={s} className="health__legend-item">
          <StatusIcon status={s} /> {STATUS_WORD[s]}
        </span>
      ))}
    </div>
  );
}

function StatusIcon({ status }: { status: Status }) {
  return (
    <span className={`health__icon health__icon--${status}`} role="img" aria-label={STATUS_WORD[status]} title={STATUS_WORD[status]}>
      {STATUS_ICON[status]}
    </span>
  );
}

function CountsLine({ counts }: { counts: Counts }) {
  return <span className="health__counts">{summarize(counts)}</span>;
}

function useOpenState() {
  const [overrides, setOverrides] = useState<Record<string, boolean>>({});
  const isOpen = (key: string, status: Status) => overrides[key] ?? startsOpen(status);
  const toggle = (key: string, status: Status) => setOverrides((o) => ({ ...o, [key]: !(o[key] ?? startsOpen(status)) }));
  return { isOpen, toggle };
}

function SectionCard({ section }: { section: Section }) {
  const { isOpen, toggle } = useOpenState();
  const [sectionOverride, setSectionOverride] = useState<boolean | null>(null);
  // Sections open when something needs a look (or there is no data, which the page should say);
  // a section that is all green stays collapsed to its one-line summary.
  const sectionOpen = sectionOverride ?? (startsOpen(section.status) || section.status === 'nodata');

  return (
    <section className={`health__section health__section--${section.status}`}>
      <button
        className="health__section-head"
        aria-expanded={sectionOpen}
        onClick={() => setSectionOverride(!sectionOpen)}
      >
        <StatusIcon status={section.status} />
        <h2>{section.label}</h2>
        <CountsLine counts={section.counts} />
        <span className="health__chevron" aria-hidden>
          {sectionOpen ? '▾' : '▸'}
        </span>
      </button>
      {sectionOpen && (
        <div className="health__groups">
          {section.groups.map((group) => {
            const key = toggleKey(section.id, group.label);
            const groupOpen = isOpen(key, group.status);
            return (
              <div key={key} className={`health__group health__group--${group.status}`}>
                {group.label && (
                  <button className="health__group-head" aria-expanded={groupOpen} onClick={() => toggle(key, group.status)}>
                    <StatusIcon status={group.status} />
                    <h3>{group.label}</h3>
                    <CountsLine counts={group.counts} />
                    <span className="health__chevron" aria-hidden>
                      {groupOpen ? '▾' : '▸'}
                    </span>
                  </button>
                )}
                {(groupOpen || !group.label) &&
                  group.subjects.map((subject) => (
                    <div key={subject.label} className="health__subject">
                      {subject.label && (
                        <div className="health__subject-head">
                          <StatusIcon status={subject.status} />
                          <h4>{subject.label}</h4>
                        </div>
                      )}
                      {subject.checks.map((check) => (
                        <Row key={check.id + check.key} check={check} />
                      ))}
                    </div>
                  ))}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function Row({ check }: { check: CheckRow }) {
  const note = latchNote(check);
  return (
    <div className={`health__row health__row--${check.status}`} title={check.help || undefined}>
      <StatusIcon status={check.status} />
      <span className="health__label">{check.label}</span>
      <span className="health__value">{check.display || (check.status === 'na' ? 'n/a' : '')}</span>
      <span className="health__rule">{check.rule}</span>
      {(check.detail || note) && (
        <span className="health__row-detail">
          {check.detail}
          {check.detail && note ? ' · ' : ''}
          {note && <em className="health__latched">{note}</em>}
        </span>
      )}
    </div>
  );
}
