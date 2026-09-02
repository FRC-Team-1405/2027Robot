// The playback clock. Deliberately a plain class, not React state.
//
// The whole reason this tool exists is that the previous implementation re-rendered
// everything on every tick. The rule here is: advancing time must not touch React.
// `time` is a mutable field; panels subscribe with a callback and draw to canvas from
// inside it. React re-renders only when something a human did changes the chrome
// (play/pause, speed, a legend toggle) -- a handful of renders per session, not 60/sec.
//
// Time is advanced from real elapsed wall-clock (performance.now deltas), not by adding
// a fixed step per frame. The old tab assumed each tick was exactly 200ms and drifted
// whenever a tick ran long; here a slow frame costs smoothness, never sync.

export type FrameListener = (time: number, dt: number) => void;
export type StateListener = (state: ClockState) => void;

export interface ClockState {
  playing: boolean;
  speed: number;
  time: number;
}

export const SPEEDS = [0.25, 0.5, 1, 2, 4, 8];

/**
 * requestAnimationFrame if there is a compositor, null if there isn't.
 *
 * Returning null (rather than a fake id) matters: `rafId !== null` is what guards
 * against double-scheduling, so handing back a placeholder id would wedge the clock
 * permanently. Where there is no rAF -- unit tests, and any headless use -- frames are
 * driven explicitly through renderNow()/advance() instead.
 */
function scheduleFrame(cb: (now: number) => void): number | null {
  if (typeof requestAnimationFrame !== 'function') return null;
  return requestAnimationFrame(cb);
}

function cancelFrame(id: number): void {
  if (typeof cancelAnimationFrame === 'function') cancelAnimationFrame(id);
}

export class PlayerClock {
  /** Current playhead, in seconds relative to the start of the log. Read every frame. */
  time = 0;
  playing = false;
  speed = 1;

  /** Rolling frames-per-second, for the ?debug=1 overlay. */
  fps = 0;

  private readonly frameListeners = new Set<FrameListener>();
  private readonly stateListeners = new Set<StateListener>();
  private rafId: number | null = null;
  private lastNow = 0;
  private fpsAccum = 0;
  private fpsFrames = 0;

  constructor(public readonly duration: number) {}

  // ── Subscriptions ────────────────────────────────────────────────────────────
  /** Per-frame callback. Canvas panels draw from here and never call setState. */
  onFrame(cb: FrameListener): () => void {
    this.frameListeners.add(cb);
    return () => this.frameListeners.delete(cb);
  }

  /** Coarse callback for React chrome; fires only on play/pause/speed/seek. */
  onState(cb: StateListener): () => void {
    this.stateListeners.add(cb);
    return () => this.stateListeners.delete(cb);
  }

  // ── Transport ────────────────────────────────────────────────────────────────
  play(): void {
    if (this.playing) return;
    // Restart from the top if we're parked at the end, so Play always plays.
    if (this.time >= this.duration - 1e-6) this.time = 0;
    this.playing = true;
    this.lastNow = performance.now();
    this.emitState();
    this.ensureRunning();
  }

  pause(): void {
    if (!this.playing) return;
    this.playing = false;
    this.emitState();
  }

  toggle(): void {
    this.playing ? this.pause() : this.play();
  }

  seek(time: number): void {
    this.time = Math.min(Math.max(time, 0), this.duration);
    this.emitState();
    this.invalidate();
  }

  /** Nudge by a relative amount (arrow keys). */
  step(delta: number): void {
    this.seek(this.time + delta);
  }

  setSpeed(speed: number): void {
    this.speed = speed;
    this.emitState();
  }

  // ── Frame pump ───────────────────────────────────────────────────────────────
  /** Request exactly one repaint. Used when paused and something changed. */
  invalidate(): void {
    if (this.rafId !== null) return;
    this.rafId = scheduleFrame(() => {
      this.rafId = null;
      this.emitFrame(0);
      // A one-shot repaint must not silently stop an in-progress playback.
      if (this.playing) this.ensureRunning();
    });
  }

  private ensureRunning(): void {
    if (this.rafId !== null) return;
    this.lastNow = performance.now();
    const tick = (now: number) => {
      this.rafId = null;
      const dt = (now - this.lastNow) / 1000;
      this.lastNow = now;

      this.fpsAccum += dt;
      this.fpsFrames++;
      if (this.fpsAccum >= 0.25) {
        this.fps = this.fpsFrames / this.fpsAccum;
        this.fpsAccum = 0;
        this.fpsFrames = 0;
      }

      if (this.playing) {
        // Clamp dt so returning to a backgrounded tab doesn't teleport the playhead
        // by however many seconds the tab was hidden.
        this.time += Math.min(dt, 0.25) * this.speed;
        if (this.time >= this.duration) {
          this.time = this.duration;
          this.playing = false;
          this.emitState();
        }
      }

      this.emitFrame(dt);

      if (this.playing) this.rafId = scheduleFrame(tick);
    };
    this.rafId = scheduleFrame(tick);
  }

  /**
   * Draw one frame synchronously, bypassing requestAnimationFrame.
   *
   * For profiling and for automated checks: rAF does not fire in a tab the browser
   * isn't compositing, so this is the only way to exercise the draw path headlessly.
   * Not used by normal playback.
   */
  renderNow(): void {
    this.emitFrame(0);
  }

  /** Advance time by a fixed amount and draw, without rAF. Testing/profiling only. */
  advance(dt: number): void {
    this.time = Math.min(this.time + dt * this.speed, this.duration);
    this.emitFrame(dt);
  }

  private emitFrame(dt: number): void {
    for (const cb of this.frameListeners) cb(this.time, dt);
  }

  private emitState(): void {
    const state: ClockState = { playing: this.playing, speed: this.speed, time: this.time };
    for (const cb of this.stateListeners) cb(state);
  }

  dispose(): void {
    if (this.rafId !== null) cancelFrame(this.rafId);
    this.rafId = null;
    this.frameListeners.clear();
    this.stateListeners.clear();
  }
}
