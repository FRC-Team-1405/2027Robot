import { useCallback, useEffect, useState } from 'react';
import { LogPicker } from './LogPicker';
import { LAST_LOG_KEY, loadJson, saveJson } from './lib/storage';
import { ContentPage } from './content/ContentPage';
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
            Content
          </button>
        </nav>
      </header>
      <main>
        {picking || !log ? (
          <LogPicker onPick={open} current={log} />
        ) : tab === 'content' ? (
          <ContentPage log={log} onChangeLog={() => setPicking(true)} onGoTrim={() => setTab('trim')} />
        ) : (
          <TrimPage log={log} onChangeLog={() => setPicking(true)} />
        )}
      </main>
    </>
  );
}
