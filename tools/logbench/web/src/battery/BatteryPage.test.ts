import { describe, expect, it } from 'vitest';
import { formatValue, observedDelta } from './BatteryPage';

describe('Battery evidence presentation', () => {
  it('does not convert unknown evidence to zero', () => {
    expect(formatValue(null, 'A')).toBe('Unknown');
    expect(formatValue(Number.NaN)).toBe('Unknown');
    expect(formatValue(0, 'A')).toBe('0.00 A');
    expect(observedDelta(null, 20)).toBeNull();
  });
  it('reports signed observed B minus A deltas', () => {
    expect(observedDelta(80, 60)).toBe(-20);
  });
});
