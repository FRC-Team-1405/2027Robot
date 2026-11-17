// The one place that knows which log is open. Every page reads the selection from here instead
// of keeping its own folder/log dropdown, so choosing a log once carries across all the tabs.
//
// The selection itself lives in the URL (?log=, see nav/route.ts) so it survives refreshes and can be
// shared; the last choice is also remembered in localStorage so a bare launch reopens it.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import type { LogEntry } from '../compare/types';
import { navigate, useRoute } from '../nav/route';

const STORAGE_KEY = 'logbench.log';

function remembered(): string | null {
  try { return window.localStorage.getItem(STORAGE_KEY); } catch { return null; }
}
function remember(path: string | null): void {
  try {
    if (path) window.localStorage.setItem(STORAGE_KEY, path);
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch { /* blocked storage: the URL still carries the selection */ }
}

export interface LogSelection {
  root: string | null;
  logs: LogEntry[];
  status: 'loading' | 'ready' | 'error';
  error: string | null;
  /** Path of the open log, relative to the log folder; null when none is open. */
  selected: string | null;
  selectedEntry: LogEntry | null;
  /** True when a log is open but the current folder does not contain it. */
  missing: boolean;
  /** Bumps whenever the folder changes, so pages can drop anything computed from the old one. */
  folderVersion: number;
  select: (path: string | null) => void;
  refresh: () => Promise<void>;
  folderChanged: () => void;
}

const Context = createContext<LogSelection | null>(null);

export function LogSelectionProvider({ children }: { children: ReactNode }) {
  const route = useRoute();
  const [root, setRoot] = useState<string | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [status, setStatus] = useState<LogSelection['status']>('loading');
  const [error, setError] = useState<string | null>(null);
  const [folderVersion, setFolderVersion] = useState(0);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch('/api/logs');
      if (!response.ok) throw new Error(`Could not list logs (${response.status}).`);
      const body = await response.json();
      setLogs(body.logs); setRoot(body.root); setError(null); setStatus('ready');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e)); setStatus('error');
    }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);

  const selected = route.log;
  // A bare launch (no ?log=) reopens the last log, if this folder still has it.
  useEffect(() => {
    if (status !== 'ready' || selected) return;
    const last = remembered();
    if (last && logs.some((l) => l.path === last)) navigate({ log: last }, { replace: true });
  }, [status, selected, logs]);
  useEffect(() => { if (selected) remember(selected); }, [selected]);
  // A log fetched since the list was loaded (Fetch Bundle's "Open log") is not in it yet: re-read the folder once.
  const refreshedFor = useRef<string | null>(null);
  useEffect(() => {
    if (status !== 'ready' || !selected || logs.some((l) => l.path === selected) || refreshedFor.current === selected) return;
    refreshedFor.current = selected;
    void refresh();
  }, [status, selected, logs, refresh]);

  const select = useCallback((path: string | null) => {
    if (!path) remember(null); // closing the log must not let a bare launch quietly reopen it
    navigate({ log: path });
  }, []);
  const folderChanged = useCallback(() => {
    remember(null);
    navigate({ log: null }, { replace: true });
    setFolderVersion((v) => v + 1);
    void refresh();
  }, [refresh]);

  const value = useMemo<LogSelection>(() => {
    const selectedEntry = logs.find((l) => l.path === selected) ?? null;
    return {
      root, logs, status, error, selected, selectedEntry, folderVersion, select, refresh, folderChanged,
      missing: status === 'ready' && selected != null && !selectedEntry,
    };
  }, [root, logs, status, error, selected, folderVersion, select, refresh, folderChanged]);

  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useLogSelection(): LogSelection {
  const value = useContext(Context);
  if (!value) throw new Error('useLogSelection must be used inside <LogSelectionProvider>.');
  return value;
}
