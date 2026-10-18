// Health Check: one page that answers "is everything on the robot OK?" for the robot in the pits
// (live over NetworkTables) and for a finished match (a .wpilog). It replaced the Pit Check page,
// which only looked at AprilTag detection.
//
// What is checked, and the limits, comes from server/health_checks.toml -- this page just shows
// the report: every section, group and row with a status icon, the value, the rule that was applied
// in words, and any detail. Red/amber rows open by default; everything fine stays collapsed so the
// page can be scanned for icons that are not green.
import { useEffect, useMemo, useState } from 'react';

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
  const params = new URLSearchParams(window.location.search);
  const [mode, setMode] = useState<Mode>(params.get('log') ? 'log' : 'live');
  const [problemsOnly, setProblemsOnly] = useState(false);
  const [showNa, setShowNa] = useState(false);

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
    fetch('/api/logs')
      .then((r) => r.json())
      .then((d: { logs: LogEntry[] }) => {
        const sorted = [...d.logs].sort((a, b) => b.mtime - a.mtime);
        setLogs(sorted);
        setLogPath((current) => current ?? sorted[0]?.path ?? null);
      })
      .catch(() => setLogs([]));
  }, []);

  const report = mode === 'live' ? live.report : logReport.report;
  const [bands, setBands] = useState<SeverityBand[]>([]);
  useEffect(() => {
    fetch('/api/metric-catalog')
      .then((r) => r.json())
      .then((d) => setBands(d.severity ?? []))
      .catch(() => setBands([]));
  }, []);

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
          {live.stale && <span className="health__chip health__chip--error">lost contact with the server</span>}
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

      {mode === 'live' && pit.status === 'error' && (
        <div className="status status--error">
          <strong>Could not connect.</strong>
          <pre>{pit.error}</pre>
        </div>
      )}
      {mode === 'log' && logReport.error && (
        <div className="status status--error">
          <strong>Could not check that log.</strong>
          <pre>{logReport.error}</pre>
        </div>
      )}

      {report && report.config_errors && report.config_errors.length > 0 && (
        <div className="health__config-errors" role="alert">
          <strong>health_checks.toml has {report.config_errors.length === 1 ? 'a problem' : 'problems'}</strong>
          <ul>
            {report.config_errors.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
          <span>The other checks still ran.</span>
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
          <Verdict report={report} problemsOnly={problemsOnly} onToggleProblems={setProblemsOnly} showNa={showNa} onToggleNa={setShowNa} />
          <Legend showNa={showNa} />
          <div className="health__sections">
            {shownSections.map((section) => (
              <SectionCard key={section.id} section={section} />
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
          {pit.snapshot && (Math.abs(pit.snapshot.lin_speed) > 0.06 || Math.abs(pit.snapshot.ang_speed) > 0.06) && (
            <p className="health__warn">The robot is moving. Hold it still for a clean reading.</p>
          )}
          <div className="pit-cards">
            {cameras.map(([name, reading]) => (
              <CameraCard key={name} name={name} reading={reading} bands={bands} />
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
