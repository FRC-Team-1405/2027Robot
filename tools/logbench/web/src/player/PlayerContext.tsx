// React bindings for the clock and spec. Thin on purpose -- see clock.ts for why the
// clock itself is not React state.

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';

import { PlayerClock, type ClockState } from './clock';
import type { Spec } from './types';

interface PlayerContextValue {
  spec: Spec;
  clock: PlayerClock;
  /** Track ids the user has hidden. Changing this re-renders panels (rare, deliberate). */
  hidden: ReadonlySet<string>;
  toggleTrack: (trackId: string) => void;
}

const Ctx = createContext<PlayerContextValue | null>(null);

export function PlayerProvider({ spec, children }: { spec: Spec; children: ReactNode }) {
  const clock = useMemo(() => new PlayerClock(spec.duration), [spec]);
  const [hidden, setHidden] = useState<ReadonlySet<string>>(
    () => new Set(spec.tracks.filter((t) => t.hidden).map((t) => t.id)),
  );

  useEffect(() => () => clock.dispose(), [clock]);

  // Under ?debug=1, hand the clock and spec to the console. Lets playback be driven
  // and inspected without the rAF loop -- useful when profiling, and the only way to
  // exercise drawing in an automated/headless context, where rAF never fires.
  useEffect(() => {
    if (!new URLSearchParams(window.location.search).has('debug')) return;
    (window as unknown as Record<string, unknown>).__player = { clock, spec };
    return () => {
      delete (window as unknown as Record<string, unknown>).__player;
    };
  }, [clock, spec]);

  // Keyboard transport. Bound at the window so it works no matter which panel has
  // focus, but yields to text inputs so typing in a future filter box isn't hijacked.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return;
      switch (e.key) {
        case ' ':
          e.preventDefault();
          clock.toggle();
          break;
        case 'ArrowLeft':
          e.preventDefault();
          clock.step(e.shiftKey ? -10 : -1);
          break;
        case 'ArrowRight':
          e.preventDefault();
          clock.step(e.shiftKey ? 10 : 1);
          break;
        case ',':
          clock.step(-0.02);
          break;
        case '.':
          clock.step(0.02);
          break;
        case 'Home':
        case '0':
          clock.seek(0);
          break;
        case 'End':
          clock.seek(clock.duration);
          break;
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [clock]);

  const value = useMemo<PlayerContextValue>(
    () => ({
      spec,
      clock,
      hidden,
      toggleTrack: (trackId: string) =>
        setHidden((prev) => {
          const next = new Set(prev);
          next.has(trackId) ? next.delete(trackId) : next.add(trackId);
          return next;
        }),
    }),
    [spec, clock, hidden],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function usePlayer(): PlayerContextValue {
  const v = useContext(Ctx);
  if (!v) throw new Error('usePlayer must be used inside a PlayerProvider');
  return v;
}

/**
 * Subscribe to the per-frame tick. The callback is kept in a ref so panels can close
 * over fresh props without resubscribing (and without the effect re-running) every
 * render.
 *
 * Draw to canvas from here. Calling setState from this callback re-introduces exactly
 * the per-frame React work this whole design exists to avoid.
 */
export function useFrame(cb: (time: number, dt: number) => void): void {
  const { clock } = usePlayer();
  const ref = useRef(cb);
  ref.current = cb;
  useEffect(() => {
    const unsub = clock.onFrame((t, dt) => ref.current(t, dt));
    clock.invalidate(); // paint once on mount so a paused player isn't blank
    return unsub;
  }, [clock]);
}

/**
 * Force one repaint when something that changes the picture but not the time changes --
 * a resize, a legend toggle.
 *
 * Necessary because a paused player pumps no frames: without this, a canvas that first
 * measured itself as zero-width (the layout hasn't settled on the mount tick) would
 * stay blank until the user pressed play.
 */
export function useRepaintOn(deps: unknown[]): void {
  const { clock } = usePlayer();
  useEffect(() => {
    clock.invalidate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clock, ...deps]);
}

/**
 * Subscribe to transport state for chrome that genuinely needs to re-render (the
 * play/pause button's label, the speed selector). Fires on user actions only.
 */
export function useClockState(): ClockState {
  const { clock } = usePlayer();
  const [state, setState] = useState<ClockState>({
    playing: clock.playing,
    speed: clock.speed,
    time: clock.time,
  });
  useEffect(() => clock.onState(setState), [clock]);
  return state;
}

/**
 * A value derived from the playhead, sampled on a throttle. For text readouts: the
 * numbers are unreadable above ~10Hz anyway, so re-rendering them at 60Hz buys nothing
 * and costs the frame budget.
 */
export function useThrottledTime(hz = 10): number {
  const { clock } = usePlayer();
  const [time, setTime] = useState(clock.time);
  const last = useRef(-Infinity);
  useFrame((t) => {
    const now = performance.now();
    if (now - last.current >= 1000 / hz) {
      last.current = now;
      setTime(t);
    }
  });
  return time;
}
