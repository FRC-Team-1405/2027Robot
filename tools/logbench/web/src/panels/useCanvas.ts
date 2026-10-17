// Canvas sizing shared by every drawing panel.
//
// Two things every canvas here needs and neither is free: a backing store scaled to
// devicePixelRatio (otherwise everything is blurry on a laptop screen), and a redraw
// when the element resizes. Both are handled once, here.

import { useEffect, useRef, useState } from 'react';

export interface CanvasSize {
  /** CSS pixels -- draw in these units; the DPR transform is already applied. */
  width: number;
  height: number;
  dpr: number;
}

export function useCanvas(height: number) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [size, setSize] = useState<CanvasSize>({ width: 0, height, dpr: 1 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement!;

    const apply = () => {
      const dpr = window.devicePixelRatio || 1;
      const width = parent.clientWidth;
      if (width === 0) return;
      const pw = Math.round(width * dpr);
      const ph = Math.round(height * dpr);
      // Assigning canvas.width resets the bitmap even when the value is unchanged, so
      // this must be guarded: ResizeObserver fires once on observe(), and an
      // unconditional assignment there would blank whatever was just drawn -- with no
      // state change to trigger a repaint, leaving the panel permanently empty.
      if (canvas.width !== pw || canvas.height !== ph) {
        canvas.width = pw;
        canvas.height = ph;
      }
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      const ctx = canvas.getContext('2d')!;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      setSize((prev) =>
        prev.width === width && prev.height === height && prev.dpr === dpr
          ? prev
          : { width, height, dpr },
      );
    };

    apply();
    const ro = new ResizeObserver(apply);
    ro.observe(parent);
    return () => ro.disconnect();
  }, [height]);

  return { canvasRef, size };
}

/**
 * An offscreen canvas for content that does not change between frames.
 *
 * This is the trick that makes playback cheap. A trend chart's traces are identical on
 * every frame -- only the playhead moves -- so they are drawn once into this buffer and
 * blitted each frame with a single drawImage. Redrawing the polylines per frame is
 * precisely what made the Streamlit version unusable.
 */
export function useOffscreen(): { get: (w: number, h: number, dpr: number) => HTMLCanvasElement } {
  const ref = useRef<HTMLCanvasElement | null>(null);
  return {
    get(w: number, h: number, dpr: number) {
      let c = ref.current;
      if (!c) {
        c = document.createElement('canvas');
        ref.current = c;
      }
      const pw = Math.round(w * dpr);
      const ph = Math.round(h * dpr);
      if (c.width !== pw || c.height !== ph) {
        c.width = pw;
        c.height = ph;
      }
      const ctx = c.getContext('2d')!;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return c;
    },
  };
}
