import { PlayerProvider } from './player/PlayerContext';
import { BatteryPage } from './battery/BatteryPage';
import { useState } from 'react';
import { ComparePage } from './compare/ComparePage';
import { FetchBundlePage } from './fetch/FetchBundlePage';
import { PanelHost } from './panels/PanelHost';
import { PitCheckPage } from './pit/PitCheckPage';
import { TransportBar } from './controls/TransportBar';
import { TabNav } from './nav/TabNav';
import { LogPicker } from './loader/LogPicker';
import { OrderNotice } from './loader/OrderNotice';
import { useSpec } from './loader/useSpec';

export function App() {
  const params = new URLSearchParams(window.location.search);
  const debug = params.has('debug');
  const view = params.get('view');

  // Query-param-driven, like ?log=/?spec= elsewhere in this app -- no router dependency
  // for four views. The standalone export never sets ?view, so it always gets Replay --
  // and sets window.__MATCH_SPEC__, since it embeds exactly one log with nowhere else to
  // navigate to, so the tab bar doesn't render at all in that build.
  let content;
  if (view === 'battery') {
    content = <BatteryPage />;
  } else if (view === 'compare') {
    content = <ComparePage />;
  } else if (view === 'pit') {
    content = <PitCheckPage />;
  } else if (view === 'fetch') {
    content = <FetchBundlePage />;
  } else {
    content = <ReplayView debug={debug} />;
  }

  return (
    <>
      {!window.__MATCH_SPEC__ && <TabNav />}
      {content}
    </>
  );
}

function ReplayView({ debug }: { debug: boolean }) {
  const state = useSpec();
  const [dismissedWarnings, setDismissedWarnings] = useState<ReadonlySet<number>>(() => new Set());

  if (state.status === 'loading') {
    return <div className="status">Loading…</div>;
  }
  if (state.status === 'picker') {
    return <LogPicker />;
  }
  if (state.status === 'error') {
    return (
      <div className="status status--error">
        <strong>Could not load the log.</strong>
        <pre>{state.message}</pre>
      </div>
    );
  }

  const { spec } = state;
  const empty = Object.keys(spec.series).length === 0;

  return (
    <PlayerProvider spec={spec}>
      <div className="app">
        <header className="app__header">
          <div className="app__title">
            <strong>{spec.title}</strong>
            <span className="app__meta">{spec.duration.toFixed(1)}s</span>
          </div>
        </header>

        <OrderNotice order={spec.order} />
        {spec.warnings.map((w, i) => (
          !dismissedWarnings.has(i) && <div className="warning" key={i}>
            <span>{w}</span>
            <button
              className="warning__close"
              onClick={() => setDismissedWarnings((current) => new Set(current).add(i))}
              title="Dismiss warning"
              aria-label="Dismiss warning"
            >×</button>
          </div>
        ))}

        {empty ? (
          <div className="status">Nothing in this log to replay.</div>
        ) : (
          <>
            <TransportBar debug={debug} />
            <PanelHost />
            <footer className="app__footer">
              space play/pause · ←/→ 1s · shift+←/→ 10s · , / . one frame · 0 restart
            </footer>
          </>
        )}
      </div>
    </PlayerProvider>
  );
}
