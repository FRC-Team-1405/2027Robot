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


DEFAULT_TRACKING_GAP_SEC = 1.0


def _tracking_basis(data):
    """A camera is "looking at a tag" when it generates poses, even if the robot then rejects them:
    a stretch of all-rejected poses is a throughput problem, not a coverage gap."""
    for kind in ('generated', 'accepted'):
        if data[kind] is not None:
            return kind
    return None


def _tracking_spans(data, basis, lo, hi, gap):
    """Spans of [lo, hi) while tracking. Loops with poses are joined while the silence between them is
    at most `gap`; longer silences end the span. Each span runs from its first pose loop to the end of
    its last one, so a lone pose counts as one loop, not zero time."""
    cycles = [t for t, _ in data[basis]]
    hits = [t for t, count in data[basis] if lo <= t < hi and count > 0]
    if not hits:
        return []
    steps = sorted(b - a for a, b in zip(cycles, cycles[1:]) if b > a)
    typical = steps[len(steps) // 2] if steps else 0.0
    groups, start, prev = [], hits[0], hits[0]
    for t in hits[1:]:
        if t - prev > gap:
            groups.append((start, prev))
            start = t
        prev = t
    groups.append((start, prev))
    spans = []
    for first, last in groups:
        i = bisect_right(cycles, last)
        end = cycles[i] if i < len(cycles) else last + typical
        spans.append((first, min(hi, end if end > last else math.nextafter(last, math.inf))))
    return spans


def _merge(spans):
    merged = []
    for a, b in sorted(spans):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [tuple(span) for span in merged]


def _tracking_stats(datas, spans, lo, hi):
    active = sum(b - a for a, b in spans)
    result = {'active_sec': active, 'span_count': len(spans),
              'coverage_pct': 100 * active / (hi - lo) if hi > lo else None,
              'spans': [{'lo': a - lo, 'hi': b - lo} for a, b in spans]}
    for kind in ('generated', 'accepted'):
        counts = [Counts(d[kind]) if d['available'] and d[kind] is not None else None for d in datas]
        measurable = all(c is not None for c in counts) and active > 0
        total = sum(c.between(a, b) for c in counts for a, b in spans) if measurable else None
        result[f'{kind}_poses_per_sec'] = total / active if total is not None else None
        result[f'{kind}_count'] = total
    raw, accepted = result['generated_count'], result['accepted_count']
    result['acceptance_pct'] = 100 * accepted / raw if raw and accepted is not None else None
    return result


def tracking(run, camera=None, gap=DEFAULT_TRACKING_GAP_SEC):
    """Throughput while tracking. `camera=None` means the whole robot: the union of every camera's spans,
    with all cameras' poses counted inside it."""
    lo, hi = run.window.lo, run.window.hi
    names = [camera] if camera is not None else list(run.log.cameras())
    datas = [events(run, name) for name in names]
    bases = [_tracking_basis(d) for d in datas]
    spans = []
    for d, basis in zip(datas, bases):
        if d['available'] and basis is not None and hi > lo:
            spans += _tracking_spans(d, basis, lo, hi, gap)
    result = _tracking_stats(datas, _merge(spans), lo, hi)
    result['basis'] = bases[0] if len(set(bases)) == 1 else 'mixed'
    return result


def analyze(run, rolling_sec=1.0, tracking_gap_sec=DEFAULT_TRACKING_GAP_SEC):
    lo, hi = run.window.lo, run.window.hi
    log_lo, log_hi = run.log.bounds()
    if (not all(math.isfinite(v) for v in (lo, hi, rolling_sec, tracking_gap_sec)) or
            hi <= lo or lo < log_lo or hi > log_hi or not 0.1 <= rolling_sec <= 10 or not 0.1 <= tracking_gap_sec <= 30):
        raise ValueError('Choose a nonempty interval inside the log, a rolling window from 0.1 to 10 seconds '
                         'and a tracking gap from 0.1 to 30 seconds.')
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
                        'fps_mean': fps_mean, 'tracking': tracking(run, camera, tracking_gap_sec),
                        'multitag_health_pct': run.metric('multitag_pct', camera), 'series': rows})
    return {'log': run.log.path.name,
            'window': {'lo': lo - log_lo, 'hi': hi - log_lo, 'duration': hi - lo},
            'rolling_sec': rolling_sec, 'tracking_gap_sec': tracking_gap_sec, 'cameras': cameras,
            'tracking': tracking(run, None, tracking_gap_sec),
            'notes': ['Rates count poses, not individual tags. FPS also includes frames without tags.',
                      f'Tracking time: loops where a camera generated poses, joined while the silence between them is at most {tracking_gap_sec:g}s. '
                      'Longer silences are not tracking and are left out of the while-tracking rates.',
                      'Rolling rates require a full window; best 3s uses a full, sliding three-second interval.',
                      'Multi-tag is the existing health factor (a score), not the literal multi-tag fraction.',
                      'Intervals include their start and exclude their end. Rates use robot receipt time.',
                      'Compare similar routes, lighting, range and speed; repeat A/B trials.']}
