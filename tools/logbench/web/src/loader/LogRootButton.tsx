// "Change folder" control for every page that lists logs. The server opens the native
// folder dialog on its own machine (see /api/log-root/pick in server/main.py) -- a browser
// can't hand back a folder's path -- and switches its log root; the page then re-fetches
// /api/logs via onChanged.

import { useState } from 'react';

export function LogRootButton({ root, onChanged }: { root?: string | null; onChanged: (root: string) => void }) {
  const [picking, setPicking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pick = async () => {
    setPicking(true);
    setError(null);
    try {
      const r = await fetch('/api/log-root/pick', { method: 'POST' });
      const body = await r.json();
      if (!r.ok) throw new Error(body.detail ?? `${r.status}`);
      if (!body.cancelled) onChanged(body.root);
    } catch (e) {
      setError(String((e as Error).message ?? e));
    } finally {
      setPicking(false);
    }
  };

  return (
    <div className="log-root">
      {root && <span className="log-root__path" title={root}>{root}</span>}
      <button className="log-root__btn" onClick={pick} disabled={picking}>
        {picking ? 'Choose a folder in the dialog…' : 'Change folder…'}
      </button>
      {error && <span className="log-root__error" role="alert">{error}</span>}
    </div>
  );
}
