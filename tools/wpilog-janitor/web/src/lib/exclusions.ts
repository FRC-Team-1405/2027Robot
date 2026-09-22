// The list of entries the user chose to drop. Stored per log; the Trim page reads it for its savings numbers
// and sends it with every preview/export. The UI here only writes exact names; `exclude_prefixes` can come
// from elsewhere (the CLI's --exclude-prefix, an older session) and is honoured and preserved.
import type { Exclusions } from './storage';

const norm = (name: string) => name.replace(/^\/+/, '');

function coveringPrefix(name: string, e: Exclusions): string | null {
  const n = norm(name);
  for (const p of e.exclude_prefixes) {
    const q = norm(p).replace(/\/+$/, '');
    if (n === q || n.startsWith(q + '/')) return p;
  }
  return null;
}

export function isExcluded(name: string, e: Exclusions): boolean {
  const n = norm(name);
  return e.exclude.some((x) => norm(x) === n) || coveringPrefix(name, e) !== null;
}

export function countExcluded(names: string[], e: Exclusions): number {
  return names.filter((n) => isExcluded(n, e)).length;
}

/** Mark these entries excluded (on) or kept (off). `universe` is every entry name in the log: it is only
 *  needed to switch one entry back on when a prefix rule was excluding it — the prefix is then replaced by
 *  the exact names of its other entries so nothing else changes. */
export function setExcluded(e: Exclusions, names: string[], on: boolean, universe: string[]): Exclusions {
  let exclude = [...e.exclude];
  let prefixes = [...e.exclude_prefixes];
  const target = new Set(names.map(norm));
  if (on) {
    const have = new Set(exclude.map(norm));
    for (const n of names) {
      if (have.has(norm(n)) || coveringPrefix(n, { exclude, exclude_prefixes: prefixes }) !== null) continue;
      exclude.push(n);
      have.add(norm(n));
    }
  } else {
    exclude = exclude.filter((x) => !target.has(norm(x)));
    for (const n of names) {
      const p = coveringPrefix(n, { exclude, exclude_prefixes: prefixes });
      if (p === null) continue;
      prefixes = prefixes.filter((x) => x !== p);
      const q = norm(p).replace(/\/+$/, '');
      const have = new Set(exclude.map(norm));
      for (const u of universe) {
        const nu = norm(u);
        if ((nu === q || nu.startsWith(q + '/')) && !target.has(nu) && !have.has(nu)) exclude.push(u);
      }
    }
  }
  return { exclude, exclude_prefixes: prefixes };
}

export function clearExcluded(): Exclusions {
  return { exclude: [], exclude_prefixes: [] };
}

export function totalRules(e: Exclusions): number {
  return e.exclude.length + e.exclude_prefixes.length;
}
