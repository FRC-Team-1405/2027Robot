"""Build a LogBench bundle -- a .wpilog plus its Orange Pi vision recordings -- from nothing but
a match timeline, in the exact on-disk shape `coprocessor/orangepi-vision-recorder.py` writes
and `server/bundles.py` reads:

    <out>/<log>.wpilog
    <out>/<log>.vision/<camera>/boot####-<YYYYMMDD-HHMMSS>/{manifest.jsonl, frame_<t>.jpg ...}
    <out>/<log>.scenario.json        (what was built; tests and humans read it, LogBench ignores it)

Data does not have to correspond physically (no odometry/video agreement). It has the *shape* of
a match: one recording session per enabled window, frames at 3 Hz on the log's own clock, folder
timestamps from the log's wall-clock name rendered in US Eastern -- and the shapes real
recordings take when things go wrong. Scenarios are data (see SCENARIOS).

    python testkit/build_bundle.py --out <dir> --scenario clean
    python testkit/build_bundle.py --out <dir> --scenario nt-flap --log <real akit_*.wpilog>
    python testkit/build_bundle.py --list

Without --log a small synthetic match log is written (testkit/synth_log.py). With --log the
log's own mode spans and cameras are used and the file is hard-linked (or copied) into --out,
unmodified.
"""
import argparse
import dataclasses
import datetime as dt
import json
import os
import pathlib
import re
import shutil
import sys
from typing import Callable, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

_HERE = pathlib.Path(__file__).resolve()
for _p in (_HERE.parents[1], _HERE.parents[2] / 'wpilog-utils'):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from testkit import frames as frame_gen  # noqa: E402
from testkit import synth_log  # noqa: E402

PI_SESSION_TZ = ZoneInfo('America/New_York')      # the recorder's DISPLAY_TZ
DEFAULT_LOG_START = dt.datetime(2026, 10, 17, 17, 21, 3, tzinfo=dt.timezone.utc)
SAMPLE_HZ = 3.0                                    # the recorder's default
NT_DROP_GRACE_SEC = 45.0                           # the recorder's default hold through an NT dropout
LEGACY_NT_GRACE_SEC = 10.0                         # the default before 2026-10-18: what every recording in the field was made with
_AKIT_NAME = re.compile(r'^akit_(\d\d)-(\d\d)-(\d\d)_(\d\d)-(\d\d)-(\d\d)')

Span = Tuple[str, float, float]   # (mode, abs_start, abs_end) in the log's timebase


@dataclasses.dataclass
class SessionPlan:
    folder: str                    # camera folder name as the Pi names it
    camera: str                    # camera name as the log spells it
    boot_id: int
    start_t: float                 # log time the session opened (folder timestamp)
    frame_times: List[float]       # one t_sec per frame; empty -> empty manifest
    note: str = ''


@dataclasses.dataclass
class Context:
    spans: List[Span]
    cameras: List[str]
    hz: float = SAMPLE_HZ
    grace: float = NT_DROP_GRACE_SEC

    @property
    def enabled(self) -> List[Span]:
        return [s for s in self.spans if s[0] != 'disabled']


def _frame_times(lo: float, hi: float, hz: float) -> List[float]:
    step, out, t = 1.0 / hz, [], lo
    while t <= hi + 1e-9:
        out.append(round(t, 6))
        t += step
    return out


def _clean(ctx: Context, folder_of: Callable[[str], str] = lambda c: c,
           boot_of: Callable[[int], int] = lambda i: 1) -> List[SessionPlan]:
    plans = []
    for cam in ctx.cameras:
        for i, (_mode, start, end) in enumerate(ctx.enabled):
            plans.append(SessionPlan(folder_of(cam), cam, boot_of(i), start + 0.2,
                                     _frame_times(start + 0.3, end - 0.1, ctx.hz)))
    return plans


# Outage schedule (offset from the start of the enabled window, seconds, duration) modelled on the
# real Q24 log: recorder NT clients dropping for ~21 s repeatedly through teleop.
FLAP_OUTAGES = [(11.0, 21.0), (55.0, 21.0), (100.0, 21.0)]


def _nt_flap(ctx: Context) -> List[SessionPlan]:
    """What the recorder does under repeated NT dropouts: it holds a session through an outage up
    to `grace` seconds, so an outage longer than that ends the session and the reconnect opens a
    new one (same boot id, new folder). Frames keep arriving until the hold expires. This scenario
    is pinned to the legacy 10 s hold, which is what the recordings made so far have; with today's
    45 s hold the ~21 s outages would not cut a session at all."""
    plans = []
    for cam in ctx.cameras:
        for _mode, start, end in ctx.enabled:
            segments, seg_start = [], start
            for offset, duration in FLAP_OUTAGES:
                o0, o1 = start + offset, start + offset + duration
                if o0 >= end:
                    break
                if duration > ctx.grace and seg_start is not None:
                    segments.append((seg_start, min(o0 + ctx.grace, end)))
                    seg_start = o1 if o1 < end else None
            if seg_start is not None:
                segments.append((seg_start, end))
            for lo, hi in segments:
                plans.append(SessionPlan(cam, cam, 1, lo + 0.2, _frame_times(lo + 0.3, hi - 0.1, ctx.hz),
                                         'cut by NT dropout' if hi < end else ''))
    return plans


def _partial_auto_only(ctx: Context) -> List[SessionPlan]:
    """The real Q24 shape: only a few seconds around auto were ever recorded, nothing in teleop."""
    autos = [s for s in ctx.enabled if s[0] == 'auto'] or ctx.enabled[:1]
    _mode, start, end = autos[0]
    return [SessionPlan(cam, cam, 1, start + 2.4, _frame_times(start + 2.5, end + 1.6, ctx.hz),
                        'late start, runs past the end of auto') for cam in ctx.cameras]


def _empty_session(ctx: Context) -> List[SessionPlan]:
    """Clean, plus a process restart after the match that opened a session and wrote nothing
    (the real Right/boot0051)."""
    plans = _clean(ctx)
    plans.append(SessionPlan(ctx.cameras[0], ctx.cameras[0], 2, ctx.enabled[-1][2] + 20.0, [],
                             'process restart: session opened, no frames'))
    return plans


def _name_mismatch(ctx: Context) -> List[SessionPlan]:
    """The real bundle's folder is `Right` while the log says `RightCam`."""
    return _clean(ctx, folder_of=lambda c: c[:-3] if c.endswith('Cam') else c + '2')


def _two_boots(ctx: Context) -> List[SessionPlan]:
    """The recorder service restarted between auto and teleop: separate boot ids."""
    return _clean(ctx, boot_of=lambda i: 23 + i)


def _no_recording(ctx: Context) -> List[SessionPlan]:
    return []


@dataclasses.dataclass
class Scenario:
    name: str
    description: str
    plan: Callable[[Context], List[SessionPlan]]
    write_vision: bool = True
    grace: Optional[float] = None     # overrides the hold the recorder is modelled with


SCENARIOS: Dict[str, Scenario] = {s.name: s for s in [
    Scenario('clean', 'One session per enabled window (auto, teleop), frames at 3 Hz through each.', _clean),
    Scenario('nt-flap', 'Repeated ~21 s NT dropouts cut teleop into several sessions (recorder with the legacy 10 s hold).',
             _nt_flap, grace=LEGACY_NT_GRACE_SEC),
    Scenario('partial-auto-only', 'Only a few seconds around auto recorded; no teleop (the real Q24 shape).',
             _partial_auto_only),
    Scenario('empty-session', 'Clean, plus a post-match restart session with an empty manifest.', _empty_session),
    Scenario('name-mismatch', 'Recording folder name differs from the log camera name (Right vs RightCam).',
             _name_mismatch),
    Scenario('two-boots', 'Auto and teleop come from different recorder boots.', _two_boots),
    Scenario('no-recording', 'A log with no .vision folder at all.', _no_recording, write_vision=False),
]}


@dataclasses.dataclass
class Bundle:
    scenario: str
    out_dir: pathlib.Path
    log_path: pathlib.Path
    vision_dir: Optional[pathlib.Path]
    spans: List[Span]
    cameras: List[str]
    t0: float                      # first log record, log timebase
    log_start_utc: dt.datetime     # wall-clock instant of `t0`
    sessions: List[Tuple[SessionPlan, pathlib.Path]]

    def sessions_for(self, camera: str) -> List[Tuple[SessionPlan, pathlib.Path]]:
        return [(p, d) for p, d in self.sessions if p.camera == camera]


def mode_at(spans: Sequence[Span], t: float) -> str:
    for mode, start, end in spans:
        if start <= t < end:
            return mode
    return spans[-1][0] if spans and t >= spans[-1][2] else 'disabled'


def parse_akit_start(name: str) -> Optional[dt.datetime]:
    m = _AKIT_NAME.match(name)
    if not m:
        return None
    yy, mo, dd, hh, mi, ss = (int(g) for g in m.groups())
    return dt.datetime(2000 + yy, mo, dd, hh, mi, ss, tzinfo=dt.timezone.utc)


def _inspect_real_log(path: pathlib.Path) -> Tuple[List[Span], List[str], float]:
    from wpilog_utils.index import load_index
    _raw, idx = load_index(path)
    t0 = idx.t_min_us / 1e6
    spans = [(mode, t0 + s, t0 + e) for s, e, mode in idx.mode_spans()]
    cams = set()
    rx = re.compile(r'^/?(?:RealOutputs/)?Vision/([^/]+)/(?:Health/ScorePercent|AcceptedPoses|RawEstimatedPoses)$',
                    re.IGNORECASE)
    for entry in idx.entries.values():
        m = rx.match(entry.name)
        if m:
            cams.add(m.group(1))
    cams.discard('CrossCameraAgreement')
    if not spans:
        raise SystemExit('%s has no driver-station mode data; cannot place recording sessions' % path)
    return spans, sorted(cams, key=lambda c: (c.casefold(), c)), t0


def _link_or_copy(src: pathlib.Path, dst: pathlib.Path) -> None:
    dst.unlink(missing_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _manifest_row(frame_name: str, t_sec: float, wall: dt.datetime) -> dict:
    ms = round(wall.timestamp() * 1000)
    return {'frame': frame_name, 't_sec': t_sec,
            'timestamp_utc': wall.astimezone(dt.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            'timestamp_unix_ms': ms, 'timestamp_source': 'roborio_wall_clock',
            'timestamp_basis': 'recorder_receive', 'timestamp_status': 'synced'}


def build_bundle(out_dir, scenario: str = 'clean', log_path=None, spans: Optional[Sequence[Tuple[str, float]]] = None,
                 cameras: Optional[Sequence[str]] = None, log_start: Optional[dt.datetime] = None,
                 hz: float = SAMPLE_HZ, grace: float = NT_DROP_GRACE_SEC, cycle_ms: int = 100) -> Bundle:
    """Write the bundle for `scenario` into `out_dir` (created) and return what was built."""
    if scenario not in SCENARIOS:
        raise KeyError('unknown scenario %r; choose from %s' % (scenario, ', '.join(SCENARIOS)))
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if log_path is not None:
        src = pathlib.Path(log_path)
        abs_spans, found, t0 = _inspect_real_log(src)
        cams = list(cameras) if cameras else found
        log_name = src.name
        start_utc = log_start or parse_akit_start(log_name) or DEFAULT_LOG_START
        log_dest = out / log_name
        _link_or_copy(src, log_dest)
    else:
        cams = list(cameras) if cameras else ['LeftCam', 'RightCam']
        raw, info = synth_log.build_match_log(spans or synth_log.DEFAULT_SPANS, cams, cycle_ms=cycle_ms)
        abs_spans, t0 = info['spans'], info['t0']
        start_utc = log_start or DEFAULT_LOG_START
        log_name = 'akit_%s_testkit_%s.wpilog' % (start_utc.strftime('%y-%m-%d_%H-%M-%S'), scenario)
        log_dest = out / log_name
        log_dest.write_bytes(raw)
    if not cams:
        raise SystemExit('no cameras found in the log; pass --cameras')

    spec = SCENARIOS[scenario]
    plans = spec.plan(Context(abs_spans, cams, hz, grace if spec.grace is None else spec.grace))
    vision_dir = out / (log_dest.stem + '.vision') if spec.write_vision else None
    if vision_dir is not None:
        if vision_dir.exists():
            shutil.rmtree(vision_dir)
        vision_dir.mkdir()

    def wall(t: float) -> dt.datetime:
        return start_utc + dt.timedelta(seconds=t - t0)

    written: List[Tuple[SessionPlan, pathlib.Path]] = []
    used_names = set()
    for plan in plans:
        stamp = wall(plan.start_t).astimezone(PI_SESSION_TZ).strftime('%Y%m%d-%H%M%S')
        name = 'boot%04d-%s' % (plan.boot_id, stamp)
        nudge = 0
        while (plan.folder, name) in used_names:        # two sessions in one second: bump the stamp
            nudge += 1
            stamp = (wall(plan.start_t) + dt.timedelta(seconds=nudge)
                     ).astimezone(PI_SESSION_TZ).strftime('%Y%m%d-%H%M%S')
            name = 'boot%04d-%s' % (plan.boot_id, stamp)
        used_names.add((plan.folder, name))
        session = vision_dir / plan.folder / name
        session.mkdir(parents=True)
        rows = []
        for seq, t in enumerate(plan.frame_times):
            fname = 'frame_%.6f.jpg' % t
            (session / fname).write_bytes(frame_gen.make_frame(t, mode_at(abs_spans, t), seq, plan.camera))
            rows.append(_manifest_row(fname, t, wall(t)))
        (session / 'manifest.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
        written.append((plan, session))

    bundle = Bundle(scenario, out, log_dest, vision_dir, abs_spans, cams, t0, start_utc, written)
    (out / (log_dest.stem + '.scenario.json')).write_text(json.dumps({
        'scenario': scenario, 'description': spec.description, 'log': log_dest.name, 'cameras': cams,
        't0': t0, 'log_start_utc': start_utc.isoformat(),
        'spans': [list(s) for s in abs_spans],
        'sessions': [{'camera': p.camera, 'folder': p.folder, 'dir': d.name, 'boot_id': p.boot_id,
                      'frames': len(p.frame_times),
                      't_first': p.frame_times[0] if p.frame_times else None,
                      't_last': p.frame_times[-1] if p.frame_times else None, 'note': p.note}
                     for p, d in written],
    }, indent=2), encoding='utf-8')
    return bundle


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', help='output directory (created)')
    ap.add_argument('--scenario', default='clean', choices=sorted(SCENARIOS))
    ap.add_argument('--log', help='use this real .wpilog (spans and cameras are read from it) instead of a synthetic one')
    ap.add_argument('--cameras', help='comma-separated camera names (default: from the log / LeftCam,RightCam)')
    ap.add_argument('--hz', type=float, default=SAMPLE_HZ, help='frame rate of the recordings (default %(default)s)')
    ap.add_argument('--list', action='store_true', help='list scenarios and exit')
    args = ap.parse_args(argv)
    if args.list:
        for s in SCENARIOS.values():
            print('%-18s %s' % (s.name, s.description))
        return 0
    if not args.out:
        ap.error('--out is required')
    b = build_bundle(args.out, args.scenario, log_path=args.log,
                     cameras=args.cameras.split(',') if args.cameras else None, hz=args.hz)
    print('built %s: %s' % (b.scenario, b.log_path))
    for plan, d in b.sessions:
        print('  %-10s %-32s %4d frames  %s' % (plan.camera, '%s/%s' % (plan.folder, d.name),
                                                len(plan.frame_times), plan.note))
    return 0


if __name__ == '__main__':
    sys.exit(main())
