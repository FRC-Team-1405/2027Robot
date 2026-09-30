import type { Preview } from '../api';
import { fmtBytes, fmtTime } from '../lib/format';
import { removeSeg, sortSegs, updateSeg, MIN_SEG, type Seg } from '../lib/segments';
import { NumField } from './NumField';

interface Props {
  segments: Seg[];
  duration: number;
  preview: Preview | null;
  selectedId: string | null;
  cyclePeriodMs: number;
  onSegments: (next: Seg[]) => void;
  onSelect: (id: string | null) => void;
}

/** The resolved segment (server side) that corresponds to this row: snapped to cycles, so its first
 *  cycle is within a cycle period of the row's start. Rows the server skipped (no cycles) match nothing. */
function matchPreview(seg: Seg, preview: Preview | null, periodMs: number) {
  if (!preview) return null;
  const tol = Math.max(0.05, periodMs / 1000 + 0.01);
  let best: (typeof preview.segments)[number] | null = null;
  for (const p of preview.segments) {
    const d = p.orig_first - seg.start;
    if (d >= -0.001 && d <= tol && (!best || p.orig_first < best.orig_first)) best = p;
  }
  return best;
}

export function SegmentTable({ segments, duration, preview, selectedId, cyclePeriodMs, onSegments, onSelect }: Props) {
  const rows = sortSegs(segments);
  if (rows.length === 0) {
    return <p className="empty">Nothing selected yet. Click a mode band on the timeline, or drag across it to keep a range.</p>;
  }
  return (
    <div className="table-wrap">
      <table className="segments">
        <thead>
          <tr>
            <th>Keep</th>
            <th>Start (s)</th>
            <th>End (s)</th>
            <th>Length</th>
            <th title="Extra real cycles kept before the start / after the end, e.g. to keep the disable→enable edge">Pad before / after (ms)</th>
            <th>Cycles</th>
            <th>Size</th>
            <th aria-label="Remove" />
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => {
            const p = matchPreview(s, preview, cyclePeriodMs);
            return (
              <tr key={s.id} className={s.id === selectedId ? 'sel' : ''} onClick={() => onSelect(s.id)}>
                <td>
                  <span className={`chip mode-${s.label}`}>{s.label || 'range'}</span>
                </td>
                <td>
                  <NumField
                    label="Start seconds"
                    value={s.start}
                    min={0}
                    max={s.end - MIN_SEG}
                    onCommit={(v) => onSegments(updateSeg(segments, s.id, { start: v, label: 'manual' }))}
                  />
                </td>
                <td>
                  <NumField
                    label="End seconds"
                    value={s.end}
                    min={s.start + MIN_SEG}
                    max={duration}
                    onCommit={(v) => onSegments(updateSeg(segments, s.id, { end: v, label: 'manual' }))}
                  />
                </td>
                <td className="muted">{fmtTime(s.end - s.start)}</td>
                <td className="pads">
                  <NumField label="Pad before, ms" value={s.padPre} min={0} max={60000} step={20} decimals={0} onCommit={(v) => onSegments(updateSeg(segments, s.id, { padPre: v }))} />
                  <NumField label="Pad after, ms" value={s.padPost} min={0} max={60000} step={20} decimals={0} onCommit={(v) => onSegments(updateSeg(segments, s.id, { padPost: v }))} />
                </td>
                <td className="muted">{p ? p.n_cycles.toLocaleString() : '—'}</td>
                <td className="muted">{p ? fmtBytes(p.bytes) : '—'}</td>
                <td>
                  <button
                    type="button"
                    className="icon-btn"
                    aria-label={`Remove ${s.label || 'range'} ${fmtTime(s.start)} to ${fmtTime(s.end)}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSegments(removeSeg(segments, s.id));
                    }}
                  >
                    ✕
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
