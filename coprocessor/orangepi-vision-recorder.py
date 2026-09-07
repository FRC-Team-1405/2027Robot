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

TEAM_NUMBER = 1405

CAMERA_STREAM_URL = "http://localhost:1181/stream.mjpg"  # PhotonVision RAW (pre-detection) stream for Cam1 — confirmed on bench, re-check if camera config changes
SAMPLE_HZ = 3.0

RECORDINGS_DIR = "/home/photon/vision-recordings"  # local storage for v1; swap to a USB mount point here once one is attached
MAX_STORAGE_BYTES = 5 * 1024 * 1024 * 1024  # 5GB flat cap

FMS_INFO_TABLE = "FMSInfo"
FMS_CONTROL_TOPIC = "FMSControlData"
ENABLED_BIT = 0  # HAL_ControlWord bit order: enabled, autonomous, test, eStop, fmsAttached, dsAttached — verify on bench (see docs/orangepi-vision-recorder-setup.md)

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


def new_session_dir(base):
    os.makedirs(base, exist_ok=True)
    session = os.path.join(base, time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(session, exist_ok=True)
    return session


def main():
    import ntcore

    inst = ntcore.NetworkTableInstance.getDefault()
    inst.startClient4("OrangePiVisionRecorder")
    inst.setServerTeam(TEAM_NUMBER)

    control_word_entry = inst.getTable(FMS_INFO_TABLE).getIntegerTopic(FMS_CONTROL_TOPIC).getEntry(0)

    print(f"Connecting to roboRIO (team {TEAM_NUMBER})…")

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
                    enforce_storage_cap(RECORDINGS_DIR, MAX_STORAGE_BYTES)
                    session_dir = new_session_dir(RECORDINGS_DIR)
                    manifest = open(os.path.join(session_dir, "manifest.jsonl"), "a")
                    print(f"Enabled — starting session {session_dir}")
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
