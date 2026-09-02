// Play/pause, speed, scrub, and the time readout.
//
// The scrub thumb and the clock text have to move every frame, but re-rendering them
// through React state would put a component render on the hot path -- the exact thing
// this design avoids. So both are updated by writing to the DOM node directly from the
// frame callback. React renders this component only when playing/speed changes.

import { useRef } from 'react';

import { SPEEDS } from '../player/clock';
import { usePlayer, useClockState, useFrame } from '../player/PlayerContext';

function fmt(seconds: number): string {
  const s = Math.max(0, seconds);
  const m = Math.floor(s / 60);
  return `${m}:${(s - m * 60).toFixed(1).padStart(4, '0')}`;
}

export function TransportBar({ debug }: { debug: boolean }) {
  const { clock } = usePlayer();
  const { playing, speed } = useClockState();
  const scrubRef = useRef<HTMLInputElement | null>(null);
  const timeRef = useRef<HTMLSpanElement | null>(null);
  const fpsRef = useRef<HTMLSpanElement | null>(null);
  const dragging = useRef(false);

  useFrame((time) => {
    // While the user is dragging, the input is the source of truth -- don't fight them.
    if (scrubRef.current && !dragging.current) {
      scrubRef.current.value = String(time);
    }
    if (timeRef.current) {
      timeRef.current.textContent = `${fmt(time)} / ${fmt(clock.duration)}`;
    }
    if (fpsRef.current) {
      fpsRef.current.textContent = `${clock.fps.toFixed(0)} fps`;
    }
  });

  return (
    <div className="transport">
      <button
        className="transport__btn transport__btn--primary"
        onClick={() => clock.toggle()}
        title="Play/pause (space)"
      >
        {playing ? '⏸' : '▶'}
      </button>
      <button
        className="transport__btn"
        onClick={() => {
          clock.pause();
          clock.seek(0);
        }}
        title="Back to start (0)"
      >
        ⏮
      </button>

      <input
        ref={scrubRef}
        className="transport__scrub"
        type="range"
        min={0}
        max={clock.duration}
        step={0.01}
        defaultValue={0}
        onPointerDown={() => {
          dragging.current = true;
        }}
        onPointerUp={() => {
          dragging.current = false;
        }}
        onChange={(e) => clock.seek(Number(e.target.value))}
        title="Scrub"
      />

      <span className="transport__time" ref={timeRef}>
        0:00.0
      </span>

      <label className="transport__speed">
        <select value={speed} onChange={(e) => clock.setSpeed(Number(e.target.value))}>
          {SPEEDS.map((s) => (
            <option key={s} value={s}>
              {s}×
            </option>
          ))}
        </select>
      </label>

      {debug && <span className="transport__fps" ref={fpsRef} />}
    </div>
  );
}
