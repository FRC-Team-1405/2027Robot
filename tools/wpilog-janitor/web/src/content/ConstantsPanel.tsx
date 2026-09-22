import type { ContentEntry } from '../api';
import { fmtBytes, fmtPct } from '../lib/format';

interface Props {
  entries: ContentEntry[]; // the constant ones
  totalBytes: number;
  isExcluded: (name: string) => boolean;
  onToggle: (names: string[], on: boolean) => void;
}

export function ConstantsPanel({ entries, totalBytes, isExcluded, onToggle }: Props) {
  const bytes = entries.reduce((s, e) => s + e.bytes, 0);
  const rows = [...entries].sort((a, b) => b.bytes - a.bytes || a.name.localeCompare(b.name));
  const allOn = rows.length > 0 && rows.every((e) => isExcluded(e.name));
  return (
    <div>
      <p className="muted">
        Entries that never changed in this window: zeroed joystick axes, empty alert lists, protocol versions. They are logged once and cost almost
        nothing — <strong>{rows.length}</strong> of them add up to <strong>{fmtBytes(bytes)}</strong> ({totalBytes > 0 ? fmtPct((bytes / totalBytes) * 100) : '0%'} of the analysed data). Dropping them
        rarely saves anything, and many are replay inputs.
      </p>
      {rows.length === 0 ? (
        <p className="empty">No constant entries in this window.</p>
      ) : (
        <>
          <div className="row">
            <button type="button" className="btn small" onClick={() => onToggle(rows.map((e) => e.name), !allOn)}>
              {allOn ? 'Keep them all again' : `Exclude all ${rows.length} constants`}
            </button>
          </div>
          <div className="table-wrap tall">
            <table className="consts">
              <thead>
                <tr>
                  <th aria-label="Exclude" />
                  <th>Entry</th>
                  <th>Value</th>
                  <th>Type</th>
                  <th className="r">Size</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((e) => (
                  <tr key={e.id} className={isExcluded(e.name) ? 'excluded' : ''}>
                    <td className="check">
                      <input type="checkbox" checked={isExcluded(e.name)} onChange={(ev) => onToggle([e.name], ev.target.checked)} aria-label={`Exclude ${e.name}`} />
                    </td>
                    <td className="name">
                      <span className="label">{e.name}</span>
                      {e.protected && (
                        <span className="lock" role="img" aria-label={`Protected: ${e.protected}`} title={e.protected}>
                          🔒
                        </span>
                      )}
                    </td>
                    <td className="muted">
                      <code>{e.sample ?? '—'}</code>
                    </td>
                    <td className="muted small">{e.type}</td>
                    <td className="r">{fmtBytes(e.bytes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
