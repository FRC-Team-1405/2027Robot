// Current score per group, with the robot's own explanation when it couldn't measure.
//
// The one panel that is DOM rather than canvas, and therefore the one that re-renders.
// It is throttled to 10Hz: text changing 60 times a second is unreadable, so the extra
// 50 renders would cost frame budget and buy nothing.

import { useMemo } from 'react';

import { severityColor } from '../lib/severity';
import { Cursor, sampleAt } from '../player/cursor';
import { usePlayer, useThrottledTime } from '../player/PlayerContext';
import type { Panel, ScalarSeries, StringSeries } from '../player/types';

export function ReadoutPanel({ panel }: { panel: Panel }) {
  const { spec } = usePlayer();
  const time = useThrottledTime(10);

  const stalenessSec = spec.static.staleness_sec ?? 1;
  const bands = spec.static.severity ?? [];
  const reasonFor = (panel.options.reason_for ?? {}) as Record<string, string>;

  const rows = useMemo(
    () =>
      panel.tracks
        .map((id) => {
          const series = spec.series[id] as ScalarSeries | undefined;
          if (!series || series.kind !== 'scalar') return null;
          const reasonId = reasonFor[id];
          const reason = spec.series[reasonId] as StringSeries | undefined;
          return {
            id,
            label: spec.trackById[id].label,
            series,
            cursor: new Cursor(series.t),
            reason: reason?.kind === 'string' ? reason : undefined,
            reasonCursor: reason?.kind === 'string' ? new Cursor(reason.t) : undefined,
          };
        })
        .filter((r): r is NonNullable<typeof r> => r !== null),
    [spec, panel, reasonFor],
  );

  return (
    <div className="panel panel--readout">
      <div className="panel__title">{panel.title}</div>
      <div className="readout">
        {rows.map((row) => {
          const value = sampleAt(row.series.t, row.series.v, row.cursor, time, stalenessSec);
          let reason = '';
          if (row.reason && row.reasonCursor) {
            const i = row.reasonCursor.seek(time);
            if (i >= 0) reason = row.reason.v[i];
          }
          // A non-empty reason means the robot is telling us the score is not a real
          // measurement -- show its explanation instead of a misleading number.
          // (health_display.is_unmeasurable does the same thing on the Python side.)
          const unmeasurable = Number.isNaN(value) || reason !== '';
          const color = severityColor(bands, unmeasurable ? NaN : value);
          return (
            <div className="readout__row" key={row.id}>
              <div className="readout__label">{row.label}</div>
              <div className="readout__value" style={{ color }}>
                {unmeasurable ? 'n/a' : value.toFixed(0)}
              </div>
              <div className="readout__bar">
                <div
                  className="readout__fill"
                  style={{
                    width: unmeasurable ? '0%' : `${Math.max(0, Math.min(100, value))}%`,
                    background: color,
                  }}
                />
              </div>
              {reason && <div className="readout__reason">{reason}</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
