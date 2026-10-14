import { useEffect, useState } from 'react';
import { api, type OrderReport, type ReorderResult } from '../api';
import { fmtBytes, fmtPct } from '../lib/format';

// Out-of-order logs: plain WPILib DataLogManager logs (FRC_*.wpilog) mirror NetworkTables values stamped
// with their publish time, and values published off the main loop reach the file a few ms after newer
// records. Trimming needs time order, so this page shows how far off the log is and writes a sorted copy.

function fmtMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : ms >= 10 ? `${ms.toFixed(0)} ms` : `${ms.toFixed(1)} ms`;
}

export function OrderPage({ log, onChangeLog, onOpen }: { log: string; onChangeLog: () => void; onOpen: (path: string) => void }) {
  const [report, setReport] = useState<OrderReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState<'save' | 'download' | null>(null);
  const [result, setResult] = useState<ReorderResult | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    const ac = new AbortController();
    setReport(null);
    setError(null);
    setResult(null);
    setActionError(null);
    setName('');
    api
      .order(log, ac.signal)
      .then(setReport)
      .catch((e: Error) => {
        if (e.name !== 'AbortError') setError(e.message);
      });
    return () => ac.abort();
  }, [log]);

  const filename = name.trim() || undefined;

  const save = async () => {
    setBusy('save');
    setActionError(null);
    try {
      setResult(await api.reorderSave(log, filename));
    } catch (e) {
      setActionError((e as Error).message);
      setResult(null);
    } finally {
      setBusy(null);
    }
  };

  const download = async () => {
    setBusy('download');
    setActionError(null);
    try {
      const { blob, name: fname } = await api.reorderDownload(log, filename);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fname;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  if (error) {
    return (
      <div className="page">
        <p className="error" role="alert">
          {error}
        </p>
        <button type="button" className="btn" onClick={onChangeLog}>
          Choose another log
        </button>
      </div>
    );
  }
  if (!report) {
    return (
      <div className="page">
        <p className="status" role="status">
          Checking the record order in <strong>{log}</strong>…
        </p>
      </div>
    );
  }

  const biggest = Math.max(1, ...report.lateness.map((l) => l.records));

  return (
    <div className="page">
      <section className="card log-head">
        <div className="title-row">
          <div>
            <h1 title={log}>{report.name}</h1>
            <p className="muted small">Record order</p>
          </div>
          <button type="button" className="btn" onClick={onChangeLog}>
            Change log
          </button>
        </div>
        {report.ordered ? (
          <p className="ok">✓ Every record is in time order. Nothing to fix: this log can be trimmed as it is.</p>
        ) : (
          <>
            <dl className="facts">
              <div>
                <dt>Out of order</dt>
                <dd>
                  {report.n_late.toLocaleString()} <span className="muted">of {report.n_records.toLocaleString()} ({fmtPct(report.late_pct)})</span>
                </dd>
              </div>
              <div>
                <dt>Worst</dt>
                <dd>{fmtMs(report.max_late_ms)} behind</dd>
              </div>
              <div>
                <dt>Entries affected</dt>
                <dd>{report.n_entries_late.toLocaleString()}</dd>
              </div>
            </dl>
            <p className="small">
              These records were written to the file after newer ones. That is normal for a plain WPILib log (FRC_*.wpilog): it copies
              NetworkTables values stamped with the time they were published, and values published outside the main loop (swerve
              telemetry, PhotonVision) arrive a little late. Nothing is wrong with the data, but trimming needs the records in time
              order, so make a time-ordered copy below and trim that.
            </p>
            {report.n_backwards === 0 ? (
              <p className="ok small">
                ✓ Every entry's own records are already in order, so reordering changes no signal's values or their sequence: it
                only changes how the entries are interleaved.
              </p>
            ) : (
              <p className="warn small">
                {report.n_backwards.toLocaleString()} records are out of order within their own entry. Reordering sorts those
                entries by time, so their sequence in the copy differs from the original.
              </p>
            )}
          </>
        )}
      </section>

      {!report.ordered && (
        <>
          <section className="card">
            <h2>How far behind</h2>
            <div className="table-wrap">
              <table className="order-buckets">
                <thead>
                  <tr>
                    <th>Behind the newest record by</th>
                    <th className="r">Records</th>
                    <th aria-hidden="true" />
                  </tr>
                </thead>
                <tbody>
                  {report.lateness.map((l) => (
                    <tr key={l.bucket}>
                      <td>{l.bucket}</td>
                      <td className="r">{l.records.toLocaleString()}</td>
                      <td className="bar-cell" aria-hidden="true">
                        <span className="bar" style={{ width: `${(100 * l.records) / biggest}%` }} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card">
            <h2>Entries with the most late records</h2>
            <div className="table-wrap tall">
              <table>
                <thead>
                  <tr>
                    <th>Entry</th>
                    <th className="r">Late</th>
                    <th className="r">Records</th>
                    <th className="r">Worst</th>
                  </tr>
                </thead>
                <tbody>
                  {report.entries.map((e) => (
                    <tr key={e.name}>
                      <td className="name">{e.name}</td>
                      <td className="r">{e.late.toLocaleString()}</td>
                      <td className="r muted">{e.records.toLocaleString()}</td>
                      <td className="r">{fmtMs(e.max_late_ms)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {report.n_entries_late > report.entries.length && (
              <p className="muted small">
                Showing {report.entries.length} of {report.n_entries_late} entries.
              </p>
            )}
          </section>

          <section className="card export">
            <h2>Make a time-ordered copy</h2>
            <label className="field">
              <span>File name</span>
              <input
                type="text"
                value={name}
                placeholder={report.default_name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && void save()}
                spellCheck={false}
              />
              <small>Saved next to the original as .wpilog. An existing file is never overwritten; a number is added instead.</small>
            </label>
            <div className="row">
              <button type="button" className="btn primary" onClick={() => void save()} disabled={busy !== null}>
                {busy === 'save' ? 'Reordering…' : 'Reorder & save'}
              </button>
              <button type="button" className="btn" onClick={() => void download()} disabled={busy !== null}>
                {busy === 'download' ? 'Preparing…' : 'Download'}
              </button>
            </div>
            {actionError && (
              <p className="error" role="alert">
                {actionError}
              </p>
            )}
            {result && (
              <div className="result" role="status">
                <p>
                  <strong>Saved {result.name}</strong> — {fmtBytes(result.bytes)}, {result.n_moved.toLocaleString()} records moved into
                  place.
                </p>
                <p className="path">
                  <code>{result.abs_path}</code>
                </p>
                {result.verify && result.verify.ok && (
                  <p className="ok">✓ Checked against the original: every record present, in time order, values and timestamps unchanged.</p>
                )}
                {result.verify && !result.verify.ok && (
                  <div className="error">
                    <p>
                      The written file failed its check ({result.verify.n_issues} issue{result.verify.n_issues === 1 ? '' : 's'}). Do
                      not rely on it:
                    </p>
                    <ul>
                      {result.verify.issues.map((i) => (
                        <li key={i}>{i}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {result.verify_skipped && <p className="muted small">The automatic check was skipped because the log is very large.</p>}
                <div className="row">
                  <button type="button" className="btn primary" onClick={() => onOpen(result.path)} disabled={!!result.verify && !result.verify.ok}>
                    Open the copy and trim it
                  </button>
                </div>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
