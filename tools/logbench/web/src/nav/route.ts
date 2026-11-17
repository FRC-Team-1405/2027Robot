// The app's whole location state -- which page (`view`) and which log (`log`) -- lives in the
// query string, so a refresh, a bookmark and a pasted link all land on the same page with the
// same log. Navigation uses history.pushState instead of following links, so moving between
// pages never reloads the app and nothing held in memory (the log list, the selected log) is lost.
import { useMemo, useSyncExternalStore } from 'react';

export interface Route {
  view: string | null;
  log: string | null;
}

export const ROUTE_EVENT = 'logbench:route';

/** Pages that analyse the open log; the log browser sends you back to one of these. */
export const LOG_VIEWS = ['health', 'replay', 'vision', 'compare', 'battery'] as const;

export function parseRoute(search: string): Route {
  const params = new URLSearchParams(search);
  return { view: params.get('view'), log: params.get('log') };
}

/** The view to show. `pit` is the old name of Health Check; a bare `?log=` link predates the
 *  tab bar and meant Vision Logs; with nothing at all, Health Check is the overview to land on. */
export function resolveView(route: Route, standalone = false): string {
  if (standalone) return 'replay';
  if (route.view === 'pit') return 'health';
  return route.view ?? (route.log ? 'replay' : 'health');
}

/** The new query string after applying a patch; params this module does not own (debug, spec) are kept. */
export function buildSearch(search: string, patch: Partial<Route>): string {
  const params = new URLSearchParams(search);
  for (const key of ['view', 'log'] as const) {
    if (!(key in patch)) continue;
    const value = patch[key];
    if (value) params.set(key, value);
    else params.delete(key);
  }
  const text = params.toString();
  return text ? `?${text}` : '';
}

/** What an in-app `<a href="?view=...&log=...">` means, or null for a link that is not ours to handle. */
export function routeFromHref(href: string): Partial<Route> | null {
  if (!href.startsWith('?')) return null;
  const params = new URLSearchParams(href);
  const patch: Partial<Route> = {};
  if (params.has('log')) patch.log = params.get('log');
  if (params.has('view')) patch.view = params.get('view');
  else if (params.has('log')) patch.view = 'replay';
  return Object.keys(patch).length ? patch : null;
}

export function navigate(patch: Partial<Route>, options: { replace?: boolean } = {}): void {
  const next = buildSearch(window.location.search, patch);
  if (next === window.location.search) return;
  const url = `${window.location.pathname}${next}${window.location.hash}`;
  if (options.replace) window.history.replaceState(null, '', url);
  else window.history.pushState(null, '', url);
  window.dispatchEvent(new Event(ROUTE_EVENT));
}

function subscribe(listener: () => void): () => void {
  window.addEventListener('popstate', listener);
  window.addEventListener(ROUTE_EVENT, listener);
  return () => {
    window.removeEventListener('popstate', listener);
    window.removeEventListener(ROUTE_EVENT, listener);
  };
}

export function useRoute(): Route {
  const search = useSyncExternalStore(subscribe, () => window.location.search, () => '');
  return useMemo(() => parseRoute(search), [search]);
}

/** Turns clicks on in-app `?view=` links into pushState navigation. Installed once by App. */
export function handleLinkClick(event: MouseEvent): void {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  const anchor = (event.target as Element | null)?.closest?.('a');
  if (!anchor || anchor.target || anchor.hasAttribute('download')) return;
  const patch = routeFromHref(anchor.getAttribute('href') ?? '');
  if (!patch) return;
  event.preventDefault();
  navigate(patch);
}
