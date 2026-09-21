import { NumField } from './NumField';

interface Props {
  gapMs: number;
  policy: 'compact' | 'preserve';
  cyclePeriodMs: number;
  onGap: (ms: number) => void;
  onPolicy: (p: 'compact' | 'preserve') => void;
}

export function GapControls({ gapMs, policy, cyclePeriodMs, onGap, onPolicy }: Props) {
  const cycles = Math.round(gapMs / cyclePeriodMs);
  return (
    <fieldset className="gap">
      <legend>Between kept periods</legend>
      <label className={`radio ${policy === 'compact' ? 'on' : ''}`}>
        <input type="radio" name="policy" checked={policy === 'compact'} onChange={() => onPolicy('compact')} />
        <span>
          <strong>Close the gap</strong> <em>(recommended)</em>
          <small>
            Keep a short stretch of the real time on each side of every cut and re-time what follows, so the log plays
            straight through with no jump. The original times are saved inside the file.
          </small>
        </span>
      </label>
      {policy === 'compact' && (
        <div className="gap-row">
          <label>
            Real time kept at each cut{' '}
            <NumField label="Gap in milliseconds" value={gapMs} min={0} max={60000} step={20} decimals={0} onCommit={onGap} /> ms
          </label>
          <span className="muted">
            ≈ {cycles} cycle{cycles === 1 ? '' : 's'} at {cyclePeriodMs.toFixed(1)} ms
            {gapMs === 0 && ' — the periods butt up against each other'}
          </span>
        </div>
      )}
      <label className={`radio ${policy === 'preserve' ? 'on' : ''}`}>
        <input type="radio" name="policy" checked={policy === 'preserve'} onChange={() => onPolicy('preserve')} />
        <span>
          <strong>Keep original timestamps</strong>
          <small>Leaves an empty hole where time was cut. Times still line up with other files that share the log&apos;s clock.</small>
        </span>
      </label>
    </fieldset>
  );
}
