#!/usr/bin/env python3
"""Records low-rate raw camera frames for post-match vision diagnosis.

Run this on the Orange Pi co-processor alongside PhotonVision. It taps
PhotonVision's own raw/input MJPEG stream (the pre-AprilTag-processing
feed PhotonVision already produces for its dashboard) rather than opening
the camera device a second time, so it can't compete with the detection
pipeline for camera access.

Frames are sampled at SAMPLE_HZ, gated to only while the robot is enabled
(decoded from the roboRIO's /FMSInfo NT table), and written as JPEGs with
NT-server-synced timestamps (same clock domain as .wpilog files) into a
per-session directory under RECORDINGS_DIR. Total storage is capped at
MAX_STORAGE_BYTES by deleting the oldest whole sessions.

Each manifest row also includes a real UTC receipt date/time derived from the
robot's WallClockMs publication and its atomic NT server timestamp. Missing or
stale clock correlation is recorded explicitly as null, never a guessed Pi date.

Run one service instance per camera hosted on a board, on any number of
Orange Pis. Each instance has its own CAMERA_STREAM_URL. Set CAMERA_NAME
(env var) to namespace this instance's sessions under
RECORDINGS_DIR/<CAMERA_NAME>/ and give it its own boot-id counter at
RECORDINGS_DIR/<CAMERA_NAME>/.boot_id -- required whenever more than one
camera is recorded on a board, so two instances never race on the same boot-id file or
collide on identical session-folder names. When CAMERA_NAME is unset,
sessions go directly under RECORDINGS_DIR as before (single-camera / legacy
deployments need no change). The service also reads ORANGEPI_METRICS_NAME
from the board configuration: its NT client name includes both the board
name and camera instance. It only reads the shared robot-state/clock topics;
the separate metrics publisher writes under /OrangePi/<board-name>/.

The Pi has no RTC battery, so its wall clock is unreliable across power
cycles (it can reset to a stale build-image date whenever it loses power
without reaching NTP). Session folders are therefore named
"boot<NNNN>-<timestamp>" where <NNNN> is a counter persisted on disk and
incremented once per process start — so folders from this power-on are
always distinguishable from an earlier one regardless of the clock.

For the timestamp itself: the roboRIO's clock is set from the Driver
Station laptop on every connect (a normal, accurate, battery-backed
clock), so robot code publishes it over NT (RobotContainer.publishRobotData(),
under RobotTime/WallClockMs) and this script uses the offset to label
folders with the real date/time in America/New_York, without ever
touching the Pi's own OS clock. If no robot connection has been made yet,
folders fall back to the Pi's local (possibly stale) clock — the boot
counter still makes them unambiguous either way.

Install dependency and service instances (creates a shared venv with pyntcore):
    bash setup-orangepi.sh

Run:
    ~/.venv-ntpublisher/bin/python3 orangepi-vision-recorder.py

To run on boot, add a systemd service instance (see orangepi-vision-recorder@.service
and docs/orangepi-vision-recorder-setup.md).
"""

import json
import collections
import logging
from logging.handlers import RotatingFileHandler
import os
import shutil
import socket
import threading
import time
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TEAM_NUMBER = 1405
RECORDER_VERSION = "2026.10.18.1"
MAX_WALL_CLOCK_AGE_SEC = 5.0


def _env_number(name, default, cast, minimum_exclusive=0):
    """Read a positive numeric override from the environment. Blank/unset gives
    the default; a malformed or non-positive value prints a warning and also
    falls back to the default, so a typo in an env file can't stop recording."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = cast(raw)
        if value <= minimum_exclusive or value != value or value == float("inf"):
            raise ValueError("must be positive and finite")
        return value
    except ValueError as e:
        print(f"Ignoring {name}={raw!r} ({e}); using default {default}")
        return default


# Optional: point the NT client at an explicit server (host/IP, optional port) instead of the
# roboRIO at team TEAM_NUMBER. Used with coprocessor/sim/fake_robot.py to test without a robot.
# Unset/blank = unchanged behavior (setServerTeam(TEAM_NUMBER)).
NT_SERVER = os.environ.get("NT_SERVER", "").strip()
NT_PORT = _env_number("NT_PORT", 0, int)  # 0 = NT4 default port (5810)
if NT_PORT > 65535:
    print(f"Ignoring NT_PORT={NT_PORT} (must be 1-65535); using default NT4 port")
    NT_PORT = 0

# Fallback only: each instance's EnvironmentFile must specify its confirmed RAW
# stream on this board. Ports depend on that board's PhotonVision camera config.
CAMERA_STREAM_URL = os.environ.get("CAMERA_STREAM_URL", "http://localhost:1181/stream.mjpg")
SAMPLE_HZ = _env_number("SAMPLE_HZ", 3.0, float)  # env-overridable (e.g. raised for fast simulated-match tests)

# Set when more than one camera is recorded on this Pi (see module docstring). Sessions
# and the boot-id counter are namespaced under RECORDINGS_DIR/<CAMERA_NAME>/ so the Left
# and Right systemd instances never collide.
CAMERA_NAME = os.environ.get("CAMERA_NAME", "").strip()
BOARD_NAME = os.environ.get("ORANGEPI_METRICS_NAME", "").strip() or socket.gethostname()

RECORDINGS_DIR = os.environ.get("RECORDINGS_DIR", "/home/pi/vision-recordings")  # local storage for v1; swap to a USB mount point here once one is attached
RECORDINGS_BASE = os.path.join(RECORDINGS_DIR, CAMERA_NAME) if CAMERA_NAME else RECORDINGS_DIR
MAX_STORAGE_BYTES = _env_number("MAX_STORAGE_BYTES", 5 * 1024 * 1024 * 1024, int)  # 5GB flat cap, per camera instance (env-overridable, bytes)

# Frames older than this (arrival to write) are skipped rather than recorded: it means the stream stalled.
MAX_FRAME_AGE_SEC = 2.0
# A robot that loses comms is disabled by the field, but a mere NT dropout (Pi's link, roboRIO code
# restart) reads as control word 0 == "disabled". Hold the current session through a dropout this
# long instead of ending it, so one continuous enabled period stays one session. 45 s because
# field logs (Ruckus 2026 Q24) show recorder clients dropping for ~21 s repeatedly through teleop;
# the previous 10 s default cut each of those into a separate session.
NT_DROP_GRACE_SEC = _env_number("NT_DROP_GRACE_SEC", 45.0, float)
# Right after a reconnect the control-word entry can read 0 until the server republishes it (a
# roboRIO restarting its code does this). Ignore "disabled" for this long after a reconnect that
# interrupted an enabled session.
NT_SETTLE_SEC = 2.0

# Health heartbeat: where this recorder publishes its own status, next to orangepi-nt-publisher's
# CPU/RAM/disk numbers: /OrangePi/[<ORANGEPI_METRICS_NAME>/]Recorders/<camera>/. LogBench's Health
# Check page reads it live; the robot code mirrors /OrangePi/** into the AdvantageKit log so a
# match log can be checked afterwards too. See docs/orangepi-vision-recorder-setup.md.
METRICS_NAME = os.environ.get("ORANGEPI_METRICS_NAME", "").strip()
HEARTBEAT_ROOT = "OrangePi"
HEARTBEAT_INTERVAL_SEC = 1.0
DISK_CHECK_INTERVAL_SEC = 10.0
USED_CHECK_INTERVAL_SEC = 60.0

FMS_INFO_TABLE = "FMSInfo"
FMS_CONTROL_TOPIC = "FMSControlData"
ENABLED_BIT = 0  # HAL_ControlWord bit order: enabled, autonomous, test, eStop, fmsAttached, dsAttached — verify on bench (see docs/orangepi-vision-recorder-setup.md)

# The roboRIO's system clock is set from the Driver Station laptop on every connect, so it
# stays accurate even though it (like this Pi) has no RTC battery. RobotContainer.publishRobotData()
# publishes it as UTC epoch ms; we read it and use the offset purely to *label* session
# folders with real dates — we deliberately never touch the Pi's own OS clock (no root needed,
# no risk of confusing systemd/logs/TLS if this script has a bug).
ROBOT_TIME_TABLE = "RobotTime"
ROBOT_TIME_TOPIC = "WallClockMs"
DISPLAY_TZ = ZoneInfo("America/New_York")

JPEG_SOI = b"\xff\xd8"
JPEG_EOI = b"\xff\xd9"


class RecorderDiagnostics(logging.Handler):
    """Keep startup context, then mirror diagnostics into the selected session.

    Leave the file attached while disabled so a missing next enable is diagnosable.
    Both memory and disk history are bounded; no journal permissions are required.
    """

    def __init__(self):
        super().__init__()
        self.recent = collections.deque(maxlen=100)
        self.file_handler = None
        self.log = logging.Logger("vision-recorder", level=logging.INFO)
        self.formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        console = logging.StreamHandler()
        console.setFormatter(self.formatter)
        self.log.addHandler(console)
        self.log.addHandler(self)

    def emit(self, record):
        self.recent.append(record)
        if self.file_handler is not None:
            self.file_handler.handle(record)

    def start_session(self, session_dir):
        handler = RotatingFileHandler(
            os.path.join(session_dir, "recorder.log"), maxBytes=1024 * 1024,
            backupCount=1, encoding="utf-8")
        handler.setFormatter(self.formatter)
        if self.file_handler is not None:
            self.file_handler.close()
        self.file_handler = handler
        for record in self.recent:
            handler.handle(record)

    def detach(self):
        """Release the session log file (history stays in memory for the next session). Needed
        before the storage cap deletes old sessions: a held-open file blocks deletion on Windows."""
        if self.file_handler is not None:
            self.file_handler.close()
            self.file_handler = None

    def close(self):
        self.detach()
        super().close()


def is_enabled(control_word_entry):
    """Decode the roboRIO's control word. Returns False if not yet connected."""
    raw = control_word_entry.get(0)
    return bool(int(raw) & (1 << ENABLED_BIT))


_last_server_offset_us = 0  # last offset seen while connected; reused during a dropout so t_sec stays in the server domain


def server_time_sec(inst):
    """Current time in the NT-server clock domain, in float seconds (same
    units as .wpilog timestamps). Falls back to local NT time if the
    client hasn't synced with the server yet, and to the last known offset
    (not zero) while the connection is down."""
    import ntcore

    global _last_server_offset_us
    offset_us = inst.getServerTimeOffset()
    if offset_us is not None:
        _last_server_offset_us = offset_us
    return (ntcore._now() + _last_server_offset_us) / 1_000_000.0


def frame_manifest_row(filename, t_sec, inst, robot_time_entry):
    """Map a received frame's NT time to a real UTC date/time.

    getAtomic() pairs the robot's epoch milliseconds with that publication's
    server timestamp, so transport delay and an incorrect Pi clock do not shift
    the result. This is receipt time, not camera exposure time. Missing/stale
    clock data is explicit rather than replaced with the Pi's unreliable RTC.
    """
    row = {"frame": filename, "t_sec": t_sec, "timestamp_utc": None,
           "timestamp_unix_ms": None, "timestamp_source": None,
           "timestamp_basis": "recorder_receive", "timestamp_status": "unavailable"}
    if not inst.isConnected():
        row["timestamp_status"] = "nt_disconnected"
        return row
    if inst.getServerTimeOffset() is None:
        row["timestamp_status"] = "nt_clock_unsynced"
        return row
    sample = robot_time_entry.getAtomic()
    if sample.value <= 0 or sample.serverTime <= 1:
        row["timestamp_status"] = "robot_clock_unavailable"
        return row
    age_sec = t_sec - sample.serverTime / 1_000_000.0
    if abs(age_sec) > MAX_WALL_CLOCK_AGE_SEC:
        row["timestamp_status"] = "robot_clock_stale"
        return row
    epoch_ms = sample.value + round(age_sec * 1000)
    row.update(timestamp_unix_ms=epoch_ms,
               timestamp_utc=datetime.fromtimestamp(epoch_ms / 1000, timezone.utc)
                   .isoformat(timespec="milliseconds").replace("+00:00", "Z"),
               timestamp_source="roborio_wall_clock", timestamp_status="synced")
    return row


class MjpegFrameReader:
    """Pulls single JPEG frames off a multipart/x-mixed-replace MJPEG
    stream using only the stdlib — avoids adding an OpenCV dependency for
    a job this small."""

    def __init__(self, url):
        self.url = url
        self._stream = None
        self._buf = b""

    def _ensure_open(self):
        if self._stream is None:
            self._stream = urllib.request.urlopen(self.url, timeout=5)
            self._buf = b""

    def _extract(self):
        """Cut one complete JPEG out of the buffer, or return None if there isn't one yet."""
        start = self._buf.find(JPEG_SOI)
        if start == -1:
            self._buf = self._buf[-16:]  # keep a small tail in case SOI spans chunks
            return None
        end = self._buf.find(JPEG_EOI, start)
        if end == -1:
            if start > 0:
                self._buf = self._buf[start:]  # drop leading multipart headers
            return None
        frame = self._buf[start:end + 2]
        self._buf = self._buf[end + 2:]
        return frame

    def read_frame(self):
        self._ensure_open()
        while True:
            # Parse what is already buffered BEFORE reading more: one read can carry several
            # frames, and reading first would return one frame per call while the rest pile up.
            frame = self._extract()
            if frame is not None:
                return frame
            # read1() returns whatever has arrived; read(n) would block until n bytes did.
            chunk = self._stream.read1(65536)
            if not chunk:
                raise ConnectionError("MJPEG stream closed")
            self._buf += chunk

    def close(self):
        if self._stream is not None:
            self._stream.close()
            self._stream = None


class LatestFrameReader:
    """Drains the MJPEG stream continuously on a background thread, keeping only the newest
    frame and the NT-server time it arrived.

    PhotonVision's raw stream runs at the camera rate (about 100 fps here) while we only want a
    few frames per second. Reading one frame per sample leaves the rest queued, so each read
    returned an older and older frame (measured on a Pi: recorded frames were minutes old by the
    end of a match, all predating the robot being enabled). Draining keeps the newest frame
    fresh at all times, including right after a disabled gap, and stamping it on arrival gives
    the recorded t_sec the true capture time rather than the time we got around to reading it."""

    def __init__(self, reader, inst, log=None):
        self._reader = reader
        self._inst = inst
        self._log = log
        self._lock = threading.Lock()
        self._latest = None  # (jpeg bytes, arrival t_sec, sequence number)
        self._seq = 0
        self._stop = threading.Event()
        self._last_error_print = 0.0
        self._thread = threading.Thread(target=self._run, name="mjpeg-drain", daemon=True)

    def start(self):
        self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            try:
                frame = self._reader.read_frame()
                t_sec = server_time_sec(self._inst)
                with self._lock:
                    self._seq += 1
                    self._latest = (frame, t_sec, self._seq)
            except Exception as e:
                if not self._stop.is_set() and time.monotonic() - self._last_error_print > 30.0:
                    self._last_error_print = time.monotonic()
                    if self._log is not None:  # lands in the session's recorder.log
                        self._log.error("Stream error (will keep retrying): %s", e, exc_info=True)
                    else:
                        print(f"Stream error (will keep retrying): {e}")
                self._reader.close()
                self._stop.wait(1.0)

    def latest(self):
        with self._lock:
            return self._latest

    def close(self):
        self._stop.set()
        self._reader.close()


BOOT_ID_FILE = ".boot_id"  # persisted on disk (survives power loss, unlike the Pi's batteryless RTC) so session folders stay distinguishable across restarts even when the wall clock resets


def next_boot_id(base):
    """Increment and return a counter persisted in BOOT_ID_FILE under base.

    The Orange Pi has no RTC battery, so its wall clock resets to some
    build-image default on every power cycle until it can reach an NTP
    server (often never, on a field network). A session folder named only
    by that clock can't be told apart from one made a month ago. This
    counter increments once per process start (i.e. once per boot, since
    the service starts at boot) and gets baked into the session folder
    name instead, so "this session" vs. "last session" is always clear
    regardless of what the clock reads.
    """
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, BOOT_ID_FILE)
    try:
        with open(path) as f:
            boot_id = int(f.read().strip()) + 1
    except (FileNotFoundError, ValueError):
        boot_id = 1
    with open(path, "w") as f:
        f.write(str(boot_id))
    return boot_id


def session_dirs(base):
    if not os.path.isdir(base):
        return []
    return sorted(
        (os.path.join(base, d) for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))),
        key=os.path.getmtime,
    )


def enforce_storage_cap(base, max_bytes):
    """Delete oldest whole session directories until under the cap. Never
    deletes partial sessions, so every remaining manifest.jsonl stays
    internally consistent."""
    dirs = session_dirs(base)
    total = sum(
        sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d))
        for d in dirs
    )
    i = 0
    while total > max_bytes and i < len(dirs):
        size = sum(os.path.getsize(os.path.join(dirs[i], f)) for f in os.listdir(dirs[i]))
        shutil.rmtree(dirs[i], ignore_errors=True)
        total -= size
        i += 1


def robot_clock_offset_sec(robot_time_entry):
    """Offset (seconds) to add to local time.time() to get the roboRIO's
    synced wall clock. Returns None if we haven't received a value yet
    (not connected, or robot code hasn't published one this session)."""
    raw_ms = robot_time_entry.get(0)
    if not raw_ms:
        return None
    return (raw_ms / 1000.0) - time.time()


def session_timestamp_str(offset_sec):
    """Timestamp for session/folder naming, corrected to the roboRIO's
    synced clock (falls back to the Pi's own possibly-stale local clock
    if we haven't synced yet), rendered in DISPLAY_TZ regardless of the
    Pi's own timezone setting."""
    ts = time.time() + (offset_sec or 0.0)
    return datetime.fromtimestamp(ts, tz=DISPLAY_TZ).strftime("%Y%m%d-%H%M%S")


def new_session_dir(base, boot_id, offset_sec):
    os.makedirs(base, exist_ok=True)
    session = os.path.join(base, f"boot{boot_id:04d}-{session_timestamp_str(offset_sec)}")
    os.makedirs(session, exist_ok=True)
    return session


def heartbeat_path(metrics_name=None, camera=None):
    """NT table path the heartbeat publishes under."""
    name = METRICS_NAME if metrics_name is None else metrics_name
    cam = (CAMERA_NAME if camera is None else camera) or "default"
    return "/".join(part for part in (HEARTBEAT_ROOT, name, "Recorders", cam) if part)


def directory_bytes(path):
    """Total size of the files under `path` (0 if it does not exist)."""
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


class RecorderHeartbeat:
    """Publishes this recorder's health to NetworkTables about once a second.

    Everything a person checking the robot in the pits wants to see: is the recorder alive, is the
    camera stream actually delivering frames (even while the robot is disabled), is it recording,
    is anything failing, and is there room on the disk. The consumer decides what is healthy; this
    only reports. Publishing problems are logged once and never affect recording.

    Topics (under heartbeat_path()):
      State            string   'starting' | 'idle' (stream ok, waiting for enable) | 'recording' |
                                'no_stream' (no fresh camera frames) | 'error' (recent error)
      Recording        boolean  a session is open
      StreamOk         boolean  the newest camera frame is fresh
      StreamAgeSec     double   age of the newest camera frame, -1 if none yet
      StreamFps        double   frames per second arriving from the camera stream
      SessionFrames    integer  frames written in the current/last session
      Sessions         integer  sessions started since this process booted
      TotalFrames      integer  frames written since boot
      Errors           integer  errors since boot
      LastError        string   last error message ('' if none)
      DiskFreeGB       double   free space where recordings are stored
      RecordingsUsedGB double   space the recordings under this camera's folder use
      ClockSynced      boolean  the roboRIO wall clock has been received (session names are trustworthy)
      UptimeSec        double   seconds since this process started
      HeartbeatSec     double   increments every publish; also lets a consumer see a frozen loop
      Version, BootId, SampleHz   static identity
    """

    def __init__(self, table, version, boot_id, sample_hz, recordings_dir, recordings_base,
                 clock=time.monotonic, disk_usage=shutil.disk_usage, dir_bytes=directory_bytes,
                 interval=HEARTBEAT_INTERVAL_SEC):
        self._clock = clock
        self._disk_usage = disk_usage
        self._dir_bytes = dir_bytes
        self._dir = recordings_dir
        self._base = recordings_base
        self._interval = interval
        self._started = clock()
        self._last_publish = None
        self._beats = 0
        self._last_seq = None
        self._last_seq_time = None
        self._fps = 0.0
        self._disk_free_gb = 0.0
        self._disk_checked = None
        self._used_gb = 0.0
        self._used_checked = None
        self._failed = False
        self._pubs = {}
        try:
            for name, kind in (
                ("State", "String"), ("Recording", "Boolean"), ("StreamOk", "Boolean"),
                ("StreamAgeSec", "Double"), ("StreamFps", "Double"), ("SessionFrames", "Integer"),
                ("Sessions", "Integer"), ("TotalFrames", "Integer"), ("Errors", "Integer"),
                ("LastError", "String"), ("DiskFreeGB", "Double"), ("RecordingsUsedGB", "Double"),
                ("ClockSynced", "Boolean"), ("UptimeSec", "Double"), ("HeartbeatSec", "Double"),
                ("Version", "String"), ("BootId", "Integer"), ("SampleHz", "Double"),
            ):
                self._pubs[name] = getattr(table, f"get{kind}Topic")(name).publish()
            self._pubs["Version"].set(version)
            self._pubs["BootId"].set(int(boot_id))
            self._pubs["SampleHz"].set(float(sample_hz))
            self._pubs["State"].set("starting")
        except Exception:
            self._failed = True
            self._pubs = {}

    def _refresh_slow(self, now):
        if self._disk_checked is None or now - self._disk_checked >= DISK_CHECK_INTERVAL_SEC:
            self._disk_checked = now
            try:
                probe = self._dir if os.path.isdir(self._dir) else os.path.dirname(self._dir.rstrip("/")) or "/"
                self._disk_free_gb = round(self._disk_usage(probe).free / 1e9, 2)
            except OSError:
                self._disk_free_gb = -1.0
        if self._used_checked is None or now - self._used_checked >= USED_CHECK_INTERVAL_SEC:
            self._used_checked = now
            try:
                self._used_gb = round(self._dir_bytes(self._base) / 1e9, 3)
            except OSError:
                self._used_gb = -1.0

    def due(self):
        """True when update() would publish now, so callers can skip gathering the inputs."""
        return not self._failed and (self._last_publish is None
                                     or self._clock() - self._last_publish >= self._interval)

    def update(self, *, recording, stream_age_sec, stream_seq, session_frames, sessions, total_frames,
               errors, last_error, last_error_age_sec, clock_synced, log=None):
        """Call every loop; publishes at most once per interval. Returns True if it published."""
        now = self._clock()
        if self._failed:
            return False
        if self._last_publish is not None and now - self._last_publish < self._interval:
            return False
        self._last_publish = now
        self._refresh_slow(now)
        if stream_seq is not None and self._last_seq is not None and now > self._last_seq_time:
            self._fps = round(max(0, stream_seq - self._last_seq) / (now - self._last_seq_time), 1)
        elif stream_seq is None:
            self._fps = 0.0
        if stream_seq is not None:
            self._last_seq, self._last_seq_time = stream_seq, now
        stream_ok = stream_age_sec is not None and stream_age_sec <= MAX_FRAME_AGE_SEC
        if last_error and last_error_age_sec is not None and last_error_age_sec < 30.0:
            state = "error"
        elif not stream_ok:
            state = "no_stream"
        elif recording:
            state = "recording"
        else:
            state = "idle"
        self._beats += 1
        values = {
            "State": state, "Recording": bool(recording), "StreamOk": bool(stream_ok),
            "StreamAgeSec": round(stream_age_sec, 3) if stream_age_sec is not None else -1.0,
            "StreamFps": self._fps, "SessionFrames": int(session_frames), "Sessions": int(sessions),
            "TotalFrames": int(total_frames), "Errors": int(errors), "LastError": last_error or "",
            "DiskFreeGB": self._disk_free_gb, "RecordingsUsedGB": self._used_gb,
            "ClockSynced": bool(clock_synced), "UptimeSec": round(now - self._started, 1),
            "HeartbeatSec": float(self._beats),
        }
        try:
            for name, value in values.items():
                self._pubs[name].set(value)
        except Exception:
            self._failed = True
            if log is not None:
                log.exception("Heartbeat publishing failed; recording continues without it")
            return False
        return True


def _session_summary(stats):
    """One-line summary of a finished session: frames written, how old each was when written
    (arrival to write, so roughly the sampling jitter), and any frames skipped."""
    ages = sorted(stats["age_ms"])
    if not ages:
        return "no frames written"
    return (f"{len(ages)} frames written, age at write ms median/max {ages[len(ages) // 2]:.0f}/{ages[-1]:.0f}, "
            f"skipped {stats['stale']} stale + {stats['nonew']} with no new frame")


def main():
    import ntcore

    inst = ntcore.NetworkTableInstance.getDefault()
    inst.startClient4(f"OrangePiVisionRecorder-{BOARD_NAME}-{CAMERA_NAME or 'default'}")
    if NT_SERVER:
        inst.setServer(NT_SERVER, NT_PORT)
        server_desc = f"NT server {NT_SERVER}:{NT_PORT or 5810}"
    else:
        inst.setServerTeam(TEAM_NUMBER)
        server_desc = None

    control_word_entry = inst.getTable(FMS_INFO_TABLE).getIntegerTopic(FMS_CONTROL_TOPIC).getEntry(0)
    robot_time_entry = inst.getTable(ROBOT_TIME_TABLE).getIntegerTopic(ROBOT_TIME_TOPIC).getEntry(0)

    boot_id = next_boot_id(RECORDINGS_BASE)
    heartbeat = RecorderHeartbeat(inst.getTable(heartbeat_path()), RECORDER_VERSION, boot_id, SAMPLE_HZ,
                                  RECORDINGS_DIR, RECORDINGS_BASE)

    diagnostics = RecorderDiagnostics()
    log = diagnostics.log
    cam_note = f" [camera {CAMERA_NAME}]" if CAMERA_NAME else ""
    target = server_desc or f"roboRIO (team {TEAM_NUMBER})"
    context = (f"version={RECORDER_VERSION} board={BOARD_NAME} camera={CAMERA_NAME or 'default'} "
               f"boot={boot_id} team={TEAM_NUMBER} stream={CAMERA_STREAM_URL} sample_hz={SAMPLE_HZ}")
    log.info("Recorder started: %s", context)
    log.info("Connecting to %s%s [boot %s, local clock reads %s]", target, cam_note, boot_id,
             time.strftime("%Y-%m-%d %H:%M:%S"))

    reader = MjpegFrameReader(CAMERA_STREAM_URL)
    frame_source = LatestFrameReader(reader, inst, log)
    frame_source.start()
    period_s = 1.0 / SAMPLE_HZ

    session_dir = None
    manifest = None
    was_enabled = False
    disconnected_since = None
    reconnected_at = None
    ever_connected = False
    last_seq = 0
    stats = {"age_ms": [], "stale": 0, "nonew": 0}
    frames = 0
    errors = 0
    last_state = None
    last_status = float('-inf')
    sessions_started = 0
    total_frames = 0
    total_errors = 0
    last_error = ""
    last_error_at = None

    try:
        while True:
            loop_start = time.monotonic()
            newest = None  # the newest camera frame, if the capture step below fetched it
            try:
                if inst.isConnected():
                    enabled = is_enabled(control_word_entry)
                    if disconnected_since is not None and ever_connected:
                        log.info("NT reconnected after %.1fs", time.monotonic() - disconnected_since)
                        reconnected_at = time.monotonic()
                    elif not ever_connected:
                        log.info("NT connected")
                    ever_connected = True
                    disconnected_since = None
                    if (was_enabled and not enabled and reconnected_at is not None
                            and time.monotonic() - reconnected_at < NT_SETTLE_SEC):
                        enabled = True  # stale 0 right after a reconnect, not a real disable
                else:
                    # An NT dropout reads as control word 0 == "disabled"; hold the session through a short one.
                    if disconnected_since is None:
                        disconnected_since = time.monotonic()
                        if was_enabled:
                            log.warning("NT connection lost while enabled - holding the session up to %gs",
                                        NT_DROP_GRACE_SEC)
                    enabled = was_enabled and time.monotonic() - disconnected_since <= NT_DROP_GRACE_SEC
                    if was_enabled and not enabled:
                        log.warning("NT NOT connected for over %gs - treating the robot as disabled",
                                    NT_DROP_GRACE_SEC)

                state = (inst.isConnected(), int(control_word_entry.get(0)), enabled)
                if state != last_state:
                    log.info("Robot state: nt_connected=%s control_word=%s enabled=%s", *state)
                    last_state = state
                if loop_start - last_status >= 10.0:
                    log.info("Status: nt_connected=%s control_word=%s enabled=%s frames=%d errors=%d "
                             "nt_time=%.6f clock_synced=%s", *state, frames, errors,
                             server_time_sec(inst), inst.getServerTimeOffset() is not None)
                    last_status = loop_start

                if enabled and not was_enabled:
                    offset_sec = robot_clock_offset_sec(robot_time_entry)
                    diagnostics.detach()
                    enforce_storage_cap(RECORDINGS_BASE, MAX_STORAGE_BYTES)
                    session_dir = new_session_dir(RECORDINGS_BASE, boot_id, offset_sec)
                    try:
                        diagnostics.start_session(session_dir)
                    except OSError:
                        log.exception("Could not open session diagnostics in %s", session_dir)
                    manifest = open(os.path.join(session_dir, "manifest.jsonl"), "a")
                    sessions_started += 1
                    frames = errors = 0
                    sync_note = f"synced to roboRIO, offset {offset_sec:+.1f}s" if offset_sec is not None \
                        else "NOT synced to roboRIO — using Pi's own possibly-stale clock"
                    stats = {"age_ms": [], "stale": 0, "nonew": 0}
                    log.info("Enabled — starting session %s (%s); %s", session_dir, sync_note, context)
                elif not enabled and was_enabled:
                    if manifest:
                        manifest.close()
                    manifest = None
                    nt_note = "NT connected" if inst.isConnected() else "NT NOT connected"
                    log.info("Disabled — session ended (%s): frames=%d errors=%d; %s",
                             nt_note, frames, errors, _session_summary(stats))

                was_enabled = enabled

                if enabled and session_dir:
                    latest = newest = frame_source.latest()
                    if latest is None or latest[2] == last_seq:
                        stats["nonew"] += 1
                    else:
                        frame, t_sec, last_seq = latest
                        age_sec = server_time_sec(inst) - t_sec
                        if age_sec > MAX_FRAME_AGE_SEC:
                            stats["stale"] += 1  # stream stalled; never record an old frame as if it were current
                        else:
                            filename = f"frame_{t_sec:.6f}.jpg"
                            row = frame_manifest_row(filename, t_sec, inst, robot_time_entry)
                            with open(os.path.join(session_dir, filename), "wb") as f:
                                f.write(frame)
                            manifest.write(json.dumps(row) + "\n")
                            manifest.flush()
                            frames += 1
                            total_frames += 1
                            stats["age_ms"].append(age_sec * 1000.0)

            except Exception as exc:
                errors += 1
                total_errors += 1
                last_error, last_error_at = f"{type(exc).__name__}: {exc}"[:200], time.monotonic()
                log.exception("Recorder error: frames=%d errors=%d", frames, errors)

            try:
                if heartbeat.due():
                    if newest is None:
                        newest = frame_source.latest()
                    heartbeat.update(
                        recording=manifest is not None,
                        stream_age_sec=(server_time_sec(inst) - newest[1]) if newest else None,
                        stream_seq=newest[2] if newest else None,
                        session_frames=frames, sessions=sessions_started, total_frames=total_frames,
                        errors=total_errors, last_error=last_error,
                        last_error_age_sec=(time.monotonic() - last_error_at) if last_error_at else None,
                        clock_synced=inst.getServerTimeOffset() is not None and bool(robot_time_entry.get(0)),
                        log=log)
            except Exception:
                log.exception("Heartbeat update failed")

            elapsed = time.monotonic() - loop_start
            time.sleep(max(0.0, period_s - elapsed))
    finally:
        log.info("Recorder stopping: frames=%d errors=%d", frames, errors)
        if manifest:
            manifest.close()
        frame_source.close()
        diagnostics.close()


if __name__ == "__main__":
    main()
