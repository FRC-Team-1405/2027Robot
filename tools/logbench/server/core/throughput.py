"""Pose throughput shared by Vision Insights, Compare and the CLI.

Arrays are loop state, not events: AdvantageKit omits unchanged values. Rebuild
that state on /Timestamp cycles, or on changed raw capture-timestamp batches.
Never infer 50 Hz and never use nearest (potentially future) array values.
Intervals are half open [lo, hi); timestamps refer to robot receipt/logging time.
"""
from bisect import bisect_left, bisect_right
import math

from . import signals as sig


def _reader(series):
    ordered = sorted(series or [], key=lambda item: item[0])
    times = [t for t, _ in ordered]

    def at(t, default=None):
        i = bisect_right(times, t) - 1
        return ordered[i][1] if i >= 0 else default
    return at


def events(run, camera):
    key = ('throughput_events', camera)
    if key in run.cache:
        return run.cache[key]
    signals = run.log.signals
    raw = sig.find_signal(signals, f'Vision/{camera}/RawEstimatedPoses')
    accepted = sig.find_signal(signals, f'Vision/{camera}/AcceptedPoses')
    if accepted is None:
        accepted = sig.find_signal(signals, f'Vision/{camera}/estimatedPoses')
    cycles = signals.get('/Timestamp') or signals.get('Timestamp')
    capture = sig.find_signal(signals, f'Vision/{camera}/RawTimestampsSec')
    warnings = []
    if cycles:
        times = sorted({t for t, _ in cycles})
        source = 'Robot loop timestamps; unchanged pose arrays reconstructed.'
    elif capture is not None:
        # Each nonempty batch contains fresh capture timestamps, including when
        # consecutive stationary pose arrays are byte-for-byte identical.
        times = sorted({t for t, values in capture if values})
        source = 'Raw capture-timestamp batches; unchanged pose arrays reconstructed.'
    else:
        times = []
        source = 'Unavailable'
        warnings.append('Exact throughput needs robot loop timestamps or raw capture-timestamp batches. '
                        'Pose-array record counts alone can undercount unchanged measurements.')
    raw_at, accepted_at = _reader(raw), _reader(accepted)
    result = {
        'generated': [(t, len(raw_at(t, []) or [])) for t in times] if raw is not None else None,
        'accepted': [(t, len(accepted_at(t, []) or [])) for t in times] if accepted is not None else None,
        'available': bool(cycles) or capture is not None,
        'source': source, 'warnings': warnings,
    }
    if raw is None:
        warnings.append('Raw generated-pose arrays are missing; generated throughput and acceptance are unavailable.')
    if accepted is None:
        warnings.append('Accepted-pose arrays are missing; accepted throughput is unavailable.')
    run.cache[key] = result
    return result


class Counts:
    def __init__(self, series):
        self.times = []
        self.sums = [0]
        for t, value in series or []:
            self.times.append(t)
            self.sums.append(self.sums[-1] + value)

    def between(self, lo, hi):
        return self.sums[bisect_left(self.times, hi)] - self.sums[bisect_left(self.times, lo)]

    def best(self, lo, hi, seconds=3.0):
        if hi - lo < seconds:
            return None
        # A half-open sliding window changes at event times or just after one.
        ends = {lo + seconds, hi}
        for t in self.times:
            for end in (t, math.nextafter(t, math.inf), t + seconds):
                if lo + seconds <= end <= hi:
                    ends.add(end)
        return max(self.between(end - seconds, end) / seconds for end in ends)


def summary(run, camera):
    key = ('throughput_summary', camera)
    if key in run.cache:
        return run.cache[key]
    data = events(run, camera)
    lo, hi = run.window.lo, run.window.hi
    duration = hi - lo
    result = {'source': data['source'], 'warnings': data['warnings']}
    for kind in ('generated', 'accepted'):
        series = data[kind]
        measurable = data['available'] and series is not None and duration > 0
        counts = Counts(series)
        total = counts.between(lo, hi) if measurable else None
        result[f'{kind}_count'] = total
        result[f'{kind}_poses_per_sec'] = total / duration if total is not None else None
        result[f'best_3s_{kind}_poses_per_sec'] = counts.best(lo, hi) if measurable else None
    raw, accepted = result['generated_count'], result['accepted_count']
    result['acceptance_pct'] = 100 * accepted / raw if raw and accepted is not None else None
    run.cache[key] = result
    return result


def analyze(run, rolling_sec=1.0):
    lo, hi = run.window.lo, run.window.hi
    log_lo, log_hi = run.log.bounds()
    if (not all(math.isfinite(v) for v in (lo, hi, rolling_sec)) or
            hi <= lo or lo < log_lo or hi > log_hi or not 0.1 <= rolling_sec <= 10):
        raise ValueError('Choose a nonempty interval inside the log and a rolling window from 0.1 to 10 seconds.')
    cameras = []
    for camera in run.log.cameras():
        data = events(run, camera)
        sums = {kind: Counts(data[kind]) for kind in ('generated', 'accepted')}
        multi_at = _reader(sig.find_signal(run.log.signals, f'Vision/{camera}/Health/MultiTagRatioPercent'))
        # Bounded payload, independent of original camera/robot loop frequency.
        n = min(1200, max(1, math.ceil((hi - lo) / 0.1)))
        rows = []
        for i in range(n + 1):
            t = lo + (hi - lo) * i / n
            full = t - lo >= rolling_sec - 1e-9
            counts = {kind: sums[kind].between(max(lo, t - rolling_sec), t)
                      if data['available'] and data[kind] is not None and full else None
                      for kind in sums}
            raw, accepted = counts['generated'], counts['accepted']
            rows.append({'t': t - lo,
                         'generated': raw / rolling_sec if raw is not None else None,
                         'accepted': accepted / rolling_sec if accepted is not None else None,
                         'acceptance': 100 * accepted / raw if raw and accepted is not None else None,
                         'multitag': multi_at(t)})
        fps = sig.find_signal(run.log.signals, f'Vision/{camera}/CurrentFps')
        fps_mean = sig.time_weighted_mean(sig.hold_intervals(sorted(fps or []), lo, hi))
        cameras.append({'camera': camera, **summary(run, camera),
                        'fps_mean': fps_mean,
                        'multitag_health_pct': run.metric('multitag_pct', camera), 'series': rows})
    return {'log': run.log.path.name,
            'window': {'lo': lo - log_lo, 'hi': hi - log_lo, 'duration': hi - lo},
            'rolling_sec': rolling_sec, 'cameras': cameras,
            'notes': ['Rates count poses, not individual tags. FPS also includes frames without tags.',
                      'Rolling rates require a full window; best 3s uses a full, sliding three-second interval.',
                      'Multi-tag is the existing health factor (a score), not the literal multi-tag fraction.',
                      'Intervals include their start and exclude their end. Rates use robot receipt time.',
                      'Compare similar routes, lighting, range and speed; repeat A/B trials.']}
