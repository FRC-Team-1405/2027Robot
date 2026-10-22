import { describe, expect, it } from 'vitest';
import { formatDuration, formatSize, logLabel, logTime, parseLogName } from './logName';

describe('log names', () => {
  it('reads the recorder start time and the event/match tail from a competition log name', () => {
    const parsed = parseLogName('akit_26-10-17_12-36-15_nyroc1_q1.wpilog');
    expect(parsed.tag).toBe('nyroc1 q1');
    expect(parsed.when?.getFullYear()).toBe(2026);
    expect(parsed.when?.getMonth()).toBe(9);
    expect(parsed.when?.getHours()).toBe(12);
    expect(parseLogName('FRC_20261017_123615.wpilog').when).toBeNull();
  });

  it('copes with no tail, trimmed copies and unrecognised names', () => {
    expect(parseLogName('akit_26-10-17_12-36-15.wpilog').tag).toBe('');
    expect(parseLogName('akit_26-10-17_12-36-15_q1.trimmed.wpilog').tag).toBe('q1');
    expect(parseLogName('my_test_run.wpilog')).toEqual({ when: null, tag: 'my test run' });
  });

  it('dates a log by its name, falling back to the file time', () => {
    expect(logTime({ name: 'akit_26-10-17_12-36-15.wpilog', mtime: 0 })).toBe(new Date(2026, 9, 17, 12, 36, 15).getTime());
    expect(logTime({ name: 'odd.wpilog', mtime: 100 })).toBe(100000);
  });

  it('formats sizes, durations and menu labels', () => {
    expect(formatSize(49_618_944)).toBe('49.6 MB');
    expect(formatSize(1200)).toBe('1 KB');
    expect(formatDuration(155)).toBe('2:35');
    expect(logLabel({ path: 'x/akit_26-10-17_12-36-15_nyroc1_q1.wpilog', name: 'akit_26-10-17_12-36-15_nyroc1_q1.wpilog', size: 49_618_944, mtime: 0 }))
      .toContain('nyroc1 q1 · 49.6 MB');
  });
});
