"""End-to-end vision scenarios (Tier 1 of docs/logbench-e2e-test-plan.md).

`testkit.build_bundle` writes a match-shaped log plus the recorder's `.vision/<camera>/boot####-<ts>/`
folders for each scenario -- clean, NT flapping, only-auto-recorded, an empty session, a camera
name mismatch, two recorder boots, no recording -- with no robot, Pi or camera. These tests push
each one through the same code the dashboard uses: bundles -> pairing -> specs.camera_health.

Part 1 checks the kit itself. Part 2 is the contract for the dashboard data the plan asks for
(every session per camera, driver-station mode windows, recording coverage, empty-session and
partial-recording warnings). ffmpeg is not needed: preview-video building is stubbed.
"""
import datetime as dt
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import paths  # noqa: F401  (side effect: sys.path bridges)

import bundles
import pairing
import remote_fetch
from specs import camera_health
from testkit import build_bundle, frames
from vision_analyzer.parser import parse_wpilog

_REAL_PREVIEW = bundles.ensure_preview_video   # the autouse fixture below stubs the module attribute

SCENARIOS = sorted(build_bundle.SCENARIOS)
HAVE_VISION = [s for s in SCENARIOS if build_bundle.SCENARIOS[s].write_vision]
SHOWN = [s for s in HAVE_VISION if s != 'name-mismatch']   # name-mismatch is deliberately not shown


@pytest.fixture(scope='module')
def built(tmp_path_factory):
    """scenario name -> (Bundle, parsed signals). Built once per module."""
    cache = {}

    def get(name):
        if name not in cache:
            bundle = build_bundle.build_bundle(tmp_path_factory.mktemp(name.replace('-', '_')), name, cycle_ms=250)
            cache[name] = (bundle, parse_wpilog(str(bundle.log_path)))
        return cache[name]
    return get


@pytest.fixture(autouse=True)
def stub_ffmpeg(monkeypatch):
    def fake_preview(session_dir, camera=''):
        out = pathlib.Path(session_dir) / bundles.PREVIEW_NAME
        out.write_bytes(b'stub')
        return out
    monkeypatch.setattr(bundles, 'ensure_preview_video', fake_preview)


def _spec(bundle, signals):
    spec, _data = camera_health.build(signals, log_path=bundle.log_path, log_root=bundle.out_dir)
    return spec


def _with_frames(bundle, camera):
    return [(p, d) for p, d in bundle.sessions_for(camera) if p.frame_times]


# ---- Part 1: the kit, and what works today ------------------------------------------------------

def test_every_scenario_is_registered_with_a_description():
    assert {'clean', 'nt-flap', 'partial-auto-only', 'empty-session', 'name-mismatch', 'two-boots',
            'no-recording'} <= set(SCENARIOS)
    assert all(s.description for s in build_bundle.SCENARIOS.values())


@pytest.mark.parametrize('scenario', SCENARIOS)
def test_log_has_the_match_shape_the_mode_bands_need(built, scenario):
    bundle, signals = built(scenario)
    modes = [m for m, _s, _e in bundle.spans]
    assert modes == ['disabled', 'auto', 'disabled', 'teleop', 'disabled']
    assert camera_health.discover_cameras(signals) == ['LeftCam', 'RightCam']


@pytest.mark.parametrize('scenario', HAVE_VISION)
def test_frames_carry_their_own_log_time_and_mode(built, scenario):
    """The burned-in log time must equal the manifest's t_sec -- the property the dashboard's
    video sync is checked against."""
    bundle, _ = built(scenario)
    seen = 0
    for plan, session in bundle.sessions:
        manifest = [json.loads(line) for line in (session / 'manifest.jsonl').read_text().splitlines()]
        assert len(manifest) == len(plan.frame_times)
        for row in manifest[::7]:
            info = frames.decode_frame_info((session / row['frame']).read_bytes())
            assert info['t_sec'] == pytest.approx(row['t_sec'], abs=1e-6)
            assert info['mode'] == build_bundle.mode_at(bundle.spans, row['t_sec'])
            assert info['camera'] == plan.camera
            seen += 1
    assert seen or scenario == 'no-recording'


@pytest.mark.parametrize('scenario', HAVE_VISION)
def test_frames_stay_inside_the_log_and_sessions_inside_enabled_windows(built, scenario):
    bundle, signals = built(scenario)
    spec = _spec(bundle, signals)
    for plan, _session in bundle.sessions:
        if not plan.frame_times:
            continue
        assert spec.t0 <= plan.frame_times[0] and plan.frame_times[-1] <= spec.t1 + 2.0
        assert plan.frame_times == sorted(plan.frame_times)
        assert build_bundle.mode_at(bundle.spans, plan.frame_times[len(plan.frame_times) // 2]) != 'disabled'


@pytest.mark.parametrize('scenario', HAVE_VISION)
def test_session_folders_are_listed_per_camera_folder(built, scenario):
    bundle, _ = built(scenario)
    listed = bundles.list_vision_sessions(bundle.log_path)
    expected = {}
    for plan, session in bundle.sessions:
        expected.setdefault(plan.folder, []).append(session.name)
    assert {k: sorted(d.name for d in v) for k, v in listed.items()} == {k: sorted(v) for k, v in expected.items()}


def test_no_recording_scenario_has_no_vision_folder(built):
    bundle, signals = built('no-recording')
    assert bundle.vision_dir is None
    assert bundles.list_vision_sessions(bundle.log_path) == {}
    assert bundles.local_status(bundle.log_path) == 'logs only'
    assert 'vision' not in _spec(bundle, signals).static


@pytest.mark.parametrize('scenario', HAVE_VISION)
def test_folder_timestamps_pair_every_session_with_the_log(built, scenario):
    """The recorder names folders in US Eastern and the log is named in UTC; both must resolve to
    the same real instants or Fetch Bundle cannot pair them."""
    bundle, _ = built(scenario)
    rio = pairing.RioLogInfo(name=bundle.log_path.name, wall_clock=remote_fetch._parse_rio_wall_clock(
        bundle.log_path.name), duration_sec=bundle.spans[-1][2] - bundle.t0)
    assert rio.wall_clock == bundle.log_start_utc
    pis = []
    for plan, session in bundle.sessions:
        wall = remote_fetch._parse_pi_session_wall_clock(session.name)
        expected = bundle.log_start_utc + dt.timedelta(seconds=plan.start_t - bundle.t0)
        assert abs((wall - expected).total_seconds()) < 3.0, session.name
        pis.append(pairing.PiSessionInfo(camera=plan.folder, name=session.name, wall_clock=wall))
    [paired] = pairing.suggest_pairings([rio], pis)
    assert len(paired.pi_sessions) == len(bundle.sessions)


def test_nt_flap_cuts_teleop_into_several_sessions_and_clean_does_not(built):
    flap, _ = built('nt-flap')
    clean, _ = built('clean')
    assert len(clean.sessions_for('LeftCam')) == 2          # auto + teleop
    assert len(flap.sessions_for('LeftCam')) > 3            # teleop cut by the ~21 s dropouts
    gaps = [b[0].frame_times[0] - a[0].frame_times[-1]
            for a, b in zip(flap.sessions_for('LeftCam'), flap.sessions_for('LeftCam')[1:])]
    assert any(gap > 10 for gap in gaps)


def test_testkit_models_the_recorders_current_default_hold():
    """Drift guard: the kit's NT_DROP_GRACE_SEC must be the recorder's own default."""
    import importlib.util
    script = pathlib.Path(__file__).resolve().parents[3] / 'coprocessor' / 'orangepi-vision-recorder.py'
    spec = importlib.util.spec_from_file_location('recorder_under_test', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert build_bundle.NT_DROP_GRACE_SEC == module.NT_DROP_GRACE_SEC == 45.0


def test_partial_auto_only_matches_the_real_q24_shape(built):
    bundle, _ = built('partial-auto-only')
    [(plan, _d)] = bundle.sessions_for('LeftCam')
    auto = next(s for s in bundle.spans if s[0] == 'auto')
    assert len(plan.frame_times) < 50                       # the real recordings held 8-48 frames
    assert auto[1] <= plan.frame_times[0] and plan.frame_times[-1] > auto[2] - 1  # around auto, spilling past it
    assert all(t < next(s for s in bundle.spans if s[0] == 'teleop')[1] for t in plan.frame_times)


def test_two_boots_have_distinct_boot_ids(built):
    bundle, _ = built('two-boots')
    assert [p.boot_id for p, _d in bundle.sessions_for('LeftCam')] == [23, 24]


def test_empty_session_has_a_manifest_but_no_frames(built):
    bundle, _ = built('empty-session')
    [(plan, session)] = [(p, d) for p, d in bundle.sessions if not p.frame_times]
    assert (session / 'manifest.jsonl').read_text() == ''
    assert list(session.glob('frame_*.jpg')) == []


def test_name_mismatch_is_reported_not_guessed(built):
    bundle, signals = built('name-mismatch')
    spec = _spec(bundle, signals)
    assert 'vision' not in spec.static
    assert any('does not match any camera' in w and 'Right' in w for w in spec.warnings)


def test_missing_ffmpeg_stays_a_clear_warning(built, monkeypatch):
    def no_ffmpeg(session_dir, camera=''):
        raise bundles.FfmpegNotFoundError('ffmpeg is not on PATH -- required to build the preview')
    monkeypatch.setattr(bundles, 'ensure_preview_video', no_ffmpeg)
    bundle, signals = built('clean')
    spec = _spec(bundle, signals)
    assert 'vision' not in spec.static
    assert any('ffmpeg' in w and 'LeftCam' in w for w in spec.warnings)


# ---- Part 2: the dashboard contract (all sessions per camera, modes, coverage, warnings) ----------

@pytest.mark.parametrize('scenario', SHOWN)
def test_every_session_with_frames_reaches_the_dashboard(built, scenario):
    """spec.static['vision_segments'][camera] = [{'video', 't0', 't1'}, ...] in time order, one
    per session with frames; static['vision'][camera] stays as the first segment for old clients."""
    bundle, signals = built(scenario)
    spec = _spec(bundle, signals)
    segments = spec.static.get('vision_segments', {})
    for cam in bundle.cameras:
        expected = _with_frames(bundle, cam)
        got = segments.get(cam, [])
        assert len(got) == len(expected), (cam, got)
        for segment, (plan, _d) in zip(got, expected):
            assert segment['t0'] == pytest.approx(plan.frame_times[0], abs=1e-3)
            assert segment['t1'] == pytest.approx(plan.frame_times[-1], abs=1.0)
            assert segment['video'].startswith('/vision-video/')
        assert [s['t0'] for s in got] == sorted(s['t0'] for s in got)
        if expected:
            assert spec.static['vision'][cam]['t0'] == got[0]['t0']


@pytest.mark.parametrize('scenario', SCENARIOS)
def test_spec_carries_the_driver_station_modes(built, scenario):
    """spec.static['modes'] = [{'mode', 't0', 't1'}, ...] in the log timebase, from the log's own
    DriverStation signals, so the UI can label and shade disabled/auto/teleop."""
    bundle, signals = built(scenario)
    modes = _spec(bundle, signals).static.get('modes')
    assert modes is not None
    assert [m['mode'] for m in modes] == [m for m, _s, _e in bundle.spans]
    for got, (_m, start, end) in zip(modes, bundle.spans):
        assert got['t0'] == pytest.approx(start, abs=0.3)
        assert got['t1'] == pytest.approx(end, abs=0.3)


@pytest.mark.parametrize('scenario', SHOWN)
def test_recording_coverage_says_how_much_of_the_enabled_time_has_video(built, scenario):
    """spec.static['vision_coverage'][camera] = {'enabled_sec', 'covered_sec', 'fraction'}."""
    bundle, signals = built(scenario)
    coverage = _spec(bundle, signals).static.get('vision_coverage', {})
    enabled = [s for s in bundle.spans if s[0] != 'disabled']
    for cam in bundle.cameras:
        if not _with_frames(bundle, cam):
            assert cam not in coverage      # no recording, nothing to cover
            continue
        covered = 0.0
        for plan, _d in _with_frames(bundle, cam):
            lo, hi = plan.frame_times[0], plan.frame_times[-1] + 1.0 / build_bundle.SAMPLE_HZ
            covered += sum(max(0.0, min(hi, e) - max(lo, s)) for _m, s, e in enabled)
        total = sum(e - s for _m, s, e in enabled)
        assert coverage[cam]['enabled_sec'] == pytest.approx(total, abs=0.5)
        assert coverage[cam]['covered_sec'] == pytest.approx(covered, abs=1.0)
        assert coverage[cam]['fraction'] == pytest.approx(covered / total, abs=0.02)


def test_an_empty_session_is_reported_as_a_warning(built):
    bundle, signals = built('empty-session')
    [(plan, session)] = [(p, d) for p, d in bundle.sessions if not p.frame_times]
    spec = _spec(bundle, signals)
    assert any(session.name in w and 'no frames' in w.lower() for w in spec.warnings), spec.warnings
    assert len(spec.static['vision_segments'][plan.camera]) == 2   # the real sessions still show


def test_partial_recording_warns_that_most_of_the_match_has_no_video(built):
    bundle, signals = built('partial-auto-only')
    spec = _spec(bundle, signals)
    assert any('teleop' in w.lower() and 'no video' in w.lower() for w in spec.warnings), spec.warnings


# ---- Optional: the same builder over the real Q24 log (skipped when it is not on this machine) -----

GOLDEN = pathlib.Path(r'C:\Users\importsjc\robotics\logs\ruckus2026\akit_26-10-17_17-21-03_nyroc1_q24-bundle'
                      r'\akit_26-10-17_17-21-03_nyroc1_q24.wpilog')


@pytest.mark.skipif(not GOLDEN.is_file(), reason='real Q24 log not present on this machine')
def test_builder_reads_a_real_logs_modes_and_cameras(tmp_path):
    bundle = build_bundle.build_bundle(tmp_path, 'clean', log_path=GOLDEN)
    assert [m for m, _s, _e in bundle.spans] == ['disabled', 'auto', 'disabled', 'teleop', 'disabled']
    assert bundle.cameras == ['LeftCam', 'RightCam']
    assert bundle.log_start_utc == dt.datetime(2026, 10, 17, 17, 21, 3, tzinfo=dt.timezone.utc)
    auto = next(s for s in bundle.spans if s[0] == 'auto')
    assert auto[1] == pytest.approx(316.7, abs=0.5)           # 315.1 s after the log's first record at 1.6 s
    assert len(bundle.sessions_for('LeftCam')) == 2


# ---- With a real ffmpeg (skipped when it is not installed) ---------------------------------------

@pytest.mark.skipif(shutil.which('ffmpeg') is None or shutil.which('ffprobe') is None, reason='ffmpeg/ffprobe not on PATH')
def test_a_real_preview_video_spans_the_sessions_recorded_time(built):
    """Builds an actual mp4 from a session's frames (this is what broke on ffmpeg 9, which removed
    `-vsync`) and checks its length is the session's span, so video time = log time - first t_sec."""
    bundle, _ = built('clean')
    plan, session = _with_frames(bundle, 'LeftCam')[0]
    (session / bundles.PREVIEW_NAME).unlink(missing_ok=True)   # other tests leave a stub here
    mp4 = _REAL_PREVIEW(session, camera='LeftCam')
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(mp4)],
                         capture_output=True, text=True, check=True).stdout
    span = plan.frame_times[-1] - plan.frame_times[0]
    assert float(out) == pytest.approx(span + 1.0 / build_bundle.SAMPLE_HZ, abs=0.5)


# ---- testkit/check_bundle.py: the plain-words report used on simulated and real bundles ---------------

def _problems(bundle):
    from testkit import check_bundle
    return check_bundle.check(bundle.log_path, out=lambda *_a: None)


def test_checker_passes_a_clean_bundle(built):
    assert _problems(built('clean')[0]) == []


def test_checker_passes_two_boots_and_nt_flap(built):
    assert _problems(built('two-boots')[0]) == []
    assert _problems(built('nt-flap')[0]) == []


def test_checker_reports_missing_teleop_video(built):
    problems = _problems(built('partial-auto-only')[0])
    assert any('only 0% of teleop' in p for p in problems), problems


def test_checker_reports_name_mismatch_and_empty_sessions_and_no_recording(built):
    assert any('matches no logged camera' in p for p in _problems(built('name-mismatch')[0]))
    assert any('no frames' in p for p in _problems(built('empty-session')[0]))
    assert any('no vision recordings' in p for p in _problems(built('no-recording')[0]))


@pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg not on PATH')
def test_preview_video_builds_when_the_session_path_is_relative(built, monkeypatch):
    bundle, _ = built('clean')
    plan, session = _with_frames(bundle, 'RightCam')[0]
    (session / bundles.PREVIEW_NAME).unlink(missing_ok=True)
    monkeypatch.chdir(session.parents[3])
    mp4 = _REAL_PREVIEW(session.relative_to(session.parents[3]), camera='RightCam')
    assert mp4.is_file() and mp4.stat().st_size > 0


# ---- Why a camera has no video: static.vision_status ---------------------------------------------

def _status(built, scenario):
    bundle, signals = built(scenario)
    return _spec(bundle, signals).static['vision_status']


@pytest.mark.parametrize('scenario', ['clean', 'two-boots', 'nt-flap'])
def test_status_is_ok_for_every_recorded_camera(built, scenario):
    status = _status(built, scenario)
    assert {c: v['state'] for c, v in status.items()} == {'LeftCam': 'ok', 'RightCam': 'ok'}
    assert all(v['sessions'] >= 2 for v in status.values())


def test_one_camera_bundle_says_the_other_camera_has_no_recorder_folder(built):
    """The Tier 2 shape: one Pi, one camera. 'RightCam (no recording)' is accurate, and the status
    says exactly why."""
    status = _status(built, 'one-camera')
    assert status['LeftCam']['state'] == 'ok' and status['LeftCam']['sessions'] == 2
    assert status['RightCam']['state'] == 'no_folder'
    assert 'no recorder folder named RightCam' in status['RightCam']['detail']
    assert 'LeftCam' in status['RightCam']['detail']          # names the folders that do exist


def test_name_mismatch_status_names_the_folders_that_were_found(built):
    status = _status(built, 'name-mismatch')
    assert {v['state'] for v in status.values()} == {'no_folder'}
    assert 'Left' in status['LeftCam']['detail'] and 'Right' in status['LeftCam']['detail']


def test_no_recording_status(built):
    status = _status(built, 'no-recording')
    assert {v['state'] for v in status.values()} == {'no_folder'}
    assert 'no vision recordings' in status['LeftCam']['detail']


def test_empty_sessions_only_status(built, tmp_path):
    """A camera whose only sessions are empty reports 'empty', not a generic 'none'."""
    bundle = build_bundle.build_bundle(tmp_path, 'empty-session', cycle_ms=250)
    for plan, session in bundle.sessions_for('LeftCam'):
        if plan.frame_times:
            for f in session.glob('frame_*.jpg'):
                f.unlink()
            (session / 'manifest.jsonl').write_text('')
    from vision_analyzer.parser import parse_wpilog as parse
    status = _spec(bundle, parse(str(bundle.log_path))).static['vision_status']
    assert status['LeftCam']['state'] == 'empty'
    assert status['LeftCam']['empty_sessions'] == 3
    assert status['RightCam']['state'] == 'ok'


def test_each_cameras_frames_say_which_camera_they_are(built):
    """Two feeds must be distinguishable in the video: the burned-in camera number differs."""
    bundle, _ = built('clean')
    numbers = {}
    for plan, session in bundle.sessions:
        if plan.frame_times:
            first = sorted(session.glob('frame_*.jpg'))[0]
            numbers[plan.camera] = frames.decode_frame_info(first.read_bytes())['camera_index']
    assert numbers == {'LeftCam': 1, 'RightCam': 2}


# ---- A recorder that lost power mid-write must not take the whole page down ---------------------------

def _tear(session, keep_rows):
    """Leave the manifest as a brown-out would: whole rows, then half of the next one."""
    lines = (session / 'manifest.jsonl').read_text().splitlines()
    torn = lines[keep_rows][: len(lines[keep_rows]) // 2]
    (session / 'manifest.jsonl').write_text('\n'.join(lines[:keep_rows] + [torn]))
    return len(lines)


def test_read_manifest_skips_a_torn_last_row_and_a_garbage_row(tmp_path):
    (tmp_path / 'a.jpg').write_bytes(b'x')
    (tmp_path / 'b.jpg').write_bytes(b'x')
    (tmp_path / 'manifest.jsonl').write_text(
        '{"frame":"a.jpg","t_sec":1.0}\n'
        'not json at all\n'
        '{"frame":"b.jpg","t_sec":2.0}\n'
        '{"frame":"c.jpg","t_sec":3.0}\n'      # row is fine, JPEG is gone
        '{"frame":"d.jpg"}\n'                   # no t_sec
        '{"frame":"e.jpg","t_se')               # torn
    report = bundles.read_manifest(tmp_path, check_files=True)
    assert report.frames == [(1.0, 'a.jpg'), (2.0, 'b.jpg')]
    assert (report.bad_lines, report.missing_frames) == (3, 1)
    assert report.damaged
    # the plain loader tolerates it too, and (without check_files) keeps rows whose JPEG is missing
    assert [t for t, _ in bundles.load_manifest(tmp_path)] == [1.0, 2.0, 3.0]


def test_a_torn_manifest_still_builds_the_dashboard_and_says_so(built, tmp_path):
    bundle = build_bundle.build_bundle(tmp_path, 'clean', cycle_ms=250)
    plan, session = _with_frames(bundle, 'LeftCam')[1]            # LeftCam teleop
    total = _tear(session, keep_rows=100)
    from vision_analyzer.parser import parse_wpilog as parse
    spec = _spec(bundle, parse(str(bundle.log_path)))             # used to raise JSONDecodeError
    segments = spec.static['vision_segments']['LeftCam']
    assert len(segments) == 2
    assert segments[1]['t1'] < plan.frame_times[-1] - 5            # the lost tail is not claimed
    assert any('LeftCam' in w and 'unreadable' in w and 'half-written' in w for w in spec.warnings), spec.warnings
    assert spec.static['vision_status']['LeftCam']['state'] == 'ok'
    assert spec.static['vision_status']['RightCam']['sessions'] == 2   # the other camera is untouched
    assert total > 100


def test_missing_frame_files_are_skipped_not_fatal(tmp_path):
    bundle = build_bundle.build_bundle(tmp_path, 'clean', cycle_ms=250)
    plan, session = _with_frames(bundle, 'RightCam')[0]
    for jpg in sorted(session.glob('frame_*.jpg'))[3:7]:
        jpg.unlink()
    from vision_analyzer.parser import parse_wpilog as parse
    spec = _spec(bundle, parse(str(bundle.log_path)))
    assert len(spec.static['vision_segments']['RightCam']) == 2
    assert any('4 missing frame rows skipped' in w for w in spec.warnings), spec.warnings


@pytest.mark.skipif(shutil.which('ffmpeg') is None, reason='ffmpeg not on PATH')
def test_a_real_preview_video_is_built_from_a_damaged_session(tmp_path):
    bundle = build_bundle.build_bundle(tmp_path, 'clean', cycle_ms=250)
    plan, session = _with_frames(bundle, 'LeftCam')[0]
    jpgs = sorted(session.glob('frame_*.jpg'))
    jpgs[5].unlink()
    (session / 'manifest.jsonl').write_text((session / 'manifest.jsonl').read_text() + '{"frame":"frame_999.jp')
    (session / bundles.PREVIEW_NAME).unlink(missing_ok=True)
    assert _REAL_PREVIEW(session, camera='LeftCam').stat().st_size > 0
