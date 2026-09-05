"""Packs (timestamp, value) sample lists into the compact columnar wire format the
web player consumes, and serializes a whole PlayerSpec to JSON.

Why this exists: the Streamlit replay tab shipped every sample of every trace to the
browser five times a second as Plotly JSON. The player ships the data exactly once,
so the one-time payload is the only transport cost -- but a 2:30 match at 50Hz across
~20 tracks is ~300k samples, and naive [[t, v], ...] JSON of that is tens of megabytes
of mostly redundant digits. Four things fix it:

  1. Columnar, not pairs: {"t": [...], "v": [...]} drops half the brackets.
  2. Timestamps become integer milliseconds relative to t0, then delta-encoded. Log
     samples are near-periodic, so the deltas are tiny repeated integers (20, 20, 20)
     that gzip crushes.
  3. Values are rounded to the precision anyone can actually see on a chart.
  4. String/enum tracks are run-length encoded -- a Reason field holds the same
     string for thousands of consecutive samples.

Decoding lives in web/src/player/decode.ts and must stay in step with this file.
"""
import dataclasses
import json
from typing import Any, Optional

# Above this many samples a track is decimated for transport. Sized so a normal
# 2:30 match at 50Hz (~7.5k samples) is never touched -- decimation is a safety net
# for pathological logs, not the common path.
DECIMATE_THRESHOLD = 20_000
DECIMATE_TARGET = 8_000

SCALAR_DECIMALS = 2
POSE_DECIMALS = 4  # sub-millimeter; more is noise from a vision estimate


def _round(v, decimals: int):
    """Non-finite in, None out. The robot publishes NaN for "couldn't measure this"
    (see camera_calibration/health_display.is_unmeasurable), and JSON has no NaN --
    Python would emit a bare NaN token that JSON.parse rejects. Encoding it as null
    keeps the sample on the timeline so the player can render an honest gap, rather
    than dropping it and letting the previous value look current."""
    f = float(v)
    if f != f or f in (float('inf'), float('-inf')):
        return None
    r = round(f, decimals)
    # 45.0 serializes as "45.0"; 45 as "45". Saves two bytes on a large fraction of
    # samples in percentage tracks, which sit on round numbers a lot.
    return int(r) if r == int(r) else r


def _delta_encode_ms(times: list, t0: float) -> list:
    out: list = []
    prev = 0
    for t in times:
        ms = int(round((t - t0) * 1000.0))
        out.append(ms - prev)
        prev = ms
    return out


def _rle(values: list) -> list:
    """[a,a,a,b,b] -> [[a,3],[b,2]]."""
    out: list = []
    for v in values:
        if out and out[-1][0] == v:
            out[-1][1] += 1
        else:
            out.append([v, 1])
    return out


def _decimate_scalar(samples: list, target: int) -> list:
    """Min/max per bucket. Preserves spikes -- which is the whole point, since the
    reason anyone scrubs a health chart is to find the dip. Plain stride sampling
    would drop exactly the samples that matter."""
    n = len(samples)
    if n <= target:
        return samples
    buckets = max(1, target // 2)
    out: list = []
    for b in range(buckets):
        i = (n * b) // buckets
        j = (n * (b + 1)) // buckets
        if j <= i:
            continue
        chunk = samples[i:j]
        # NaN poisons min/max (every comparison is False), so rank on finite values
        # only and keep the bucket's first sample if the whole bucket is NaN.
        finite = [s for s in chunk if float(s[1]) == float(s[1])]
        if not finite:
            out.append(chunk[0])
            continue
        lo = min(finite, key=lambda s: s[1])
        hi = max(finite, key=lambda s: s[1])
        # Keep chronological order within the bucket so the polyline stays sane.
        out.extend([lo, hi] if lo[0] <= hi[0] else [hi, lo])
    return out


def encode_series(samples: list, kind: str, t0: float) -> Optional[dict]:
    """samples: list[(timestamp_seconds, value)] in ascending time order.

    Returns None for an empty track so the caller can drop it from the payload
    entirely rather than shipping an empty column pair."""
    samples = [s for s in samples if s[1] is not None]
    if kind == 'pose2d':
        # Unlike a scalar, a NaN pose has nothing to render -- there is no honest gap
        # to draw, just a point that doesn't exist. Drop those samples outright.
        samples = [s for s in samples
                   if all(float(s[1][k]) == float(s[1][k]) for k in ('x', 'y', 'rot'))]
    if not samples:
        return None

    decimated = False
    if kind == 'scalar' and len(samples) > DECIMATE_THRESHOLD:
        samples = _decimate_scalar(samples, DECIMATE_TARGET)
        decimated = True

    times = [s[0] for s in samples]
    raw = [s[1] for s in samples]
    out: dict = {'dt': _delta_encode_ms(times, t0), 'n': len(samples)}
    if decimated:
        out['decimated'] = True

    if kind == 'scalar':
        out['v'] = [_round(v, SCALAR_DECIMALS) for v in raw]
    elif kind == 'bool':
        out['enc'] = 'rle'
        out['v'] = _rle([1 if v else 0 for v in raw])
    elif kind in ('string', 'enum'):
        # Dictionary + RLE: Reason strings are long, few, and repeat for thousands
        # of consecutive samples.
        vocab: list = []
        index: dict = {}
        idxs: list = []
        for v in raw:
            s = '' if v is None else str(v)
            if s not in index:
                index[s] = len(vocab)
                vocab.append(s)
            idxs.append(index[s])
        out['enc'] = 'dict-rle'
        out['vocab'] = vocab
        out['v'] = _rle(idxs)
    elif kind == 'pose2d':
        # Three parallel columns beat a list of {x,y,rot} objects by ~3x.
        out['x'] = [_round(p['x'], POSE_DECIMALS) for p in raw]
        out['y'] = [_round(p['y'], POSE_DECIMALS) for p in raw]
        out['rot'] = [_round(p['rot'], POSE_DECIMALS) for p in raw]
    elif kind == 'intset':
        # e.g. the set of tag ids visible this loop. Deduped and sorted so the
        # front end can compare frames cheaply, then RLE'd (tag visibility holds
        # steady for long stretches).
        out['enc'] = 'rle'
        out['v'] = _rle([sorted(set(int(i) for i in (v or []))) for v in raw])
    else:
        raise ValueError('unknown track kind: %r' % (kind,))

    return out


def spec_to_dict(spec, data: dict) -> dict:
    """spec: PlayerSpec. data: track_id -> raw list[(t, value)].

    Tracks whose data encodes to nothing are dropped from BOTH the track list and
    the payload, so the front end never has to reason about a declared-but-absent
    track."""
    encoded: dict = {}
    for track in spec.tracks:
        series = encode_series(data.get(track.id, []), track.kind, spec.t0)
        if series is not None:
            encoded[track.id] = series

    kept = [t for t in spec.tracks if t.id in encoded]
    kept_ids = {t.id for t in kept}

    panels = []
    for p in spec.panels:
        tracks = [tid for tid in p.tracks if tid in kept_ids]
        # A panel that declared tracks but has none left is just an empty box.
        if p.type in ('timeseries', 'field', 'readout') and p.tracks and not tracks:
            continue
        panels.append({**dataclasses.asdict(p), 'tracks': tracks})

    panel_ids = {p['id'] for p in panels}
    layout = [[pid for pid in row if pid in panel_ids] for row in spec.layout]
    layout = [row for row in layout if row]

    return {
        'title': spec.title,
        't0': spec.t0,
        't1': spec.t1,
        'duration': spec.duration,
        'groups': [dataclasses.asdict(g) for g in spec.groups],
        'tracks': [dataclasses.asdict(t) for t in kept],
        'panels': panels,
        'layout': layout,
        'static': spec.static,
        'warnings': spec.warnings,
        'data': encoded,
    }


def spec_to_json(spec, data: dict, indent: Optional[int] = None) -> str:
    if indent is not None:
        return json.dumps(spec_to_dict(spec, data), indent=indent)
    return json.dumps(spec_to_dict(spec, data), separators=(',', ':'))
