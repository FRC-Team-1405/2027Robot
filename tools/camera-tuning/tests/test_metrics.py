import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from camera_tuning.metrics import FrameMetrics, summarize


class TrialScoringTest(unittest.TestCase):
    def test_empty_trial_is_zero_detection_and_safe(self):
        result = summarize([], expected_markers=6)
        self.assertEqual(result.frames, 0)
        self.assertEqual(result.detection_rate, 0.0)
        self.assertEqual(result.score, 0.0)

    def test_detection_reliability_dominates_sharp_background(self):
        reliable = [FrameMetrics(6, 100.0, 50.0, 0.01) for _ in range(10)]
        unreliable = [FrameMetrics(6, 1000.0, 80.0, 0.0) for _ in range(4)] + [
            FrameMetrics(0, 0.0, 80.0, 0.0) for _ in range(6)
        ]
        self.assertGreater(summarize(reliable, 6).score, summarize(unreliable, 6).score)

    def test_marker_fraction_is_capped(self):
        result = summarize([FrameMetrics(20, 100.0, 50.0, 0.0)], expected_markers=6)
        self.assertEqual(result.marker_fraction, 1.0)
        self.assertLessEqual(result.score, 100.0)

    def test_expected_markers_must_be_positive(self):
        with self.assertRaises(ValueError):
            summarize([], expected_markers=0)


if __name__ == "__main__":
    unittest.main()
