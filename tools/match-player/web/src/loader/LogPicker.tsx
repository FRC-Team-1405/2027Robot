// Landing view for the server app: pick a log to replay.
//
// Only reachable when the page was served by server/main.py with no ?log= chosen. The
// standalone export never renders this -- its data is already inlined.

import { useEffect, useState } from 'react';

interface LogEntry {
  path: string;
  name: string;
  size: number;
  mtime: number;
}

interface Listing {
  root: string;
  logs: LogEntry[];
  specs: { name: string; label: string }[];
}

function mb(bytes: number): string {
  return `${(bytes / 1e6).toFixed(1)} MB`;
}

export function LogPicker() {
  const [listing, setListing] = useState<Listing | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/logs')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${r.status}`))))
      .then(setListing)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return (
      <div className="status status--error">
        <strong>No log server reachable.</strong>
        <pre>
          {error}
          {'\n\n'}Start it with: python -m server.main --logs path/to/logs
        </pre>
      </div>
    );
  }
  if (!listing) return <div className="status">Looking for logs…</div>;

  return (
    <div className="picker">
      <h1>Pick a log</h1>
      <p className="picker__root">{listing.root}</p>
      {listing.logs.length === 0 ? (
        <div className="status">No .wpilog files under that directory.</div>
      ) : (
        <ul className="picker__list">
          {listing.logs.map((log) => (
            <li key={log.path}>
              <a href={`?log=${encodeURIComponent(log.path)}`}>
                <span className="picker__name">{log.path}</span>
                <span className="picker__size">{mb(log.size)}</span>
              </a>
            </li>
          ))}
        </ul>
      )}
      {/* Big logs take a few seconds to parse the first time; the spec is then cached
          server-side by (path, mtime), so coming back to one is instant. */}
      <p className="picker__hint">
        Large logs take a moment to parse the first time they are opened.
      </p>
    </div>
  );
}
