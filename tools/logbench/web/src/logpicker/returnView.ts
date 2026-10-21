// The log browser is a detour from whichever page you were on; opening a log from it returns you there.
import { LOG_VIEWS } from '../nav/route';

const KEY = 'logbench.returnView';

export function rememberReturnView(view: string): void {
  try { window.sessionStorage.setItem(KEY, view); } catch { /* optional convenience */ }
}

export function returnView(): string {
  try {
    const view = window.sessionStorage.getItem(KEY);
    if (view && (LOG_VIEWS as readonly string[]).includes(view)) return view;
  } catch { /* fall through */ }
  return 'health';
}
