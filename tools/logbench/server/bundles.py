"""On-disk convention for pairing a .wpilog with its Orange Pi vision recording, and
turning the recording's frame sequence into a scrubbable preview video.

Beside `<name>.wpilog` under LOG_ROOT, a sibling `<name>.vision/<camera>/boot####-
<timestamp>/{manifest.jsonl, frame_*.jpg}` holds the vision recording -- copied verbatim
from the Pi's own directory structure (coprocessor/orangepi-vision-recorder.py). Once
CAMERA_NAME namespaces sessions on the Pi, this is a direct, unmodified copy: nothing in
this module renames or restructures what the Pi wrote.

This module is stdlib-only (plus an external `ffmpeg` binary for
ensure_preview_video) and knows nothing about FastAPI, paramiko, or the wpilog binary
format -- it only understands this one directory convention, so it is testable with
plain tmp_path fixtures and no server running.
"""
import json
import pathlib
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

VISION_SUFFIX = '.vision'
MANIFEST_NAME = 'manifest.jsonl'
PREVIEW_NAME = 'preview.mp4'
CONCAT_NAME = '_concat.txt'

# Used only as a last resort when a session has exactly one frame and there is no gap to
# derive a duration from -- matches the recorder's own default SAMPLE_HZ so a one-frame
# preview at least holds for a plausible instant instead of a fixed tiny stub.
_SINGLE_FRAME_DURATION_SEC = 1.0 / 3.0


class FfmpegNotFoundError(RuntimeError):
    """ffmpeg is not on PATH. Raised instead of letting subprocess surface a raw
    FileNotFoundError, so callers (server/main.py) can turn this into one clean error
    message instead of a traceback."""


def ffmpeg_available() -> bool:
    return shutil.which('ffmpeg') is not None


def vision_dir_for(log_path) -> pathlib.Path:
    """The sibling `.vision` directory for a given .wpilog path (need not exist)."""
    log_path = pathlib.Path(log_path)
    return log_path.parent / (log_path.stem + VISION_SUFFIX)


def list_vision_sessions(log_path) -> Dict[str, List[pathlib.Path]]:
    """camera name -> sorted list of that camera's session directories, under
    vision_dir_for(log_path). Empty dict if there's no vision recording for this log at
    all.

    Supports both layouts orangepi-vision-recorder.py can produce:
      - camera-namespaced: <vision_dir>/<camera>/boot####-<timestamp>/   (CAMERA_NAME set)
      - legacy, single-camera: <vision_dir>/boot####-<timestamp>/        (CAMERA_NAME unset)
    A legacy layout is reported under the '' (unnamed) camera key so callers can still
    treat it uniformly.
    """
    vision_dir = vision_dir_for(log_path)
    if not vision_dir.is_dir():
        return {}

    def _is_boot_dir(p: pathlib.Path) -> bool:
        return p.is_dir() and p.name.startswith('boot')

    top_level_boot_dirs = sorted(
        (d for d in vision_dir.iterdir() if _is_boot_dir(d)), key=lambda d: d.name)
    if top_level_boot_dirs:
        return {'': top_level_boot_dirs}

    sessions: Dict[str, List[pathlib.Path]] = {}
    for cam_dir in sorted((d for d in vision_dir.iterdir() if d.is_dir()), key=lambda d: d.name):
        cam_sessions = sorted(
            (d for d in cam_dir.iterdir() if _is_boot_dir(d)), key=lambda d: d.name)
        if cam_sessions:
            sessions[cam_dir.name] = cam_sessions
    return sessions


def load_manifest(session_dir) -> List[Tuple[float, str]]:
    """Returns [(t_sec, frame_filename), ...] sorted by t_sec, read from
    <session_dir>/manifest.jsonl. Empty list if the manifest is missing or empty --
    callers decide whether that's an error."""
    session_dir = pathlib.Path(session_dir)
    manifest_path = session_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        return []

    frames: List[Tuple[float, str]] = []
    with open(manifest_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            frames.append((float(row['t_sec']), row['frame']))
    frames.sort(key=lambda row: row[0])
    return frames


def ensure_preview_video(session_dir, camera: str = '') -> pathlib.Path:
    """Transcodes session_dir's frame_*.jpg sequence into preview.mp4, once, and returns
    its path.

    Idempotent: if preview.mp4 already exists and is at least as new as manifest.jsonl,
    it's returned unchanged rather than regenerated -- the same "cache keyed on mtime"
    idea server/main.py's spec cache uses, so re-opening a log already bundled with a
    video is instant and re-fetching/re-importing (which touches manifest.jsonl) is what
    invalidates it.

    Frame timing comes from each frame's own recorded t_sec, not an assumed capture rate
    -- SAMPLE_HZ can change on the Pi side without touching this code. This is done via
    an ffmpeg concat-demuxer list where each frame's duration is
    `next_frame.t_sec - this_frame.t_sec`; the last frame reuses the prior gap (there is
    no next frame to derive one from).

    ffmpeg concat-demuxer quirk: a `duration` directive only takes effect for the `file`
    line immediately above it, and per ffmpeg's own documentation the duration of the
    *last* file in the list is determined by demuxer/decoder behavior, not the last
    duration line -- in practice the last frame's duration is silently dropped to ~0
    unless its `file` line is repeated once more with no trailing duration. That repeated
    line is what actually makes the last frame hold for its intended time.
    """
    session_dir = pathlib.Path(session_dir)
    manifest_path = session_dir / MANIFEST_NAME
    preview_path = session_dir / PREVIEW_NAME

    if not manifest_path.is_file():
        raise FileNotFoundError('no %s in %s' % (MANIFEST_NAME, session_dir))

    if preview_path.is_file() and preview_path.stat().st_mtime >= manifest_path.stat().st_mtime:
        return preview_path

    if not ffmpeg_available():
        raise FfmpegNotFoundError(
            'ffmpeg is not on PATH -- required to build the %s vision preview video for '
            '%s. Install ffmpeg on the machine running server/main.py (not the RIO or '
            'the Pi).' % (camera or '(unnamed camera)', session_dir)
        )

    frames = load_manifest(session_dir)
    if not frames:
        raise ValueError('%s in %s has no frames' % (MANIFEST_NAME, session_dir))

    concat_lines: List[str] = []
    for i, (t_sec, filename) in enumerate(frames):
        frame_path = session_dir / filename
        if i + 1 < len(frames):
            duration = max(frames[i + 1][0] - t_sec, 0.001)
        elif i > 0:
            duration = max(t_sec - frames[i - 1][0], 0.001)
        else:
            duration = _SINGLE_FRAME_DURATION_SEC
        concat_lines.append("file '%s'" % frame_path.as_posix())
        concat_lines.append('duration %.6f' % duration)
    # The ffmpeg concat quirk described above: repeat the last file line once more, with
    # no duration, or the last frame's duration is not honored.
    concat_lines.append("file '%s'" % (session_dir / frames[-1][1]).as_posix())

    concat_file = session_dir / CONCAT_NAME
    concat_file.write_text('\n'.join(concat_lines) + '\n', encoding='utf-8')

    try:
        result = subprocess.run(
            ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', str(concat_file),
             '-vsync', 'vfr', '-pix_fmt', 'yuv420p', str(preview_path)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                'ffmpeg failed transcoding %s (%s camera):\n%s'
                % (session_dir, camera or '(unnamed)', result.stderr[-4000:])
            )
    finally:
        concat_file.unlink(missing_ok=True)

    return preview_path


def local_status(log_path) -> str:
    """'none' / 'logs only' / 'logs and vision' -- what the Fetch Bundle page's local-
    status column shows next to each remote RIO log, via list_vision_sessions."""
    log_path = pathlib.Path(log_path)
    if not log_path.is_file():
        return 'none'
    sessions = list_vision_sessions(log_path)
    has_frames = any(session_list for session_list in sessions.values())
    return 'logs and vision' if has_frames else 'logs only'
