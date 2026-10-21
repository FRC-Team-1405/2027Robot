import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { CameraCard } from '../pit/CameraCard';
import type { CameraReading } from '../pit/types';
import { parseHealthReport, parseLiveSnapshot } from './healthData';

export const reportFixture = (kind = 'live') => ({ kind, verdict: 'ok', sections: [{
  id: 'system', label: 'System', status: 'warn', groups: [{ label: '', status: 'warn', subjects: [{
    label: '', status: 'warn', checks: [{ id: 'cpu', key: 'cpu', label: 'CPU load', status: 'warn', display: '72 %' }],
  }] }],
}] });

describe('health API data', () => {
  it('renders null, absent and non-finite camera readings without converting them to zero', () => {
    for (const missing of [null, undefined, NaN, Infinity, 'broken']) {
      const reading = { current_fps: missing, health_score: missing, health_stillness: missing,
        health_reason: '', visible_tag_ids: null } as unknown as CameraReading;
      const html = renderToStaticMarkup(<CameraCard name="Right" reading={reading} bands={[]} />);
      expect(html).toContain('n/a fps');
      expect(html).not.toContain('NaN');
      expect(html).not.toContain('Infinity');
      expect(html).not.toContain('>0<');
    }
  });
  it('keeps valid zero readings visible', () => {
    const parsed = parseLiveSnapshot({ cameras: { Right: { current_fps: 0, health_score: 0, health_reason: '', health_area: 0 } } });
    const html = renderToStaticMarkup(<CameraCard name="Right" reading={parsed.value.cameras.Right} bands={[]} />);
    expect(html).toContain('0 fps');
    expect(html).toContain('>0<');
  });
  it('keeps good cameras and normalizes malformed fields with a warning', () => {
    const parsed = parseLiveSnapshot({ cameras: { Good: { health_score: 100, current_fps: 'bad', visible_tag_ids: [7, null] }, Bad: null } });
    expect(parsed.value.cameras.Good).toMatchObject({ health_score: 100, current_fps: null, visible_tag_ids: [7] });
    expect(parsed.value.cameras.Bad).toBeUndefined();
    expect(parsed.warnings).toHaveLength(2);
  });
  it('keeps good sections but does not report all-green when another section is malformed', () => {
    const raw = reportFixture();
    const parsed = parseHealthReport({ ...raw, sections: [...raw.sections, { label: 'Bad', groups: null }] });
    expect(parsed.value.counts).toMatchObject({ warn: 1, nodata: 1 });
    expect(parsed.value.verdict).toBe('warn');
    expect(parsed.value.sections[0].groups[0].subjects[0].checks[0].display).toBe('72 %');
    expect(parsed.warnings).toHaveLength(1);
    raw.sections[0].groups[0].subjects[0].checks[0].status = 'ok';
    expect(parseHealthReport({ ...raw, sections: [...raw.sections, null] }).value.verdict).toBe('incomplete');
  });
  it('rejects invalid envelopes and nested statuses before they reach render functions', () => {
    for (const body of [null, [], {}, { kind: 'live', sections: null }]) expect(() => parseHealthReport(body)).toThrow();
    expect(() => parseLiveSnapshot({ cameras: null })).toThrow();
    const raw = reportFixture();
    raw.sections[0].groups[0].subjects[0].checks[0].status = 'unknown';
    expect(parseHealthReport(raw).warnings).toHaveLength(1);
  });
});
