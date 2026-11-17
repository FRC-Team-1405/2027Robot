import { describe, expect, it } from 'vitest';
import type { LogDetails, LogEntry } from '../compare/types';
import { filterLogs, sortLogs } from './logList';
import { matchTitle } from './LogBrowserPage';

const log = (name: string, size: number, folder = '', cameras: string[] = []): LogEntry =>
  ({ path: `${folder ? `${folder}/` : ''}${name}`, name, size, mtime: 0, folder, vision_cameras: cameras });
const logs = [
  log('akit_26-10-17_12-36-15_nyroc1_q1.wpilog', 50, 'b-bundle', ['LeftCam']),
  log('akit_26-10-17_15-19-42_nyroc1_q17.wpilog', 30, 'a-bundle'),
  log('akit_26-09-15_22-01-04_visionRecorder1.wpilog', 70),
];

describe('log browser list', () => {
  it('sorts newest first by default and by any column either way', () => {
    expect(sortLogs(logs, { key: 'when', dir: 'desc' }).map((l) => l.size)).toEqual([30, 50, 70]);
    expect(sortLogs(logs, { key: 'when', dir: 'asc' }).map((l) => l.size)).toEqual([70, 50, 30]);
    expect(sortLogs(logs, { key: 'size', dir: 'desc' }).map((l) => l.size)).toEqual([70, 50, 30]);
    expect(sortLogs(logs, { key: 'folder', dir: 'asc' }).map((l) => l.folder)).toEqual(['', 'a-bundle', 'b-bundle']);
    expect(sortLogs(logs, { key: 'name', dir: 'asc' })[0].name).toContain('nyroc1_q1.');
  });

  it('does not reorder the list it was given', () => {
    const before = logs.map((l) => l.path);
    sortLogs(logs, { key: 'size', dir: 'asc' });
    expect(logs.map((l) => l.path)).toEqual(before);
  });

  it('keeps logs matching every word, across name, folder and recorded cameras', () => {
    expect(filterLogs(logs, 'q17')).toHaveLength(1);
    expect(filterLogs(logs, 'nyroc1 leftcam')).toHaveLength(1);
    expect(filterLogs(logs, 'a-bundle')).toHaveLength(1);
    expect(filterLogs(logs, '  ')).toHaveLength(3);
    expect(filterLogs(logs, 'nothing like this')).toHaveLength(0);
  });

  it('also searches what an inspected log contains', () => {
    const details = { [logs[2].path]: { event: 'nydbx', match_type: 'Practice', match_number: 3, cameras: ['RightCam'] } as unknown as LogDetails };
    expect(filterLogs(logs, 'nydbx', details).map((l) => l.path)).toEqual([logs[2].path]);
    expect(filterLogs(logs, 'rightcam practice', details)).toHaveLength(1);
  });

  it('titles a match from whatever the driver station recorded', () => {
    const d = (over: Partial<LogDetails>) => ({ event: null, match_type: null, match_number: null, ...over }) as LogDetails;
    expect(matchTitle(d({ event: 'nyroc1', match_type: 'Qualification', match_number: 17 }))).toBe('nyroc1 · Qualification 17');
    expect(matchTitle(d({ match_number: 4 }))).toBe('Match 4');
    expect(matchTitle(d({}))).toBeNull();
  });
});
