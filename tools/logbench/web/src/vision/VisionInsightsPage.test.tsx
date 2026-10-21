import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { CameraReport, Trend } from './VisionInsightsPage';

describe('vision throughput display', () => {
  it('does not join a line across an unavailable interval or turn unknown into zero', () => {
    const html = renderToStaticMarkup(<Trend duration={3} traces={[{
      label: 'A accepted', field: 'accepted', color: 'blue', points: [
        { t: 0, accepted: null, generated: null, acceptance: null, multitag: null },
        { t: 1, accepted: 5, generated: 5, acceptance: 100, multitag: 100 },
        { t: 2, accepted: null, generated: null, acceptance: null, multitag: null },
        { t: 3, accepted: 0, generated: 0, acceptance: null, multitag: null },
      ],
    }]} />);
    const path = html.match(/<path[^>]*d="([^"]*)"/)?.[1];
    expect(path?.match(/M/g)).toHaveLength(2);
    expect(path).not.toContain('L');
    expect(html).not.toContain('NaN');
  });
  it('keeps the B columns and reports unavailable when a camera exists only in A', () => {
    const html = renderToStaticMarkup(<CameraReport name="Left" duration={3} comparing a={{
      camera: 'Left', generated_count: 10, accepted_count: 0, generated_poses_per_sec: 3.3,
      accepted_poses_per_sec: 0, best_3s_accepted_poses_per_sec: 0, acceptance_pct: 0,
      fps_mean: 100, multitag_health_pct: null, source: 'Test', warnings: [], series: [],
    }} />);
    expect(html).toContain('missing from B');
    expect(html).toContain('B − A');
    expect(html).toContain('Unavailable');
    expect(html).toContain('>0.0<');
  });
});
