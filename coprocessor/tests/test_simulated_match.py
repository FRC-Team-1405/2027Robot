"""End-to-end tests of orangepi-vision-recorder.py against a simulated match.

fake_robot.py plays a match as an NT4 server and fake_mjpeg.py stands in for the
camera; the real recorder script runs as a subprocess pointed at both (NT_SERVER /
NT_PORT / CAMERA_STREAM_URL). Needs pyntcore; skipped with a reason if it is missing.
Runs with either `python -m pytest coprocessor/tests -q` or `python -m unittest`.
"""
import contextlib
import importlib.util
import io
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

COPROCESSOR = Path(__file__).resolve().parents[1]
SIM = COPROCESSOR / "sim"
RECORDER = COPROCESSOR / "orangepi-vision-recorder.py"
sys.path.insert(0, str(SIM))

import fake_mjpeg  # noqa: E402  (stdlib only)

try:
    import ntcore  # noqa: F401
    HAVE_NTCORE = True
except ImportError:
    HAVE_NTCORE = False

SAMPLE_HZ = 10.0
SESSION_RE = re.compile(r"^boot(\d{4})-(\d{8}-\d{6})$")
NY = ZoneInfo("America/New_York")
CLOCK_OFFSET_SEC = 400 * 86400  # fake robot clock is ~400 days ahead of the laptop's

# --fast 10: every phase below plays in a tenth of the time (pre 0.5s, auto 2s, pause 1s, ...).
FAST_MATCH = ["--fast", "10", "--pre-sec", "5", "--auto-sec", "20", "--pause-sec", "10",
              "--teleop-sec", "40", "--post-sec", "10"]
SHORT_MATCH = ["--fast", "10", "--pre-sec", "5", "--auto-sec", "15", "--pause-sec", "5",
               "--teleop-sec", "15", "--post-sec", "10"]


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def load_recorder(env=None):
    spec = importlib.util.spec_from_file_location("recorder_under_test", RECORDER)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(os.environ, env or {}):
        spec.loader.exec_module(module)
    return module


class Scenario:
    """One simulated match: fake camera + fake robot + the real recorder subprocess."""

    def __init__(self, tmp, recordings_dir, robot_args, recorder_env=None, camera="test",
                 expected_ends=2, pad_bytes=0):
        self.recordings_dir = recordings_dir
        self.base = Path(recordings_dir) / camera
        self.event_log = Path(tmp) / f"events-{time.monotonic_ns()}.jsonl"
        self.recorder_log = Path(tmp) / f"recorder-{time.monotonic_ns()}.log"
        nt_port = free_port()
        camera_server = fake_mjpeg.FakeMjpegServer(fps=30, pad_bytes=pad_bytes).start()
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8",
                   NT_SERVER="127.0.0.1", NT_PORT=str(nt_port), CAMERA_STREAM_URL=camera_server.url,
                   RECORDINGS_DIR=str(recordings_dir), CAMERA_NAME=camera, SAMPLE_HZ=str(SAMPLE_HZ))
        env.update(recorder_env or {})
        try:
            with open(self.recorder_log, "wb") as log:
                recorder = subprocess.Popen([sys.executable, str(RECORDER)], env=env,
                                            stdout=log, stderr=subprocess.STDOUT)
                try:
                    robot = subprocess.run(
                        [sys.executable, str(SIM / "fake_robot.py"), "--port", str(nt_port),
                         "--wait-for-clients", "1", "--wait-timeout-sec", "20",
                         "--event-log", str(self.event_log)] + robot_args,
                        capture_output=True, text=True, timeout=60)
                    self.robot_stdout = robot.stdout
                    assert robot.returncode == 0, robot.stdout + robot.stderr
                    # let the recorder notice the final disable, then stop it
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline and self.log_text().count("session ended") < expected_ends:
                        time.sleep(0.1)
                finally:
                    recorder.kill()
                    recorder.wait(timeout=10)
        finally:
            camera_server.stop()
        self.events = [json.loads(line) for line in self.event_log.read_text().splitlines()]

    def log_text(self):
        return self.recorder_log.read_text(encoding="utf-8", errors="replace")

    def sessions(self):
        if not self.base.is_dir():
            return []
        return sorted(d for d in self.base.iterdir() if d.is_dir())

    def event(self, phase, match=1):
        return next(e for e in self.events if e["phase"] == phase and e["match"] == match)

    def enabled_windows(self, match=1):
        """(name, start, end) in NT server seconds for each enabled phase of a match."""
        out = []
        for i, e in enumerate(self.events[:-1]):
            if e["match"] == match and e["phase"] in ("auto", "teleop"):
                nxt = next(n for n in self.events[i + 1:] if n["phase"] not in ("drop_start", "drop_end"))
                out.append((e["phase"], e["server_time_sec"], nxt["server_time_sec"]))
        return out


def read_manifest(session):
    lines = (session / "manifest.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines]


@unittest.skipUnless(HAVE_NTCORE, "pyntcore (ntcore) is not installed; cannot run the simulated match")
class SimulatedMatchTests(unittest.TestCase):
    """Two back-to-back recorder runs sharing one RECORDINGS_DIR:
    run 1 is a normal match with a synced (skewed) clock, run 2 has no clock and a
    1-byte storage cap, which also proves .boot_id increments across process starts."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        recordings = Path(cls._tmp.name) / "recordings"
        cls.run1 = Scenario(cls._tmp.name, recordings, FAST_MATCH + ["--clock-offset-sec", str(CLOCK_OFFSET_SEC)])
        cls.run1_sessions = cls.run1.sessions()
        cls.run1_manifests = {s.name: read_manifest(s) for s in cls.run1_sessions}
        # snapshot the files now: run 2's 1-byte storage cap deletes run 1's sessions
        cls.run1_files = {s.name: {p.name: fake_mjpeg.decode_frame_info(p.read_bytes()) for p in s.glob("*.jpg")}
                          for s in cls.run1_sessions}
        cls.run2 = Scenario(cls._tmp.name, recordings, SHORT_MATCH + ["--no-clock"],
                            recorder_env={"MAX_STORAGE_BYTES": "1"})

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_one_match_makes_exactly_two_sessions_split_by_the_pause(self):
        names = [s.name for s in self.run1_sessions]
        self.assertEqual(len(names), 2, names)
        for name in names:
            m = SESSION_RE.match(name)
            self.assertIsNotNone(m, name)
            self.assertEqual(m.group(1), "0001")
        self.assertEqual(self.run1.log_text().count("starting session"), 2)
        self.assertEqual(self.run1.log_text().count("session ended"), 2)

    def test_folder_names_use_the_synced_fake_clock(self):
        log = self.run1.log_text()
        self.assertIn("synced to roboRIO", log)
        self.assertNotIn("NOT synced", log)
        for session, phase in zip(self.run1_sessions, ("auto", "teleop")):
            started = datetime.strptime(SESSION_RE.match(session.name).group(2), "%Y%m%d-%H%M%S")
            expected = datetime.fromtimestamp(self.run1.event(phase)["wall_ms"] / 1000 + CLOCK_OFFSET_SEC, tz=NY)
            self.assertAlmostEqual(started.timestamp(), expected.replace(tzinfo=None).timestamp(), delta=5,
                                   msg=f"{phase}: {session.name} vs {expected}")
        # sanity: the fake clock really is far from the laptop's clock
        self.assertGreater(datetime.strptime(SESSION_RE.match(self.run1_sessions[0].name).group(2), "%Y%m%d-%H%M%S").year,
                           datetime.now().year)

    def test_manifest_matches_jpegs_one_to_one(self):
        for session in self.run1_sessions:
            manifest = self.run1_manifests[session.name]
            on_disk = self.run1_files[session.name]
            self.assertGreater(len(manifest), 0, session.name)
            self.assertEqual(sorted(m["frame"] for m in manifest), sorted(on_disk), session.name)
            self.assertEqual(len(set(m["frame"] for m in manifest)), len(manifest))
            for m in manifest:
                self.assertEqual(m["frame"], f"frame_{m['t_sec']:.6f}.jpg")
                self.assertIsNotNone(on_disk[m["frame"]], m)  # a real frame from the fake camera

    def test_timestamps_increase_and_stay_inside_enabled_windows(self):
        windows = self.run1.enabled_windows()
        self.assertEqual([w[0] for w in windows], ["auto", "teleop"])
        for session, (name, start, end) in zip(self.run1_sessions, windows):
            t = [m["t_sec"] for m in self.run1_manifests[session.name]]
            self.assertEqual(t, sorted(set(t)), f"{name}: t_sec must be strictly increasing")
            # a frame is stamped after the enable is seen and after the read, so allow
            # one sample period (+ read) after the disable, and a hair before the enable
            self.assertGreaterEqual(t[0], start - 0.05, name)
            self.assertLessEqual(t[-1], end + 0.5, name)

    def test_frame_count_tracks_sample_rate(self):
        for session, (name, start, end) in zip(self.run1_sessions, self.run1.enabled_windows()):
            expected = SAMPLE_HZ * (end - start)
            count = len(self.run1_manifests[session.name])
            self.assertGreaterEqual(count, 0.6 * expected - 2, f"{name}: {count} frames, expected ~{expected:.0f}")
            self.assertLessEqual(count, 1.15 * expected + 2, f"{name}: {count} frames, expected ~{expected:.0f}")

    def test_no_frames_while_disabled(self):
        windows = [(s - 0.05, e + 0.5) for _, s, e in self.run1.enabled_windows()]
        pause_start = self.run1.event("pause")["server_time_sec"]
        pause_end = self.run1.event("teleop")["server_time_sec"]
        for session in self.run1_sessions:
            for m in self.run1_manifests[session.name]:
                self.assertTrue(any(lo <= m["t_sec"] <= hi for lo, hi in windows), m)
                # nothing in the middle of the pause (after the recorder's one-period lag)
                self.assertFalse(pause_start + 0.5 < m["t_sec"] < pause_end - 0.05, m)

    def test_recorded_frames_are_fresh(self):
        """The regression this guards: the recorder used to read one frame per sample from a stream
        running far faster, so recorded frames fell further and further behind real time (minutes
        old by the end of a match on real PhotonVision). Age = recorded t_sec (mapped to wall time
        through the event log) minus the wall time stamped into the frame by the fake camera."""
        ev = self.run1.event("auto")
        offset = ev["wall_ms"] / 1000.0 - ev["server_time_sec"]
        ages = []
        for session in self.run1_sessions:
            for m in self.run1_manifests[session.name]:
                made_ms = self.run1_files[session.name][m["frame"]]["ms"]
                ages.append(m["t_sec"] + offset - made_ms / 1000.0)
        self.assertGreater(len(ages), 20)
        ages.sort()
        p95 = ages[int(0.95 * (len(ages) - 1))]
        self.assertLess(p95, 0.4, f"p95 frame age {p95:.2f}s, max {ages[-1]:.2f}s")
        self.assertGreater(ages[0], -0.2)  # and never from the future

    def test_session_summary_reports_frame_ages(self):
        log = self.run1.log_text()
        self.assertEqual(log.count("frames written, age at write ms median/max"), 2, log)

    def test_recorder_logs_whether_nt_was_up_when_disabled(self):
        self.assertEqual(self.run1.log_text().count("session ended (NT connected)"), 2)

    def test_second_process_increments_boot_id_and_cap_keeps_only_newest_whole_session(self):
        self.assertEqual((self.run1.base / ".boot_id").read_text().strip(), "2")
        remaining = self.run2.sessions()
        # MAX_STORAGE_BYTES=1: each session start deletes every older session, including run 1's.
        # So only run 2's teleop session (the last one started) survives, intact.
        self.assertEqual([s.name[:8] for s in remaining], ["boot0002"], [s.name for s in remaining])
        manifest = read_manifest(remaining[0])
        self.assertGreater(len(manifest), 0)
        self.assertEqual(sorted(m["frame"] for m in manifest), sorted(p.name for p in remaining[0].glob("*.jpg")))
        self.assertFalse(any(s.name.startswith("boot0001") for s in remaining))

    def test_no_clock_falls_back_to_local_clock(self):
        log = self.run2.log_text()
        self.assertEqual(log.count("NOT synced"), 2)
        started = datetime.strptime(SESSION_RE.match(self.run2.sessions()[0].name).group(2), "%Y%m%d-%H%M%S")
        now = datetime.now(NY).replace(tzinfo=None)
        self.assertAlmostEqual(started.timestamp(), now.timestamp(), delta=120)


@unittest.skipUnless(HAVE_NTCORE, "pyntcore (ntcore) is not installed; cannot run the simulated match")
class CommsDropTests(unittest.TestCase):
    """An NT dropout mid-teleop reads as control word 0 (disabled). The recorder holds the session
    through a dropout shorter than NT_DROP_GRACE_SEC (one continuous teleop stays ONE session, video
    keeps recording) and ends it once the grace period is exceeded."""

    FAST = ["--fast", "10", "--pre-sec", "5", "--auto-sec", "20", "--pause-sec", "10",
            "--teleop-sec", "60", "--post-sec", "10", "--drop-at-sec", "1.5", "--drop-for-sec", "1.5"]

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.short = Scenario(cls._tmp.name, Path(cls._tmp.name) / "short", cls.FAST, expected_ends=2)
        cls.long = Scenario(cls._tmp.name, Path(cls._tmp.name) / "long", cls.FAST,
                            recorder_env={"NT_DROP_GRACE_SEC": "0.4"}, expected_ends=4)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_short_dropout_keeps_one_teleop_session(self):
        sessions = self.short.sessions()
        self.assertEqual(len(sessions), 2, [s.name for s in sessions])  # auto + ONE teleop
        log = self.short.log_text()
        self.assertEqual(log.count("starting session"), 2, log)
        self.assertIn("NT connection lost while enabled - holding the session", log)
        self.assertIn("NT reconnected after", log)
        self.assertEqual(log.count("session ended (NT connected)"), 2, log)

    def test_video_keeps_recording_through_a_short_dropout_in_the_server_clock(self):
        down = next(e for e in self.short.events if e["phase"] == "drop_start")["server_time_sec"]
        up = next(e for e in self.short.events if e["phase"] == "drop_end")["server_time_sec"]
        times = [m["t_sec"] for s in self.short.sessions() for m in read_manifest(s)]
        self.assertTrue(any(down + 0.3 < t < up for t in times), "frames expected during the dropout")
        # t_sec must stay in the server clock domain (no jump when the offset is unavailable)
        self.assertTrue(all(abs(t - down) < 1000 for t in times))
        teleop = read_manifest(self.short.sessions()[1])
        gaps = [b["t_sec"] - a["t_sec"] for a, b in zip(teleop, teleop[1:])]
        self.assertLess(max(gaps), 1.0, "no recording gap across the dropout")

    def test_dropout_longer_than_grace_ends_the_session(self):
        sessions = self.long.sessions()
        self.assertEqual(len(sessions), 3, [s.name for s in sessions])  # auto + teleop before + teleop after
        log = self.long.log_text()
        self.assertIn("treating the robot as disabled", log)
        self.assertIn("session ended (NT NOT connected)", log)


class FakeMjpegTests(unittest.TestCase):
    def test_frame_roundtrips_counter_and_time(self):
        for counter, ms in ((0, 0), (812, 1792341703538), (10**9 + 7, 1792341703999)):
            jpeg = fake_mjpeg.make_frame(counter, ms, pad_bytes=70000)
            self.assertEqual(fake_mjpeg.decode_frame_info(jpeg), {"n": counter, "ms": ms})
        self.assertIsNone(fake_mjpeg.decode_frame_info(b"not a jpeg"))

    def test_first_eoi_is_the_real_one(self):
        # the recorder cuts a frame at the first FFD9, so none may appear before the end
        for counter in range(0, 4000, 41):
            jpeg = fake_mjpeg.make_frame(counter, 1792341703538 + counter, pad_bytes=1000)
            self.assertEqual(jpeg.find(b"\xff\xd9"), len(jpeg) - 2)

    def test_frames_decode_with_a_real_jpeg_decoder(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed; JPEG validity not checked (optional)")
        for counter in (0, 123456789, 255, 65535):
            image = Image.open(io.BytesIO(fake_mjpeg.make_frame(counter, 1792341703538)))
            image.load()
            self.assertEqual(image.size, (320, 240))

    def test_latest_frame_reader_stays_fresh_at_a_slow_sample_rate(self):
        recorder = load_recorder()
        server = fake_mjpeg.FakeMjpegServer(fps=30, pad_bytes=20000).start()
        inst = MagicMock()
        inst.getServerTimeOffset.return_value = 0
        frames = recorder.LatestFrameReader(recorder.MjpegFrameReader(server.url), inst)
        frames.start()
        try:
            ages, start = [], time.monotonic()
            for i in range(10):
                time.sleep(max(0.0, (i + 1) / 3.0 - (time.monotonic() - start)))
                latest = frames.latest()
                self.assertIsNotNone(latest)
                ages.append(time.time() * 1000 - fake_mjpeg.decode_frame_info(latest[0])["ms"])
        finally:
            frames.close()
            server.stop()
        self.assertLess(max(ages), 300, ages)

    def test_slow_consumer_reads_stale_frames(self):
        """Why LatestFrameReader exists: a bare MjpegFrameReader takes one frame per call from a
        stream that keeps flowing, so a 3 Hz reader on a 30 fps stream gets frames that age
        by seconds in socket buffers instead of fresh ones. (Real PhotonVision buffering may
        differ; this shows what the reader does with a server that never drops frames.)"""
        recorder = load_recorder()
        server = fake_mjpeg.FakeMjpegServer(fps=30, pad_bytes=20000).start()
        reader = recorder.MjpegFrameReader(server.url)
        try:
            ages = []
            start = time.monotonic()
            for i in range(10):
                frame = reader.read_frame()
                ages.append(time.time() * 1000 - fake_mjpeg.decode_frame_info(frame)["ms"])
                time.sleep(max(0.0, (i + 1) / 3.0 - (time.monotonic() - start)))
        finally:
            reader.close()
            server.stop()
        self.assertLess(ages[0], 500)  # the first frame is fresh
        self.assertGreater(ages[-1], 1500, ages)  # ...then it falls behind by seconds
        self.assertGreater(ages[-1], ages[1], ages)


class RecorderConfigTests(unittest.TestCase):
    def run_main(self, env):
        module = load_recorder(dict({"CAMERA_NAME": "x", "NT_SERVER": "", "NT_PORT": ""}, **env))
        instance = MagicMock()
        fake_nt = SimpleNamespace(NetworkTableInstance=SimpleNamespace(getDefault=lambda: instance))

        class Stop(BaseException):
            pass

        stderr = io.StringIO()  # the recorder logs through a console handler bound to stderr
        with patch.dict(sys.modules, ntcore=fake_nt), \
             patch.object(module, "next_boot_id", return_value=1), \
             patch.object(module, "MjpegFrameReader", side_effect=Stop), \
             contextlib.redirect_stderr(stderr):
            with self.assertRaises(Stop):
                module.main()
        return instance, stderr.getvalue()

    def test_unset_nt_server_still_targets_team_1405(self):
        instance, out = self.run_main({})
        instance.setServerTeam.assert_called_once_with(1405)
        instance.setServer.assert_not_called()
        self.assertIn("roboRIO (team 1405)", out)

    def test_nt_server_and_port_override_the_team_lookup(self):
        instance, out = self.run_main({"NT_SERVER": "10.0.0.5", "NT_PORT": "5811"})
        instance.setServer.assert_called_once_with("10.0.0.5", 5811)
        instance.setServerTeam.assert_not_called()
        self.assertIn("10.0.0.5:5811", out)

    def test_nt_server_without_port_uses_default_port(self):
        instance, out = self.run_main({"NT_SERVER": "localhost"})
        instance.setServer.assert_called_once_with("localhost", 0)
        self.assertIn("localhost:5810", out)

    def test_nt_drop_grace_defaults_to_45s_and_is_overridable(self):
        # Field logs show ~21 s NT dropouts repeating through teleop; 10 s cut each into a session.
        self.assertEqual(load_recorder({"NT_DROP_GRACE_SEC": ""}).NT_DROP_GRACE_SEC, 45.0)
        self.assertEqual(load_recorder({"NT_DROP_GRACE_SEC": "0.4"}).NT_DROP_GRACE_SEC, 0.4)

    def test_numeric_env_overrides_and_validation(self):
        module = load_recorder({"SAMPLE_HZ": "7.5", "MAX_STORAGE_BYTES": "12345"})
        self.assertEqual((module.SAMPLE_HZ, module.MAX_STORAGE_BYTES), (7.5, 12345))
        defaults = load_recorder({"SAMPLE_HZ": "", "MAX_STORAGE_BYTES": ""})
        self.assertEqual((defaults.SAMPLE_HZ, defaults.MAX_STORAGE_BYTES), (3.0, 5 * 1024 ** 3))
        with patch("builtins.print"):
            for bad in ("0", "-2", "abc", "nan", "inf"):
                module = load_recorder({"SAMPLE_HZ": bad, "MAX_STORAGE_BYTES": bad})
                self.assertEqual((module.SAMPLE_HZ, module.MAX_STORAGE_BYTES), (3.0, 5 * 1024 ** 3), bad)
            self.assertEqual(load_recorder({"NT_PORT": "70000"}).NT_PORT, 0)
            self.assertEqual(load_recorder({"NT_PORT": "x"}).NT_PORT, 0)


class StorageCapTests(unittest.TestCase):
    def test_deletes_only_oldest_whole_sessions_until_under_cap(self):
        recorder = load_recorder()
        for cap, survivors in ((3500, ["c", "b", "a"]), (2500, ["c", "b"]), (1500, ["c"])):
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as base:
                for age, name in enumerate(("a", "b", "c")):  # a is oldest
                    session = Path(base) / name
                    session.mkdir()
                    for i in range(2):
                        (session / f"f{i}.jpg").write_bytes(b"x" * 500)
                    (session / "manifest.jsonl").write_bytes(b"y" * 0)
                    os.utime(session, (1_000_000 + age * 100, 1_000_000 + age * 100))
                recorder.enforce_storage_cap(base, cap)
                self.assertEqual(sorted(p.name for p in Path(base).iterdir()), sorted(survivors), cap)
                for name in survivors:  # survivors are whole, never trimmed
                    self.assertEqual(len(list((Path(base) / name).iterdir())), 3)


if __name__ == "__main__":
    unittest.main()
