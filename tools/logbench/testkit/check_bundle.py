"""Check a bundle (a .wpilog plus its .vision folder) against what it should look like, and say
what is wrong in plain words. Works on bundles from build_bundle.py and on the real thing -- a
laptop simulation run with the Pi recording it (coprocessor/sim/Run-SimRobotMatch.ps1) or a
bundle fetched after a match.

    python testkit/check_bundle.py <dir or .wpilog>

For the log's driver-station windows it reports, per camera, how many recording sessions and
frames there are and how much of each enabled window has video; it flags frames recorded while
the robot was disabled, frames in the future of the log, empty sessions, sessions that pair to the
log by wall clock badly, camera folders that match no logged camera, and recorder clocks that are
off from the log's. Exit status 0 = no problems, 1 = problems found.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys
from typing import List, Optional

_HERE = pathlib.Path(__file__).resolve()
for _p in (_HERE.parents[1], _HERE.parents[1] / 'server', _HERE.parents[2] / 'wpilog-utils'):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import paths  # noqa: E402,F401  (side effect: sys.path bridges)
import bundles  # noqa: E402
import remote_fetch  # noqa: E402
from wpilog_utils.index import load_index  # noqa: E402

CAMERA_RX = re.compile(r'^/?(?:RealOutputs/)?Vision/([^/]+)/(?:Health/ScorePercent|AcceptedPoses|RawEstimatedPoses)$',
                       re.IGNORECASE)
EDGE_SLOP_SEC = 0.5          # a frame this close to an enable/disable edge is sampling and propagation jitter, not a bug
CLOCK_TOLERANCE_SEC = 15.0   # recorder wall clock vs the log's name; DS-rename lag lives inside this


def find_log(target: pathlib.Path) -> pathlib.Path:
    if target.is_file():
        return target
    logs = sorted(target.glob('*.wpilog'))
    if not logs:
        raise SystemExit('no .wpilog in %s' % target)
    return logs[0]


def check(log_path: pathlib.Path, out=print, expect_cameras: Optional[List[str]] = None) -> List[str]:
    """Returns the list of problems (empty = fine); prints a report through `out`.

    `expect_cameras` limits which logged cameras must have a recording folder (default: all of them),
    for a rig with fewer Pis than the robot has cameras."""
    problems: List[str] = []
    _raw, idx = load_index(log_path)
    t0 = idx.t_min_us / 1e6
    windows = [(m, t0 + s, t0 + e) for s, e, m in idx.mode_spans()]
    enabled = [w for w in windows if w[0] != 'disabled']
    cameras = sorted({m.group(1) for e in idx.entries.values() for m in [CAMERA_RX.match(e.name)] if m}
                     - {'CrossCameraAgreement'}, key=str.casefold)
    out('%s: %.1f s, cameras %s' % (log_path.name, idx.t_max_us / 1e6 - t0, ', '.join(cameras) or '(none logged)'))
    if not enabled:
        problems.append('the log has no enabled (auto/teleop) time, so there is nothing for video to cover')
    for mode, a, b in windows:
        out('  %-8s %7.1f - %7.1f s  (%.1f s)' % (mode, a, b, b - a))

    wall_name = re.match(r'^akit_(\d\d)-(\d\d)-(\d\d)_(\d\d)-(\d\d)-(\d\d)', log_path.name)
    log_start: Optional[dt.datetime] = None
    if wall_name:
        yy, mo, dd, hh, mi, ss = (int(g) for g in wall_name.groups())
        log_start = dt.datetime(2000 + yy, mo, dd, hh, mi, ss, tzinfo=dt.timezone.utc)

    by_folder = bundles.list_vision_sessions(log_path)
    if not by_folder:
        problems.append('no vision recordings beside the log (%s)' % bundles.vision_dir_for(log_path).name)
    folded = {c.casefold(): c for c in cameras}
    for folder, sessions in by_folder.items():
        cam = folded.get(folder.casefold())
        label = folder or '(unnamed)'
        if cam is None:
            problems.append('recording folder "%s" matches no logged camera (%s)' % (label, ', '.join(cameras)))
        out('  camera folder %s%s' % (label, '' if cam == folder or cam is None else '  (log calls it %s)' % cam))
        covered = {id(w): 0.0 for w in enabled}
        for session in sessions:
            frames = bundles.load_manifest(session)
            if not frames:
                problems.append('%s/%s has no frames (empty manifest)' % (label, session.name))
                out('    %-30s no frames' % session.name)
                continue
            first, last = frames[0][0], frames[-1][0]
            out('    %-30s %4d frames  %7.1f - %7.1f s' % (session.name, len(frames), first, last))
            off = [t for t, _f in frames if not any(a - EDGE_SLOP_SEC <= t < b + EDGE_SLOP_SEC for _m, a, b in enabled)]
            if off:
                problems.append('%s/%s: %d of %d frames fall while the robot was disabled (first at %.1f s)'
                                % (label, session.name, len(off), len(frames), off[0]))
            if last > idx.t_max_us / 1e6 + 2.0 or first < t0 - 2.0:
                problems.append('%s/%s: frames at %.1f-%.1f s lie outside the log (%.1f-%.1f s)'
                                % (label, session.name, first, last, t0, idx.t_max_us / 1e6))
            tail = (frames[-1][0] - frames[-2][0]) if len(frames) > 1 else 1 / 3
            for w in enabled:
                covered[id(w)] += max(0.0, min(last + tail, w[2]) - max(first, w[1]))
            if log_start is not None:
                wall = remote_fetch._parse_pi_session_wall_clock(session.name)
                expect = log_start + dt.timedelta(seconds=first - t0)
                if wall is not None and abs((wall - expect).total_seconds()) > CLOCK_TOLERANCE_SEC:
                    problems.append('%s/%s: folder timestamp is %.0f s from where the log says its first frame '
                                    'was (recorder clock or time zone off?)'
                                    % (label, session.name, (wall - expect).total_seconds()))
        for w in enabled:
            share = covered[id(w)] / (w[2] - w[1]) if w[2] > w[1] else 0.0
            out('    video covers %3.0f%% of %s (%.0f s)' % (share * 100, w[0], w[2] - w[1]))
            if share < 0.5 and w[2] - w[1] >= 5:
                problems.append('%s: video covers only %.0f%% of %s' % (label, share * 100, w[0]))
    required = [c for c in cameras if expect_cameras is None or c.casefold() in {e.casefold() for e in expect_cameras}]
    for cam in required:
        if cam.casefold() not in {f.casefold() for f in by_folder}:
            problems.append('logged camera %s has no recording folder' % cam)
    out('')
    out('OK' if not problems else '%d problem(s):' % len(problems))
    for p in problems:
        out('  - ' + p)
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('target', help='a bundle directory or a .wpilog')
    ap.add_argument('--expect-cameras', help='comma-separated logged cameras that must have a recording (default: all)')
    ap.add_argument('--json', action='store_true', help='print the problems as JSON instead of the report')
    args = ap.parse_args(argv)
    log = find_log(pathlib.Path(args.target))
    expect = args.expect_cameras.split(',') if args.expect_cameras else None
    if args.json:
        problems = check(log, out=lambda *_a: None, expect_cameras=expect)
        print(json.dumps({'log': log.name, 'problems': problems}, indent=2))
    else:
        problems = check(log, expect_cameras=expect)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
