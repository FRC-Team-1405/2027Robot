import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { CameraReport, ScoreCard, ThroughputOverview, Trend } from './VisionInsightsPage';

const tracking = (accepted: number | null, coverage: number | null = 40) => ({
  basis: 'generated', active_sec: 4, span_count: 1, coverage_pct: coverage, spans: [{ lo: 0, hi: 4 }],
  generated_poses_per_sec: accepted == null ? null : accepted * 2, accepted_poses_per_sec: accepted, acceptance_pct: 50,
});

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
      fps_mean: 100, multitag_health_pct: null, source: 'Test', warnings: [], series: [], tracking: tracking(0),
    }} />);
    expect(html).toContain('missing from B');
    expect(html).toContain('B − A');
    expect(html).toContain('Unavailable');
    expect(html).toContain('>0.0<');
  });
  it('draws one accepted line per camera plus a combined total, each in its own color', () => {
    const cam = (camera: string, rate: number) => ({
      camera, generated_count: 20, accepted_count: 10, generated_poses_per_sec: 2 * rate, accepted_poses_per_sec: rate,
      best_3s_accepted_poses_per_sec: null, acceptance_pct: 50, fps_mean: 90, multitag_health_pct: null, source: 'Test', warnings: [], tracking: tracking(rate),
      series: [0, 1, 2].map(t => ({ t, accepted: rate, generated: 2 * rate, acceptance: 50, multitag: null })),
    });
    const report = { log: 'x', window: { lo: 0, hi: 2, duration: 2 }, rolling_sec: 1, tracking_gap_sec: 1, tracking: tracking(7), notes: [], cameras: [cam('Left', 3), cam('Right', 4)] };
    const html = renderToStaticMarkup(<ThroughputOverview reports={[report, null]} cameras={['Left', 'Right']} duration={2} showGenerated={false} />);
    expect(html.match(/<path /g)).toHaveLength(3);
    expect(new Set(html.match(/<path[^>]*stroke="([^"]*)"/g)).size).toBe(3);
    expect(html).toContain('All cameras accepted');
    expect(html).not.toContain('generated');
  });
  it('shows A, B and the difference on a comparison scorecard', () => {
    const s = (accepted: number) => ({ tracking_accepted: accepted, tracking_generated: 9, tracking_acceptance: 50, coverage_pct: 40, active_sec: 4, average_accepted: 1, best_3s_accepted: null });
    const html = renderToStaticMarkup(<ScoreCard name="Left" color="red" comparing a={s(4)} b={s(6.5)} />);
    expect(html).toContain('+2.5');
    expect(html).toContain('accepted poses/sec while tracking');
    expect(html).toContain('Tracking coverage');
  });
  it('shades the time nothing was tracking, and only that time', () => {
    const point = { t: 0, accepted: 1, generated: 1, acceptance: 100, multitag: null };
    const html = renderToStaticMarkup(<Trend duration={10} shade={[{ lo: 0, hi: 2 }, { lo: 6, hi: 10 }]} shadeLabel="not tracking" traces={[{ label: 'x', field: 'accepted', color: 'red', points: [point] }]} />);
    expect(html.match(/class="vision-idle"/g)?.length).toBe(3); // two shaded spans plus the legend swatch
    expect(html).toContain('not tracking');
  });
});
