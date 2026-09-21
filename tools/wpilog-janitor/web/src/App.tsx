import { useCallback, useEffect, useState } from 'react';
import { LogPicker } from './LogPicker';
import { LAST_LOG_KEY, loadJson, saveJson } from './lib/storage';
import { TrimPage } from './trim/TrimPage';

type Tab = 'trim' | 'content';

/** `#log=path/to/x.wpilog` in the URL wins (shareable), then the last log used on this machine. */
function initialLog(): string | null {
  const m = /[#&]log=([^&]*)/.exec(window.location.hash);
  if (m) return decodeURIComponent(m[1]);
  return loadJson<string | null>(LAST_LOG_KEY, null);
}

export default function App() {
  const [log, setLog] = useState<string | null>(initialLog);
  const [picking, setPicking] = useState(() => initialLog() === null);
  const [tab, setTab] = useState<Tab>('trim');

  const open = useCallback((path: string) => {
    setLog(path);
    setPicking(false);
    setTab('trim');
    saveJson(LAST_LOG_KEY, path);
    window.history.replaceState(null, '', `#log=${encodeURIComponent(path)}`);
  }, []);

  useEffect(() => {
    document.title = log && !picking ? `${log.split('/').pop()} · WPILog Janitor` : 'WPILog Janitor';
  }, [log, picking]);

  return (
    <>
      <header className="topbar">
        <span className="brand">WPILog Janitor</span>
        <nav aria-label="Tools">
          <button type="button" className={`tab ${tab === 'trim' ? 'on' : ''}`} onClick={() => setTab('trim')} aria-current={tab === 'trim' ? 'page' : undefined}>
            Trim
          </button>
          <button type="button" className={`tab ${tab === 'content' ? 'on' : ''}`} onClick={() => setTab('content')} aria-current={tab === 'content' ? 'page' : undefined}>
            Content <span className="soon">soon</span>
          </button>
        </nav>
      </header>
      <main>
        {tab === 'content' ? (
          <div className="page">
            <section className="card">
              <h1>Content</h1>
              <p>
                Coming next: where the bytes are, entries that are logged more than once, choosing entries to drop (which the Trim page then
                counts in its savings), and an extract you can hand to an LLM to ask which data you do not need.
              </p>
              <p className="muted small">Until then, the command line can already drop entries: <code>python -m janitor trim … --exclude-prefix /RealOutputs/Vision</code>.</p>
            </section>
          </div>
        ) : picking || !log ? (
          <LogPicker onPick={open} current={log} />
        ) : (
          <TrimPage log={log} onChangeLog={() => setPicking(true)} />
        )}
      </main>
    </>
  );
}
