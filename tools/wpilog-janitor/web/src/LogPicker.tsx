import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, type LogEntry } from './api';
import { fmtBytes, fmtDate } from './lib/format';

export function LogPicker({ onPick, current }: { onPick: (path: string) => void; current: string | null }) {
  const [logs, setLogs] = useState<LogEntry[] | null>(null);
  const [root, setRoot] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [choosing, setChoosing] = useState(false);

  const load = useCallback(() => {
    api
      .logs()
      .then((r) => {
        setLogs(r.logs);
        setRoot(r.root);
        setError(null);
      })
      .catch((e: Error) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  // The server opens the native folder dialog (a browser can't hand back a folder's path) and
  // switches its log root until it restarts; then this list is re-fetched.
  const changeFolder = async () => {
    setChoosing(true);
    setError(null);
    try {
      const r = await api.pickLogRoot();
      if (!r.cancelled) {
        setQuery('');
        load();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setChoosing(false);
    }
  };

  const shown = useMemo(() => {
    const words = query.toLowerCase().split(/\s+/).filter(Boolean);
    return (logs ?? []).filter((l) => words.every((w) => l.path.toLowerCase().includes(w)));
  }, [logs, query]);

  return (
    <div className="page">
      <section className="card">
        <h1>Choose a log</h1>
        <p className="muted small root-line">
          {root && (
            <span>
              Looking in <code>{root}</code>
            </span>
          )}
          <button type="button" className="btn small" onClick={changeFolder} disabled={choosing}>
            {choosing ? 'Choose a folder in the dialog…' : 'Change folder…'}
          </button>
        </p>
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {logs === null && !error && <p className="status">Looking for logs…</p>}
        {logs && logs.length === 0 && <p className="empty">No .wpilog files found under that folder. Pick another with <em>Change folder…</em>.</p>}
        {logs && logs.length > 0 && (
          <>
            <input
              className="search"
              type="search"
              placeholder={`Filter ${logs.length} logs — e.g. "9-15 recorder"`}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Filter logs"
              autoFocus
            />
            <div className="table-wrap tall">
              <table className="logs">
                <thead>
                  <tr>
                    <th>Log</th>
                    <th className="r">Size</th>
                    <th>Modified</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((l) => {
                    const dir = l.path.includes('/') ? l.path.slice(0, l.path.lastIndexOf('/') + 1) : '';
                    return (
                      <tr key={l.path} className={l.path === current ? 'sel' : ''}>
                        <td>
                          <button type="button" className="link" onClick={() => onPick(l.path)}>
                            <span className="muted">{dir}</span>
                            {l.name}
                          </button>
                        </td>
                        <td className="r">{fmtBytes(l.size)}</td>
                        <td className="muted">{fmtDate(l.mtime)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {shown.length === 0 && <p className="empty">No log matches “{query}”.</p>}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
