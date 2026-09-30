import { useState } from 'react';
import type { ContentEntry, DupGroup, Twin } from '../api';
import { fmtBytes } from '../lib/format';

interface Props {
  groups: DupGroup[];
  twins: Twin[];
  byId: Map<number, ContentEntry>;
  isExcluded: (name: string) => boolean;
  /** Exclude (on) or keep again (off) these entries, asking first when protected ones are involved. */
  onToggle: (names: string[], on: boolean) => void;
  /** Exclude `drop`, and make sure `keep` is not excluded. */
  onExcludeOthers: (drop: string[], keep: string) => void;
  scopeNote: string;
}

const KIND: Record<DupGroup['kind'], { label: string; help: string }> = {
  identical: { label: 'identical', help: 'The same values, logged at the same instants.' },
  values: { label: 'same values', help: 'The same values, logged at different instants (for example one from processInputs and one from an output).' },
  near: { label: 'near-identical', help: 'Almost every value matches.' },
};

function GroupCard({ g, byId, isExcluded, onToggle, onExcludeOthers }: { g: DupGroup } & Omit<Props, 'groups' | 'twins' | 'scopeNote'>) {
  const [keeper, setKeeper] = useState(g.keeper);
  const members = g.members.map((id) => byId.get(id)).filter((e): e is ContentEntry => !!e);
  const others = members.filter((m) => m.id !== keeper);
  const recoverable = others.reduce((s, m) => s + m.bytes, 0);
  const done = others.length > 0 && others.every((m) => isExcluded(m.name)) && !isExcluded(members.find((m) => m.id === keeper)?.name ?? '');
  const nProtected = others.filter((m) => m.protected).length;
  const k = KIND[g.kind];

  return (
    <article className={`card group ${g.weak ? 'weak' : ''}`}>
      <header>
        <span className="badge kind" title={k.help}>
          {k.label}
        </span>
        <span className="evidence">{g.evidence}</span>
        <span className="spacer" />
        <strong>{fmtBytes(recoverable)}</strong>
        <span className="muted small"> recoverable</span>
      </header>
      <table className="members">
        <tbody>
          {members.map((m) => (
            <tr key={m.id} className={isExcluded(m.name) ? 'excluded' : ''}>
              <td className="check">
                <input type="radio" name={`keep-${g.id}`} checked={m.id === keeper} onChange={() => setKeeper(m.id)} aria-label={`Keep ${m.name}`} />
              </td>
              <td className="name">
                <span className="label">{m.name}</span>
                {m.id === keeper ? <span className="flag keep">keep</span> : <span className="flag drop">drop</span>}
                <span className={`flag cls-${m.cls}`}>{m.cls === 'replay-input' ? 'input' : m.cls}</span>
                {m.protected && (
                  <span className="lock" role="img" aria-label={`Protected: ${m.protected}`} title={m.protected}>
                    🔒
                  </span>
                )}
              </td>
              <td className="r">{fmtBytes(m.bytes)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <footer>
        {done ? (
          <>
            <span className="ok">✓ The other {others.length === 1 ? 'copy is' : `${others.length} copies are`} excluded</span>
            <button type="button" className="btn small" onClick={() => onToggle(others.map((m) => m.name), false)}>
              Keep them again
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              className="btn"
              onClick={() =>
                onExcludeOthers(
                  others.map((m) => m.name),
                  members.find((m) => m.id === keeper)?.name ?? '',
                )
              }
            >
              Exclude the {others.length === 1 ? 'other copy' : `${others.length} others`} ({fmtBytes(recoverable)})
            </button>
            {nProtected > 0 && (
              <span className="muted small">
                {nProtected} of {others.length} {nProtected === 1 ? 'is' : 'are'} protected — you will be asked first.
              </span>
            )}
          </>
        )}
      </footer>
    </article>
  );
}

export function DuplicatesPanel({ groups, twins, byId, isExcluded, onToggle, onExcludeOthers, scopeNote }: Props) {
  const strong = groups.filter((g) => !g.weak);
  const weak = groups.filter((g) => g.weak);
  const total = strong.reduce((s, g) => s + g.recoverable_bytes, 0);
  const common = { byId, isExcluded, onToggle, onExcludeOthers };

  return (
    <div className="dups">
      <p className="muted">
        Entries that record the same data twice. Constants are never listed here (they would all match each other). <em>Nothing is excluded until you press a button.</em> {scopeNote}
      </p>
      {strong.length === 0 ? (
        <p className="empty">No duplicates found in this window.</p>
      ) : (
        <>
          <p>
            <strong>{strong.length}</strong> duplicate group{strong.length === 1 ? '' : 's'} · {fmtBytes(total)} recoverable
          </p>
          {strong.map((g) => (
            <GroupCard key={g.id} g={g} {...common} />
          ))}
        </>
      )}

      {weak.length > 0 && (
        <details className="weak-list">
          <summary>
            {weak.length} weak match{weak.length === 1 ? '' : 'es'} — probably coincidence
          </summary>
          <p className="muted small">
            Every member changed fewer than 6 times, so two unrelated short series can easily agree (two booleans that each flip once). They are shown
            for completeness, not as a suggestion.
          </p>
          {weak.map((g) => (
            <GroupCard key={g.id} g={g} {...common} />
          ))}
        </details>
      )}

      {twins.length > 0 && (
        <section className="card">
          <h2>Same name, different data</h2>
          <p className="muted small">Entries that share a name apart from their prefix but do not hold the same values — worth a look before assuming they are copies.</p>
          <ul className="twins">
            {twins.map((t) => (
              <li key={t.key}>
                <code>{t.key}</code> <span className="muted">— {t.members.map((id) => byId.get(id)?.name ?? id).join('  vs  ')}</span>
                <div className="small">{t.note}</div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
