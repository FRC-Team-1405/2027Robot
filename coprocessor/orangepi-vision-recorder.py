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

Install dependency:
    pip install pyntcore

Run:
    python3 orangepi-vision-recorder.py

To run on boot, add a systemd service (see orangepi-vision-recorder.service).
"""

import json
import os
import shutil
import time
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

TEAM_NUMBER = 1405

CAMERA_STREAM_URL = "http://localhost:1181/stream.mjpg"  # PhotonVision RAW (pre-detection) stream for Cam1 — confirmed on bench, re-check if camera config changes
SAMPLE_HZ = 3.0

RECORDINGS_DIR = "/home/pi/vision-recordings"  # local storage for v1; swap to a USB mount point here once one is attached
MAX_STORAGE_BYTES = 5 * 1024 * 1024 * 1024  # 5GB flat cap

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


def is_enabled(control_word_entry):
    """Decode the roboRIO's control word. Returns False if not yet connected."""
    raw = control_word_entry.get(0)
    return bool(int(raw) & (1 << ENABLED_BIT))


def server_time_sec(inst):
    """Current time in the NT-server clock domain, in float seconds (same
    units as .wpilog timestamps). Falls back to local NT time if the
    client hasn't synced with the server yet."""
    import ntcore

    offset_us = inst.getServerTimeOffset() or 0
    local_us = ntcore._now()
    return (local_us + offset_us) / 1_000_000.0


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

    def read_frame(self):
        self._ensure_open()
        while True:
            chunk = self._stream.read(4096)
            if not chunk:
                raise ConnectionError("MJPEG stream closed")
            self._buf += chunk
            start = self._buf.find(JPEG_SOI)
            if start == -1:
                self._buf = self._buf[-16:]  # keep a small tail in case SOI spans chunks
                continue
            end = self._buf.find(JPEG_EOI, start)
            if end == -1:
                if start > 0:
                    self._buf = self._buf[start:]  # drop leading multipart headers
                continue
            frame = self._buf[start:end + 2]
            self._buf = self._buf[end + 2:]
            return frame

    def close(self):
        if self._stream is not None:
            self._stream.close()
            self._stream = None


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


def main():
    import ntcore

    inst = ntcore.NetworkTableInstance.getDefault()
    inst.startClient4("OrangePiVisionRecorder")
    inst.setServerTeam(TEAM_NUMBER)

    control_word_entry = inst.getTable(FMS_INFO_TABLE).getIntegerTopic(FMS_CONTROL_TOPIC).getEntry(0)
    robot_time_entry = inst.getTable(ROBOT_TIME_TABLE).getIntegerTopic(ROBOT_TIME_TOPIC).getEntry(0)

    boot_id = next_boot_id(RECORDINGS_DIR)

    print(f"Connecting to roboRIO (team {TEAM_NUMBER})… [boot {boot_id}, local clock reads {time.strftime('%Y-%m-%d %H:%M:%S')}]")

    reader = MjpegFrameReader(CAMERA_STREAM_URL)
    period_s = 1.0 / SAMPLE_HZ

    session_dir = None
    manifest = None
    was_enabled = False

    try:
        while True:
            loop_start = time.monotonic()
            try:
                enabled = is_enabled(control_word_entry)

                if enabled and not was_enabled:
                    offset_sec = robot_clock_offset_sec(robot_time_entry)
                    enforce_storage_cap(RECORDINGS_DIR, MAX_STORAGE_BYTES)
                    session_dir = new_session_dir(RECORDINGS_DIR, boot_id, offset_sec)
                    manifest = open(os.path.join(session_dir, "manifest.jsonl"), "a")
                    sync_note = f"synced to roboRIO, offset {offset_sec:+.1f}s" if offset_sec is not None \
                        else "NOT synced to roboRIO — using Pi's own possibly-stale clock"
                    print(f"Enabled — starting session {session_dir} ({sync_note})")
                elif not enabled and was_enabled:
                    if manifest:
                        manifest.close()
                    manifest = None
                    print("Disabled — session ended")

                was_enabled = enabled

                if enabled and session_dir:
                    frame = reader.read_frame()
                    t_sec = server_time_sec(inst)
                    filename = f"frame_{t_sec:.6f}.jpg"
                    with open(os.path.join(session_dir, filename), "wb") as f:
                        f.write(frame)
                    manifest.write(json.dumps({"frame": filename, "t_sec": t_sec}) + "\n")
                    manifest.flush()

            except Exception as e:
                print(f"Recorder error: {e}")
                reader.close()

            elapsed = time.monotonic() - loop_start
            time.sleep(max(0.0, period_s - elapsed))
    finally:
        if manifest:
            manifest.close()
        reader.close()


if __name__ == "__main__":
    main()
