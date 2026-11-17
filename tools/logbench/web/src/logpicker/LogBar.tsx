// The strip above the tabs: which folder, which log. Present on every page, so choosing a log
// (or a different folder) never has to be repeated per tab and never moves you off the page you are on.
import { LogRootButton } from '../loader/LogRootButton';
import { logLabel, logTime } from '../lib/logName';
import { LOG_VIEWS, navigate, resolveView, useRoute } from '../nav/route';
import { rememberReturnView } from './returnView';
import { useLogSelection } from './LogSelection';
import './logs.css';

export function LogBar() {
  const { root, logs, status, error, selected, missing, select, folderChanged } = useLogSelection();
  const view = resolveView(useRoute());
  const newestFirst = [...logs].sort((a, b) => logTime(b) - logTime(a));

  const browse = () => {
    if ((LOG_VIEWS as readonly string[]).includes(view)) rememberReturnView(view);
    navigate({ view: 'logs' });
  };

  return (
    <div className="log-bar">
      <LogRootButton root={root} onChanged={folderChanged} />
      <label className="log-bar__pick">
        <span>Log</span>
        <select value={selected ?? ''} onChange={(e) => select(e.target.value || null)} aria-label="Open log" disabled={status !== 'ready'}>
          <option value="">{status === 'loading' ? 'Loading logs…' : logs.length ? 'Choose a log…' : 'No logs in this folder'}</option>
          {missing && selected && <option value={selected}>{selected} (not in this folder)</option>}
          {newestFirst.map((log) => <option key={log.path} value={log.path}>{logLabel(log)}</option>)}
        </select>
      </label>
      <button className="log-bar__btn" onClick={browse}>Browse logs…</button>
      <a className="log-bar__link" href="?view=fetch">Fetch a bundle →</a>
      {error && <span className="log-bar__error" role="alert">{error}</span>}
    </div>
  );
}
