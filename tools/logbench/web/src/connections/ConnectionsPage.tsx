import { useEffect, useRef, useState } from 'react';
import type { RemoteJob } from '../fetch/types';

interface Device {
  host: string; name: string; user: string; port: number; address: string;
  source_address: string; photonvision: boolean; ssh: boolean; login: string;
  recordings: string; identity: string; model: string; hostname: string; detail: string;
}
interface Scan {
  interfaces: { name: string; address: string; network: string; up: boolean }[];
  devices: Device[]; notes: string[]; targets_checked: number;
}

export function ConnectionsPage() {
  const [target, setTarget] = useState('');
  const [result, setResult] = useState<Scan | null>(null);
  const [progress, setProgress] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const jobId = useRef<string | null>(null);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);

  const scan = async () => {
    setBusy(true); setError(''); setResult(null); setProgress('Starting scan…');
    try {
      const response = await fetch('/api/connections/scan/jobs', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target }),
      });
      const started = await response.json();
      if (!response.ok) throw new Error(started.detail ?? `HTTP ${response.status}`);
      jobId.current = started.job_id;
      while (alive.current) {
        const r = await fetch(`/api/remote/jobs/${started.job_id}`);
        const job = await r.json() as RemoteJob;
        if (!r.ok) throw new Error(job.error ?? `HTTP ${r.status}`);
        if (!alive.current) return;
        setProgress(job.phase);
        if (job.status === 'complete') { setResult(job.result as unknown as Scan); return; }
        if (job.status === 'error' || job.status === 'cancelled') {
          throw new Error(job.error ?? 'Scan cancelled.');
        }
        await new Promise(resolve => window.setTimeout(resolve, 300));
      }
    } catch (e) {
      if (alive.current) setError((e as Error).message);
    } finally {
      jobId.current = null;
      if (alive.current) setBusy(false);
    }
  };

  return <main className="fetch-page">
    <h1 className="fetch-page__title">Connections</h1>
    <p>Find Orange Pis on this computer’s connected IPv4 networks. The roboRIO does not need to be online.</p>
    <form className="connections-form" onSubmit={event => { event.preventDefault(); void scan(); }}>
      <label htmlFor="connection-target">Optional Pi IP or subnet</label>
      <input id="connection-target" value={target} onChange={e => setTarget(e.target.value)}
        placeholder="10.14.5.11 or 192.168.1.0/24" disabled={busy} />
      <button className="fetch-run" disabled={busy}>{busy ? 'Scanning…' : 'Scan connections'}</button>
      {busy && <button type="button" onClick={async () => {
        if (jobId.current) await fetch(`/api/remote/jobs/${jobId.current}`, { method: 'DELETE' });
      }}>Cancel</button>}
    </form>
    <p className="fetch-hint">Automatic scans cover active private IPv4 subnets of /22 or smaller, plus configured targets.
      For larger networks (including 169.254.x.x), enter the Pi IP or a smaller subnet.</p>
    {busy && <p role="status">{progress}</p>}
    {error && <p role="alert" className="fetch-row__error">{error}</p>}
    {result && <>
      <section className="fetch-section">
        <h2>Local adapters</h2>
        <p className="fetch-hint">These are the adapters on the computer running Logbench.</p>
        <div className="connections-scroll"><table className="fetch-pi-table"><thead><tr>
          <th>Adapter</th><th>Address</th><th>Subnet</th><th>Link</th>
        </tr></thead><tbody>{result.interfaces.map(i => <tr key={`${i.name}/${i.address}`}>
          <td>{i.name}</td><td>{i.address}</td><td>{i.network}</td><td>{i.up ? 'Up' : 'Down'}</td>
        </tr>)}</tbody></table></div>
      </section>
      <section className="fetch-section">
        <h2>Devices ({result.devices.length})</h2>
        <p>{result.targets_checked} addresses checked. An open port alone does not identify an Orange Pi.</p>
        {result.devices.length === 0 && <p>No devices found.</p>}
        {result.devices.map(d => <article className="connections-device" key={d.host}>
          <h3>{d.hostname || d.name || d.host} <small>— {d.identity}</small></h3>
          <p><code>{d.address || d.host}</code> · Laptop source: <code>{d.source_address || 'unavailable'}</code></p>
          <dl className="connections-checks">
            <div><dt>PhotonVision :5800</dt><dd>{d.photonvision ? 'Reachable' : 'No response'}</dd></div>
            <div><dt>SSH :{d.port}</dt><dd>{d.ssh ? 'Reachable' : 'No response'}</dd></div>
            <div><dt>Login as {d.user}</dt><dd>{d.login}</dd></div>
            <div><dt>Recordings</dt><dd>{d.recordings}</dd></div>
          </dl>
          <p>{d.detail}</p>
          {d.ssh && <p>SSH command: <code>ssh -p {d.port} {d.user}@{d.address}</code></p>}
        </article>)}
      </section>
      {result.notes.map(note => <p className="fetch-hint" key={note}>{note}</p>)}
    </>}
    <section className="fetch-section">
      <h2>Direct Ethernet troubleshooting</h2>
      <p>A cable alone does not put both machines on the same IP subnet. Check the Ethernet adapter above;
        if the Pi uses a static 10.14.5.x address, the laptop needs an unused 10.14.5.x address with a matching netmask.
        If Wi-Fi and Ethernet use the same subnet, the Laptop source field helps reveal which route is being used.</p>
      <p>SSH reachable with login rejected points to credentials. Login working with recordings unavailable points to the folder or permissions.</p>
      <a href="?view=fetch">Fetch logs and recordings →</a>
    </section>
  </main>;
}
