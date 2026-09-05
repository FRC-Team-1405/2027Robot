// Third top-level view (see App.tsx's ?view= switch): the pit/field "hold the robot
// still and look at one camera" check, live over NetworkTables. Replaces
// camera-calibration's Tab 5 (Live Health) -- same connection UX (team number or
// address, NT root table), but through logbench's FastAPI backend instead of a
// Streamlit process, so it can eventually share layout/severity conventions with the
// replay and compare views instead of maintaining a third copy of them.
import { useEffect, useState } from 'react';

import { CameraCard } from './CameraCard';
import { usePitConnection } from './usePitConnection';
import type { SeverityBand } from '../lib/severity';

const DEFAULT_ROOT_TABLE = 'AdvantageKit';

export function PitCheckPage() {
  const { status, error, snapshot, connect, disconnect } = usePitConnection();
  const [server, setServer] = useState('');
  const [rootTable, setRootTable] = useState(DEFAULT_ROOT_TABLE);
  const [bands, setBands] = useState<SeverityBand[]>([]);

  useEffect(() => {
    fetch('/api/metric-catalog')
      .then((r) => r.json())
      .then((d) => setBands(d.severity ?? []));
  }, []);

  const cameras = snapshot ? Object.entries(snapshot.cameras) : [];

  return (
    <div className="pit-page">
      <div className="pit-page__head">
        <h1 className="pit-page__title">Pit Check</h1>
        <a href={window.location.pathname}>← Back to replay</a>
      </div>
      <p className="pit-page__hint">
        Hold the robot still with a tag in view. This is a calibration diagnostic, not a
        match-accuracy score -- it's the same VisionHealth.java score the robot already
        computes, read live over NetworkTables.
      </p>

      <div className="pit-connect">
        <input
          className="pit-connect__input"
          placeholder="Team number or IP address"
          value={server}
          onChange={(e) => setServer(e.target.value)}
          disabled={status === 'connected' || status === 'connecting'}
        />
        <input
          className="pit-connect__input"
          placeholder="NT root table"
          value={rootTable}
          onChange={(e) => setRootTable(e.target.value)}
          disabled={status === 'connected' || status === 'connecting'}
        />
        {status === 'connected' ? (
          <button className="pit-connect__btn" onClick={disconnect}>
            Disconnect
          </button>
        ) : (
          <button
            className="pit-connect__btn pit-connect__btn--primary"
            disabled={!server || status === 'connecting'}
            onClick={() => connect(server, rootTable)}
          >
            {status === 'connecting' ? 'Connecting…' : 'Connect'}
          </button>
        )}
        <span className={`pit-status pit-status--${status}`}>
          {status === 'connected' && (snapshot?.nt_connected ? 'connected' : 'client started, waiting for server…')}
          {status === 'connecting' && 'connecting…'}
          {status === 'disconnected' && 'not connected'}
          {status === 'error' && 'error'}
        </span>
      </div>

      {status === 'error' && (
        <div className="status status--error">
          <strong>Could not connect.</strong>
          <pre>{error}</pre>
        </div>
      )}

      {snapshot && snapshot.nt_connected && (
        <div className="pit-drivetrain">
          speed: {snapshot.lin_speed.toFixed(2)} m/s · {snapshot.ang_speed.toFixed(2)} rad/s
          {Math.abs(snapshot.lin_speed) > 0.06 || Math.abs(snapshot.ang_speed) > 0.06 ? (
            <span className="pit-drivetrain__warn"> -- hold the robot still for a clean reading</span>
          ) : null}
        </div>
      )}

      {cameras.length > 0 && (
        <div className="pit-cards">
          {cameras.map(([name, reading]) => (
            <CameraCard key={name} name={name} reading={reading} bands={bands} />
          ))}
        </div>
      )}
    </div>
  );
}
