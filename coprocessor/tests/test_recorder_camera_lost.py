"""The recorder notices PhotonVision's "Camera Lost" card, survives power cuts, and says exactly
which code it is.

Background (2026-10-24 practice log): LeftCam's USB camera dropped mid-teleop. PhotonVision kept
serving its raw stream, but every frame was the same 105x60 "Camera Lost" card, so the recorder
wrote 93 s of it while reporting 0 stale frames and 0 errors. The robot was then powered off
seconds after disable, and the RightPi lost the end of recorder.log and its last frames because
nothing had been fsynced. And both Pis reported version 2026.10.18.1, a string that had not been
bumped across four later commits, so the log could not say which code was running.
"""
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_nt_identities import load_script
from test_recorder_heartbeat import beat, make

FIXTURES = Path(__file__).resolve().parent / "fixtures"
COPROCESSOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COPROCESSOR / "sim"))

import fake_mjpeg  # noqa: E402  (stdlib only)

# PhotonVision's own placeholder, saved from the LeftPi recording of that log.
CAMERA_LOST_CARD = (FIXTURES / "photonvision-camera-lost.jpg").read_bytes()


class ListLog(logging.Logger):
    def __init__(self):
        super().__init__("test", level=logging.INFO)
        self.lines = []
        handler = logging.Handler()
        handler.emit = lambda record: self.lines.append((record.levelname, record.getMessage()))
        self.addHandler(handler)


class JpegSizeTests(unittest.TestCase):
    def setUp(self):
        self.module = load_script("orangepi-vision-recorder.py", "LeftPi", "LeftCam")

    def test_reads_the_size_of_the_real_camera_lost_card(self):
        self.assertEqual(self.module.jpeg_size(CAMERA_LOST_CARD), (105, 60))

    def test_reads_the_size_of_a_simulated_camera_frame(self):
        self.assertEqual(self.module.jpeg_size(fake_mjpeg.make_frame(1, 0)),
                         (fake_mjpeg.WIDTH, fake_mjpeg.HEIGHT))

    def test_garbage_gives_none_rather_than_raising(self):
        for data in (b"", b"\xff\xd8", b"\xff\xd8\x00\x00", b"\xff\xd8\xff\xc0\x00"):
            self.assertIsNone(self.module.jpeg_size(data), data)


class CameraLostDetectorTests(unittest.TestCase):
    def setUp(self):
        self.module = load_script("orangepi-vision-recorder.py", "LeftPi", "LeftCam")
        self.log = ListLog()
        self.camera = self.module.CameraLostDetector(repeats=3)

    def feed(self, frames, t0=100.0, dt=1 / 3):
        for k, frame in enumerate(frames):
            self.camera.observe(frame, t0 + k * dt, self.log)

    def test_a_live_camera_is_never_lost(self):
        self.feed([fake_mjpeg.make_frame(i, 0) for i in range(30)])
        self.assertFalse(self.camera.lost)
        self.assertEqual(self.camera.snapshot(200.0), (0, 0.0))
        self.assertEqual(self.log.lines, [])

    def test_the_camera_lost_card_is_detected_once_and_logged_with_its_size(self):
        live = [fake_mjpeg.make_frame(i, 0) for i in range(5)]
        self.feed(live + [CAMERA_LOST_CARD] * 10)
        self.assertTrue(self.camera.lost)
        self.assertEqual(self.camera.lost_count, 1)
        warnings = [m for level, m in self.log.lines if level == "WARNING"]
        self.assertEqual(len(warnings), 1, self.log.lines)
        self.assertIn("Camera lost", warnings[0])
        self.assertIn("105x60", warnings[0])
        self.assertTrue(any("frame size changed" in m and "-> 105x60" in m for _, m in self.log.lines))

    def test_two_identical_frames_are_not_enough(self):
        self.feed([fake_mjpeg.make_frame(1, 0), CAMERA_LOST_CARD, CAMERA_LOST_CARD, fake_mjpeg.make_frame(2, 0)])
        self.assertEqual(self.camera.lost_count, 0)

    def test_recovery_is_logged_and_the_lost_time_counted(self):
        # card from t=100 (detected on the 3rd identical frame, at t=101), camera back at t=110
        for t in (100.0, 100.5, 101.0, 105.0):
            self.camera.observe(CAMERA_LOST_CARD, t, self.log)
        self.assertEqual(self.camera.snapshot(106.0), (1, 5.0))  # a loss in progress counts
        self.camera.observe(fake_mjpeg.make_frame(1, 0), 110.0, self.log)
        self.assertFalse(self.camera.lost)
        self.assertEqual(self.camera.snapshot(500.0), (1, 9.0))
        self.assertTrue(any("Camera back after 9.0s" in m for _, m in self.log.lines), self.log.lines)

    def test_a_second_loss_counts_again(self):
        self.feed([CAMERA_LOST_CARD] * 3 + [fake_mjpeg.make_frame(1, 0)] + [CAMERA_LOST_CARD] * 3)
        self.assertEqual(self.camera.lost_count, 2)

    def test_session_summary_reports_camera_losses(self):
        stats = {"age_ms": [18.0, 20.0], "stale": 0, "nonew": 0, "camera_lost": (1, 93.0)}
        self.assertIn("camera lost 1 time(s), 93.0s", self.module._session_summary(stats))
        del stats["camera_lost"]
        self.assertNotIn("camera lost", self.module._session_summary(stats))


class HeartbeatCameraLostTests(unittest.TestCase):
    def setUp(self):
        self.module = load_script("orangepi-vision-recorder.py", "LeftPi", "LeftCam")

    def test_camera_lost_fields_are_published(self):
        hb, table, _ = make(self.module, script_blob="ab" * 20)
        beat(hb, camera_lost=True, camera_lost_count=2, camera_lost_sec=93.4, frame_size=(105, 60))
        v = table.values
        self.assertEqual((v["CameraLost"], v["CameraLostCount"], v["CameraLostSec"], v["FrameSize"]),
                         (True, 2, 93.4, "105x60"))
        self.assertEqual(v["ScriptBlob"], "ab" * 20)
        self.assertEqual(v["StreamOk"], True)  # the card is a fresh stream; only CameraLost says otherwise

    def test_defaults_before_any_frame(self):
        hb, table, _ = make(self.module)
        beat(hb)
        self.assertEqual((table.values["CameraLost"], table.values["FrameSize"]), (False, ""))


class VersionTests(unittest.TestCase):
    def setUp(self):
        self.module = load_script("orangepi-vision-recorder.py", "LeftPi", "LeftCam")
        self.script = COPROCESSOR / "orangepi-vision-recorder.py"

    def test_build_combines_the_hand_set_version_with_the_blob_id(self):
        self.assertRegex(self.module.SCRIPT_BLOB, r"^[0-9a-f]{40}$")
        self.assertEqual(self.module.RECORDER_BUILD,
                         f"{self.module.RECORDER_VERSION}+{self.module.SCRIPT_BLOB[:12]}")

    @unittest.skipUnless(shutil.which("git"), "git is not installed")
    def test_blob_id_is_what_git_hash_object_prints(self):
        expected = subprocess.run(["git", "hash-object", "--no-filters", str(self.script)],
                                  capture_output=True, text=True, check=True).stdout.strip()
        data = self.script.read_bytes()
        if b"\r\n" not in data:  # a CRLF checkout is covered by the next test
            self.assertEqual(self.module.SCRIPT_BLOB, expected)

    def test_crlf_copy_gives_the_same_id_as_lf(self):
        with tempfile.TemporaryDirectory() as tmp:
            lf, crlf = Path(tmp) / "lf.py", Path(tmp) / "crlf.py"
            lf.write_bytes(b"print('hi')\nprint('there')\n")
            crlf.write_bytes(b"print('hi')\r\nprint('there')\r\n")
            self.assertEqual(self.module.script_blob_id(str(lf)), self.module.script_blob_id(str(crlf)))
            if shutil.which("git"):
                expected = subprocess.run(["git", "hash-object", "--no-filters", str(lf)],
                                          capture_output=True, text=True, check=True).stdout.strip()
                self.assertEqual(self.module.script_blob_id(str(crlf)), expected)

    def test_unreadable_file_reports_unknown(self):
        self.assertEqual(self.module.script_blob_id("/no/such/file.py"), "unknown")


class DurabilityTests(unittest.TestCase):
    def setUp(self):
        self.module = load_script("orangepi-vision-recorder.py", "LeftPi", "LeftCam")

    def test_sync_file_never_raises_even_on_a_closed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = open(os.path.join(tmp, "x"), "w")
            f.write("a")
            self.module.sync_file(f)
            f.close()
            self.module.sync_file(f)  # ValueError swallowed

    def test_sync_dir_tolerates_platforms_that_cannot_open_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.module.sync_dir(tmp)
            self.module.sync_dir(os.path.join(tmp, "missing"))

    def test_session_log_handler_writes_every_line_through(self):
        with tempfile.TemporaryDirectory() as tmp:
            diagnostics = self.module.RecorderDiagnostics()
            try:
                diagnostics.start_session(tmp)
                self.assertIsInstance(diagnostics.file_handler, self.module.SyncedRotatingFileHandler)
                diagnostics.log.info("line one")
                # readable from a separate handle without closing the handler
                self.assertIn("line one", Path(tmp, "recorder.log").read_text(encoding="utf-8"))
            finally:
                diagnostics.close()


if __name__ == "__main__":
    unittest.main()
