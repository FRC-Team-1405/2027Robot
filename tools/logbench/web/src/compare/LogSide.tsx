// One side (A or B) of the comparison: pick a log, see its DS-mode timeline, and
// optionally override the shared --mode selection with a manual [lo, hi] slice for this
// log specifically. Two of these render side by side in ComparePage.
import { useLogInfo } from './useLogInfo';
import type { LogEntry, ManualWindow, Mode } from './types';

const MODE_COLOR: Record<string, string> = {
  disabled: '#374151',
  auto: '#2ecc71',
  teleop: '#3987e5',
};

export function LogSide({
  label,
  logs,
  logPath,
  onLogChange,
  mode,
  manual,
  onManualChange,
}: {
  label: string;
  logs: LogEntry[];
  logPath: string | null;
  onLogChange: (path: string) => void;
  mode: Mode;
  manual: ManualWindow;
  onManualChange: (m: ManualWindow) => void;
}) {
  const info = useLogInfo(logPath);
  const matchingSpan = info?.mode_spans.find((s) => s.mode === mode);

  return (
    <div className="compare-side">
      <div className="compare-side__head">Log {label}</div>
      <select
        className="compare-side__select"
        value={logPath ?? ''}
        onChange={(e) => onLogChange(e.target.value)}
      >
        <option value="" disabled>
          Choose a log…
        </option>
        {logs.map((l) => (
          <option key={l.path} value={l.path}>
            {l.path}
          </option>
        ))}
      </select>

      {info && (
        <>
          <div className="compare-side__meta">
            {info.duration.toFixed(1)}s · {info.cameras.join(', ') || 'no cameras found'}
          </div>
          {info.mode_spans.length > 0 && (
            <div className="compare-timeline" title="Disabled / autonomous / teleop over this log">
              {info.mode_spans.map((s, i) => (
                <div
                  key={i}
                  className="compare-timeline__span"
                  style={{
                    flexGrow: Math.max(s.hi - s.lo, 0.01),
                    background: MODE_COLOR[s.mode] ?? '#4b5563',
                    outline: s.mode === mode ? '2px solid #fff' : 'none',
                  }}
                />
              ))}
            </div>
          )}
        </>
      )}

      {!manual.enabled && mode !== 'whole' && info && (
        matchingSpan ? (
          <div className="compare-side__hint">
            using {mode}: [{matchingSpan.lo.toFixed(1)}, {matchingSpan.hi.toFixed(1)}]s
          </div>
        ) : (
          <div className="compare-side__hint compare-side__hint--warn">no &quot;{mode}&quot; span in this log</div>
        )
      )}

      <label className="compare-side__custom-toggle">
        <input
          type="checkbox"
          checked={manual.enabled}
          onChange={(e) =>
            onManualChange({
              ...manual,
              enabled: e.target.checked,
              hi: manual.hi || info?.duration || manual.hi,
            })
          }
        />
        Custom time slice
      </label>
      {manual.enabled && (
        <div className="compare-side__manual">
          <input
            type="number"
            step="0.1"
            value={manual.lo}
            onChange={(e) => onManualChange({ ...manual, lo: Number(e.target.value) })}
          />
          <span>to</span>
          <input
            type="number"
            step="0.1"
            value={manual.hi}
            onChange={(e) => onManualChange({ ...manual, hi: Number(e.target.value) })}
          />
          <span>s (relative to this log's start)</span>
        </div>
      )}
    </div>
  );
}
