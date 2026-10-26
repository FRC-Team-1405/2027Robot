// Shown by a page that analyses one log when none is open yet.
import { navigate, resolveView, useRoute } from '../nav/route';
import { rememberReturnView } from './returnView';
import { useLogSelection } from './LogSelection';
import './logs.css';

export function NeedLog({ what }: { what: string }) {
  const { status, missing, selected } = useLogSelection();
  const view = resolveView(useRoute());
  const browse = () => { rememberReturnView(view); navigate({ view: 'logs' }); };
  if (status === 'loading') return <div className="need-log"><p>Looking for logs…</p></div>;
  return <div className="need-log">
    <h1>{missing ? 'That log is not in this folder' : 'No log open'}</h1>
    <p>{missing ? `${selected} is not under the current log folder.` : `Open a log to see ${what}.`} Use the Log menu above, or browse logs by date, size and match.</p>
    <button className="log-bar__btn" onClick={browse}>Browse logs…</button>
  </div>;
}
