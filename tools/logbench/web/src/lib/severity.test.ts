import { describe, expect, it } from 'vitest';

import { severityColor } from './severity';

const BANDS = [
  { min: 80, color: 'good' },
  { min: 40, color: 'marginal' },
  { min: 0, color: 'bad' },
];

describe('severityColor', () => {
  it('picks the highest band the value clears', () => {
    expect(severityColor(BANDS, 95)).toBe('good');
    expect(severityColor(BANDS, 80)).toBe('good');
    expect(severityColor(BANDS, 79)).toBe('marginal');
    expect(severityColor(BANDS, 40)).toBe('marginal');
    expect(severityColor(BANDS, 0)).toBe('bad');
  });

  it('is gray for an unmeasurable (NaN) value regardless of bands', () => {
    expect(severityColor(BANDS, NaN)).toBe('#6b7280');
  });

  it('falls back to gray below every band (e.g. a negative value with no 0-floor band)', () => {
    expect(severityColor([{ min: 40, color: 'marginal' }], 10)).toBe('#6b7280');
  });
});
