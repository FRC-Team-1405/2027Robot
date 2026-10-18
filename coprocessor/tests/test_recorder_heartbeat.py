"""The recorder publishes its own health to NetworkTables for LogBench's Health Check page."""
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from test_nt_identities import load_script


class FakeTable:
    """Records every value a topic is given: values[name] is the latest, history[name] all of them."""

    def __init__(self):
        self.values = {}
        self.history = {}

    def _topic(self, name):
        def publish():
            def set_(value):
                self.values[name] = value
                self.history.setdefault(name, []).append(value)
            return SimpleNamespace(set=set_)
        return SimpleNamespace(publish=publish)

    def getStringTopic(self, name):
        return self._topic(name)

    getBooleanTopic = getDoubleTopic = getIntegerTopic = getStringTopic


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make(module, **kw):
    table, clock = FakeTable(), Clock()
    hb = module.RecorderHeartbeat(
        table, "9.9.9", 7, 3.0, "/rec", "/rec/cam", clock=clock,
        disk_usage=lambda path: SimpleNamespace(free=50_000_000_000),
        dir_bytes=lambda path: 2_500_000_000, **kw)
    return hb, table, clock


def beat(hb, **over):
    args = dict(recording=False, stream_age_sec=0.05, stream_seq=1, session_frames=0, sessions=0,
                total_frames=0, errors=0, last_error="", last_error_age_sec=None, clock_synced=True)
    args.update(over)
    return hb.update(**args)


class HeartbeatTests(unittest.TestCase):
    def setUp(self):
        self.module = load_script("orangepi-vision-recorder.py", "LeftPi", "LeftCam")

    def test_path_follows_the_metrics_name_next_to_the_cpu_ram_disk_publisher(self):
        self.assertEqual(self.module.heartbeat_path(), "OrangePi/LeftPi/Recorders/LeftCam")
        self.assertEqual(self.module.heartbeat_path("", "front"), "OrangePi/Recorders/front")
        self.assertEqual(self.module.heartbeat_path("PiB", ""), "OrangePi/PiB/Recorders/default")

    def test_identity_is_published_immediately_and_state_starts_as_starting(self):
        _hb, table, _clock = make(self.module)
        self.assertEqual((table.values["Version"], table.values["BootId"], table.values["SampleHz"]),
                         ("9.9.9", 7, 3.0))
        self.assertEqual(table.values["State"], "starting")

    def test_idle_when_the_camera_is_fresh_and_the_robot_is_disabled(self):
        hb, table, _ = make(self.module)
        self.assertTrue(beat(hb))
        v = table.values
        self.assertEqual((v["State"], v["Recording"], v["StreamOk"]), ("idle", False, True))
        self.assertEqual((v["DiskFreeGB"], v["RecordingsUsedGB"]), (50.0, 2.5))
        self.assertTrue(v["ClockSynced"])

    def test_recording_state_and_counters(self):
        hb, table, _ = make(self.module)
        beat(hb, recording=True, session_frames=42, sessions=2, total_frames=130)
        v = table.values
        self.assertEqual((v["State"], v["Recording"], v["SessionFrames"], v["Sessions"], v["TotalFrames"]),
                         ("recording", True, 42, 2, 130))

    def test_a_stalled_camera_reports_no_stream_even_while_recording(self):
        hb, table, _ = make(self.module)
        beat(hb, recording=True, stream_age_sec=7.5)
        self.assertEqual((table.values["State"], table.values["StreamOk"], table.values["StreamAgeSec"]),
                         ("no_stream", False, 7.5))

    def test_no_frames_ever_is_no_stream_with_age_minus_one(self):
        hb, table, _ = make(self.module)
        beat(hb, stream_age_sec=None, stream_seq=None)
        self.assertEqual((table.values["State"], table.values["StreamAgeSec"], table.values["StreamFps"]),
                         ("no_stream", -1.0, 0.0))

    def test_a_recent_error_wins_and_expires_after_thirty_seconds(self):
        hb, table, clock = make(self.module)
        beat(hb, errors=1, last_error="OSError: disk full", last_error_age_sec=2.0)
        self.assertEqual((table.values["State"], table.values["LastError"], table.values["Errors"]),
                         ("error", "OSError: disk full", 1))
        clock.now += 2
        beat(hb, errors=1, last_error="OSError: disk full", last_error_age_sec=40.0)
        self.assertEqual(table.values["State"], "idle")
        self.assertEqual(table.values["LastError"], "OSError: disk full")   # still shown, no longer 'error'

    def test_stream_fps_is_computed_from_frame_arrivals_between_beats(self):
        hb, table, clock = make(self.module)
        beat(hb, stream_seq=100)
        clock.now += 2.0
        beat(hb, stream_seq=300)
        self.assertEqual(table.values["StreamFps"], 100.0)

    def test_publishes_at_most_once_per_interval_and_counts_beats(self):
        hb, table, clock = make(self.module)
        self.assertTrue(hb.due())
        self.assertTrue(beat(hb))
        self.assertFalse(hb.due())
        self.assertFalse(beat(hb))
        clock.now += 1.0
        self.assertTrue(hb.due())
        self.assertTrue(beat(hb))
        self.assertEqual(table.history["HeartbeatSec"], [1.0, 2.0])
        self.assertEqual(table.values["UptimeSec"], 1.0)

    def test_disk_and_usage_checks_are_throttled(self):
        calls = {"disk": 0, "dir": 0}

        def disk(path):
            calls["disk"] += 1
            return SimpleNamespace(free=1_000_000_000)

        def used(path):
            calls["dir"] += 1
            return 0

        table, clock = FakeTable(), Clock()
        hb = self.module.RecorderHeartbeat(table, "v", 1, 3.0, "/rec", "/rec/cam", clock=clock,
                                           disk_usage=disk, dir_bytes=used)
        for _ in range(5):
            beat(hb)
            clock.now += 1.0
        self.assertEqual(calls, {"disk": 1, "dir": 1})
        clock.now += 60
        beat(hb)
        self.assertEqual(calls, {"disk": 2, "dir": 2})

    def test_an_unreadable_disk_reports_minus_one_instead_of_crashing(self):
        table, clock = FakeTable(), Clock()

        def broken(path):
            raise OSError("gone")
        hb = self.module.RecorderHeartbeat(table, "v", 1, 3.0, "/rec", "/rec/cam", clock=clock,
                                           disk_usage=broken, dir_bytes=broken)
        beat(hb)
        self.assertEqual((table.values["DiskFreeGB"], table.values["RecordingsUsedGB"]), (-1.0, -1.0))

    def test_a_publishing_failure_is_contained_and_logged_once(self):
        hb, table, clock = make(self.module)
        hb._pubs["State"] = SimpleNamespace(set=MagicMock(side_effect=RuntimeError("nt gone")))
        log = MagicMock()
        self.assertFalse(beat(hb, log=log))
        log.exception.assert_called_once()
        clock.now += 5
        self.assertFalse(beat(hb, log=log))
        self.assertFalse(hb.due())
        log.exception.assert_called_once()

    def test_a_table_that_cannot_publish_disables_the_heartbeat_without_raising(self):
        table = MagicMock()
        table.getStringTopic.side_effect = RuntimeError("no nt")
        hb = self.module.RecorderHeartbeat(table, "v", 1, 3.0, "/rec", "/rec/cam")
        self.assertFalse(hb.due())
        self.assertFalse(beat(hb))

    def test_main_loop_publishes_a_heartbeat_with_no_robot_enabled(self):
        module = load_script("orangepi-vision-recorder.py", "RightPi", "RightCam")
        inst = MagicMock()
        inst.isConnected.return_value = True
        inst.getServerTimeOffset.return_value = 0
        table = FakeTable()
        inst.getTable.side_effect = lambda path: table if path.startswith("OrangePi") else MagicMock()
        frame_source = MagicMock()
        frame_source.latest.return_value = (b"jpeg", 12.4, 5)
        ntcore = SimpleNamespace(NetworkTableInstance=SimpleNamespace(getDefault=lambda: inst))

        class Stop(BaseException):
            pass

        with tempfile.TemporaryDirectory() as root, \
             patch.dict(sys.modules, ntcore=ntcore), \
             patch.object(module, "RECORDINGS_BASE", root), \
             patch.object(module, "RECORDINGS_DIR", root), \
             patch.object(module, "MjpegFrameReader", return_value=MagicMock()), \
             patch.object(module, "LatestFrameReader", return_value=frame_source), \
             patch.object(module, "is_enabled", return_value=False), \
             patch.object(module, "server_time_sec", return_value=12.5), \
             patch.object(module.time, "sleep", side_effect=[None, Stop]):
            with self.assertRaises(Stop):
                module.main()
        self.assertEqual(table.values["State"], "idle")
        self.assertTrue(table.values["StreamOk"])
        self.assertEqual(table.values["Recording"], False)
        self.assertGreaterEqual(table.values["DiskFreeGB"], 0)
        self.assertEqual(table.values["Version"], module.RECORDER_VERSION)


if __name__ == "__main__":
    unittest.main()
