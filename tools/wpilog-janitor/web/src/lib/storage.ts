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
