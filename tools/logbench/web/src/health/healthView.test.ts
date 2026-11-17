import { describe, expect, it } from 'vitest';

import { hideNotApplicable, latchNote, modesLine, onlyProblems, startsOpen, summarize, verdictView, worse } from './healthView';
import type { CheckRow, HealthReport, Section, Status } from './types';

const row = (status: Status, extra: Partial<CheckRow> = {}): CheckRow => ({
  id: 'c', key: 'k', section: 'S', group: 'G', subject: '', label: 'L', status, value: 1, display: '1', unit: '',
  rule: 'info only', detail: '', help: '', ...extra,
});

const counts = (over: Partial<Record<Status, number>> = {}) => ({ ok: 0, warn: 0, fail: 0, nodata: 0, na: 0, ...over });

describe('summarize', () => {
  it('lists problems first and leaves zero counts out', () => {
    expect(summarize(counts({ fail: 2, warn: 1, ok: 14, nodata: 3 }))).toBe('2 problems · 1 warning · 14 OK · 3 no data');
    expect(summarize(counts({ ok: 5 }))).toBe('5 OK');
    expect(summarize(counts({ fail: 1 }))).toBe('1 problem');
    expect(summarize(counts({ na: 4 }))).toBe('nothing checked');
  });
});

describe('status ordering', () => {
  it('ranks problem over warning over no-data over ok', () => {
    expect(worse('fail', 'warn')).toBe(true);
    expect(worse('warn', 'nodata')).toBe(true);
    expect(worse('nodata', 'ok')).toBe(true);
    expect(worse('ok', 'na')).toBe(true);
    expect(worse('ok', 'ok')).toBe(false);
  });

  it('opens only the things that need a look', () => {
    expect(['ok', 'warn', 'fail', 'nodata', 'na'].map((s) => startsOpen(s as Status))).toEqual([false, true, true, false, false]);
  });
});

describe('verdictView', () => {
  it('words the verdict for the live robot and for a log', () => {
    expect(verdictView('ok', 'live').headline).toBe('All checks passing');
    expect(verdictView('ok', 'log').headline).toBe('Nothing stands out');
    expect(verdictView('fail', 'live')).toMatchObject({ tone: 'fail', headline: 'Problems found' });
    expect(verdictView('incomplete', 'log').tone).toBe('nodata');
    expect(verdictView('empty', 'live').headline).toBe('No checks configured');
  });
});

describe('latchNote', () => {
  it('says when a row was worse earlier, with the peak', () => {
    expect(latchNote(row('ok', { worst: 'fail', peak_display: '95 %' }))).toBe('was problem since reset (peak 95 %)');
    expect(latchNote(row('ok', { worst: 'warn' }))).toBe('was warning since reset');
  });

  it('is silent when nothing worse happened, or in a log', () => {
    expect(latchNote(row('ok', { worst: 'ok' }))).toBeNull();
    expect(latchNote(row('fail', { worst: 'fail' }))).toBeNull();
    expect(latchNote(row('ok'))).toBeNull();
  });
});

describe('onlyProblems', () => {
  const sections: Section[] = [
    {
      id: 'A', label: 'A', status: 'fail', counts: counts(),
      groups: [
        { label: 'g1', status: 'fail', counts: counts(), subjects: [
          { label: 'm1', status: 'fail', counts: counts(), checks: [row('ok'), row('fail', { id: 'bad' })] },
          { label: 'm2', status: 'ok', counts: counts(), checks: [row('ok')] },
        ] },
        { label: 'g2', status: 'ok', counts: counts(), subjects: [{ label: '', status: 'ok', counts: counts(), checks: [row('nodata')] }] },
      ],
    },
    { id: 'B', label: 'B', status: 'ok', counts: counts(), groups: [
      { label: 'g', status: 'ok', counts: counts(), subjects: [{ label: '', status: 'ok', counts: counts(), checks: [row('ok')] }] },
    ] },
  ];

  it('keeps only warning and problem rows and drops emptied containers', () => {
    const out = onlyProblems(sections);
    expect(out.map((s) => s.id)).toEqual(['A']);
    expect(out[0].groups.map((g) => g.label)).toEqual(['g1']);
    expect(out[0].groups[0].subjects.map((s) => s.label)).toEqual(['m1']);
    expect(out[0].groups[0].subjects[0].checks.map((c) => c.id)).toEqual(['bad']);
  });

  it('keeps a row that is fine now but was bad earlier (live latch)', () => {
    const latched: Section[] = [{ id: 'A', label: 'A', status: 'ok', counts: counts(), groups: [
      { label: 'g', status: 'ok', counts: counts(), subjects: [{ label: '', status: 'ok', counts: counts(), checks: [row('ok', { worst: 'warn' })] }] },
    ] }];
    expect(onlyProblems(latched)).toHaveLength(1);
  });
});

describe('hideNotApplicable', () => {
  const sub = (label: string, ...checks: CheckRow[]) => ({ label, status: 'ok' as Status, counts: counts(), checks });
  const sections: Section[] = [
    { id: 'A', label: 'A', status: 'ok', counts: counts(), groups: [
      { label: 'g1', status: 'ok', counts: counts(), subjects: [sub('', row('ok'), row('na', { id: 'live-only' }))] },
      { label: 'g2', status: 'na', counts: counts(), subjects: [sub('', row('na'))] },
    ] },
    { id: 'B', label: 'B', status: 'na', counts: counts(), groups: [
      { label: 'g', status: 'na', counts: counts(), subjects: [sub('', row('na'))] },
    ] },
  ];

  it('removes not-applicable rows and anything left empty by that', () => {
    const out = hideNotApplicable(sections);
    expect(out.map((s) => s.id)).toEqual(['A']);
    expect(out[0].groups.map((g) => g.label)).toEqual(['g1']);
    expect(out[0].groups[0].subjects[0].checks.map((c) => c.status)).toEqual(['ok']);
  });
});

describe('modesLine', () => {
  it('summarises auto and teleop time for a log', () => {
    const report = { kind: 'log', verdict: 'ok', counts: counts(), sections: [], meta: { modes: [
      { mode: 'disabled', start: 0, end: 315 }, { mode: 'auto', start: 315, end: 325 }, { mode: 'teleop', start: 338, end: 478 },
    ] } } as HealthReport;
    expect(modesLine(report)).toBe('auto 10 s · teleop 140 s');
    expect(modesLine({ ...report, meta: {} })).toBe('');
  });
});
