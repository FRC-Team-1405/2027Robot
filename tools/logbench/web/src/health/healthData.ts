// Runtime validation at the API boundary. TypeScript types alone do not validate JSON.
import type { CameraReading, LiveSnapshot } from '../pit/types';
import { FACTOR_FIELDS } from '../pit/types';
import type { Parsed } from '../lib/request';
import type { CheckRow, Counts, HealthReport, Section, Status } from './types';

type Obj = Record<string, unknown>;
function object(value: unknown): Obj {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Expected an object in the server response.');
  return value as Obj;
}
const text = (value: unknown) => typeof value === 'string' ? value : '';
const numeric = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;
const statuses: Status[] = ['ok', 'warn', 'fail', 'nodata', 'na'];
function status(value: unknown): Status {
  if (!statuses.includes(value as Status)) throw new Error('A check has an invalid status.');
  return value as Status;
}
const counts = (): Counts => ({ ok: 0, warn: 0, fail: 0, nodata: 0, na: 0 });
function tally(rows: { counts: Counts }[]): Counts {
  const result = counts();
  for (const row of rows) for (const key of statuses) result[key] += row.counts[key];
  return result;
}
function list(value: unknown): unknown[] {
  if (!Array.isArray(value)) throw new Error('A list is missing from the server response.');
  return value;
}

export function parseHealthReport(body: unknown): Parsed<HealthReport> {
  const data = object(body);
  if (data.kind !== 'live' && data.kind !== 'log') throw new Error('The health report has an invalid kind.');
  const warnings: string[] = [];
  const sections = list(data.sections).map((item, i): Section => {
    try {
      const section = object(item);
      const groups = list(section.groups).map((item) => {
        const group = object(item);
        const subjects = list(group.subjects).map((item) => {
          const subject = object(item);
          const checks = list(subject.checks).map((item): CheckRow => {
            const row = object(item);
            const state = status(row.status);
            return {
              id: text(row.id), key: text(row.key), section: text(row.section), group: text(row.group), subject: text(row.subject),
              label: text(row.label), status: state, display: text(row.display), unit: text(row.unit), rule: text(row.rule),
              detail: text(row.detail), help: text(row.help),
              value: typeof row.value === 'string' || typeof row.value === 'boolean' ? row.value : numeric(row.value),
              worst: row.worst == null ? undefined : status(row.worst), peak: numeric(row.peak) ?? undefined,
              peak_display: text(row.peak_display),
            };
          });
          const total = counts(); for (const check of checks) total[check.status]++;
          return { label: text(subject.label), status: status(subject.status), counts: total, checks };
        });
        return { label: text(group.label), status: status(group.status), counts: tally(subjects), subjects };
      });
      return { id: text(section.id) || `section-${i}`, label: text(section.label), status: status(section.status), counts: tally(groups), groups };
    } catch {
      const label = item && typeof item === 'object' ? text((item as Obj).label) : '';
      warnings.push(`${label || `Health section ${i + 1}`} returned invalid data. Other sections are still shown.`);
      return { id: `invalid-${i}`, label: label || `Health section ${i + 1}`, status: 'nodata', counts: { ...counts(), nodata: 1 }, groups: [] };
    }
  });
  const total = tally(sections);
  const verdict = total.fail ? 'fail' : total.warn ? 'warn' : total.nodata ? 'incomplete' : total.ok || total.na ? 'ok' : 'empty';
  const meta = data.meta == null ? {} : object(data.meta);
  return { warnings, value: {
    kind: data.kind, sections, counts: total, verdict, connected: data.connected === true,
    config_errors: Array.isArray(data.config_errors) ? data.config_errors.filter((v): v is string => typeof v === 'string') : [],
    meta: { log: text(meta.log), duration: numeric(meta.duration) ?? undefined, topics: numeric(meta.topics) ?? undefined,
      robot: meta.robot === 'auto' || meta.robot === 'teleop' || meta.robot === 'disabled' ? meta.robot : null,
      modes: Array.isArray(meta.modes) ? meta.modes.flatMap((item) => {
        if (!item || typeof item !== 'object') return [];
        const mode = item as Obj;
        return typeof mode.mode === 'string' && numeric(mode.start) !== null && numeric(mode.end) !== null
          ? [{ mode: mode.mode, start: mode.start as number, end: mode.end as number }] : [];
      }) : [],
    },
  } };
}

export function parseLiveSnapshot(body: unknown): Parsed<LiveSnapshot> {
  const data = object(body);
  const cameras: Record<string, CameraReading> = {};
  const warnings: string[] = [];
  for (const [name, raw] of Object.entries(object(data.cameras))) {
    try {
      const camera = object(raw);
      const values = Object.fromEntries(FACTOR_FIELDS.map(({ key }) => [key, numeric(camera[key])]));
      const keys = [...FACTOR_FIELDS.map(({ key }) => key), 'current_fps', 'health_score', 'motion_score'];
      if (keys.some((key) => camera[key] != null && numeric(camera[key]) === null)
          || (camera.visible_tag_ids != null && (!Array.isArray(camera.visible_tag_ids) || camera.visible_tag_ids.some((v) => !Number.isInteger(v))))) {
        warnings.push(`Camera ${name} has invalid readings; unavailable values are shown as n/a.`);
      }
      cameras[name] = {
        ...values, connected: camera.connected === true, current_fps: numeric(camera.current_fps),
        health_score: numeric(camera.health_score), motion_score: numeric(camera.motion_score), health_reason: text(camera.health_reason),
        visible_tag_ids: Array.isArray(camera.visible_tag_ids) ? camera.visible_tag_ids.filter((v): v is number => Number.isInteger(v)) : [],
      } as CameraReading;
    } catch { warnings.push(`Camera ${name} returned invalid data. Other cameras are still shown.`); }
  }
  return { warnings, value: { nt_connected: data.nt_connected === true, lin_speed: numeric(data.lin_speed),
    ang_speed: numeric(data.ang_speed), cross_score: numeric(data.cross_score), cross_reason: text(data.cross_reason), cameras } };
}
