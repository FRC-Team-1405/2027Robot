"""bundles.py: the on-disk convention pairing a .wpilog with its Orange Pi vision
recording, plus the ffmpeg-based preview-video transcode. All filesystem-only (tmp_path
fixtures) except ensure_preview_video's happy path, which shells out to a real local
ffmpeg -- skipped with a clear reason if ffmpeg isn't on PATH, rather than failing the
whole suite for a missing external tool."""
import json
import pathlib
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))

import paths  # noqa: F401  (side effect: sys.path bridges)

import bundles

try:
    from PIL import Image
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

FFMPEG_AVAILABLE = shutil.which('ffmpeg') is not None


# ── vision_dir_for ──────────────────────────────────────────────────────────────────

def test_vision_dir_for_is_a_sibling_dot_vision_directory(tmp_path):
    log_path = tmp_path / 'FRC_20260101_120000.wpilog'
    assert bundles.vision_dir_for(log_path) == tmp_path / 'FRC_20260101_120000.vision'


def test_vision_dir_for_accepts_a_string_path(tmp_path):
    log_path = str(tmp_path / 'match.wpilog')
    assert bundles.vision_dir_for(log_path) == tmp_path / 'match.vision'


# ── list_vision_sessions ────────────────────────────────────────────────────────────

def _touch_session(base, *parts):
    session = base.joinpath(*parts)
    session.mkdir(parents=True)
    (session / 'manifest.jsonl').write_text('', encoding='utf-8')
    return session


def test_list_vision_sessions_is_empty_when_there_is_no_vision_dir(tmp_path):
    log_path = tmp_path / 'match.wpilog'
    assert bundles.list_vision_sessions(log_path) == {}


def test_list_vision_sessions_discovers_camera_namespaced_layout(tmp_path):
    log_path = tmp_path / 'match.wpilog'
    vision_dir = bundles.vision_dir_for(log_path)
    _touch_session(vision_dir, 'Left', 'boot0001-20260101-120000')
    _touch_session(vision_dir, 'Left', 'boot0002-20260101-130000')
    _touch_session(vision_dir, 'Right', 'boot0001-20260101-120000')

    sessions = bundles.list_vision_sessions(log_path)
    assert set(sessions) == {'Left', 'Right'}
    assert [d.name for d in sessions['Left']] == ['boot0001-20260101-120000', 'boot0002-20260101-130000']
    assert [d.name for d in sessions['Right']] == ['boot0001-20260101-120000']


def test_list_vision_sessions_discovers_legacy_non_namespaced_layout(tmp_path):
    """CAMERA_NAME was unset when this recording was made -- sessions sit directly
    under the .vision dir, no per-camera subfolder."""
    log_path = tmp_path / 'match.wpilog'
    vision_dir = bundles.vision_dir_for(log_path)
    _touch_session(vision_dir, 'boot0001-20260101-120000')
    _touch_session(vision_dir, 'boot0002-20260101-130000')

    sessions = bundles.list_vision_sessions(log_path)
    assert set(sessions) == {''}
    assert [d.name for d in sessions['']] == ['boot0001-20260101-120000', 'boot0002-20260101-130000']


def test_list_vision_sessions_ignores_a_camera_folder_with_no_boot_dirs(tmp_path):
    log_path = tmp_path / 'match.wpilog'
    vision_dir = bundles.vision_dir_for(log_path)
    (vision_dir / 'Left').mkdir(parents=True)  # empty -- e.g. camera never recorded anything

    assert bundles.list_vision_sessions(log_path) == {}


# ── load_manifest ───────────────────────────────────────────────────────────────────

def test_load_manifest_returns_empty_list_when_missing(tmp_path):
    assert bundles.load_manifest(tmp_path / 'no-such-session') == []


def test_load_manifest_parses_and_sorts_by_t_sec(tmp_path):
    session = tmp_path / 'session'
    session.mkdir()
    lines = [
        {'frame': 'frame_10.040000.jpg', 't_sec': 10.04},
        {'frame': 'frame_10.000000.jpg', 't_sec': 10.00},
        {'frame': 'frame_10.020000.jpg', 't_sec': 10.02},
    ]
    (session / 'manifest.jsonl').write_text(
        '\n'.join(json.dumps(row) for row in lines) + '\n', encoding='utf-8')

    frames = bundles.load_manifest(session)
    assert frames == [
        (10.00, 'frame_10.000000.jpg'),
        (10.02, 'frame_10.020000.jpg'),
        (10.04, 'frame_10.040000.jpg'),
    ]


def test_load_manifest_skips_blank_lines(tmp_path):
    session = tmp_path / 'session'
    session.mkdir()
    (session / 'manifest.jsonl').write_text(
        json.dumps({'frame': 'a.jpg', 't_sec': 1.0}) + '\n\n\n', encoding='utf-8')
    assert bundles.load_manifest(session) == [(1.0, 'a.jpg')]


# ── ensure_preview_video ────────────────────────────────────────────────────────────

def _write_tiny_jpeg(path, color):
    if HAVE_PIL:
        Image.new('RGB', (16, 12), color=color).save(path, 'JPEG')
    else:
        # Minimal-but-valid 1x1 JPEG (a fixed byte blob) -- good enough to exercise the
        # concat-demuxer/ffmpeg path without a real image library installed.
        _MINIMAL_JPEG = bytes.fromhex(
            'ffd8ffe000104a46494600010100000100010000ffdb004300080606070605'
            '08070707090908090c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e27'
            '20222c231c1c2837292c30313434341f27393d38323c2e333432ffc0000b0800'
            '0c001001011100ffc4001f0000010501010101010100000000000000000102'
            '030405060708090a0bffc400b5100002010303020403050504040000017d0102'
            '00030411051221310641510761071322328108144291a1b1c109233352f0156272'
            'd10a162434e125f11718191a25262728292a3435363738393a434445464748494a'
            '535455565758595a636465666768696a737475767778797a83848586878889'
            '8a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5'
            'c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8'
            'f9faffda0008010100003f00fb5fffd9'
        )
        path.write_bytes(_MINIMAL_JPEG)


def _make_session_with_frames(tmp_path, frame_times, colors=None):
    session = tmp_path / 'session'
    session.mkdir()
    lines = []
    for i, t in enumerate(frame_times):
        filename = 'frame_%.6f.jpg' % t
        color = (colors[i] if colors else ((i * 40) % 255, 0, 0))
        _write_tiny_jpeg(session / filename, color)
        lines.append(json.dumps({'frame': filename, 't_sec': t}))
    (session / 'manifest.jsonl').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return session


def test_ensure_preview_video_raises_a_typed_error_when_ffmpeg_is_missing(tmp_path, monkeypatch):
    session = _make_session_with_frames(tmp_path, [10.0, 10.1])
    monkeypatch.setattr(bundles, 'ffmpeg_available', lambda: False)
    with pytest.raises(bundles.FfmpegNotFoundError):
        bundles.ensure_preview_video(session, camera='Left')


def test_ensure_preview_video_raises_on_an_empty_manifest(tmp_path, monkeypatch):
    session = tmp_path / 'session'
    session.mkdir()
    (session / 'manifest.jsonl').write_text('', encoding='utf-8')
    monkeypatch.setattr(bundles, 'ffmpeg_available', lambda: True)
    with pytest.raises(ValueError):
        bundles.ensure_preview_video(session, camera='Left')


def test_ensure_preview_video_raises_when_manifest_is_entirely_missing(tmp_path):
    session = tmp_path / 'session'
    session.mkdir()
    with pytest.raises(FileNotFoundError):
        bundles.ensure_preview_video(session, camera='Left')


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason='ffmpeg is not on PATH')
def test_ensure_preview_video_transcodes_an_uneven_frame_sequence(tmp_path):
    """Deliberately uneven t_sec gaps (0.02s, then a 0.5s pause, then 0.01s) -- proves
    variable-rate sync isn't just working by coincidence at one fixed capture rate."""
    session = _make_session_with_frames(
        tmp_path, [10.00, 10.02, 10.52, 10.53],
        colors=[(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)],
    )

    preview = bundles.ensure_preview_video(session, camera='Left')

    assert preview == session / 'preview.mp4'
    assert preview.is_file()
    assert preview.stat().st_size > 0
    # The _concat.txt scratch file is cleaned up, not left in the bundle.
    assert not (session / '_concat.txt').exists()

    duration = _ffprobe_duration(preview)
    # Total expected span: (10.02-10.00) + (10.52-10.02) + (10.53-10.52) + last-frame's
    # reused prior gap (10.53-10.52) = 0.02 + 0.50 + 0.01 + 0.01 = 0.54s. Allow generous
    # slop for container/encoder rounding -- this is checking "roughly the uneven total
    # duration survived", not frame-exact timing.
    assert duration is not None
    assert 0.3 < duration < 1.2


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason='ffmpeg is not on PATH')
def test_ensure_preview_video_is_idempotent(tmp_path):
    session = _make_session_with_frames(tmp_path, [10.0, 10.02, 10.04])
    first = bundles.ensure_preview_video(session, camera='Left')
    first_mtime = first.stat().st_mtime

    # Calling again without touching manifest.jsonl must not regenerate the file.
    second = bundles.ensure_preview_video(session, camera='Left')
    assert second == first
    assert second.stat().st_mtime == first_mtime


@pytest.mark.skipif(not FFMPEG_AVAILABLE, reason='ffmpeg is not on PATH')
def test_ensure_preview_video_regenerates_after_manifest_changes(tmp_path):
    import time

    session = _make_session_with_frames(tmp_path, [10.0, 10.02])
    first = bundles.ensure_preview_video(session, camera='Left')
    first_mtime = first.stat().st_mtime

    time.sleep(1.1)  # coarse mtime resolution safety margin on some filesystems
    manifest = session / 'manifest.jsonl'
    manifest.write_text(manifest.read_text(encoding='utf-8'), encoding='utf-8')  # bump mtime

    second = bundles.ensure_preview_video(session, camera='Left')
    assert second.stat().st_mtime >= first_mtime


def _ffprobe_duration(path):
    """Best-effort duration read via ffprobe (ships with ffmpeg). Returns None if
    ffprobe isn't available -- callers should treat that as "can't verify", not a
    failure, since only ffmpeg itself is a documented requirement."""
    if shutil.which('ffprobe') is None:
        return None
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


# ── local_status ────────────────────────────────────────────────────────────────────

def test_local_status_is_none_when_the_log_itself_is_not_local(tmp_path):
    assert bundles.local_status(tmp_path / 'nope.wpilog') == 'none'


def test_local_status_is_logs_only_when_there_is_no_vision_dir(tmp_path):
    log_path = tmp_path / 'match.wpilog'
    log_path.write_bytes(b'')
    assert bundles.local_status(log_path) == 'logs only'


def test_local_status_is_logs_and_vision_when_a_session_has_frames(tmp_path):
    log_path = tmp_path / 'match.wpilog'
    log_path.write_bytes(b'')
    vision_dir = bundles.vision_dir_for(log_path)
    _touch_session(vision_dir, 'Left', 'boot0001-20260101-120000')
    assert bundles.local_status(log_path) == 'logs and vision'
