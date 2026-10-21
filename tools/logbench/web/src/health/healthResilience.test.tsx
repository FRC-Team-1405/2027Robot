// @vitest-environment jsdom
import { act, useState } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HealthBoundary } from './HealthBoundary';
import { HealthCheckPage } from './HealthCheckPage';
import { useLiveReport, useLogReport } from './useHealthReport';
import { usePitConnection } from '../pit/usePitConnection';
import * as cameraModule from '../pit/CameraCard';

const report = (kind = 'live', display = '72 %') => ({ kind, sections: [{
  id: 'system', label: 'System', status: 'warn', groups: [{ label: '', status: 'warn', subjects: [{
    label: '', status: 'warn', checks: [{ id: 'cpu', key: 'cpu', label: 'CPU load', status: 'warn', display }],
  }] }],
}] });
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
let host: HTMLDivElement;
let root: Root;
async function render(child: React.ReactNode) { await act(async () => { root.render(child); }); }
async function tick(ms: number) { await act(async () => { await vi.advanceTimersByTimeAsync(ms); }); }
async function click(text: string) {
  const button = [...host.querySelectorAll('button')].find((button) => button.textContent === text);
  expect(button, text).toBeTruthy();
  await act(async () => { button!.click(); });
}
beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
  window.history.replaceState({}, '', '/?view=health');
});
afterEach(async () => {
  await act(async () => root.unmount()); host.remove();
  vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals();
});

function LiveHarness() {
  const live = useLiveReport(true);
  return <><div role="alert">{live.error}{live.resetError}</div>
    <span>{live.stale ? 'stale' : 'current'}</span><pre>{JSON.stringify(live.report)}</pre>
    <button onClick={() => void live.reset()}>Reset</button></>;
}

describe('live health recovery', () => {
  it('retains the report through HTTP, invalid JSON, and invalid-schema responses then recovers', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(json(report()))
      .mockResolvedValueOnce(json({ detail: 'Robot read failed' }, 503))
      .mockResolvedValueOnce(new Response('not JSON')).mockResolvedValueOnce(json({ sections: null }))
      .mockResolvedValue(json(report('live', '40 %')));
    vi.stubGlobal('fetch', fetcher);
    await render(<LiveHarness />);
    expect(host.textContent).toContain('72 %');
    await tick(1000);
    expect(host.querySelector('[role=alert]')!.textContent).toContain('Robot read failed');
    expect(host.textContent).toContain('stale'); expect(host.textContent).toContain('72 %');
    await tick(1000); expect(host.textContent).toContain('invalid JSON');
    await tick(1000); expect(host.textContent).toContain('invalid kind');
    await tick(1000);
    expect(host.textContent).toContain('current'); expect(host.textContent).toContain('40 %');
    expect(host.querySelector('[role=alert]')!.textContent).toBe('');
  });
  it('times out stalled requests, never overlaps polls, and retries', async () => {
    const fetcher = vi.fn().mockImplementationOnce((_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
    })).mockResolvedValue(json(report()));
    vi.stubGlobal('fetch', fetcher);
    await render(<LiveHarness />); await tick(9000);
    expect(fetcher).toHaveBeenCalledTimes(1);
    await tick(1000); expect(host.textContent).toContain('timed out');
    await tick(1000); expect(host.textContent).toContain('72 %');
  });
  it('shows reset failures without discarding live readings', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url) => String(url).endsWith('/reset') ? json({ detail: 'Reset unavailable' }, 500) : json(report())));
    await render(<LiveHarness />); await click('Reset');
    expect(host.textContent).toContain('Reset failed: Reset unavailable'); expect(host.textContent).toContain('72 %');
  });
  it('aborts on unmount and ignores a late response', async () => {
    let resolve!: (response: Response) => void;
    let signal!: AbortSignal;
    vi.stubGlobal('fetch', vi.fn((_url, options) => {
      signal = options.signal;
      return new Promise<Response>((done) => { resolve = done; });
    }));
    await render(<LiveHarness />); await render(<div>left page</div>);
    expect(signal.aborted).toBe(true);
    await act(async () => resolve(json(report())));
    expect(host.textContent).toBe('left page'); expect(vi.getTimerCount()).toBe(0);
  });
});

it('keeps the last report for a failed log reload, but never labels the old log as a newly selected one', async () => {
  function LogHarness() {
    const [path, setPath] = useState('a.wpilog');
    const log = useLogReport(path);
    return <><pre>{JSON.stringify(log.report)}</pre><span>{log.error}</span>
      <button onClick={() => void log.reload()}>Reload</button><button onClick={() => setPath('b.wpilog')}>Other log</button></>;
  }
  let resolve!: (response: Response) => void;
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(json(report('log')))
    .mockRejectedValueOnce(new Error('Offline')).mockImplementation(() => new Promise<Response>((done) => { resolve = done; })));
  await render(<LogHarness />); await click('Reload');
  expect(host.textContent).toContain('Offline'); expect(host.textContent).toContain('72 %');
  await click('Other log'); expect(host.textContent).not.toContain('72 %');
  await act(async () => resolve(json(report('log', '22 %'))));
  expect(host.textContent).toContain('22 %');
});

it('isolates render failures and retries the broken panel while retaining siblings', async () => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
  const notify = vi.fn(); let broken = true;
  function Card() { if (broken) throw new Error('broken camera'); return <span>camera recovered</span>; }
  await render(<><HealthBoundary label="Camera Right" onError={notify}><Card /></HealthBoundary><span>CPU still visible</span></>);
  expect(host.textContent).toContain('broken camera'); expect(host.textContent).toContain('CPU still visible');
  expect(notify).toHaveBeenCalledWith('Camera Right: broken camera');
  broken = false; await click('Retry Camera Right'); expect(host.textContent).toContain('camera recovered');
});

it('renders the real Health Check with null camera telemetry and reports poll failures at the top', async () => {
  let failing = false;
  vi.stubGlobal('fetch', vi.fn(async (url) => {
    if (String(url) === '/api/logs') return json({ logs: [] });
    if (String(url) === '/api/metric-catalog') return json({ severity: [] });
    if (String(url) === '/api/live/snapshot') return json({ nt_connected: true, cameras: { Right: { current_fps: null, health_score: null, visible_tag_ids: null } } });
    if (String(url) === '/api/health/live') return failing ? json({ detail: 'Live robot unavailable' }, 500) : json(report());
    return json({});
  }));
  await render(<HealthCheckPage />);
  const input = host.querySelector<HTMLInputElement>('input[placeholder="Team number or IP address"]')!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, '1405');
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await click('Connect');
  expect(host.textContent).toContain('n/a fps'); expect(host.textContent).toContain('CPU load');
  failing = true; await tick(1000);
  const notice = host.querySelector('[role=alert]')!;
  expect(notice.textContent).toContain('Live robot unavailable');
  expect(notice.compareDocumentPosition(host.querySelector('.health__connect')!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(host.textContent).toContain('CPU load'); expect(host.textContent).toContain('Disconnect');
  failing = false; await tick(1000); expect(host.querySelector('[role=alert]')).toBeNull();
  vi.spyOn(console, 'error').mockImplementation(() => {});
  const broken = vi.spyOn(cameraModule, 'CameraCard').mockImplementation(() => { throw new Error('camera render failed'); });
  await tick(400);
  expect(host.querySelector('[role=alert]')!.textContent).toContain('Camera Right: camera render failed');
  expect(host.textContent).toContain('CPU load'); expect(host.textContent).toContain('Disconnect');
  broken.mockRestore(); await tick(400);
  expect(host.textContent).toContain('n/a fps');
  await click('Dismiss page errors'); expect(host.querySelector('[role=alert]')).toBeNull();
  await click('Disconnect'); expect(host.textContent).not.toContain('CPU load');
});

it('does not reconnect or restart polling when a cancelled connect response arrives late', async () => {
  function ConnectionHarness() {
    const pit = usePitConnection();
    return <><span>{pit.status}</span><button onClick={() => void pit.connect('1405', 'AdvantageKit')}>Start</button>
      <button onClick={() => void pit.disconnect()}>Stop</button></>;
  }
  let resolve!: (response: Response) => void;
  const fetcher = vi.fn().mockImplementationOnce(() => new Promise<Response>((done) => { resolve = done; })).mockResolvedValue(json({}));
  vi.stubGlobal('fetch', fetcher);
  await render(<ConnectionHarness />); await click('Start'); await click('Stop');
  await act(async () => resolve(json({ connected: true })));
  await tick(1000);
  expect(host.textContent).toContain('disconnected');
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it('shows auxiliary-load and unexpected async errors above usable page controls', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => json(null)));
  await render(<HealthCheckPage />);
  expect(host.querySelector('[role=alert]')!.textContent).toContain('Invalid log list');
  expect(host.textContent).toContain('Connect');
  await act(async () => { window.dispatchEvent(new ErrorEvent('error', { message: 'unexpected callback failure' })); });
  expect(host.querySelector('[role=alert]')!.textContent).toContain('unexpected callback failure');
  vi.stubGlobal('fetch', vi.fn(async (url) => json(String(url) === '/api/logs' ? { logs: [] } : { severity: [] })));
  await click('Retry page data'); await click('Dismiss page errors');
  expect(host.querySelector('[role=alert]')).toBeNull();
});
