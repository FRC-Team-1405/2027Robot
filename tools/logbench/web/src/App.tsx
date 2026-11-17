import { VisionInsightsPage } from './vision/VisionInsightsPage';
import { ConnectionsPage } from './connections/ConnectionsPage';
import { PlayerProvider } from './player/PlayerContext';
import { BatteryPage } from './battery/BatteryPage';
import { useEffect, useState } from 'react';
import { ComparePage } from './compare/ComparePage';
import { FetchBundlePage } from './fetch/FetchBundlePage';
import { PanelHost } from './panels/PanelHost';
import { HealthCheckPage } from './health/HealthCheckPage';
import { TransportBar } from './controls/TransportBar';
import { TabNav } from './nav/TabNav';
import { LogBar } from './logpicker/LogBar';
import { LogBrowserPage } from './logpicker/LogBrowserPage';
import { LogSelectionProvider } from './logpicker/LogSelection';
import { NeedLog } from './logpicker/NeedLog';
import { handleLinkClick, navigate, resolveView, useRoute } from './nav/route';
import { OrderNotice } from './loader/OrderNotice';
import { useSpec } from './loader/useSpec';

export function App() {
  // The standalone export embeds exactly one log: no server, no log list, no tab bar.
  if (window.__MATCH_SPEC__) return <ReplayView debug={new URLSearchParams(window.location.search).has('debug')} log={null} />;
  return (
    <LogSelectionProvider>
      <Shell />
    </LogSelectionProvider>
  );
}

// Which page is showing and which log is open both come from the URL (nav/route.ts), so switching
// pages never reloads the app and every page sees the same open log (logpicker/LogSelection.tsx).
function Shell() {
  const route = useRoute();
  const debug = new URLSearchParams(window.location.search).has('debug');
  const view = resolveView(route);

  useEffect(() => {
    document.addEventListener('click', handleLinkClick);
    return () => document.removeEventListener('click', handleLinkClick);
  }, []);
  // Spell the view out in the URL so a refresh or a pasted link lands on the same page.
  useEffect(() => { if (route.view !== view) navigate({ view }, { replace: true }); }, [route.view, view]);

  let content;
  if (view === 'vision') {
    content = <VisionInsightsPage />;
  } else if (view === 'connections') {
    content = <ConnectionsPage />;
  } else if (view === 'battery') {
    content = <BatteryPage />;
  } else if (view === 'compare') {
    content = <ComparePage />;
  } else if (view === 'health') {
    content = <HealthCheckPage />;
  } else if (view === 'fetch') {
    content = <FetchBundlePage />;
  } else if (view === 'logs') {
    content = <LogBrowserPage />;
  } else {
    content = <ReplayView key={route.log ?? 'none'} debug={debug} log={route.log} />;
  }

  return (
    <>
      <LogBar />
      <TabNav />
      {content}
    </>
  );
}

function ReplayView({ debug, log }: { debug: boolean; log: string | null }) {
  const state = useSpec(log);
  const [dismissedWarnings, setDismissedWarnings] = useState<ReadonlySet<number>>(() => new Set());

  if (state.status === 'loading') {
    return <div className="status">Loading…</div>;
  }
  if (state.status === 'picker') {
    return <NeedLog what="the replay" />;
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
