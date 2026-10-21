import { useEffect, useRef, useState } from 'react';
import { LogSide } from '../compare/LogSide';
import type { ManualWindow, Mode } from '../compare/types';
import { useLogSelection } from '../logpicker/LogSelection';
import { OrderNotice } from '../loader/OrderNotice';
import './vision.css';

type Point = { t: number; generated: number | null; accepted: number | null; acceptance: number | null; multitag: number | null };
type Span = { lo: number; hi: number };
type Tracking = {
  basis: string | null; active_sec: number; span_count: number; coverage_pct: number | null; spans: Span[];
  generated_poses_per_sec: number | null; accepted_poses_per_sec: number | null; acceptance_pct: number | null;
};
type Camera = {
  camera: string; generated_count: number | null; accepted_count: number | null;
  generated_poses_per_sec: number | null; accepted_poses_per_sec: number | null;
  best_3s_accepted_poses_per_sec: number | null; acceptance_pct: number | null;
  fps_mean: number | null; multitag_health_pct: number | null;
  source: string; warnings: string[]; series: Point[]; tracking: Tracking;
};
type Report = {
  log: string; window: { lo: number; hi: number; duration: number }; rolling_sec: number; tracking_gap_sec: number;
  tracking: Tracking; cameras: Camera[]; notes: string[]; order?: { n_late: number; late_pct: number; max_late_ms: number } | null;
};
type Trace = { label: string; points: Point[]; field: keyof Omit<Point, 't'>; color: string; dash?: string; width?: number };
/** What a scorecard shows. The headline is the rate while tracking; the whole-interval average is kept for context. */
type Summary = {
  tracking_accepted: number | null; tracking_generated: number | null; tracking_acceptance: number | null;
  coverage_pct: number | null; active_sec: number; average_accepted: number | null; best_3s_accepted: number | null;
};
const emptyWindow = (): ManualWindow => ({ enabled: false, lo: 0, hi: 0 });
const fmt = (n: number | null | undefined, digits = 1) => n == null ? 'Unavailable' : n.toFixed(digits);

// Every chart answers a different question, so each gets its own colors. Within a chart solid = run A and dashed = run B;
// dotted = generated (summary chart only).
const B_DASH = '7 4', GENERATED_DASH = '2 4';
const CAMERA_COLORS = ['#60a5fa', '#f472b6', '#f87171', '#94a3b8'];
const TOTAL_COLOR = '#e2e8f0';
const THROUGHPUT_COLORS = { accepted: '#4ade80', generated: '#fbbf24' };
const QUALITY_COLORS = { acceptance: '#c084fc', multitag: '#2dd4bf' };
const cameraColor = (index: number) => CAMERA_COLORS[index % CAMERA_COLORS.length];

const sumOf = (values: (number | null)[]) => values.length === 0 || values.some(v => v == null) ? null : (values as number[]).reduce((x, y) => x + y, 0);
const cameraSummary = (c: Camera): Summary => ({
  tracking_accepted: c.tracking.accepted_poses_per_sec, tracking_generated: c.tracking.generated_poses_per_sec,
  tracking_acceptance: c.tracking.acceptance_pct, coverage_pct: c.tracking.coverage_pct, active_sec: c.tracking.active_sec,
  average_accepted: c.accepted_poses_per_sec, best_3s_accepted: c.best_3s_accepted_poses_per_sec,
});
// The robot is tracking while any camera is, so its coverage comes from the server's union of camera spans.
const robotSummary = (r: Report): Summary => ({
  tracking_accepted: r.tracking.accepted_poses_per_sec, tracking_generated: r.tracking.generated_poses_per_sec,
  tracking_acceptance: r.tracking.acceptance_pct, coverage_pct: r.tracking.coverage_pct, active_sec: r.tracking.active_sec,
  average_accepted: sumOf(r.cameras.map(c => c.accepted_poses_per_sec)), best_3s_accepted: null, // Per-camera bests need not coincide.
});
const idleSpans = (spans: Span[], total: number): Span[] => {
  const idle: Span[] = [];
  let at = 0;
  for (const span of spans) { if (span.lo > at) idle.push({ lo: at, hi: span.lo }); at = Math.max(at, span.hi); }
  if (at < total) idle.push({ lo: at, hi: total });
  return idle;
};
// Camera series share one sampling grid, so the combined rate is a point-wise sum; unknown anywhere means unknown.
function totalSeries(cams: Camera[], field: 'accepted' | 'generated'): Point[] {
  const n = cams[0]?.series.length ?? 0;
  if (cams.length < 2 || cams.some(c => c.series.length !== n)) return [];
  return cams[0].series.map((p, i) => ({
    t: p.t, generated: null, accepted: null, acceptance: null, multitag: null,
    [field]: sumOf(cams.map(c => c.series[i][field])),
  }));
}

export function Trend({ traces, duration, percent = false, label, shade = [], shadeLabel }: { traces: Trace[]; duration: number; percent?: boolean; label?: string; shade?: Span[]; shadeLabel?: string }) {
  const maximum = percent ? 100 : Math.max(1, ...traces.flatMap(trace => trace.points.map(p => p[trace.field] ?? 0))) * 1.1;
  const w = 900, h = 240, left = 55, right = 15, top = 15, bottom = 35;
  const x = (t: number) => left + t / Math.max(duration, 0.001) * (w - left - right);
  const y = (v: number) => h - bottom - v / maximum * (h - top - bottom);
  return <div className="vision-chart">
    <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label={label ?? (percent ? 'Acceptance and multi-tag health over selected interval' : 'Poses per second over selected interval')}>
      {[0, 0.25, 0.5, 0.75, 1].map(f => <g key={f}>
        <line x1={left} x2={w - right} y1={y(f * maximum)} y2={y(f * maximum)} stroke="#334155" />
        <text x={left - 8} y={y(f * maximum) + 4} textAnchor="end">{(f * maximum).toFixed(0)}{percent ? '%' : ''}</text>
        <text x={x(f * duration)} y={h - 12} textAnchor="middle">{(f * duration).toFixed(1)}s</text>
      </g>)}
      {shade.map((span, i) => <rect key={i} className="vision-idle" x={x(span.lo)} y={top} width={Math.max(0, x(span.hi) - x(span.lo))} height={h - top - bottom} />)}
      {traces.map(trace => {
        let start = true;
        const path = trace.points.map(p => {
          const value = p[trace.field];
          if (value == null) { start = true; return ''; }
          const command = `${start ? 'M' : 'L'}${x(p.t).toFixed(2)},${y(value).toFixed(2)}`;
          start = false;
          return command;
        }).join(' ');
        return <path key={trace.label} d={path} fill="none" stroke={trace.color} strokeWidth={trace.width ?? 2} strokeDasharray={trace.dash} />;
      })}
    </svg>
    <div className="vision-legend">{traces.map(trace => <span key={trace.label}>
      <svg width="30" height="10" aria-hidden="true"><line x1="0" x2="30" y1="5" y2="5" stroke={trace.color} strokeWidth={trace.width ?? 2} strokeDasharray={trace.dash} /></svg> {trace.label}
    </span>)}{shade.length > 0 && shadeLabel && <span><svg width="30" height="10" aria-hidden="true"><rect className="vision-idle" width="30" height="10" /></svg> {shadeLabel}</span>}</div>
  </div>;
}

/** One headline number; with a B run it shows both values and the B − A difference. */
function Value({ a, b, comparing, digits = 1, suffix = '' }: { a?: number | null; b?: number | null; comparing: boolean; digits?: number; suffix?: string }) {
  if (!comparing) return <span>{a == null ? 'Unavailable' : `${a.toFixed(digits)}${suffix}`}</span>;
  const diff = a == null || b == null ? null : b - a;
  return <span className="vision-ab">
    <span><i>A</i> {a == null ? 'n/a' : `${a.toFixed(digits)}${suffix}`}</span>
    <span><i>B</i> {b == null ? 'n/a' : `${b.toFixed(digits)}${suffix}`}</span>
    <span className={diff == null || Math.abs(diff) < 0.05 ? 'delta' : diff > 0 ? 'delta up' : 'delta down'}>{diff == null ? 'Unavailable' : `${diff > 0 ? '+' : ''}${diff.toFixed(digits)}${suffix}`}</span>
  </span>;
}

export function ScoreCard({ name, color, a, b, comparing, missing }: { name: string; color: string; a?: Summary; b?: Summary; comparing: boolean; missing?: string }) {
  const hasBest = a?.best_3s_accepted != null || b?.best_3s_accepted != null;
  return <div className="vision-card" style={{ borderTopColor: color }}>
    <h3><span className="vision-swatch" style={{ background: color }} />{name}</h3>
    {missing && <p className="warning">{missing}</p>}
    <div className="vision-big"><Value a={a?.tracking_accepted} b={b?.tracking_accepted} comparing={comparing} /><small>accepted poses/sec while tracking</small></div>
    <dl>
      <dt>Generated poses/sec while tracking</dt><dd><Value a={a?.tracking_generated} b={b?.tracking_generated} comparing={comparing} /></dd>
      <dt>Acceptance while tracking</dt><dd><Value a={a?.tracking_acceptance} b={b?.tracking_acceptance} comparing={comparing} suffix="%" /></dd>
      <dt>Tracking coverage (time seeing tags)</dt><dd><Value a={a?.coverage_pct} b={b?.coverage_pct} comparing={comparing} suffix="%" digits={0} /></dd>
      <dt>Whole-interval average accepted/sec</dt><dd><Value a={a?.average_accepted} b={b?.average_accepted} comparing={comparing} /></dd>
      {hasBest && <><dt>Best 3s accepted/sec</dt><dd><Value a={a?.best_3s_accepted} b={b?.best_3s_accepted} comparing={comparing} /></dd></>}
    </dl>
  </div>;
}

export function ThroughputOverview({ reports, cameras, duration, showGenerated }: { reports: (Report | null)[]; cameras: string[]; duration: number; showGenerated: boolean }) {
  const runs = reports.flatMap((r, i) => r ? [{ report: r, letter: i ? 'B' : 'A', dash: i ? B_DASH : undefined }] : []);
  const comparing = runs.length > 1;
  const traces: Trace[] = [];
  for (const { report, letter, dash } of runs) {
    const tag = comparing ? ` (${letter})` : '';
    const present = cameras.flatMap(c => report.cameras.find(x => x.camera === c) ?? []);
    cameras.forEach((name, i) => {
      const cam = report.cameras.find(x => x.camera === name);
      if (!cam) return;
      traces.push({ label: `${name} accepted${tag}`, points: cam.series, field: 'accepted', color: cameraColor(i), dash });
      if (showGenerated && !comparing) traces.push({ label: `${name} generated`, points: cam.series, field: 'generated', color: cameraColor(i), dash: GENERATED_DASH, width: 1.5 });
    });
    if (present.length > 1) {
      traces.push({ label: `All cameras accepted${tag}`, points: totalSeries(present, 'accepted'), field: 'accepted', color: TOTAL_COLOR, dash, width: 3 });
      if (showGenerated && !comparing) traces.push({ label: 'All cameras generated', points: totalSeries(present, 'generated'), field: 'generated', color: TOTAL_COLOR, dash: GENERATED_DASH, width: 1.5 });
    }
  }
  const first = runs[0]?.report;
  const shade = !comparing && first ? idleSpans(first.tracking.spans, first.window.duration) : [];
  return <Trend traces={traces} duration={duration} shade={shade} shadeLabel="not tracking (no camera saw tags)" label="Accepted poses per second by camera over the selected interval" />;
}

export function CameraReport({ name, a, b, duration, comparing, accent = '#94a3b8' }: { name: string; a?: Camera; b?: Camera; duration: number; comparing: boolean; accent?: string }) {
  const rows: [string, (c: Camera) => number | null | undefined, number][] = [
    ['Accepted poses/sec while tracking', c => c.tracking?.accepted_poses_per_sec, 1],
    ['Generated poses/sec while tracking', c => c.tracking?.generated_poses_per_sec, 1],
    ['Tracking coverage (% of interval)', c => c.tracking?.coverage_pct, 0],
    ['Tracking time (s)', c => c.tracking?.active_sec, 1],
    ['Separate tracking stretches', c => c.tracking?.span_count, 0],
    ['Whole-interval average accepted poses/sec', c => c.accepted_poses_per_sec, 1],
    ['Whole-interval average generated poses/sec', c => c.generated_poses_per_sec, 1],
    ['Best sustained 3s accepted poses/sec', c => c.best_3s_accepted_poses_per_sec, 1],
    ['Accepted pose count', c => c.accepted_count, 0],
    ['Generated pose count', c => c.generated_count, 0],
    ['Actual acceptance (%)', c => c.acceptance_pct, 1],
    ['Average received FPS (includes no-tag frames)', c => c.fps_mean, 1],
    ['Multi-tag health factor (%)', c => c.multitag_health_pct, 1],
  ];
  const throughput: Trace[] = [], quality: Trace[] = [];
  for (const [label, cam, dash] of [['A', a, undefined], ['B', b, B_DASH]] as const) {
    if (!cam) continue;
    // Acceptance is usually high, so the lines overlap: draw generated thick underneath and accepted thin on top to keep both visible.
    throughput.push({ label: `${label} generated`, points: cam.series, field: 'generated', color: THROUGHPUT_COLORS.generated, dash, width: 4 },
      { label: `${label} accepted`, points: cam.series, field: 'accepted', color: THROUGHPUT_COLORS.accepted, dash, width: 1.5 });
    quality.push({ label: `${label} actual acceptance`, points: cam.series, field: 'acceptance', color: QUALITY_COLORS.acceptance, dash },
      { label: `${label} multi-tag health factor`, points: cam.series, field: 'multitag', color: QUALITY_COLORS.multitag, dash });
  }
  const headline = comparing ? 'A vs B' : `${fmt(a?.tracking?.accepted_poses_per_sec)} accepted/s while tracking · tracking ${fmt(a?.tracking?.coverage_pct, 0)}% of the time`;
  return <details className="vision-camera" style={{ borderLeftColor: accent }}>
    <summary><span className="vision-swatch" style={{ background: accent }} /><strong>{name}</strong> <span className="vision-muted">{headline} · click to expand</span></summary>
    {comparing && (!a || !b) && <p className="warning">This camera is missing from {!a ? 'A' : 'B'}. Its values are unavailable.</p>}
    {[['A', a], ['B', b]].map(([label, cam]) => cam && typeof cam !== 'string' && <div key={label as string}>
      <p className="vision-muted">{label as string}: {cam.source}</p>
      {cam.warnings.map(w => <p className="warning" key={w}>{label as string}: {w}</p>)}
    </div>)}
    <table className="vision-summary"><thead><tr><th>Selected interval</th><th>A</th>{comparing && <><th>B</th><th>B − A</th></>}</tr></thead>
      <tbody>{rows.map(([label, get, digits]) => {
        const va = a && get(a), vb = b && get(b);
        return <tr key={label}><th>{label}</th><td>{fmt(va, digits)}</td>{comparing && <><td>{fmt(vb, digits)}</td><td>{va == null || vb == null ? 'Unavailable' : `${vb - va > 0 ? '+' : ''}${(vb - va).toFixed(digits)}`}</td></>}</tr>;
      })}</tbody>
    </table>
    <h3 className="vision-chart-title" style={{ borderLeftColor: THROUGHPUT_COLORS.accepted }}>Accepted vs generated poses per second</h3>
    <p className="vision-muted">The gap between the lines is poses the robot’s filter threw away.{comparing && ' Solid = A, dashed = B.'}</p>
    <Trend traces={throughput} duration={duration} shade={!comparing && a ? idleSpans(a.tracking?.spans ?? [], duration) : []} shadeLabel="not tracking" label="Generated and accepted poses per second over selected interval" />
    <h3 className="vision-chart-title" style={{ borderLeftColor: QUALITY_COLORS.acceptance }}>Acceptance and multi-tag context</h3>
    <p className="vision-muted">Acceptance is accepted ÷ generated poses in the rolling window. Multi-tag is your existing scored health factor; it is not a detection rate.{comparing && ' Solid = A, dashed = B.'}</p>
    <Trend traces={quality} duration={duration} percent />
  </details>;
}

export function VisionInsightsPage() {
  // Run A is the open log (chosen in the log bar); a second run B is picked here when comparing.
  const { logs, selected: logA, folderVersion } = useLogSelection();
  const [logB, setLogB] = useState<string | null>(null), [compare, setCompare] = useState(false);
  const [mode, setMode] = useState<Mode>('whole');
  const [manualA, setManualA] = useState(emptyWindow), [manualB, setManualB] = useState(emptyWindow);
  const [rolling, setRolling] = useState(1), [result, setResult] = useState<[Report, Report | null] | null>(null);
  const [error, setError] = useState<string | null>(null), [loading, setLoading] = useState(false);
  const [showGenerated, setShowGenerated] = useState(false), [gap, setGap] = useState(1);
  const requestId = useRef(0);
  useEffect(() => { setLogB(null); }, [folderVersion]);
  useEffect(() => { setManualA(emptyWindow()); }, [logA]); // a custom slice belongs to the log it was set on
  // Never present a report as if it came from selectors that changed after Analyze.
  useEffect(() => { requestId.current++; setLoading(false); setResult(null); setError(null); }, [logA, logB, compare, mode, manualA, manualB, rolling, gap]);
  async function analyze() {
    if (!logA || (compare && !logB)) return;
    const id = ++requestId.current;
    setLoading(true); setError(null); setResult(null);
    async function getReport(log: string, manual: ManualWindow): Promise<Report> {
      const params = new URLSearchParams({ log, mode, rolling_sec: String(rolling), tracking_gap_sec: String(gap) });
      if (manual.enabled) params.set('window', `${manual.lo},${manual.hi}`);
      const response = await fetch(`/api/vision-insights?${params}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? `Analysis failed (${response.status}).`);
      return data;
    }
    try {
      const reports = await Promise.all([getReport(logA, manualA), compare && logB ? getReport(logB, manualB) : Promise.resolve(null)]);
      if (id === requestId.current) setResult(reports);
    } catch (e) { if (id === requestId.current) setError(String(e)); }
    finally { if (id === requestId.current) setLoading(false); }
  }
  const cameras = [...new Set(result?.flatMap(r => r?.cameras.map(c => c.camera) ?? []) ?? [])];
  const duration = Math.max(...(result?.map(r => r?.window.duration ?? 0) ?? [1]));
  const comparing = Boolean(result?.[1]);
  const pick = (report: Report | null | undefined, camera: string) => report?.cameras.find(c => c.camera === camera);
  const cameraOf = (report: Report | null | undefined, camera: string) => { const c = pick(report, camera); return c && cameraSummary(c); };
  const totals = result ? result.map(r => r && r.cameras.length > 1 ? robotSummary(r) : undefined) : [];
  return <main className="vision-insights">
    <h1>Vision Insights</h1>
    <p>Measure how many generated and accepted poses each camera delivers. Compare the same section of repeated runs alongside acceptance and multi-tag quality.</p>
    <div className="vision-controls">
      <label>Interval <select value={mode} onChange={e => setMode(e.target.value as Mode)}><option value="whole">Whole log</option><option value="auto">Autonomous (longest span)</option><option value="teleop">Teleop (longest span)</option><option value="disabled">Disabled (longest span)</option></select></label>
      <label>Rolling window <select value={rolling} onChange={e => setRolling(Number(e.target.value))}>{[1, 3, 5].map(n => <option value={n} key={n}>{n} second{n > 1 ? 's' : ''}</option>)}</select></label>
      <label title="Silence shorter than this is treated as flapping and still counts as tracking. Longer silence is not tracking.">Tracking gap tolerance <select value={gap} onChange={e => setGap(Number(e.target.value))}>{[0.5, 1, 2, 3].map(n => <option value={n} key={n}>{n} second{n === 1 ? '' : 's'}</option>)}</select></label>
      <label><input type="checkbox" checked={compare} onChange={e => setCompare(e.target.checked)} /> Compare A/B</label>
    </div>
    <div className="compare-sides">
      <LogSide label="A" logs={logs} logPath={logA} onLogChange={() => undefined} locked mode={mode} manual={manualA} onManualChange={setManualA} />
      {compare && <LogSide label="B" logs={logs} logPath={logB} onLogChange={setLogB} mode={mode} manual={manualB} onManualChange={setManualB} />}
    </div>
    <button className="vision-analyze" disabled={!logA || (compare && !logB) || loading} onClick={() => void analyze()}>{loading ? 'Analyzing…' : 'Analyze vision'}</button>
    {error && <p role="alert" className="warning">{error}</p>}
    {result && <>
      <div className="vision-controls">{result.map((r, i) => r && <div key={i}><strong>{i ? 'B' : 'A'}: {r.log}</strong><p>{r.window.lo.toFixed(2)}–{r.window.hi.toFixed(2)}s · {r.window.duration.toFixed(2)}s selected</p><OrderNotice order={r.order} /></div>)}</div>
      {result[1] && Math.abs(result[0].window.duration - result[1].window.duration) > 0.1 && <p className="warning">Intervals have different lengths. Compare average rates; pose totals also reflect duration. The longer trace continues after the shorter one ends.</p>}
      {cameras.length === 0 && <p>No camera pose signals found in this log. Open an AdvantageKit vision log with pose inputs and outputs.</p>}
      {cameras.length > 0 && <>
        <section className="vision-overview">
          <h2>Throughput summary</h2>
          <div className="vision-cards">
            {cameras.map((camera, i) => <ScoreCard key={camera} name={camera} color={cameraColor(i)} a={cameraOf(result[0], camera)} b={cameraOf(result[1], camera)} comparing={comparing}
              missing={comparing && (!pick(result[0], camera) || !pick(result[1], camera)) ? `Missing from ${!pick(result[0], camera) ? 'A' : 'B'}.` : undefined} />)}
            {cameras.length > 1 && <ScoreCard name="All cameras" color={TOTAL_COLOR} a={totals[0]} b={totals[1]} comparing={comparing} />}
          </div>
          <div className="vision-chart-head">
            <h3 className="vision-chart-title" style={{ borderLeftColor: cameraColor(0) }}>Accepted poses per second, by camera <span className="vision-muted">(grey = no camera was seeing tags)</span></h3>
            {!comparing && <label><input type="checkbox" checked={showGenerated} onChange={e => setShowGenerated(e.target.checked)} /> Also show generated (dotted)</label>}
          </div>
          <ThroughputOverview reports={result} cameras={cameras} duration={duration} showGenerated={showGenerated} />
          <p className="vision-muted">Charts start at each selected interval’s beginning. Rates use a trailing {result[0].rolling_sec}s window; the initial partial window is blank. The cards’ headline rate averages only the time spent tracking; chart values are raw per-second rates.{comparing && ' Solid = A, dashed = B.'}</p>
        </section>
        <section className="vision-glossary" aria-label="What the numbers mean">
          <h2>What the numbers mean</h2>
          <ul>
            <li><strong>Generated</strong> — pose estimates the camera pipeline produced from AprilTags, before the robot checks them. This is the supply: it drops when tags are out of view, blurry, or the camera is struggling.</li>
            <li><strong>Accepted</strong> — the generated poses that passed the robot’s vision filter (field boundary, sudden-jump and trust checks) and were handed to odometry. <em>This is the number that matters most: accepted poses per second is how often vision actually corrects the robot’s position.</em></li>
            <li><strong>While tracking</strong> — throughput should say how many poses you get <em>when you are looking at a tag</em>, so time with no tags is left out (that measures coverage, shown separately). A camera counts as tracking while it keeps generating poses; a silence up to the “tracking gap tolerance” ({result[0].tracking_gap_sec}s) is treated as flapping and still counts, so brief blur or glare lowers the rate instead of being hidden. Longer silence ends the tracking stretch.</li>
            <li><strong>Acceptance</strong> — accepted ÷ generated. Low generated with high acceptance means the camera isn’t seeing tags. High generated with low acceptance means the filter is rejecting what the camera sees.</li>
          </ul>
        </section>
        <h2>Per-camera details</h2>
        <p className="vision-muted">Collapsed by default. Open a camera for its full table, acceptance chart and data-source warnings.</p>
        {cameras.map((camera, i) => <CameraReport key={camera} name={camera} accent={cameraColor(i)} a={pick(result[0], camera)} b={pick(result[1], camera)} duration={duration} comparing={comparing} />)}
      </>}
      <details><summary>How to read these measurements</summary><ul>{result[0].notes.map(n => <li key={n}>{n}</li>)}</ul><p>Accepted poses are measurements queued by the vision filter, not a measure of pose accuracy or odometry weight. A high multi-tag score can coexist with low throughput. The best 3s rate is a capacity hint; prefer the interval average and repeated A/B trials.</p></details>
    </>}
  </main>;
}
