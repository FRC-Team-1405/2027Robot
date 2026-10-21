import { useEffect, useRef, useState } from 'react';
import { LogSide } from '../compare/LogSide';
import type { LogEntry, ManualWindow, Mode } from '../compare/types';
import { LogRootButton } from '../loader/LogRootButton';
import { OrderNotice } from '../loader/OrderNotice';
import './vision.css';

type Point = { t: number; generated: number | null; accepted: number | null; acceptance: number | null; multitag: number | null };
type Camera = {
  camera: string; generated_count: number | null; accepted_count: number | null;
  generated_poses_per_sec: number | null; accepted_poses_per_sec: number | null;
  best_3s_accepted_poses_per_sec: number | null; acceptance_pct: number | null;
  fps_mean: number | null; multitag_health_pct: number | null;
  source: string; warnings: string[]; series: Point[];
};
type Report = {
  log: string; window: { lo: number; hi: number; duration: number }; rolling_sec: number;
  cameras: Camera[]; notes: string[]; order?: { n_late: number; late_pct: number; max_late_ms: number } | null;
};
type Trace = { label: string; points: Point[]; field: keyof Omit<Point, 't'>; color: string; dashed?: boolean };
const emptyWindow = (): ManualWindow => ({ enabled: false, lo: 0, hi: 0 });
const fmt = (n: number | null | undefined, digits = 1) => n == null ? 'Unavailable' : n.toFixed(digits);

export function Trend({ traces, duration, percent = false }: { traces: Trace[]; duration: number; percent?: boolean }) {
  const maximum = percent ? 100 : Math.max(1, ...traces.flatMap(trace => trace.points.map(p => p[trace.field] ?? 0))) * 1.1;
  const w = 900, h = 240, left = 55, right = 15, top = 15, bottom = 35;
  const x = (t: number) => left + t / Math.max(duration, 0.001) * (w - left - right);
  const y = (v: number) => h - bottom - v / maximum * (h - top - bottom);
  return <div className="vision-chart">
    <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label={percent ? 'Acceptance and multi-tag health over selected interval' : 'Generated and accepted poses per second over selected interval'}>
      {[0, 0.25, 0.5, 0.75, 1].map(f => <g key={f}>
        <line x1={left} x2={w - right} y1={y(f * maximum)} y2={y(f * maximum)} stroke="#334155" />
        <text x={left - 8} y={y(f * maximum) + 4} textAnchor="end">{(f * maximum).toFixed(0)}{percent ? '%' : ''}</text>
        <text x={x(f * duration)} y={h - 12} textAnchor="middle">{(f * duration).toFixed(1)}s</text>
      </g>)}
      {traces.map(trace => {
        let start = true;
        const path = trace.points.map(p => {
          const value = p[trace.field];
          if (value == null) { start = true; return ''; }
          const command = `${start ? 'M' : 'L'}${x(p.t).toFixed(2)},${y(value).toFixed(2)}`;
          start = false;
          return command;
        }).join(' ');
        return <path key={trace.label} d={path} fill="none" stroke={trace.color} strokeWidth={2} strokeDasharray={trace.dashed ? '7 4' : undefined} />;
      })}
    </svg>
    <div className="vision-legend">{traces.map(trace => <span key={trace.label} style={{ color: trace.color }}>{trace.dashed ? '┄' : '━'} {trace.label}</span>)}</div>
  </div>;
}

export function CameraReport({ name, a, b, duration, comparing }: { name: string; a?: Camera; b?: Camera; duration: number; comparing: boolean }) {
  const rows: [string, keyof Camera, number][] = [
    ['Average accepted poses/sec', 'accepted_poses_per_sec', 1],
    ['Average generated poses/sec', 'generated_poses_per_sec', 1],
    ['Best sustained 3s accepted poses/sec', 'best_3s_accepted_poses_per_sec', 1],
    ['Accepted pose count', 'accepted_count', 0],
    ['Generated pose count', 'generated_count', 0],
    ['Actual acceptance (%)', 'acceptance_pct', 1],
    ['Average received FPS (includes no-tag frames)', 'fps_mean', 1],
    ['Multi-tag health factor (%)', 'multitag_health_pct', 1],
  ];
  const throughput: Trace[] = [], quality: Trace[] = [];
  for (const [label, cam, color, rawColor] of [['A', a, '#38bdf8', '#818cf8'], ['B', b, '#4ade80', '#fbbf24']] as const) {
    if (!cam) continue;
    throughput.push({ label: `${label} accepted`, points: cam.series, field: 'accepted', color },
      { label: `${label} generated`, points: cam.series, field: 'generated', color: rawColor, dashed: true });
    quality.push({ label: `${label} actual acceptance`, points: cam.series, field: 'acceptance', color },
      { label: `${label} multi-tag health factor`, points: cam.series, field: 'multitag', color: rawColor, dashed: true });
  }
  return <section className="vision-camera">
    <h2>{name}</h2>
    {comparing && (!a || !b) && <p className="warning">This camera is missing from {!a ? 'A' : 'B'}. Its values are unavailable.</p>}
    {[['A', a], ['B', b]].map(([label, cam]) => cam && typeof cam !== 'string' && <div key={label as string}>
      <p className="vision-muted">{label as string}: {cam.source}</p>
      {cam.warnings.map(w => <p className="warning" key={w}>{label as string}: {w}</p>)}
    </div>)}
    <table className="vision-summary"><thead><tr><th>Selected interval</th><th>A</th>{comparing && <><th>B</th><th>B − A</th></>}</tr></thead>
      <tbody>{rows.map(([label, field, digits]) => {
        const va = a?.[field] as number | null | undefined, vb = b?.[field] as number | null | undefined;
        return <tr key={field}><th>{label}</th><td>{fmt(va, digits)}</td>{comparing && <><td>{fmt(vb, digits)}</td><td>{va == null || vb == null ? 'Unavailable' : `${vb - va > 0 ? '+' : ''}${(vb - va).toFixed(digits)}`}</td></>}</tr>;
      })}</tbody>
    </table>
    <h3>Pose throughput</h3><Trend traces={throughput} duration={duration} />
    <h3>Acceptance and multi-tag context</h3><Trend traces={quality} duration={duration} percent />
    <p className="vision-muted">Acceptance is accepted ÷ generated poses in the rolling window. Multi-tag is your existing scored health factor; it is not a detection rate.</p>
  </section>;
}

export function VisionInsightsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]), [root, setRoot] = useState<string | null>(null);
  const [logA, setLogA] = useState<string | null>(new URLSearchParams(window.location.search).get('log'));
  const [logB, setLogB] = useState<string | null>(null), [compare, setCompare] = useState(false);
  const [mode, setMode] = useState<Mode>('whole');
  const [manualA, setManualA] = useState(emptyWindow), [manualB, setManualB] = useState(emptyWindow);
  const [rolling, setRolling] = useState(1), [result, setResult] = useState<[Report, Report | null] | null>(null);
  const [error, setError] = useState<string | null>(null), [loading, setLoading] = useState(false);
  const requestId = useRef(0);
  async function loadLogs() {
    try {
      const response = await fetch('/api/logs');
      if (!response.ok) throw new Error(`Could not list logs (${response.status}).`);
      const data = await response.json(); setLogs(data.logs); setRoot(data.root);
    } catch (e) { setError(String(e)); }
  }
  useEffect(() => { void loadLogs(); }, []);
  // Never present a report as if it came from selectors that changed after Analyze.
  useEffect(() => { requestId.current++; setLoading(false); setResult(null); setError(null); }, [logA, logB, compare, mode, manualA, manualB, rolling]);
  async function analyze() {
    if (!logA || (compare && !logB)) return;
    const id = ++requestId.current;
    setLoading(true); setError(null); setResult(null);
    async function getReport(log: string, manual: ManualWindow): Promise<Report> {
      const params = new URLSearchParams({ log, mode, rolling_sec: String(rolling) });
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
  return <main className="vision-insights">
    <h1>Vision Insights</h1>
    <p>Measure how many generated and accepted poses each camera delivers. Compare the same section of repeated runs alongside acceptance and multi-tag quality.</p>
    <LogRootButton root={root} onChanged={() => { requestId.current++; setResult(null); setLogA(null); setLogB(null); void loadLogs(); }} />
    <div className="vision-controls">
      <label>Interval <select value={mode} onChange={e => setMode(e.target.value as Mode)}><option value="whole">Whole log</option><option value="auto">Autonomous (longest span)</option><option value="teleop">Teleop (longest span)</option><option value="disabled">Disabled (longest span)</option></select></label>
      <label>Rolling window <select value={rolling} onChange={e => setRolling(Number(e.target.value))}>{[1, 3, 5].map(n => <option value={n} key={n}>{n} second{n > 1 ? 's' : ''}</option>)}</select></label>
      <label><input type="checkbox" checked={compare} onChange={e => setCompare(e.target.checked)} /> Compare A/B</label>
    </div>
    <div className="compare-sides">
      <LogSide label="A" logs={logs} logPath={logA} onLogChange={setLogA} mode={mode} manual={manualA} onManualChange={setManualA} />
      {compare && <LogSide label="B" logs={logs} logPath={logB} onLogChange={setLogB} mode={mode} manual={manualB} onManualChange={setManualB} />}
    </div>
    <button className="vision-analyze" disabled={!logA || (compare && !logB) || loading} onClick={() => void analyze()}>{loading ? 'Analyzing…' : 'Analyze vision'}</button>
    {error && <p role="alert" className="warning">{error}</p>}
    {result && <>
      <div className="vision-controls">{result.map((r, i) => r && <div key={i}><strong>{i ? 'B' : 'A'}: {r.log}</strong><p>{r.window.lo.toFixed(2)}–{r.window.hi.toFixed(2)}s · {r.window.duration.toFixed(2)}s selected</p><OrderNotice order={r.order} /></div>)}</div>
      <p>Charts start at each selected interval’s beginning. Rates use a trailing {result[0].rolling_sec}s window; the initial partial window is blank. Summaries use the entire selected interval.</p>
      {result[1] && Math.abs(result[0].window.duration - result[1].window.duration) > 0.1 && <p className="warning">Intervals have different lengths. Compare average rates; pose totals also reflect duration. The longer trace continues after the shorter one ends.</p>}
      {cameras.length === 0 && <p>No camera pose signals found in this log. Open an AdvantageKit vision log with pose inputs and outputs.</p>}
      {cameras.map(camera => <CameraReport key={camera} name={camera} a={result[0].cameras.find(c => c.camera === camera)} b={result[1]?.cameras.find(c => c.camera === camera)} duration={duration} comparing={Boolean(result[1])} />)}
      <details><summary>How to read these measurements</summary><ul>{result[0].notes.map(n => <li key={n}>{n}</li>)}</ul><p>Accepted poses are measurements queued by the vision filter, not a measure of pose accuracy or odometry weight. A high multi-tag score can coexist with low throughput. The best 3s rate is a capacity hint; prefer the interval average and repeated A/B trials.</p></details>
    </>}
  </main>;
}
