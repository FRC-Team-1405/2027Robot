import { useCallback, useEffect, useRef, useState } from 'react';
import { LogPicker } from './LogPicker';
import { LAST_LOG_KEY, loadJson, saveJson } from './lib/storage';
import { ContentPage } from './content/ContentPage';
import { OrderPage } from './order/OrderPage';
import { TrimPage } from './trim/TrimPage';

type Tab = 'trim' | 'content' | 'order';

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
  // logs we already sent to the Order page automatically; after that the Trim page only shows a banner
  const jumped = useRef(new Set<string>());

  const open = useCallback((path: string) => {
    setLog(path);
    setPicking(false);
    saveJson(LAST_LOG_KEY, path);
    window.history.replaceState(null, '', `#log=${encodeURIComponent(path)}`);
  }, []);

  const onOutOfOrder = useCallback(
    (auto: boolean) => {
      if (!log) return;
      if (auto && jumped.current.has(log)) return;
      jumped.current.add(log);
      setTab('order');
    },
    [log],
  );

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
          <button type="button" className={`tab ${tab === 'order' ? 'on' : ''}`} onClick={() => setTab('order')} aria-current={tab === 'order' ? 'page' : undefined}>
            Order
          </button>
        </nav>
      </header>
      <main>
        {picking || !log ? (
          <LogPicker onPick={open} current={log} />
        ) : tab === 'order' ? (
          <OrderPage
            log={log}
            onChangeLog={() => setPicking(true)}
            onOpen={(path) => {
              open(path);
              setTab('trim');
            }}
          />
        ) : tab === 'content' ? (
          <ContentPage log={log} onChangeLog={() => setPicking(true)} onGoTrim={() => setTab('trim')} />
        ) : (
          <TrimPage log={log} onChangeLog={() => setPicking(true)} onOutOfOrder={onOutOfOrder} />
        )}
      </main>
    </>
  );
}
