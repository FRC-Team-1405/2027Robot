import { describe, expect, it } from 'vitest';

import { cameraOptionLabel, cameraSummaries, matchWindow, modeAt, nextSegment, segmentAt, videoTime } from './match';

// The Q24 shape, absolute log seconds (spec.t0 = 1.6): disabled, auto, pause, teleop, disabled.
const T0 = 1.6;
const MODES = [
  { mode: 'disabled', t0: 1.6, t1: 316.6 },
  { mode: 'auto', t0: 316.6, t1: 326.6 },
  { mode: 'disabled', t0: 326.6, t1: 338.6 },
  { mode: 'teleop', t0: 338.6, t1: 478.6 },
  { mode: 'disabled', t0: 478.6, t1: 555.5 },
];
const DURATION = 555.5 - T0;

describe('modeAt', () => {
  it('reads the playhead as seconds after spec.t0', () => {
    expect(modeAt(MODES, T0, 0)).toBe('disabled');
    expect(modeAt(MODES, T0, 316.6 - T0 + 0.1)).toBe('auto');
    expect(modeAt(MODES, T0, 400)).toBe('teleop');
    expect(modeAt(MODES, T0, DURATION)).toBe('disabled');
  });

  it('is null without mode data', () => {
    expect(modeAt(undefined, T0, 10)).toBeNull();
    expect(modeAt([], T0, 10)).toBeNull();
  });
});

describe('matchWindow', () => {
  it('crops the 315 s disabled lead-in and the tail to the enabled part plus padding', () => {
    const [lo, hi] = matchWindow(MODES, T0, DURATION)!;
    expect(lo).toBeCloseTo(316.6 - T0 - 10, 3);
    expect(hi).toBeCloseTo(478.6 - T0 + 10, 3);
    expect(hi - lo).toBeLessThan(DURATION / 2);
  });

  it('never extends past the log', () => {
    const [lo, hi] = matchWindow([{ mode: 'teleop', t0: 2, t1: 30 }], T0, 60)!;
    expect(lo).toBe(0);
    expect(hi).toBeCloseTo(30 - T0 + 10, 3);
    expect(matchWindow([{ mode: 'teleop', t0: 2, t1: 61.6 }], T0, 60)).toBeNull();
  });

  it('is null when there is nothing to crop', () => {
    expect(matchWindow(undefined, T0, DURATION)).toBeNull();
    expect(matchWindow([{ mode: 'disabled', t0: 1.6, t1: 555.5 }], T0, DURATION)).toBeNull();
    expect(matchWindow([{ mode: 'teleop', t0: 1.6, t1: 555.5 }], T0, DURATION)).toBeNull();
  });
});

describe('video segments', () => {
  const SEGS = [
    { video: 'a.mp4', t0: 317.0, t1: 326.0, session: 'auto' },
    { video: 'b.mp4', t0: 339.0, t1: 400.0, session: 'teleop1' },
    { video: 'c.mp4', t0: 421.0, t1: 478.0, session: 'teleop2' },
  ];

  it('picks the segment by ABSOLUTE log time, so playhead + spec.t0', () => {
    const playhead = 340.0 - T0;
    expect(segmentAt(SEGS, playhead + T0)?.video).toBe('b.mp4');
    // Reading the playhead as absolute would land 1.6 s early -- in the gap before b.mp4.
    expect(segmentAt(SEGS, playhead)).toBeNull();
  });

  it('plays the video from the segment start', () => {
    expect(videoTime(SEGS[1], 340.0)).toBeCloseTo(1.0, 6);
  });

  it('has no segment in a gap, and says which comes next', () => {
    expect(segmentAt(SEGS, 410)).toBeNull();
    expect(nextSegment(SEGS, 410)?.video).toBe('c.mp4');
    expect(nextSegment(SEGS, 500)).toBeNull();
  });

  it('treats a segment end as exclusive', () => {
    expect(segmentAt(SEGS, 326.0)).toBeNull();
    expect(segmentAt(SEGS, 317.0)?.video).toBe('a.mp4');
  });
});

describe('camera status text', () => {
  const SEG = { video: 'a.mp4', t0: 1, t1: 2, session: 's' };
  const STATUS = {
    LeftCam: { state: 'ok', detail: '2 recording sessions', sessions: 2, empty_sessions: 0, folder: 'LeftCam' },
    RightCam: {
      state: 'no_folder',
      detail: 'no recorder folder named RightCam in this bundle (folders found: LeftCam)',
      sessions: 0,
      empty_sessions: 0,
      folder: null,
    },
  };

  it('labels a camera without video with the reason, not just "no recording"', () => {
    expect(cameraOptionLabel('LeftCam', STATUS.LeftCam, true)).toBe('LeftCam');
    expect(cameraOptionLabel('RightCam', STATUS.RightCam, false)).toBe('RightCam (no recorder folder)');
    expect(cameraOptionLabel('X', { ...STATUS.RightCam, state: 'empty' }, false)).toBe('X (only empty sessions)');
    expect(cameraOptionLabel('Y', undefined, false)).toBe('Y (no recording)');
  });

  it('summarises every camera, with coverage when known', () => {
    const rows = cameraSummaries(
      ['LeftCam', 'RightCam'],
      { LeftCam: [SEG, SEG] },
      STATUS,
      { LeftCam: { enabled_sec: 50, covered_sec: 49, fraction: 0.98 } },
    );
    expect(rows[0]).toEqual({ camera: 'LeftCam', ok: true, text: '2 sessions, 98% of enabled time' });
    expect(rows[1].ok).toBe(false);
    expect(rows[1].text).toContain('no recorder folder named RightCam');
  });
});
