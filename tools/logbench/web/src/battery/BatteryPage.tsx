import { useEffect, useMemo, useState } from 'react';
import { decodeSpec } from '../player/decode';
import type { Spec, WireSpec } from '../player/types';
import { PlayerProvider, usePlayer, useThrottledTime } from '../player/PlayerContext';
import { TransportBar } from '../controls/TransportBar';
import { TimeSeriesPanel } from '../panels/TimeSeriesPanel';
import { LogRootButton } from '../loader/LogRootButton';
import { OrderNotice, type OrderInfo } from '../loader/OrderNotice';
import './battery.css';

type Stats = Record<string, number | null>;
interface Motor {
  id: string; name: string; subsystem: string; aliases: string[]; legacy: boolean;
  stats: Stats; stator_stats: Stats; tracking_error: Stats; sources: Record<string, string>; configuration: Record<string, unknown>;
  limiting_seconds: Stats;
}
export interface BatteryReport {
  schema: string; log: string; window: [number, number]; summary: Stats; warnings: string[];
  source_log: string; low_voltage_warning: number; battery_id: string; acquisition_basis: string;
  channels: { channel: number; mapping: string; stats: Stats }[];
  windows: { label: string; lo: number; hi: number }[];
  motors: Motor[]; subsystems: { name: string; stats: Stats }[];
  events: { start: number; end: number; kind: string; entity: string }[];
  spec: WireSpec;
  order?: OrderInfo | null;
  insights: Insights;
}
// server/battery_insights.py: the conclusions and what drove them.
interface Contributor { name: string; kind: string; group: string; peak_a: number; reading_age_s: number | null; stale: boolean }
interface Episode {
  start: number; end: number; duration_s: number; min_voltage: number | null; at: number; brownout: boolean;
  period: string | null; contributors: Contributor[];
}
interface Load {
  name: string; group: string; kind: string; peak_a: number; average_a: number | null;
  peak_during_dips_a: number | null; samples_per_s: number | null;
}
interface Insights {
  context: { event: string | null; match: string | null; alliance: string | null; log_kind: string };
  findings: string[]; episodes: Episode[]; loads: Load[];
  voltage: {
    warning: number; brownout_threshold: number | null; seconds_below: Record<string, number | null>;
    resting_before: number | null;
    recovery: {
      load_end_v: number | null; points: { after_s: number; voltage: number | null }[]; drop_v: number | null;
      drop_measured_after_s: number | null; tau_s: number | null; projected_rest_v: number | null;
    } | null;
  };
}
// [summary key, label, unit, digits]
const METRICS: [string, string, string, number][] = [
  ['brownout_count', 'Brownouts', '', 0], ['low_voltage_count', 'Dips below warning', '', 0],
  ['min_voltage', 'Lowest voltage', 'V', 2], ['low_voltage_seconds', 'Time below warning', 's', 1],
  ['measured_motor_peak', 'Peak measured motor draw', 'A', 0], ['measured_motor_average', 'Average measured motor draw', 'A', 1],
  ['brownout_seconds', 'Time browned out', 's', 2], ['peak', 'PDH peak current', 'A', 0],
  ['average', 'PDH average current', 'A', 1], ['ah', 'Consumed charge (PDH)', 'Ah', 2], ['wh', 'Consumed energy (PDH)', 'Wh', 2],
];
export const formatValue = (value: number | null | undefined, unit = '', digits = 2) =>
  value == null || !Number.isFinite(value) ? 'Unknown' : `${value.toFixed(digits)} ${unit}`.trim();
export function observedDelta(a: number | null | undefined, b: number | null | undefined) {
  return a == null || b == null ? null : b - a;
}

export function BatteryPage() {
  const [logs, setLogs] = useState<{ path: string; name: string }[]>([]);
  const [root, setRoot] = useState<string | null>(null);
  // Bumped when the log folder changes, to reload the list and remount the slots so they
  // drop selections that belonged to the old folder.
  const [generation, setGeneration] = useState(0);
  const [error, setError] = useState('');
  const [compare, setCompare] = useState(false);
  const [a, setA] = useState<BatteryReport | null>(null);
  const [b, setB] = useState<BatteryReport | null>(null);
  const comparisonQuery = a && b ? new URLSearchParams({ log: a.source_log, log_b: b.source_log,
    window: a.window.join(','), window_b: b.window.join(','),
    low_voltage: String(a.low_voltage_warning), low_voltage_b: String(b.low_voltage_warning) }) : null;
  useEffect(() => {
    const abort = new AbortController();
    fetch('/api/logs', { signal: abort.signal }).then(async r => {
      if (!r.ok) throw new Error(await r.text());
      const body = await r.json();
      setLogs(body.logs); setRoot(body.root); setError('');
    }).catch(e => { if (!abort.signal.aborted) setError(String(e)); });
    return () => abort.abort();
  }, [generation]);
  const changeRoot = () => {
    // The slots seed their log from ?log=, which named a log in the old folder.
    const url = new URL(window.location.href); url.searchParams.delete('log'); window.history.replaceState(null, '', url);
    setA(null); setB(null); setGeneration(g => g + 1);
  };
  return <main className="battery-page">
    <header><p className="battery-eyebrow">MATCH DIAGNOSTICS</p><h1>Battery Insights</h1>
      <p>Find voltage dips, inspect motor demand, and see evidence of current limiting.</p></header>
    <div className="battery-note">Requested output, measured current, and reported limiting are different evidence.
      Unrestricted amperage and “amps saved” are unknown without a validated model.</div>
    <LogRootButton root={root} onChanged={changeRoot} />
    {error && <p role="alert">{error}</p>}
    <label><input type="checkbox" checked={compare} onChange={e => setCompare(e.target.checked)} /> Compare a second window</label>
    {compare && a && b && <section className="battery-card"><h2>Observed change: B − A</h2>
      <p>Different driving, battery condition, state, and policy can affect these deltas. These are not causal savings.</p>
      <p><a href={`/api/battery/export?${comparisonQuery}&format=html`}>Comparison HTML</a> · <a href={`/api/battery/export?${comparisonQuery}&format=json`}>Comparison JSON</a></p>
      <table><thead><tr><th>Metric</th><th>A</th><th>B</th><th>Change</th></tr></thead><tbody>
        {METRICS.map(([key, label, unit, digits]) => <tr key={key}><th>{label}</th>
          <td>{formatValue(a.summary[key], unit, digits)}</td><td>{formatValue(b.summary[key], unit, digits)}</td>
          <td>{formatValue(observedDelta(a.summary[key], b.summary[key]), unit, digits)}</td></tr>)}
      </tbody></table>
      <h3>Subsystem average supply current</h3><table><thead><tr><th>Subsystem</th><th>A</th><th>B</th></tr></thead><tbody>
        {[...new Set([...a.subsystems, ...b.subsystems].map(s => s.name))].map(name => <tr key={name}><th>{name}</th>
          <td>{formatValue(a.subsystems.find(s => s.name === name)?.stats.average, 'A')}</td>
          <td>{formatValue(b.subsystems.find(s => s.name === name)?.stats.average, 'A')}</td></tr>)}
      </tbody></table>
      <h3>Motor response and limiting</h3>
      <table><thead><tr><th>Motor</th><th>Supply limited: A / B</th><th>Stator limited: A / B</th><th>Mean absolute tracking error: A / B (native)</th></tr></thead><tbody>
        {[...new Set([...a.motors, ...b.motors].map(m => m.name))].map(name => {
          const ma = a.motors.find(m => m.name === name), mb = b.motors.find(m => m.name === name);
          return <tr key={name}><th>{name}</th>
            <td>{formatValue(ma?.limiting_seconds.SupplyLimited, 's')} / {formatValue(mb?.limiting_seconds.SupplyLimited, 's')}</td>
            <td>{formatValue(ma?.limiting_seconds.StatorLimited, 's')} / {formatValue(mb?.limiting_seconds.StatorLimited, 's')}</td>
            <td>{formatValue(ma?.tracking_error.average)} / {formatValue(mb?.tracking_error.average)}</td></tr>;
        })}
      </tbody></table></section>}
    <AnalysisSlot key={`a${generation}`} label={compare ? 'Window A' : 'Match'} logs={logs} onReport={setA} />
    {compare && <AnalysisSlot key={`b${generation}`} label="Window B" logs={logs} onReport={setB} />}
  </main>;
}

function AnalysisSlot({ label, logs, onReport }: {
  label: string; logs: { path: string; name: string }[]; onReport: (r: BatteryReport | null) => void;
}) {
  const [log, setLog] = useState(new URLSearchParams(window.location.search).get('log') ?? '');
  const [range, setRange] = useState('');
  const [lo, setLo] = useState('0');
  const [hi, setHi] = useState('');
  const [warning, setWarning] = useState('8');
  const [report, setReport] = useState<BatteryReport | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const query = useMemo(() => new URLSearchParams({ log, ...(range ? { window: range } : {}), low_voltage: warning }), [log, range, warning]);
  useEffect(() => {
    if (!log) return;
    const abort = new AbortController();
    setLoading(true); setError(''); setReport(null); onReport(null);
    fetch(`/api/battery?${query}`, { signal: abort.signal }).then(async r => {
      const body = await r.json();
      if (!r.ok) throw new Error(body.detail ?? r.statusText);
      if (!abort.signal.aborted) { setReport(body); onReport(body); setLoading(false); }
    }).catch(e => { if (!abort.signal.aborted) { setError(String(e)); setLoading(false); } });
    return () => abort.abort();
  }, [log, query, onReport]);
  const spec = useMemo(() => report ? decodeSpec(report.spec) : null, [report]);
  return <section className="battery-slot"><h2>{label}</h2>
    <div className="battery-selectors">
      <label>Log<select value={log} onChange={e => { setRange(''); setLog(e.target.value); }}>
        <option value="">Choose a log…</option>{logs.map(l => <option key={l.path} value={l.path}>{l.path}</option>)}
      </select></label>
      <label>Warning voltage<input type="number" min="1" max="15" step="0.25" value={warning} onChange={e => setWarning(e.target.value)} /></label>
    </div>
    {report && <div className="battery-selectors"><label>Recorded interval<select value={range} onChange={e => setRange(e.target.value)}>
      <option value="">Whole log</option>{report.windows.slice(1).map((w, i) => <option key={i} value={`${w.lo},${w.hi}`}>{w.label}</option>)}
      {range && !report.windows.some(w => `${w.lo},${w.hi}` === range) && <option value={range}>Custom: {range}s</option>}
    </select></label><label>Start (s)<input type="number" value={lo} onChange={e => setLo(e.target.value)} /></label>
      <label>End (s)<input type="number" value={hi} placeholder={String(report.spec.duration)} onChange={e => setHi(e.target.value)} /></label>
      <button onClick={() => setRange(`${lo},${hi || report.spec.duration}`)}>Analyze interval</button>
      <a href={`/api/battery/export?${query}&format=html`}>HTML report</a><a href={`/api/battery/export?${query}&format=json`}>JSON data</a>
    </div>}
    {loading && <p role="status">Analyzing power telemetry…</p>}
    {error && <p role="alert">{error} <button onClick={() => { setRange(''); setWarning('8'); }}>Reset interval</button></p>}
    {report && spec && <PlayerProvider key={query.toString()} spec={spec}>
      <Report report={report} spec={spec} selectRange={(a, b) => setRange(`${a},${b}`)} />
    </PlayerProvider>}
  </section>;
}

function AtPlayhead({ ids }: { ids: string[] }) {
  const { spec } = usePlayer();
  const time = useThrottledTime();
  return <dl className="battery-readouts">{ids.map(id => {
    const s = spec.series[id];
    if (!s || s.kind === 'pose2d' || s.kind === 'intset') return null;
    let lo = 0, hi = s.t.length;
    while (lo < hi) { const mid = (lo + hi) >>> 1; if (s.t[mid] <= time) lo = mid + 1; else hi = mid; }
    const value = lo ? s.v[lo - 1] : null;
    return <div key={id}><dt>{spec.trackById[id]?.label ?? id}</dt>
      <dd>{value == null ? 'Unknown' : typeof value === 'number' ? formatValue(value, spec.trackById[id]?.unit ?? '') : String(value)}</dd></div>;
  })}</dl>;
}

function StateTimeline({ window: selectedWindow }: { window: [number, number] }) {
  const { spec, clock } = usePlayer();
  const state = spec.series['Power/State/Active'];
  if (!state || state.kind !== 'string') return null;
  const [lo, hi] = selectedWindow;
  return <div className="battery-state-timeline" aria-label="Recorded state timeline">
    {Array.from(state.t).map((time, i) => {
      const start = Math.max(lo, time), end = Math.min(hi, i+1 < state.t.length ? state.t[i+1] : spec.duration);
      if (end <= start) return null;
      return <button key={i} style={{ left: `${100*(start-lo)/(hi-lo)}%`, width: `${100*(end-start)/(hi-lo)}%` }}
        title={`${state.v[i]}: ${start.toFixed(2)}–${end.toFixed(2)}s`} onClick={() => clock.seek(start)}>{state.v[i]}</button>;
    })}
  </div>;
}

function Report({ report, spec, selectRange }: { report: BatteryReport; spec: Spec; selectRange: (a: number, b: number) => void }) {
  const { clock } = usePlayer();
  const [motor, setMotor] = useState<string>('');
  useEffect(() => { clock.seek(report.window[0]); }, [clock, report]);
  const details = spec.tracks.filter(t => t.id.startsWith(`motor/${motor}/`));
  const selected = report.motors.find(m => m.id === motor);
  const stateIds = spec.tracks.filter(t => t.id.startsWith('Power/')).map(t => t.id);
  function detailDomain(pattern: RegExp): [number, number] {
    const selected = details.filter(t => pattern.test(t.id)).map(t => spec.series[t.id]);
    const values = selected.flatMap(s => s?.kind === 'scalar' && Number.isFinite(s.min) && Number.isFinite(s.max) ? [s.min, s.max] : []);
    const low = Math.min(0, ...values), high = Math.max(1, ...values);
    return [low, high * 1.1];
  }
  const ins = report.insights;
  const context = [ins.context.event, ins.context.match, ins.context.alliance && `${ins.context.alliance} alliance`, ins.context.log_kind]
    .filter(Boolean).join(' · ');
  return <>
    <p>{context}{context ? ' · ' : ''}Battery: {report.battery_id} · PDH validity: {report.acquisition_basis}</p>
    <ul className="battery-findings">{ins.findings.map(f => <li key={f}>{f}</li>)}</ul>
    <div className="battery-metrics">{METRICS.map(([key, label, unit, digits]) => <div className="battery-card" key={key}>
      <span>{label}</span><strong>{formatValue(report.summary[key], unit, digits)}</strong></div>)}</div>
    <p>Time below: {Object.entries(ins.voltage.seconds_below).map(([level, s]) => `${level} V ${formatValue(s, 's', 1)}`).join(' · ')}</p>
    {(ins.voltage.resting_before != null || ins.voltage.recovery) && <section className="battery-card"><h3>Battery at rest and recovery</h3>
      <table><tbody>
        <tr><th>At rest before the match</th><td>{formatValue(ins.voltage.resting_before, 'V')}</td></tr>
        {ins.voltage.recovery && <>
          <tr><th>Under the last load</th><td>{formatValue(ins.voltage.recovery.load_end_v, 'V')}</td></tr>
          {ins.voltage.recovery.points.map(p => <tr key={p.after_s}><th>{p.after_s} s after</th><td>{formatValue(p.voltage, 'V')}</td></tr>)}
          {ins.voltage.recovery.drop_v != null && <tr><th>Drop (measured {ins.voltage.recovery.drop_measured_after_s} s after)</th>
            <td>{formatValue(ins.voltage.recovery.drop_v, 'V')}</td></tr>}
          <tr><th>Recovery time constant (exploratory)</th><td>{formatValue(ins.voltage.recovery.tau_s, 's', 0)}</td></tr>
          <tr><th>Projected resting voltage</th><td>{formatValue(ins.voltage.recovery.projected_rest_v, 'V')}</td></tr>
        </>}
      </tbody></table>
      <p>Measured while disabled. The battery keeps recovering for a minute or two after a match, so a drop measured soon after
        overstates it. Logs trimmed by the WPILog Janitor keep this by default (battery voltage and match info are kept for the
        whole log).</p>
    </section>}
    <p>Current coverage: {formatValue((report.summary.coverage ?? 0) * 100, '%')} · Energy coverage: {formatValue((report.summary.energy_coverage ?? 0) * 100, '%')}.
      Integrals cover valid samples only; missing data is not zero consumption.</p>
    <OrderNotice order={report.order} className="battery-note" />
    {report.warnings.map(w => <p className="battery-note" key={w}>{w}</p>)}
    <TransportBar debug={false} />
    {spec.panels.map(p => <TimeSeriesPanel expanded key={p.id} panel={p} />)}
    <section className="battery-card"><h3>Dips below {ins.voltage.warning} V ({ins.episodes.length})</h3>
      <p>Dips less than a second apart are one episode. "Drawing the most" is each current signal's peak from half a second
        before the dip to its end. Stator and torque current are motor-side sizes (they include braking); supply current is what
        the battery delivers. A reading marked old was logged more than half a second before the lowest point.</p>
      {ins.episodes.length ? <table><thead><tr><th>At</th><th>Length</th><th>Lowest</th><th>Period</th><th>Drawing the most (peak)</th><th>Inspect</th></tr></thead><tbody>
        {ins.episodes.map((e, i) => <tr key={i} className={e.brownout ? 'battery-brownout' : undefined}>
          <td><button onClick={() => clock.seek(e.at)}>{e.start.toFixed(1)}s</button></td>
          <td>{e.duration_s.toFixed(2)}s</td>
          <td>{formatValue(e.min_voltage, 'V')}{e.brownout && <strong> brownout</strong>}</td>
          <td>{e.period ?? ''}</td>
          <td>{e.contributors.slice(0, 3).map(c => <div key={c.name}>{c.name} <strong>{c.peak_a.toFixed(0)} A</strong> {c.kind}
            {c.stale && c.reading_age_s != null && <span className="battery-muted"> (reading {c.reading_age_s.toFixed(1)} s old)</span>}</div>)}
            {!e.contributors.length && <span className="battery-muted">No current signal above 5 A</span>}</td>
          <td><button onClick={() => selectRange(Math.max(0, e.start-2), Math.min(spec.duration, e.end+2))}>Surrounding interval</button></td>
        </tr>)}
      </tbody></table> : <p>None.</p>}
    </section>
    <section className="battery-card"><h3>Current by signal ({ins.loads.length})</h3>
      <p>Every current signal in this log, whatever wrote it, largest first. Signals of different kinds are not added together.
        Samples per second shows how finely each one was logged.</p>
      {ins.loads.length ? <table><thead><tr><th>Signal</th><th>Kind</th><th>Peak</th><th>Average</th><th>Peak during dips</th><th>Samples/s</th></tr></thead><tbody>
        {ins.loads.map(l => <tr key={l.name}><td>{l.name}</td><td>{l.kind}</td><td>{formatValue(l.peak_a, 'A', 0)}</td>
          <td>{formatValue(l.average_a, 'A', 1)}</td><td>{formatValue(l.peak_during_dips_a, 'A', 0)}</td>
          <td>{formatValue(l.samples_per_s, '', 1)}</td></tr>)}
      </tbody></table> : <p>No current signals in this log.</p>}
    </section>
    <section className="battery-card"><h3>State and allocation at playhead</h3>
      <StateTimeline window={report.window} />
      {stateIds.length ? <AtPlayhead ids={stateIds} /> : <p>No recorded power state or allocation. Priority is unknown.</p>}
      <p>Off, shadow, and enforced allocation are separate modes. Proposed limits are not applied limits.</p>
    </section>
    <details className="battery-card"><summary>PDH channels — separate measurements, not added to motor totals</summary>
      <p>Channel-to-device wiring is not inferred. Accessory and servo loads remain at channel resolution until mapped.</p>
      <table><thead><tr><th>Channel</th><th>Mapping</th><th>Peak / average current</th><th>Energy</th><th>Coverage</th></tr></thead><tbody>
        {report.channels.map(c => <tr key={c.channel}><th>{c.channel}</th><td>{c.mapping}</td>
          <td>{formatValue(c.stats.peak, 'A')} / {formatValue(c.stats.average, 'A')}</td><td>{formatValue(c.stats.wh, 'Wh')}</td>
          <td>{formatValue((c.stats.coverage ?? 0) * 100, '%')}</td></tr>)}
      </tbody></table>{!report.channels.length && <p>No channel measurements in this log.</p>}
    </details>
    <section className="battery-card"><h3>Subsystems and physical motors</h3>
      <p>Supply current contributes to battery accounting. Stator current does not. Expand a subsystem to inspect its motors.</p>
      {report.subsystems.map(g => <details key={g.name} open={g.name === selected?.subsystem}><summary>{g.name} · {formatValue(g.stats.average, 'A average')} · {formatValue(g.stats.wh, 'Wh')}</summary>
        <table><thead><tr><th>Motor</th><th>Peak / avg supply</th><th>Peak stator</th><th>Tracking error (native)</th><th>Energy</th><th>Supply limited</th><th>Stator limited</th><th>Coverage</th></tr></thead><tbody>
          {report.motors.filter(m => m.subsystem === g.name).map(m => <tr key={m.id}><th><button onClick={() => setMotor(m.id)}>{m.name}</button></th>
            <td>{formatValue(m.stats.peak, 'A')} / {formatValue(m.stats.average, 'A')}</td><td>{formatValue(m.stator_stats.peak, 'A')}</td>
            <td>{formatValue(m.tracking_error.average)}</td><td>{formatValue(m.stats.wh, 'Wh')}</td>
            <td>{formatValue(m.limiting_seconds.SupplyLimited, 's')} ({formatValue((m.limiting_seconds.SupplyLimitedCoverage ?? 0) * 100, '% coverage')})</td>
            <td>{formatValue(m.limiting_seconds.StatorLimited, 's')} ({formatValue((m.limiting_seconds.StatorLimitedCoverage ?? 0) * 100, '% coverage')})</td>
            <td>{formatValue((m.stats.coverage ?? 0) * 100, '%')}</td></tr>)}
        </tbody></table></details>)}
      {!report.motors.length && <p>No per-motor current data in this log.</p>}
    </section>
    {selected && <section className="battery-card"><h3>{selected.name}</h3>
      <p>{selected.legacy ? 'Legacy telemetry: limit state and acquisition health may be unavailable.' : `Physical device: ${selected.id}`}
        {selected.aliases.length > 0 && ` · Aliases: ${selected.aliases.join(', ')} (counted once)`}</p>
      <p>Limit traces show configured values; check enable flags and configuration status. Reported limiting is separate evidence.</p>
      <AtPlayhead ids={details.map(t => t.id)} />
      {[
        ['Current and limits (A)', /SupplyCurrent|StatorCurrent|TorqueCurrent|LimitAmps|RequestedAmps/],
        ['Applied voltage / duty cycle', /OutputVoltage|SupplyVoltage|DutyCycle/],
        ['Request, motion and tracking (see request units)', /Velocity|Position|ClosedLoop|RequestedSetpoint/],
        ['Reported limiting (1 = reported, gaps = unknown)', /\/(SupplyLimited|StatorLimited)$/],
      ].map(([title, pattern]) => <TimeSeriesPanel expanded key={`${motor}/${title}`} panel={{ id: String(title), type: 'timeseries', title: String(title),
        tracks: details.filter(t => (pattern as RegExp).test(t.id) && t.kind === 'scalar').map(t => t.id),
        options: { step: true, domain: detailDomain(pattern as RegExp), view: report.window } }} />)}
      <details><summary>Source keys and configuration at interval start</summary><pre>{JSON.stringify({ sources: selected.sources, configuration: selected.configuration }, null, 2)}</pre></details>
    </section>}
    <details className="battery-card"><summary>All events ({report.events.length})</summary>
      <p>Every event at telemetry sampling resolution, before dips are grouped. Missing flags cannot establish an absence of limiting.</p>
      <table><thead><tr><th>Time</th><th>Evidence</th><th>Source</th><th>Duration</th><th>Inspect</th></tr></thead><tbody>
        {report.events.map((e, i) => <tr key={i}><td><button onClick={() => clock.seek(e.start)}>{e.start.toFixed(2)}s</button></td>
          <td>{e.kind}</td><td>{e.entity}</td><td>{(e.end-e.start).toFixed(2)}s</td>
          <td><button onClick={() => selectRange(Math.max(0, e.start-2), Math.min(spec.duration, e.end+2))}>Surrounding interval</button></td></tr>)}
      </tbody></table>{!report.events.length && <p>No events found in available telemetry.</p>}
    </details>
  </>;
}
