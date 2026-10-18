"""Real per-frame dates use the robot's clock, with explicit unavailable states."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from test_nt_identities import load_script


class FrameTimestampTests(unittest.TestCase):
    def setUp(self):
        self.recorder = load_script('orangepi-vision-recorder.py', 'RightPi', 'RightCam')
        self.inst = Mock()
        self.inst.isConnected.return_value = True
        self.inst.getServerTimeOffset.return_value = 0  # zero is a valid sync offset
        self.entry = Mock()
        self.entry.getAtomic.return_value = SimpleNamespace(value=1792332000000, serverTime=12_000_000)

    def row(self, nt_sec=12.5):
        return self.recorder.frame_manifest_row(f'frame_{nt_sec:.6f}.jpg', nt_sec, self.inst, self.entry)

    def test_each_frame_has_its_own_utc_date_not_just_the_filename_time(self):
        first, second = self.row(), self.row(12.833)
        self.assertEqual(first['timestamp_utc'], '2026-10-18T14:00:00.500Z')
        self.assertEqual(second['timestamp_utc'], '2026-10-18T14:00:00.833Z')
        self.assertEqual(second['timestamp_unix_ms'] - first['timestamp_unix_ms'], 333)
        self.assertEqual(first['t_sec'], 12.5)
        self.assertEqual(first['timestamp_basis'], 'recorder_receive')
        self.assertEqual(first['timestamp_source'], 'roborio_wall_clock')
        json.dumps(first, allow_nan=False)

    def test_wrong_or_jumping_pi_clock_does_not_change_frame_dates(self):
        for pi_time in (0, 1_000_000_000, 9_000_000_000):
            with patch.object(self.recorder.time, 'time', return_value=pi_time):
                self.assertEqual(self.row()['timestamp_utc'], '2026-10-18T14:00:00.500Z')

    def test_publication_time_accounts_for_network_delay_and_refreshed_clock(self):
        before = self.row()
        # Same mapping, new publication received 400 ms later, not frame-receive time.
        self.entry.getAtomic.return_value = SimpleNamespace(value=1792332000400, serverTime=12_400_000)
        self.assertEqual(self.row(), before)
        # A newer clock sample just after frame receipt can also map backwards safely.
        self.assertEqual(self.row(12.3)['timestamp_unix_ms'], 1792332000300)

    def test_unsynced_disconnected_and_stale_samples_never_invent_a_date(self):
        scenarios = [
            (False, 0, 1792332000000, 12_000_000, 'nt_disconnected'),
            (True, None, 1792332000000, 12_000_000, 'nt_clock_unsynced'),
            (True, 0, 0, 0, 'robot_clock_unavailable'),
            (True, 0, 1792332000000, 1, 'robot_clock_unavailable'),
            (True, 0, 1792332000000, 1_000_000, 'robot_clock_stale'),
            (True, 0, 1792332000000, 30_000_000, 'robot_clock_stale'),
        ]
        for connected, offset, value, server_time, status in scenarios:
            with self.subTest(status=status, server_time=server_time):
                self.inst.isConnected.return_value = connected
                self.inst.getServerTimeOffset.return_value = offset
                self.entry.getAtomic.return_value = SimpleNamespace(value=value, serverTime=server_time)
                row = self.row()
                self.assertEqual(row['timestamp_status'], status)
                self.assertIsNone(row['timestamp_utc'])
                self.assertIsNone(row['timestamp_unix_ms'])
                self.assertIsNone(row['timestamp_source'])
                self.assertEqual(row['t_sec'], 12.5)

    def test_new_manifest_still_loads_in_logbench(self):
        path = Path(__file__).resolve().parents[2] / 'tools/logbench/server/bundles.py'
        spec = importlib.util.spec_from_file_location('test_bundles_compatibility', path)
        bundles = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bundles)
        with tempfile.TemporaryDirectory() as folder:
            row = self.row()
            (Path(folder) / 'manifest.jsonl').write_text(json.dumps(row) + '\n')
            self.assertEqual(bundles.load_manifest(folder), [(12.5, row['frame'])])
