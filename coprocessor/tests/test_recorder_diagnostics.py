"""Session diagnostics survive capture errors and accompany the recorded frames."""
import tempfile
import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

from test_nt_identities import load_script, StopLoop


class RecorderDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.stderr = contextlib.redirect_stderr(io.StringIO())
        self.stderr.__enter__()
        self.addCleanup(self.stderr.__exit__, None, None, None)

    def test_session_contains_startup_capture_failure_and_disable_summary(self):
        module = load_script("orangepi-vision-recorder.py", "RightPi", "RightCam")
        inst = MagicMock()
        inst.isConnected.return_value = True
        inst.getServerTimeOffset.return_value = 0
        inst.getTable.return_value.getIntegerTopic.return_value.getEntry.return_value.getAtomic.return_value = \
            SimpleNamespace(value=1792332000000, serverTime=12_000_000)
        ntcore = SimpleNamespace(NetworkTableInstance=SimpleNamespace(getDefault=lambda: inst))
        # The drain thread is replaced by a scripted source so the loop is deterministic: one fresh
        # frame, then a failure in the capture step, then the robot disables. latest() is polled
        # every loop (the Camera Lost check runs while disabled too), so loop 3 needs a value.
        frame_source = MagicMock()
        frame_source.latest.side_effect = [(b"jpeg", 12.5, 1), TimeoutError("camera stream stalled"), None, None]
        with tempfile.TemporaryDirectory() as root, \
             patch.dict(sys.modules, ntcore=ntcore), \
             patch.object(module, "RECORDINGS_BASE", root), \
             patch.object(module, "MjpegFrameReader", return_value=MagicMock()), \
             patch.object(module, "LatestFrameReader", return_value=frame_source), \
             patch.object(module, "is_enabled", side_effect=[True, True, False]), \
             patch.object(module, "robot_clock_offset_sec", return_value=0), \
             patch.object(module, "server_time_sec", return_value=12.5), \
             patch.object(module.time, "sleep", side_effect=[None, None, StopLoop]):
            with self.assertRaises(StopLoop):
                module.main()
            session, = Path(root).glob("boot*")
            text = (session / "recorder.log").read_text()
            self.assertIn("Recorder started:", text)
            self.assertIn("camera=RightCam", text)
            self.assertIn("nt_connected=True", text)
            self.assertIn("TimeoutError: camera stream stalled", text)
            self.assertIn("session ended (NT connected): frames=1 errors=1", text)
            self.assertIn("Recorder stopping", text)
            self.assertEqual(len((session / "manifest.jsonl").read_text().splitlines()), 1)
            row = json.loads((session / "manifest.jsonl").read_text())
            self.assertEqual(row['timestamp_unix_ms'], 1792332000500)
            self.assertEqual(row['timestamp_utc'], '2026-10-18T14:00:00.500Z')
            self.assertEqual(row['timestamp_status'], 'synced')

    def test_stream_errors_from_the_drain_thread_reach_the_diagnostic_log(self):
        module = load_script("orangepi-vision-recorder.py", "RightPi", "RightCam")
        diagnostics = module.RecorderDiagnostics()
        reader = MagicMock()
        reader.read_frame.side_effect = TimeoutError("camera stream stalled")
        source = module.LatestFrameReader(reader, MagicMock(), diagnostics.log)
        try:
            source.start()
            deadline = time.monotonic() + 5
            while not any("camera stream stalled" in r.getMessage() for r in diagnostics.recent):
                self.assertLess(time.monotonic(), deadline, "stream error never logged")
                time.sleep(0.01)
            record, = [r for r in diagnostics.recent if "camera stream stalled" in r.getMessage()]
            self.assertIsNotNone(record.exc_info)
        finally:
            source.close()
            diagnostics.close()

    def test_detach_releases_the_session_file_but_keeps_history(self):
        module = load_script("orangepi-vision-recorder.py", "RightPi", "RightCam")
        with tempfile.TemporaryDirectory() as root:
            diagnostics = module.RecorderDiagnostics()
            try:
                diagnostics.log.info("before")
                diagnostics.start_session(Path(root))
                diagnostics.detach()
                (Path(root) / "recorder.log").unlink()  # fails on Windows while the file is held open
                diagnostics.log.info("after")
                self.assertEqual([r.getMessage() for r in diagnostics.recent], ["before", "after"])
            finally:
                diagnostics.close()

    def test_session_switch_preserves_recent_history_and_isolates_cameras(self):
        module = load_script("orangepi-vision-recorder.py", "RightPi", "RightCam")
        with tempfile.TemporaryDirectory() as root:
            dirs = [Path(root) / name for name in ("right-auto", "right-teleop", "left")]
            for folder in dirs:
                folder.mkdir()
            right, left = module.RecorderDiagnostics(), module.RecorderDiagnostics()
            try:
                right.log.info("right startup")
                right.start_session(dirs[0])
                right.log.info("right disabled")
                right.start_session(dirs[1])
                right.log.info("right teleop")
                left.start_session(dirs[2])
                left.log.info("left only")
                self.assertIn("right disabled", (dirs[1] / "recorder.log").read_text())
                self.assertNotIn("right teleop", (dirs[0] / "recorder.log").read_text())
                self.assertNotIn("left only", (dirs[1] / "recorder.log").read_text())
                # Bound repeated errors on disk, as well as the pre-session history.
                for _ in range(105):
                    right.log.info("x" * 12000)
                self.assertEqual(len(right.recent), 100)
                self.assertTrue((dirs[1] / "recorder.log.1").exists())
            finally:
                right.close()
                left.close()
