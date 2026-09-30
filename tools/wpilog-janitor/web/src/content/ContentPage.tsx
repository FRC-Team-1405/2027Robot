import { useEffect, useMemo, useState } from 'react';
import type { ContentEntry, ContentReq, ProtectProfile } from '../api';
import { clearExcluded, isExcluded, setExcluded, totalRules } from '../lib/exclusions';
import { fmtBytes, fmtDuration, fmtPct } from '../lib/format';
import { toRequestSegments } from '../lib/segments';
import { exclusionsKey, loadJson, NO_EXCLUSIONS, PROTECT_KEY, planKey, saveJson, type Exclusions, type SavedPlan } from '../lib/storage';
import { allKeys, buildTree, flatten } from '../lib/tree';
import { ConstantsPanel } from './ConstantsPanel';
import { DuplicatesPanel } from './DuplicatesPanel';
import { TreeTable } from './TreeTable';
import { useContent } from './useContent';

type Sub = 'sizes' | 'duplicates' | 'constants';

interface Pending {
  names: string[]; // everything the user asked to exclude that is not already
  protectedNames: string[];
}

function reasonSummary(entries: (ContentEntry | undefined)[]): string {
  const counts = new Map<string, number>();
  for (const e of entries) {
    if (!e?.protected) continue;
    const short = e.protected.split(':')[0];
    counts.set(short, (counts.get(short) ?? 0) + 1);
  }
  return [...counts].map(([r, n]) => `${n} ${r}`).join(', ');
}

export function ContentPage({ log, onChangeLog, onGoTrim }: { log: string; onChangeLog: () => void; onGoTrim: () => void }) {
  const plan = useMemo(() => loadJson<SavedPlan | null>(planKey(log), null), [log]);
  const hasPlan = !!plan && plan.segs.length > 0;
  const [scope, setScope] = useState<'plan' | 'whole'>(hasPlan ? 'plan' : 'whole');
  const [protect, setProtect] = useState<ProtectProfile[]>(() => loadJson<ProtectProfile[]>(PROTECT_KEY, ['replay', 'logbench']));
  const [excl, setExcl] = useState<Exclusions>(() => loadJson(exclusionsKey(log), NO_EXCLUSIONS));
  const [sub, setSub] = useState<Sub>('sizes');
  const [query, setQuery] = useState('');
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [pending, setPending] = useState<Pending | null>(null);

  // per-log state: pick it up again when the log changes
  useEffect(() => {
    setScope(hasPlan ? 'plan' : 'whole');
    setExcl(loadJson(exclusionsKey(log), NO_EXCLUSIONS));
    setPending(null);
    setExpanded(new Set());
    setQuery('');
  }, [log, hasPlan]);
  useEffect(() => saveJson(exclusionsKey(log), excl), [excl, log]);
  useEffect(() => saveJson(PROTECT_KEY, protect), [protect]);

  const req = useMemo<ContentReq>(
    () => ({
      log,
      segments: scope === 'plan' && plan ? toRequestSegments(plan.segs) : [],
      gap_ms: plan?.gapMs ?? 200,
      gap_policy: plan?.timing ?? 'preserve',
      protect,
    }),
    [log, scope, plan, protect],
  );
  const { data, error, loading } = useContent(req);

  const byId = useMemo(() => new Map((data?.entries ?? []).map((e) => [e.id, e])), [data]);
  const byName = useMemo(() => new Map((data?.entries ?? []).map((e) => [e.name, e])), [data]);
  const universe = useMemo(() => (data?.entries ?? []).map((e) => e.name), [data]);
  const tree = useMemo(() => buildTree(data?.entries ?? []), [data]);
  const rows = useMemo(() => flatten(tree, expanded, query), [tree, expanded, query]);
  const isEx = (name: string) => isExcluded(name, excl);

  const apply = (names: string[], on: boolean) => setExcl((cur) => setExcluded(cur, names, on, universe));
  /** Turn entries off (keep) immediately; turning them on (exclude) asks first if any are protected. */
  const toggle = (names: string[], on: boolean) => {
    if (!on) return apply(names, false);
    const fresh = names.filter((n) => !isEx(n));
    const prot = fresh.filter((n) => byName.get(n)?.protected);
    if (prot.length === 0) apply(fresh, true);
    else setPending({ names: fresh, protectedNames: prot });
  };
  const excludeOthers = (drop: string[], keep: string) => {
    if (keep) apply([keep], false);
    toggle(drop, true);
  };

  const excludedEntries = (data?.entries ?? []).filter((e) => isEx(e.name));
  const excludedBytes = excludedEntries.reduce((s, e) => s + e.bytes, 0);
  const windowBytes = data?.window.bytes ?? 0;
  const consts = (data?.entries ?? []).filter((e) => e.constant);
  const nStrong = (data?.groups ?? []).filter((g) => !g.weak).length;
  const toggleProfile = (p: ProtectProfile) => setProtect((cur) => (cur.includes(p) ? cur.filter((x) => x !== p) : [...cur, p]));

  const scopeNote = data?.window.whole_log
    ? 'Analysing the whole log.'
    : `Analysing only the periods you are keeping (${data ? fmtDuration(data.window.seconds) : '…'}) — a pair can match there and not elsewhere.`;

  return (
    <div className="page">
      <section className="card">
        <div className="title-row">
          <div>
            <h1 title={log}>{log.split('/').pop()}</h1>
            <p className="muted small">Where the bytes are, and what you can leave out.</p>
          </div>
          <button type="button" className="btn" onClick={onChangeLog}>
            Change log
          </button>
        </div>

        <div className="controls">
          <fieldset>
            <legend>Analyse</legend>
            <label className={hasPlan ? '' : 'disabled'} title={hasPlan ? '' : 'Pick periods on the Trim page first'}>
              <input type="radio" name="scope" checked={scope === 'plan'} disabled={!hasPlan} onChange={() => setScope('plan')} /> the periods I am keeping
              {hasPlan && plan ? ` (${plan.segs.length})` : ''}
            </label>
            <label>
              <input type="radio" name="scope" checked={scope === 'whole'} onChange={() => setScope('whole')} /> the whole log
            </label>
          </fieldset>
          <fieldset>
            <legend>Protect (ask before excluding)</legend>
            <label>
              <input type="checkbox" checked={protect.includes('replay')} onChange={() => toggleProfile('replay')} /> replay inputs
              <span className="muted small"> — what simulateJava reads back</span>
            </label>
            <label>
              <input type="checkbox" checked={protect.includes('logbench')} onChange={() => toggleProfile('logbench')} /> what logbench reads
              <span className="muted small"> — vision, drivetrain, driver station</span>
            </label>
            <span className="muted small">Cycle marker and struct schemas are always protected: without them the log cannot be read.</span>
          </fieldset>
        </div>
      </section>

      <section className="card sticky-summary" aria-live="polite">
        <div className="summary-row">
          <div>
            <strong>{excludedEntries.length}</strong> {excludedEntries.length === 1 ? 'entry' : 'entries'} excluded
            {excludedEntries.length > 0 && (
              <>
                {' '}
                · <strong>{fmtBytes(excludedBytes)}</strong>
                {windowBytes > 0 && <> ({fmtPct((excludedBytes / windowBytes) * 100)} of the {data?.window.whole_log ? 'log' : 'kept periods'})</>}
              </>
            )}
            {totalRules(excl) > excludedEntries.length && excludedEntries.length === 0 && <span className="muted"> · {totalRules(excl)} rules from an earlier session</span>}
          </div>
          <div className="row tight">
            <button type="button" className="btn small" onClick={() => setExcl(clearExcluded())} disabled={totalRules(excl) === 0}>
              Clear
            </button>
            <button type="button" className="btn small primary" onClick={onGoTrim}>
              {totalRules(excl) > 0 ? 'Go to Trim — savings include these' : 'Go to Trim'}
            </button>
          </div>
        </div>
      </section>

      {pending && (
        <section className="confirm" role="alertdialog" aria-labelledby="confirm-title">
          <h2 id="confirm-title">
            {pending.protectedNames.length} of the {pending.names.length} {pending.names.length === 1 ? 'entry' : 'entries'} you chose {pending.protectedNames.length === 1 ? 'is' : 'are'} protected
          </h2>
          <p>
            {reasonSummary(pending.protectedNames.map((n) => byName.get(n)))}. Excluding them can change what replay does, or leave logbench without data it reads.
          </p>
          <div className="row">
            <button
              type="button"
              className="btn"
              onClick={() => {
                apply(pending.names, true);
                setPending(null);
              }}
            >
              Exclude all {pending.names.length}
            </button>
            {pending.names.length > pending.protectedNames.length && (
              <button
                type="button"
                className="btn primary"
                onClick={() => {
                  apply(
                    pending.names.filter((n) => !pending.protectedNames.includes(n)),
                    true,
                  );
                  setPending(null);
                }}
              >
                Only the {pending.names.length - pending.protectedNames.length} unprotected
              </button>
            )}
            <button type="button" className="btn" onClick={() => setPending(null)}>
              Cancel
            </button>
          </div>
        </section>
      )}

      <section className="card">
        <nav className="subtabs" aria-label="Content views">
          <button type="button" className={sub === 'sizes' ? 'on' : ''} onClick={() => setSub('sizes')}>
            Sizes
          </button>
          <button type="button" className={sub === 'duplicates' ? 'on' : ''} onClick={() => setSub('duplicates')}>
            Duplicates {data && <span className="count">{nStrong}</span>}
          </button>
          <button type="button" className={sub === 'constants' ? 'on' : ''} onClick={() => setSub('constants')}>
            Constants {data && <span className="count">{data.constants.count}</span>}
          </button>
          <span className="spacer" />
          {data && (
            <span className="muted small">
              {data.entries.length} entries · {fmtBytes(data.window.bytes)} analysed
              {loading ? ' · updating…' : ` · ${data.took_s.toFixed(1)} s`}
            </span>
          )}
        </nav>

        {error && (
          <div className="error" role="alert">
            <p>{error}</p>
            {scope === 'plan' && (
              <button type="button" className="btn small" onClick={() => setScope('whole')}>
                Analyse the whole log instead
              </button>
            )}
          </div>
        )}
        {!data && loading && (
          <p className="status" role="status">
            Analysing… the first pass over a large log can take 30 s; after that it is cached.
          </p>
        )}

        {data && (
          <div className={loading ? 'dimmed' : ''}>
            {sub === 'sizes' && (
              <>
                <div className="row tight">
                  <input className="search" type="search" placeholder="Filter entries — e.g. “vision poses”" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Filter entries" />
                  <button type="button" className="btn small" onClick={() => setExpanded(new Set(allKeys(tree)))}>
                    Expand all
                  </button>
                  <button type="button" className="btn small" onClick={() => setExpanded(new Set())}>
                    Collapse all
                  </button>
                </div>
                <TreeTable
                  rows={rows}
                  totalBytes={windowBytes}
                  isExcluded={isEx}
                  onToggle={toggle}
                  onExpand={(k) =>
                    setExpanded((cur) => {
                      const next = new Set(cur);
                      if (next.has(k)) next.delete(k);
                      else next.add(k);
                      return next;
                    })
                  }
                />
              </>
            )}
            {sub === 'duplicates' && (
              <DuplicatesPanel groups={data.groups} twins={data.twins} byId={byId} isExcluded={isEx} onToggle={toggle} onExcludeOthers={excludeOthers} scopeNote={scopeNote} />
            )}
            {sub === 'constants' && <ConstantsPanel entries={consts} totalBytes={windowBytes} isExcluded={isEx} onToggle={toggle} />}
          </div>
        )}
      </section>
    </div>
  );
}
