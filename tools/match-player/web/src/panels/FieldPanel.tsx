// Robot position on the field: every pose source, its recent trail, and which AprilTags
// were visible at the playhead.
//
// The static half (field outline, all tag markers) is drawn once into an offscreen
// buffer and blitted; only poses, trails and the lit-tag highlights are redrawn per
// frame. See useCanvas.useOffscreen.

import { useMemo, useRef } from 'react';

import { Cursor, WindowCursor } from '../player/cursor';
import { usePlayer, useFrame, useRepaintOn } from '../player/PlayerContext';
import type { FieldStatic, Panel, PoseSeries } from '../player/types';
import { useCanvas, useOffscreen } from './useCanvas';

const HEIGHT = 430;
const PAD = 28;
const HEADING_M = 0.5; // length of the robot's heading whisker, in field meters

export function FieldPanel({ panel }: { panel: Panel }) {
  const { spec, clock } = usePlayer();
  const { canvasRef, size } = useCanvas(HEIGHT);
  const offscreen = useOffscreen();
  const staticKey = useRef('');

  const field = (spec.static.field ?? { length: 16.5, width: 8.1, tags: {} }) as FieldStatic;
  const trailSec = (panel.options.trail_sec as number) ?? 3;
  const stalenessSec = spec.static.staleness_sec ?? 1;

  // Pose sources and tag sources, resolved once. Cursors live alongside them so each
  // series keeps its own remembered index across frames.
  const sources = useMemo(
    () =>
      (panel.options.pose_tracks as string[] | undefined ?? [])
        .map((id) => {
          const series = spec.series[id] as PoseSeries | undefined;
          if (!series || series.kind !== 'pose2d') return null;
          const track = spec.trackById[id];
          return {
            id,
            label: track?.label ?? id,
            color: track?.color ?? '#888',
            series,
            cursor: new Cursor(series.t),
            window: new WindowCursor(series.t),
          };
        })
        .filter((s): s is NonNullable<typeof s> => s !== null),
    [spec, panel],
  );

  const tagSources = useMemo(
    () =>
      (panel.options.tag_tracks as string[] | undefined ?? [])
        .map((id) => {
          const series = spec.series[id];
          if (!series || series.kind !== 'intset') return null;
          return { series, cursor: new Cursor(series.t) };
        })
        .filter((s): s is NonNullable<typeof s> => s !== null),
    [spec, panel],
  );

  // A resize changes the projection, so the cached static layer and the frame both
  // need redrawing even while paused.
  useRepaintOn([size]);

  const tagEntries = useMemo(
    () => Object.entries(field.tags).map(([id, [x, y]]) => ({ id: Number(id), x, y })),
    [field],
  );

  useFrame((time) => {
    const canvas = canvasRef.current;
    if (!canvas || size.width === 0) return;
    const ctx = canvas.getContext('2d')!;
    const { width, height } = size;

    // Field-meters -> canvas-pixels, aspect preserved (a squashed field misleads).
    const scale = Math.min(
      (width - PAD * 2) / field.length,
      (height - PAD * 2) / field.width,
    );
    const ox = (width - field.length * scale) / 2;
    const oy = (height - field.width * scale) / 2;
    const px = (x: number) => ox + x * scale;
    // Field Y is up; canvas Y is down.
    const py = (y: number) => oy + (field.width - y) * scale;

    // ── Static layer ──────────────────────────────────────────────────────────
    const key = `${width}x${height}@${size.dpr}`;
    const buf = offscreen.get(width, height, size.dpr);
    if (staticKey.current !== key) {
      staticKey.current = key;
      const b = buf.getContext('2d')!;
      b.clearRect(0, 0, width, height);
      b.fillStyle = '#111827';
      b.fillRect(0, 0, width, height);

      b.strokeStyle = '#3f4756';
      b.lineWidth = 1.5;
      b.strokeRect(px(0), py(field.width), field.length * scale, field.width * scale);
      // Midline, for a sense of which half the robot is in.
      b.strokeStyle = '#2b323f';
      b.beginPath();
      b.moveTo(px(field.length / 2), py(field.width));
      b.lineTo(px(field.length / 2), py(0));
      b.stroke();

      for (const tag of tagEntries) {
        b.beginPath();
        b.arc(px(tag.x), py(tag.y), 3.5, 0, Math.PI * 2);
        b.fillStyle = '#39414f';
        b.fill();
      }
    }
    ctx.drawImage(buf, 0, 0, width, height);

    // ── Lit tags ──────────────────────────────────────────────────────────────
    const visible = new Set<number>();
    for (const src of tagSources) {
      const i = src.cursor.seek(time);
      if (i >= 0 && time - src.series.t[i] <= stalenessSec) {
        for (const id of (src.series.v as number[][])[i]) visible.add(id);
      }
    }
    if (visible.size) {
      ctx.font = '10px ui-sans-serif, system-ui, sans-serif';
      ctx.textAlign = 'center';
      for (const tag of tagEntries) {
        if (!visible.has(tag.id)) continue;
        const x = px(tag.x);
        const y = py(tag.y);
        ctx.beginPath();
        ctx.arc(x, y, 6, 0, Math.PI * 2);
        ctx.fillStyle = '#27ae60';
        ctx.fill();
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = '#eafff1';
        ctx.stroke();
        ctx.fillStyle = '#9fe8b8';
        ctx.fillText(String(tag.id), x, y - 9);
      }
    }

    // ── Poses + trails ────────────────────────────────────────────────────────
    for (const src of sources) {
      const { series } = src;
      const [start, end] = src.window.range(time, trailSec);

      if (end >= start) {
        ctx.beginPath();
        for (let i = start; i <= end; i++) {
          const x = px(series.x[i]);
          const y = py(series.y[i]);
          i === start ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.strokeStyle = src.color;
        ctx.globalAlpha = 0.45;
        ctx.lineWidth = 2;
        ctx.lineJoin = 'round';
        ctx.stroke();
        ctx.globalAlpha = 1;
      }

      const i = src.cursor.seek(time);
      if (i < 0 || Math.abs(time - series.t[i]) > stalenessSec) continue;
      const x = px(series.x[i]);
      const y = py(series.y[i]);
      const rot = series.rot[i];

      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + Math.cos(rot) * HEADING_M * scale, y - Math.sin(rot) * HEADING_M * scale);
      ctx.strokeStyle = src.color;
      ctx.lineWidth = 2.5;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(x, y, 6, 0, Math.PI * 2);
      ctx.fillStyle = src.color;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#111827';
      ctx.stroke();
    }

    // ── Legend ────────────────────────────────────────────────────────────────
    ctx.font = '11px ui-sans-serif, system-ui, sans-serif';
    ctx.textAlign = 'left';
    let lx = PAD / 2;
    for (const src of sources) {
      ctx.fillStyle = src.color;
      ctx.beginPath();
      ctx.arc(lx + 4, height - 10, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#98a2b3';
      ctx.fillText(src.label, lx + 12, height - 6);
      lx += ctx.measureText(src.label).width + 30;
    }
  });

  return (
    <div className="panel panel--field">
      <div className="panel__title">
        {panel.title}
        <span className="panel__hint">trail {trailSec}s</span>
      </div>
      <div className="panel__body">
        <canvas
          ref={canvasRef}
          onClick={() => clock.toggle()}
          title="Click to play/pause"
        />
      </div>
    </div>
  );
}
