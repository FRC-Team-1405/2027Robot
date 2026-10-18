// Pure view logic for the Health Check page, kept out of the component so it is unit-tested.

import type { CheckRow, Counts, HealthReport, Section, Status, Subject, Verdict } from './types';

// Distinct shapes as well as colours, so red/amber/green are readable without colour vision.
export const STATUS_ICON: Record<Status, string> = {
  ok: '✔',
  warn: '▲',
  fail: '✖',
  nodata: '?',
  na: '–',
};

export const STATUS_WORD: Record<Status, string> = {
  ok: 'OK',
  warn: 'Warning',
  fail: 'Problem',
  nodata: 'No data',
  na: 'Not applicable',
};

const RANK: Record<Status, number> = { na: -1, ok: 0, nodata: 1, warn: 2, fail: 3 };

export function rank(status: Status): number {
  return RANK[status];
}

export function worse(a: Status, b: Status): boolean {
  return RANK[a] > RANK[b];
}

/** Rows and groups that need a look start open; everything fine starts collapsed. */
export function startsOpen(status: Status): boolean {
  return status === 'warn' || status === 'fail';
}

export function plural(n: number, one: string, many = one + 's'): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** "2 problems · 1 warning · 14 OK · 3 no data" -- zero counts are left out. */
export function summarize(counts: Counts): string {
  const parts: string[] = [];
  if (counts.fail) parts.push(plural(counts.fail, 'problem'));
  if (counts.warn) parts.push(plural(counts.warn, 'warning'));
  if (counts.ok) parts.push(`${counts.ok} OK`);
  if (counts.nodata) parts.push(`${counts.nodata} no data`);
  return parts.join(' · ') || 'nothing checked';
}

export interface VerdictView {
  headline: string;
  tone: 'ok' | 'warn' | 'fail' | 'nodata';
  hint: string;
}

export function verdictView(verdict: Verdict, kind: 'live' | 'log'): VerdictView {
  const subject = kind === 'live' ? 'the robot' : 'this match';
  switch (verdict) {
    case 'ok':
      return { headline: kind === 'live' ? 'All checks passing' : 'Nothing stands out', tone: 'ok', hint: `Every check on ${subject} is green.` };
    case 'warn':
      return { headline: 'Check these before going', tone: 'warn', hint: 'Nothing has failed, but some readings are outside their normal range.' };
    case 'fail':
      return { headline: 'Problems found', tone: 'fail', hint: `Something on ${subject} is outside its limits. Open the red sections.` };
    case 'incomplete':
      return { headline: 'Incomplete', tone: 'nodata', hint: 'Everything that reported is fine, but some checks had no data. Grey rows say why.' };
    default:
      return { headline: 'No checks configured', tone: 'nodata', hint: 'health_checks.toml has no valid checks.' };
  }
}

/** Live only: a row that is fine now but was not earlier since the last Reset. */
export function latchNote(row: CheckRow): string | null {
  if (!row.worst || !worse(row.worst, row.status)) return null;
  const was = STATUS_WORD[row.worst].toLowerCase();
  return row.peak_display ? `was ${was} since reset (peak ${row.peak_display})` : `was ${was} since reset`;
}

/** Keep only rows that are not fine (for the "problems only" toggle). Empty subjects/groups/sections go. */
export function onlyProblems(sections: Section[]): Section[] {
  const bad = (c: CheckRow) => c.status === 'warn' || c.status === 'fail' || Boolean(latchNote(c));
  const out: Section[] = [];
  for (const sec of sections) {
    const groups = [];
    for (const grp of sec.groups) {
      const subjects: Subject[] = [];
      for (const sub of grp.subjects) {
        const checks = sub.checks.filter(bad);
        if (checks.length) subjects.push({ ...sub, checks });
      }
      if (subjects.length) groups.push({ ...grp, subjects });
    }
    if (groups.length) out.push({ ...sec, groups });
  }
  return out;
}

/** Drop rows that do not apply here (a live-only check on a log, a log-only check live). Emptied
 *  subjects, groups and sections go too, so the page is not padded with "only applies to a live robot". */
export function hideNotApplicable(sections: Section[]): Section[] {
  const out: Section[] = [];
  for (const sec of sections) {
    const groups = [];
    for (const grp of sec.groups) {
      const subjects: Subject[] = [];
      for (const sub of grp.subjects) {
        const checks = sub.checks.filter((c) => c.status !== 'na');
        if (checks.length) subjects.push({ ...sub, checks });
      }
      if (subjects.length) groups.push({ ...grp, subjects });
    }
    if (groups.length) out.push({ ...sec, groups });
  }
  return out;
}

export function modesLine(report: HealthReport): string {
  const modes = report.meta?.modes ?? [];
  const secs = (mode: string) => modes.filter((m) => m.mode === mode).reduce((t, m) => t + (m.end - m.start), 0);
  const auto = secs('auto');
  const teleop = secs('teleop');
  if (!auto && !teleop) return '';
  return `auto ${auto.toFixed(0)} s · teleop ${teleop.toFixed(0)} s`;
}

export function toggleKey(...parts: string[]): string {
  return parts.join('\u0001');
}
