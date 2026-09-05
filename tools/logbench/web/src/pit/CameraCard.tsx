// One camera's live readout: the robot's own score, the derived motion_score, and the
// eight-factor breakdown so a bad score is immediately traceable -- same idea as the
// replay view's ReadoutPanel + per-camera trend chart, just live instead of scrubbed.
import { severityColor, type SeverityBand } from '../lib/severity';
import { FACTOR_FIELDS, type CameraReading } from './types';

function Bar({ label, value, bands }: { label: string; value: number; bands: SeverityBand[] }) {
  const unmeasurable = Number.isNaN(value);
  const color = severityColor(bands, unmeasurable ? NaN : value);
  return (
    <div className="readout__row">
      <div className="readout__label">{label}</div>
      <div className="readout__value" style={{ color, fontSize: 13 }}>
        {unmeasurable ? 'n/a' : value.toFixed(0)}
      </div>
      <div className="readout__bar">
        <div
          className="readout__fill"
          style={{ width: unmeasurable ? '0%' : `${Math.max(0, Math.min(100, value))}%`, background: color }}
        />
      </div>
    </div>
  );
}

export function CameraCard({
  name,
  reading,
  bands,
}: {
  name: string;
  reading: CameraReading;
  bands: SeverityBand[];
}) {
  const unmeasurable = Number.isNaN(reading.health_score) || reading.health_reason !== '';

  return (
    <div className="pit-card">
      <div className="pit-card__head">
        <span className={`pit-dot${reading.connected ? ' pit-dot--on' : ''}`} />
        <strong>{name}</strong>
        <span className="pit-card__fps">{reading.current_fps.toFixed(0)} fps</span>
        <span className="pit-card__tags">
          {reading.visible_tag_ids.length > 0 ? `tags ${reading.visible_tag_ids.join(', ')}` : 'no tag'}
        </span>
      </div>

      <div className="readout">
        <Bar label="Score (robot)" value={unmeasurable ? NaN : reading.health_score} bands={bands} />
        <Bar
          label="Motion score"
          value={reading.motion_score === null ? NaN : reading.motion_score}
          bands={bands}
        />
        {reading.health_reason && <div className="readout__reason">{reading.health_reason}</div>}
      </div>

      <div className="readout pit-card__factors">
        {FACTOR_FIELDS.map(({ key, label }) => (
          <Bar key={key} label={label} value={reading[key] as number} bands={bands} />
        ))}
      </div>
    </div>
  );
}
