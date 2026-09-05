// Health factors over the whole log, with a playhead.
//
// This panel is the direct answer to what made the old tab unusable. The traces are
// identical on every frame -- only the playhead line and the value dots move -- so the
// traces are rasterized once into an offscreen buffer and blitted. Per frame the work
// is: one drawImage, one vertical line, and one dot per visible track. The Streamlit
// version rebuilt all ~135k points as Plotly JSON five times a second to achieve the
// same picture.
//
// The static buffer is invalidated only by a resize or a legend toggle.

import { useMemo, useRef, useState } from 'react';

import { Cursor } from '../player/cursor';
import { usePlayer, useFrame, useRepaintOn } from '../player/PlayerContext';
import type { Panel, ScalarSeries, StringSeries } from '../player/types';
import { useCanvas, useOffscreen } from './useCanvas';

const HEIGHT = 200;
const PAD_L = 34;
const PAD_R = 10;
const PAD_T = 8;
const PAD_B = 20;
const MOVING_AVERAGE_SEC = 5;

function valueAt(series: StringSeries, time: number): string {
  let lo = 0;
  let hi = series.t.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >>> 1;
    if (series.t[mid] <= time) lo = mid + 1;
    else hi = mid - 1;
  }
  return hi >= 0 ? series.v[hi] : '';
}

function unavailable(reason: string): boolean {
  const normalized = reason.toLowerCase();
  return normalized.includes('no tag') || normalized.includes('not connected');
}

export function TimeSeriesPanel({ panel, expanded = false }: { panel: Panel; expanded?: boolean }) {
  const { spec, clock, hidden, toggleTrack } = usePlayer();
  const height = expanded ? 300 : HEIGHT;
  const { canvasRef, size } = useCanvas(height);
  const offscreen = useOffscreen();
  const staticKey = useRef('');
  const [view, setView] = useState<[number, number]>([0, spec.duration]);
  const [hoverTime, setHoverTime] = useState<number | null>(null);
  const [tagSamplesOnly, setTagSamplesOnly] = useState(false);
  const [movingAverage, setMovingAverage] = useState(true);

  const duration = spec.duration;
  const stalenessSec = spec.static.staleness_sec ?? 1;

  const tracks = useMemo(
    () =>
      panel.tracks
        .map((id) => {
          const series = spec.series[id] as ScalarSeries | undefined;
          if (!series || series.kind !== 'scalar') return null;
          const track = spec.trackById[id];
          return {
            id,
            label: track.label,
            color: track.color ?? '#8ab4f8',
            // The headline score is drawn heavier than the eight contributing factors.
            weight: id.endsWith('/score') ? 2 : 1.1,
            series,
            cursor: new Cursor(series.t),
          };
        })
        .filter((t): t is NonNullable<typeof t> => t !== null),
    [spec, panel],
  );

  // Resize invalidates the cached traces; a legend toggle changes which are drawn.
  const domain = (panel.options.domain as [number, number] | undefined) ?? [0, 100];
  const reasonTrack = panel.options.reason_track as string | undefined;
  const reasonSeries = reasonTrack ? spec.series[reasonTrack] as StringSeries | undefined : undefined;

  // The average always follows the selected base mode. In particular, Tag samples is
  // transformed first, then smoothed, so it never silently reintroduces unavailable values.
  const displayValues = useMemo(() => {
    const byTrack: Record<string, Float64Array> = {};
    for (const tr of tracks) {
      const values = Float64Array.from(tr.series.v);
      if (tagSamplesOnly && reasonSeries) {
        let held = Number.NaN;
        for (let i = 0; i < values.length; i++) {
          if (Number.isNaN(values[i])) continue;
          if (unavailable(valueAt(reasonSeries, tr.series.t[i]))) values[i] = held;
          else held = values[i];
        }
      }
      if (!movingAverage) {
        byTrack[tr.id] = values;
        continue;
      }
      const averaged = new Float64Array(values.length);
      let start = 0;
      let sum = 0;
      let count = 0;
      for (let i = 0; i < values.length; i++) {
        const value = values[i];
        if (Number.isNaN(value)) {
          averaged[i] = Number.NaN;
          start = i + 1;
          sum = 0;
          count = 0;
          continue;
        }
        sum += value;
        count++;
        while (start < i && tr.series.t[start] < tr.series.t[i] - MOVING_AVERAGE_SEC) {
          if (!Number.isNaN(values[start])) {
            sum -= values[start];
            count--;
          }
          start++;
        }
        averaged[i] = count ? sum / count : Number.NaN;
      }
      byTrack[tr.id] = averaged;
    }
    return byTrack;
  }, [tracks, tagSamplesOnly, movingAverage, reasonSeries]);

  useRepaintOn([size, hidden, view, tagSamplesOnly, movingAverage]);

  useFrame((time) => {
    const canvas = canvasRef.current;
    if (!canvas || size.width === 0) return;
    const ctx = canvas.getContext('2d')!;
    const { width, height } = size;

    const plotW = width - PAD_L - PAD_R;
    const plotH = height - PAD_T - PAD_B;
    const tx = (t: number) => PAD_L + ((t - view[0]) / (view[1] - view[0])) * plotW;
    const vy = (v: number) =>
      PAD_T + plotH - ((v - domain[0]) / (domain[1] - domain[0])) * plotH;

    // ── Static layer: grid, axis labels, every trace ──────────────────────────
    const visibleIds = tracks.filter((t) => !hidden.has(t.id)).map((t) => t.id).join(',');
    const key = `${width}x${height}@${size.dpr}|${visibleIds}|${view.join(':')}|${tagSamplesOnly}|${movingAverage}`;
    const buf = offscreen.get(width, height, size.dpr);
    if (staticKey.current !== key) {
      staticKey.current = key;
      const b = buf.getContext('2d')!;
      b.clearRect(0, 0, width, height);
      b.fillStyle = '#111827';
      b.fillRect(0, 0, width, height);

      b.strokeStyle = '#242c3a';
      b.lineWidth = 1;
      b.font = '10px ui-sans-serif, system-ui, sans-serif';
      b.fillStyle = '#5d6779';
      b.textAlign = 'right';
      for (let i = 0; i <= 4; i++) {
        const v = domain[0] + ((domain[1] - domain[0]) * i) / 4;
        const y = Math.round(vy(v)) + 0.5;
        b.beginPath();
        b.moveTo(PAD_L, y);
        b.lineTo(width - PAD_R, y);
        b.stroke();
        b.fillText(String(Math.round(v)), PAD_L - 5, y + 3);
      }

      b.textAlign = 'center';
      const tickCount = Math.max(2, Math.min(10, Math.floor(plotW / 90)));
      for (let i = 0; i <= tickCount; i++) {
        const t = view[0] + ((view[1] - view[0]) * i) / tickCount;
        b.fillText(`${t.toFixed(0)}s`, tx(t), height - 6);
      }

      for (const tr of tracks) {
        if (hidden.has(tr.id)) continue;
        const { t } = tr.series;
        const v = displayValues[tr.id];
        b.beginPath();
        b.strokeStyle = tr.color;
        b.lineWidth = tr.weight;
        b.lineJoin = 'round';
        let pen = false;
        for (let i = 0; i < t.length; i++) {
          const value = v[i];
          // NaN = "could not measure". Lift the pen so the chart shows a gap rather
          // than a straight line implying data that was never there.
          if (Number.isNaN(value)) {
            pen = false;
            continue;
          }
          if (t[i] < view[0] || t[i] > view[1]) continue;
          const x = tx(t[i]);
          const y = vy(value);
          if (!pen) {
            b.moveTo(x, y);
            pen = true;
          } else {
            b.lineTo(x, y);
          }
        }
        b.stroke();
      }

      // An unavailable camera/tag is status, not a quality value. The lane keeps that
      // distinction visible in either display mode without forcing every trace to zero.
      if (reasonSeries) {
        const laneY = PAD_T + plotH - 3;
        let start = view[0];
        let reason = valueAt(reasonSeries, start);
        for (let i = 0; i < reasonSeries.t.length && reasonSeries.t[i] <= view[1]; i++) {
          const next = reasonSeries.t[i];
          if (next <= view[0]) {
            reason = reasonSeries.v[i];
            continue;
          }
          if (unavailable(reason)) {
            b.fillStyle = reason.toLowerCase().includes('connected') ? '#c0392b' : '#b7791f';
            b.fillRect(tx(start), laneY, tx(next) - tx(start), 3);
          }
          start = next;
          reason = reasonSeries.v[i];
        }
        if (unavailable(reason)) {
          b.fillStyle = reason.toLowerCase().includes('connected') ? '#c0392b' : '#b7791f';
          b.fillRect(tx(start), laneY, tx(view[1]) - tx(start), 3);
        }
      }
    }
    ctx.drawImage(buf, 0, 0, width, height);

    // ── Per-frame layer: playhead + current value dots ────────────────────────
    const x = Math.round(tx(time)) + 0.5;
    ctx.beginPath();
    ctx.moveTo(x, PAD_T);
    ctx.lineTo(x, PAD_T + plotH);
    ctx.strokeStyle = '#e74c3c';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    for (const tr of tracks) {
      if (hidden.has(tr.id)) continue;
      let i = tr.cursor.seek(time);
      if (i < 0) continue;
      if (tagSamplesOnly && reasonSeries && unavailable(valueAt(reasonSeries, time))) {
        while (i >= 0 && unavailable(valueAt(reasonSeries, tr.series.t[i]))) i--;
      }
      if (i < 0) continue;
      const value = displayValues[tr.id][i];
      if (Number.isNaN(value) || (!tagSamplesOnly && time - tr.series.t[i] > stalenessSec)) continue;
      ctx.beginPath();
      ctx.arc(x, vy(value), 3, 0, Math.PI * 2);
      ctx.fillStyle = tr.color;
      ctx.fill();
    }
  });

  const timeAt = (clientX: number) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return null;
    const x = Math.max(PAD_L, Math.min(rect.width - PAD_R, clientX - rect.left));
    return view[0] + ((x - PAD_L) / (rect.width - PAD_L - PAD_R)) * (view[1] - view[0]);
  };
  const zoom = (factor: number, focus = (view[0] + view[1]) / 2) => {
    const span = Math.max(0.25, Math.min(duration, (view[1] - view[0]) * factor));
    const ratio = (focus - view[0]) / (view[1] - view[0]);
    const start = Math.max(0, Math.min(duration - span, focus - span * ratio));
    setView([start, start + span]);
  };
  const sampleAt = hoverTime === null ? [] : tracks.filter((tr) => !hidden.has(tr.id)).map((tr) => {
    const i = tr.cursor.seek(hoverTime);
    const value = i >= 0 ? displayValues[tr.id][i] : NaN;
    return { id: tr.id, label: tr.label, color: tr.color, value };
  }).filter((sample) => !Number.isNaN(sample.value));
  const hoverReason = hoverTime !== null && reasonSeries ? valueAt(reasonSeries, hoverTime) : '';

  return (
    <div className={`panel panel--timeseries${expanded ? ' panel--timeseries-expanded' : ''}`}>
      <div className="panel__title">{panel.title}</div>
      {expanded && <div className="chart-controls" aria-label={`${panel.title} display mode`}>
        <button
          className={tagSamplesOnly ? 'chart-controls__mode chart-controls__mode--active' : 'chart-controls__mode'}
          onClick={() => setTagSamplesOnly((value) => !value)}
          title={tagSamplesOnly ? 'Show all samples, including no-tag and disconnected intervals' : 'Hold the last value through no-tag and disconnected intervals'}
        >
          {tagSamplesOnly ? 'Tag samples' : 'All samples'}
        </button>
        <button
          className={movingAverage ? 'chart-controls__mode chart-controls__mode--active' : 'chart-controls__mode'}
          onClick={() => setMovingAverage((value) => !value)}
          title={movingAverage ? 'Show the selected sample mode without smoothing' : 'Show a trailing 5-second moving average of the selected sample mode'}
        >
          {movingAverage ? '5s average' : 'No average'}
        </button>
      </div>}
      <div className="panel__body panel__chart-body">
        <canvas
          ref={canvasRef}
          onClick={(e) => { const t = timeAt(e.clientX); if (t !== null) clock.seek(t); }}
          onPointerMove={(e) => setHoverTime(timeAt(e.clientX))}
          onPointerLeave={() => setHoverTime(null)}
          onWheel={(e) => {
            if (!expanded || !e.shiftKey) return;
            e.preventDefault();
            const focus = timeAt(e.clientX) ?? (view[0] + view[1]) / 2;
            zoom(e.deltaY < 0 ? 0.7 : 1 / 0.7, focus);
          }}
          title={expanded ? 'Click to seek. Hold Shift and scroll to zoom around the cursor.' : 'Click to seek'}
        />
        {expanded && hoverTime !== null && (
          <div className="chart-tooltip">
            <strong>{hoverTime.toFixed(1)}s</strong>
            {unavailable(hoverReason) && <span className="chart-tooltip__status">Status: {hoverReason}</span>}
            {sampleAt.map((sample) => <span key={sample.id}><i style={{ background: sample.color }} />{sample.label}: {sample.value.toFixed(2)}%</span>)}
          </div>
        )}
      </div>
      <div className="legend">
        {tracks.map((tr) => (
          <button
            key={tr.id}
            className={`legend__item${hidden.has(tr.id) ? ' legend__item--off' : ''}`}
            onClick={() => toggleTrack(tr.id)}
            title={hidden.has(tr.id) ? `Show ${tr.label}` : `Hide ${tr.label}`}
          >
            <span className="legend__swatch" style={{ background: tr.color }} />
            {tr.label}
          </button>
        ))}
      </div>
    </div>
  );
}
