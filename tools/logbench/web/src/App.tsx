import { PlayerProvider } from './player/PlayerContext';
import { useState } from 'react';
import { ComparePage } from './compare/ComparePage';
import { PanelHost } from './panels/PanelHost';
import { PitCheckPage } from './pit/PitCheckPage';
import { TransportBar } from './controls/TransportBar';
import { LogPicker } from './loader/LogPicker';
import { useSpec } from './loader/useSpec';

export function App() {
  const params = new URLSearchParams(window.location.search);
  const debug = params.has('debug');

  // Query-param-driven, like ?log=/?spec= elsewhere in this app -- no router dependency
  // for three views. The standalone export never sets ?view, so it always gets Replay.
  if (params.get('view') === 'compare') {
    return <ComparePage />;
  }
  if (params.get('view') === 'pit') {
    return <PitCheckPage />;
  }

  return <ReplayView debug={debug} />;
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
          <details className="app-menu">
            <summary>Replay options <span>{spec.duration.toFixed(1)}s</span></summary>
            <div className="app-menu__content">
              <strong>{spec.title}</strong>
              {!window.__MATCH_SPEC__ && (
                <>
                  <a className="app__back" href={window.location.pathname}>
                    ← Choose another log
                  </a>
                  <a className="app__back" href="?view=compare">
                    Compare two logs →
                  </a>
                  <a className="app__back" href="?view=pit">
                    Pit Check (live) →
                  </a>
                </>
              )}
            </div>
          </details>
        </header>

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
