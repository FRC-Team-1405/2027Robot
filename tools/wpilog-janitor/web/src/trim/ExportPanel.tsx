import { useEffect, useState } from 'react';
import { api, type ExportResult, type PlanReq } from '../api';
import { fmtBytes, fmtPct, stemOf } from '../lib/format';

interface Props {
  log: string;
  request: PlanReq | null;
}

export function ExportPanel({ log, request }: Props) {
  const stem = stemOf(log);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState<'save' | 'download' | null>(null);
  const [result, setResult] = useState<ExportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // a result belongs to one log; do not carry it across
  useEffect(() => {
    setResult(null);
    setError(null);
    setName('');
  }, [log]);

  const filename = name.trim() || undefined;

  const save = async () => {
    if (!request) return;
    setBusy('save');
    setError(null);
    try {
      setResult(await api.exportSave(request, filename, true));
    } catch (e) {
      setError((e as Error).message);
      setResult(null);
    } finally {
      setBusy(null);
    }
  };

  const download = async () => {
    if (!request) return;
    setBusy('download');
    setError(null);
    try {
      const { blob, name: fname } = await api.exportDownload(request, filename);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fname;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const fullPath = result ? result.abs_path : '';
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(fullPath);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked: the path is still on screen */
    }
  };

  return (
    <section className="card export">
      <h2>Export</h2>
      <label className="field">
        <span>File name</span>
        <input
          type="text"
          value={name}
          placeholder={`${stem}_trimmed`}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void save()}
          spellCheck={false}
        />
        <small>Saved next to the original as .wpilog. An existing file is never overwritten; a number is added instead.</small>
      </label>
      <div className="row">
        <button type="button" className="btn primary" onClick={() => void save()} disabled={!request || busy !== null}>
          {busy === 'save' ? 'Writing…' : 'Save next to original'}
        </button>
        <button type="button" className="btn" onClick={() => void download()} disabled={!request || busy !== null}>
          {busy === 'download' ? 'Preparing…' : 'Download'}
        </button>
      </div>
      {!request && <p className="muted small">Select at least one period first.</p>}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {result && (
        <div className="result" role="status">
          <p>
            <strong>Saved {result.name}</strong> — {fmtBytes(result.bytes)}, {fmtPct(result.saved_pct)} smaller than the original.
          </p>
          <p className="path">
            <code>{fullPath}</code>
            <button type="button" className="btn small" onClick={() => void copy()}>
              {copied ? 'Copied' : 'Copy path'}
            </button>
          </p>
          {result.verify && result.verify.ok && <p className="ok">✓ Checked against the original: every kept record present, times consistent, header intact.</p>}
          {result.verify && !result.verify.ok && (
            <div className="error">
              <p>The written file failed its check ({result.verify.n_issues} issue{result.verify.n_issues === 1 ? '' : 's'}). Do not rely on it:</p>
              <ul>
                {result.verify.issues.map((i) => (
                  <li key={i}>{i}</li>
                ))}
              </ul>
            </div>
          )}
          {result.verify_skipped && <p className="muted small">The automatic check was skipped because the log is very large.</p>}
          <p className="muted small">Original times can be recovered from the /Janitor/SegmentMap entry inside the file.</p>
        </div>
      )}
    </section>
  );
}
