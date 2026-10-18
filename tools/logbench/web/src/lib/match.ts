// Pure helpers for the match timeline: driver-station modes, the match window charts crop to,
// and which recorded video segment covers a moment. Kept free of React so they are unit-tested.
//
// Time bases: the player's playhead is RELATIVE seconds (t - spec.t0). The server ships mode
// windows and video segments in ABSOLUTE log seconds, because that is the recorder's own t_sec
// domain. Every function here that takes a playhead time says so.

import type { ModeWindow, VisionSegment } from '../player/types';

/** Seconds of lead-in / tail kept around the enabled part of a match when charts are cropped. */
export const MATCH_PAD_SEC = 10;

export const MODE_FILL: Record<string, string> = {
  auto: 'rgba(57, 135, 229, 0.20)',
  teleop: 'rgba(46, 204, 113, 0.14)',
};

export const MODE_LABEL: Record<string, string> = { disabled: 'Disabled', auto: 'Auto', teleop: 'Teleop' };

/** Mode windows converted to playhead time. */
export function relativeModes(modes: ModeWindow[] | undefined, specT0: number): ModeWindow[] {
  return (modes ?? []).map((m) => ({ ...m, t0: m.t0 - specT0, t1: m.t1 - specT0 }));
}

/** The mode in effect at a playhead time, or null when the log has no mode data. */
export function modeAt(modes: ModeWindow[] | undefined, specT0: number, playhead: number): string | null {
  if (!modes || modes.length === 0) return null;
  const abs = playhead + specT0;
  for (const m of modes) if (abs >= m.t0 && abs < m.t1) return m.mode;
  return abs < modes[0].t0 ? modes[0].mode : modes[modes.length - 1].mode;
}

/**
 * [lo, hi] in playhead seconds covering the enabled part of the match plus padding, or null when
 * there is nothing to crop (no mode data, never enabled, or the log is already about that long).
 */
export function matchWindow(
  modes: ModeWindow[] | undefined,
  specT0: number,
  duration: number,
  pad = MATCH_PAD_SEC,
): [number, number] | null {
  const enabled = (modes ?? []).filter((m) => m.mode !== 'disabled');
  if (enabled.length === 0) return null;
  const lo = Math.max(0, enabled[0].t0 - specT0 - pad);
  const hi = Math.min(duration, enabled[enabled.length - 1].t1 - specT0 + pad);
  if (lo <= 1 && hi >= duration - 1) return null;
  return [lo, hi];
}

/** The segment whose recorded span contains an ABSOLUTE log time, or null (between sessions). */
export function segmentAt(segments: VisionSegment[] | undefined, abs: number): VisionSegment | null {
  for (const s of segments ?? []) if (abs >= s.t0 && abs < s.t1) return s;
  return null;
}

/** Position in a segment's video for an ABSOLUTE log time. The video's t=0 is the segment's t0. */
export function videoTime(segment: VisionSegment, abs: number): number {
  return abs - segment.t0;
}

/** Playhead seconds of the segment nearest to a time with no video, for a "next recording" hint. */
export function nextSegment(segments: VisionSegment[] | undefined, abs: number): VisionSegment | null {
  for (const s of segments ?? []) if (s.t0 > abs) return s;
  return null;
}

/** CSS background for the scrub bar: auto and teleop tinted along the timeline. */
export function modeGradient(modes: ModeWindow[] | undefined, specT0: number, duration: number): string | undefined {
  const rel = relativeModes(modes, specT0).filter((m) => m.mode !== 'disabled');
  if (rel.length === 0 || duration <= 0) return undefined;
  const solid: Record<string, string> = { auto: '#3987e5', teleop: '#2ecc71' };
  const stops: string[] = ['transparent 0%'];
  for (const m of rel) {
    const a = Math.max(0, Math.min(100, (m.t0 / duration) * 100)).toFixed(2);
    const b = Math.max(0, Math.min(100, (m.t1 / duration) * 100)).toFixed(2);
    const c = solid[m.mode] ?? '#888';
    stops.push(`transparent ${a}%`, `${c} ${a}%`, `${c} ${b}%`, `transparent ${b}%`);
  }
  stops.push('transparent 100%');
  return `linear-gradient(to right, ${stops.join(', ')})`;
}
