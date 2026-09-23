import type { Seg } from './segments';

// localStorage that never throws: private windows, blocked storage and quota errors all just mean "no memory".

export function loadJson<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

export function saveJson(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore */
  }
}

export const LAST_LOG_KEY = 'janitor.lastLog';
export const planKey = (log: string) => `janitor.plan.v1:${log}`;
/** Written by the Content page (entries the user chose to drop); the Trim page only reads it. */
export const exclusionsKey = (log: string) => `janitor.exclusions.v1:${log}`;

export interface Exclusions {
  exclude: string[];
  exclude_prefixes: string[];
}

export const NO_EXCLUSIONS: Exclusions = { exclude: [], exclude_prefixes: [] };

/** The Trim page's selection for one log; the Content page reads it to analyse just the kept periods. */
export interface SavedPlan {
  segs: Seg[];
  gapMs: number;
  // Named `timing`, not `policy` as before: 'compact' used to be the default and was saved for every log
  // opened, so an old saved choice is not a real one. Plans without `timing` fall back to 'preserve'.
  timing?: 'compact' | 'preserve';
  /** Keep the match context (battery voltage, mode, match info) for the whole log. Missing = true. */
  context?: boolean;
}

export const PROTECT_KEY = 'janitor.protect.v1';
