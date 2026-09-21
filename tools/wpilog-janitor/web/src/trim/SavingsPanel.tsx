import type { PreviewState } from './hooks';
import { fmtBytes, fmtPct, fmtTime } from '../lib/format';

interface Props {
  state: PreviewState;
  hasSegments: boolean;
  sourceBytes: number;
}

export function SavingsPanel({ state, hasSegments, sourceBytes }: Props) {
  const { preview: p, error, pending, exactPending, canComputeExact, computeExact } = state;

  if (!hasSegments) {
    return (
      <section className="card savings" aria-live="polite">
        <h2>Result</h2>
        <p className="big-empty">{fmtBytes(sourceBytes)}</p>
        <p className="empty">Select at least one period to see what the trimmed log would weigh.</p>
      </section>
    );
  }
  if (error && !p) {
    return (
      <section className="card savings" aria-live="polite">
        <h2>Result</h2>
        <p className="error" role="alert">
          {error}
        </p>
      </section>
    );
  }
  if (!p) {
    return (
      <section className="card savings" aria-live="polite">
        <h2>Result</h2>
        <p className="empty">{pending ? 'Working it out…' : '—'}</p>
      </section>
    );
  }

  const keptPct = (p.output_bytes / p.source_bytes) * 100;
  const seamCycles = p.seams.length ? p.seams[0].real_cycles_kept_before + p.seams[0].real_cycles_kept_after : 0;

  return (
    <section className="card savings" aria-live="polite">
      <h2>
        Result{' '}
        <span className={`badge ${p.exact ? 'exact' : 'est'}`} title={p.exact ? 'Computed by the same code that writes the file' : 'Predicted from the log index; within about 1% of the exact size'}>
          {p.exact ? 'exact' : '≈ estimate'}
        </span>
      </h2>

      <div className="sizes">
        <div>
          <span className="label">Original</span>
          <span className="size">{fmtBytes(p.source_bytes)}</span>
        </div>
        <span className="arrow" aria-hidden="true">
          →
        </span>
        <div>
          <span className="label">Trimmed</span>
          <span className="size strong">
            {p.exact ? '' : '≈ '}
            {fmtBytes(p.output_bytes)}
          </span>
        </div>
      </div>

      <div className="bar" role="img" aria-label={`Trimmed log is ${fmtPct(keptPct)} of the original`}>
        <div className="bar-kept" style={{ width: `${Math.max(0.6, keptPct)}%` }} />
      </div>
      <p className="saved">
        <strong>Saves {fmtBytes(p.saved_bytes)}</strong> ({fmtPct(p.saved_pct)}) · keeps {p.n_cycles_out.toLocaleString()} of{' '}
        {p.n_cycles_source.toLocaleString()} cycles
      </p>

      {p.seams.length > 0 && (
        <p className="muted small">
          {p.seams.length} cut{p.seams.length === 1 ? '' : 's'}, each joined with {seamCycles} real cycle{seamCycles === 1 ? '' : 's'} of the surrounding time
          {p.seams.length === 1 ? ` (${p.seams[0].dropped_cycles.toLocaleString()} cycles dropped there)` : ''}.
        </p>
      )}
      {p.n_excluded_entries > 0 && <p className="muted small">{p.n_excluded_entries} entries excluded on the Content page are also left out.</p>}
      {p.exact && p.n_carried !== undefined && (
        <p className="muted small">{p.n_carried} values restated at the start of each period so signals that changed in the dropped time are still right.</p>
      )}

      {p.segments.length > 0 && (
        <ul className="seg-sizes">
          {p.segments.map((s, i) => (
            <li key={i}>
              <span className={`chip mode-${s.label}`}>{s.label || 'range'}</span>
              <span>
                {fmtTime(s.orig_first)} → {fmtTime(s.orig_last)}
              </span>
              <span className="muted">{fmtBytes(s.bytes)}</span>
            </li>
          ))}
        </ul>
      )}

      {p.warnings.map((w) => (
        <p key={w} className="warn small" role="status">
          {w}
        </p>
      ))}
      {error && (
        <p className="error small" role="alert">
          {error}
        </p>
      )}

      {!p.exact && (
        <button type="button" className="btn" onClick={computeExact} disabled={!canComputeExact}>
          {exactPending ? 'Computing exact size…' : 'Compute exact size'}
        </button>
      )}
      {!p.exact && exactPending && <p className="muted small">One pass over the whole file; large logs take several seconds.</p>}
    </section>
  );
}
