// Full-page "which log do I want?" browser: every log under the folder with when it was recorded,
// how big it is, whether vision video came with it, and (on request) what is inside -- the event
// and match the driver station recorded, how long the robot was enabled, which cameras reported.
// Opening a log makes it the open log for every page and returns you to the page you came from.
import { useEffect, useMemo, useRef, useState } from 'react';

import type { LogDetails, LogEntry } from '../compare/types';
import { formatAge, formatDuration, formatSize, formatWhen, logTime, parseLogName } from '../lib/logName';
import { navigate } from '../nav/route';
import { filterLogs, sortLogs, type Sort, type SortKey } from './logList';
import { useLogSelection } from './LogSelection';
import { returnView } from './returnView';
import './logs.css';

type Inspect = { state: 'loading' } | { state: 'error'; message: string } | { state: 'ready'; details: LogDetails };

const COLUMNS: { key: SortKey | null; label: string }[] = [
  { key: 'when', label: 'Recorded' },
  { key: 'name', label: 'Log' },
  { key: 'folder', label: 'Folder' },
  { key: 'size', label: 'Size' },
  { key: null, label: 'Vision video' },
  { key: null, label: 'Inside the log' },
  { key: null, label: '' },
];

export function matchTitle(d: LogDetails): string | null {
  const match = d.match_type && d.match_number ? `${d.match_type} ${d.match_number}` : d.match_number ? `Match ${d.match_number}` : d.match_type;
  return [d.event, match].filter(Boolean).join(' · ') || null;
}

function Inside({ inspect, onInspect }: { inspect?: Inspect; onInspect: () => void }) {
  if (!inspect) return <button className="logs-table__btn" onClick={onInspect}>Inspect</button>;
  if (inspect.state === 'loading') return <span className="logs-muted">Reading log…</span>;
  if (inspect.state === 'error') return <span className="warning-text" role="alert">{inspect.message}</span>;
  const d = inspect.details;
  const title = matchTitle(d);
  return <div className="logs-inside">
    {title && <strong>{title}{d.fms ? ' · FMS' : ''}</strong>}
    <span>{formatDuration(d.duration)} long · auto {formatDuration(d.auto_sec)} · teleop {formatDuration(d.teleop_sec)}</span>
    <span className="logs-muted">{d.cameras.length ? d.cameras.join(', ') : 'no cameras in the log'}</span>
  </div>;
}

export function LogBrowserPage() {
  const { root, logs, status, error, selected } = useLogSelection();
  const [sort, setSort] = useState<Sort>({ key: 'when', dir: 'desc' });
  const [query, setQuery] = useState('');
  const [inspected, setInspected] = useState<Record<string, Inspect>>({});
  const [inspectingAll, setInspectingAll] = useState(false);
  const stopAll = useRef(false);

  // Details belong to the folder they were read from.
  useEffect(() => { setInspected({}); }, [root]);

  const details = useMemo(() => Object.fromEntries(Object.entries(inspected)
    .map(([path, i]) => [path, i.state === 'ready' ? i.details : undefined])), [inspected]);
  const rows = useMemo(() => sortLogs(filterLogs(logs, query, details), sort), [logs, query, details, sort]);
  const totalSize = rows.reduce((sum, log) => sum + log.size, 0);

  async function inspect(path: string): Promise<void> {
    setInspected((current) => ({ ...current, [path]: { state: 'loading' } }));
    try {
      const response = await fetch(`/api/log-details?log=${encodeURIComponent(path)}`);
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? `Could not read the log (${response.status}).`);
      setInspected((current) => ({ ...current, [path]: { state: 'ready', details: body } }));
    } catch (e) {
      setInspected((current) => ({ ...current, [path]: { state: 'error', message: e instanceof Error ? e.message : String(e) } }));
    }
  }

  // One at a time: parsing a log takes seconds and the server keeps only a few in memory.
  async function inspectAll(): Promise<void> {
    stopAll.current = false;
    setInspectingAll(true);
    for (const log of rows) {
      if (stopAll.current) break;
      if (!inspected[log.path]) await inspect(log.path);
    }
    setInspectingAll(false);
  }
  useEffect(() => () => { stopAll.current = true; }, []);

  const open = (log: LogEntry) => navigate({ view: returnView(), log: log.path });
  const header = (column: (typeof COLUMNS)[number]) => {
    if (!column.key) return <th key={column.label}>{column.label}</th>;
    const key = column.key;
    const active = sort.key === key;
    return <th key={column.label} aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button className="logs-table__sort" onClick={() => setSort({ key, dir: active && sort.dir === 'desc' ? 'asc' : 'desc' })}>
        {column.label}{active ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : ''}
      </button>
    </th>;
  };

  return <main className="logs-page">
    <h1>Logs</h1>
    <p className="logs-muted">Pick the log every page analyses. Opening one returns you to the page you came from.</p>
    <div className="logs-toolbar">
      <input className="logs-toolbar__search" type="search" placeholder="Filter by name, folder, event, camera…" value={query}
        onChange={(e) => setQuery(e.target.value)} aria-label="Filter logs" />
      <button className="logs-table__btn" onClick={() => inspectingAll ? (stopAll.current = true) : void inspectAll()} disabled={rows.length === 0}>
        {inspectingAll ? 'Stop inspecting' : `Inspect all ${rows.length}`}
      </button>
      <a href="?view=fetch">Fetch a bundle →</a>
    </div>
    {status === 'loading' && <p className="logs-muted">Looking for logs…</p>}
    {status === 'error' && <p role="alert" className="warning-text">{error}</p>}
    {status === 'ready' && logs.length === 0 && <p>No .wpilog files under this folder. Change the folder or fetch a bundle.</p>}
    {logs.length > 0 && <>
      <p className="logs-muted">{rows.length === logs.length ? `${logs.length} logs` : `${rows.length} of ${logs.length} logs`} · {formatSize(totalSize)}.
        Inspect reads a log to show its match, enabled time and cameras; big logs take a few seconds the first time.</p>
      <div className="logs-scroll">
        <table className="logs-table">
          <thead><tr>{COLUMNS.map(header)}</tr></thead>
          <tbody>
            {rows.map((log) => {
              const parsed = parseLogName(log.name);
              const when = logTime(log);
              const isOpen = log.path === selected;
              return <tr key={log.path} className={isOpen ? 'logs-table__row--open' : undefined} onDoubleClick={() => open(log)}>
                <td><div>{formatWhen(when)}</div><div className="logs-muted">{formatAge(when)}</div></td>
                <td><strong>{parsed.tag || log.name}</strong>{isOpen && <span className="logs-badge">open now</span>}<div className="logs-muted logs-table__file">{log.name}</div></td>
                <td className="logs-muted">{log.folder || '(top level)'}</td>
                <td className="logs-table__num">{formatSize(log.size)}</td>
                <td>{log.vision_cameras?.length ? log.vision_cameras.join(', ') : <span className="logs-muted">none</span>}</td>
                <td><Inside inspect={inspected[log.path]} onInspect={() => void inspect(log.path)} /></td>
                <td><button className="logs-table__btn logs-table__btn--primary" onClick={() => open(log)}>Open</button></td>
              </tr>;
            })}
          </tbody>
        </table>
        {rows.length === 0 && <p className="logs-muted">No log matches that filter.</p>}
      </div>
    </>}
  </main>;
}
