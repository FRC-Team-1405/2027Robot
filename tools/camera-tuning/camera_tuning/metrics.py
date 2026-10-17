"""Pure scoring code for camera-setting trials.

Detection is intentionally the dominant signal.  Sharpness and exposure quality
only break ties between settings that detect the calibration target reliably.
The score does not penalize target motion: a gently hand-moved target is the
expected test procedure and is useful for exposing motion blur.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import statistics


@dataclass(frozen=True)
class FrameMetrics:
    marker_count: int
    sharpness: float
    contrast: float
    clipped_fraction: float


@dataclass(frozen=True)
class TrialSummary:
    frames: int
    frames_with_target: int
    detection_rate: float
    median_marker_count: float
    marker_fraction: float
    median_sharpness: float
    median_contrast: float
    median_clipped_fraction: float
    score: float

    def to_dict(self) -> dict:
        return asdict(self)


def _median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def summarize(frames: list[FrameMetrics], expected_markers: int) -> TrialSummary:
    """Aggregate a trial into a transparent 0-100 AprilTag-oriented score.

    ``expected_markers`` is only a normalization hint.  Detection rate remains
    useful when part of a board is outside the image, while the marker fraction
    rewards configurations that recover more of the same visible target.
    """
    if expected_markers < 1:
        raise ValueError("expected_markers must be at least 1")

    total = len(frames)
    if total == 0:
        return TrialSummary(
            frames=0,
            frames_with_target=0,
            detection_rate=0.0,
            median_marker_count=0.0,
            marker_fraction=0.0,
            median_sharpness=0.0,
            median_contrast=0.0,
            median_clipped_fraction=0.0,
            score=0.0,
        )
    detected = [f for f in frames if f.marker_count > 0]
    detection_rate = len(detected) / total
    median_count = _median([float(f.marker_count) for f in detected])
    marker_fraction = min(1.0, median_count / expected_markers)
    sharpness = _median([f.sharpness for f in detected])
    contrast = _median([f.contrast for f in frames])
    clipped = _median([f.clipped_fraction for f in frames])

    # Laplacian variance is camera/resolution dependent, so use a saturating
    # curve. Values near 150 are already crisp enough; extra edge enhancement
    # should not be able to outweigh missed detections.
    sharpness_quality = 1.0 - math.exp(-max(0.0, sharpness) / 75.0)
    # Healthy grayscale contrast saturates near 60 standard deviations.
    contrast_quality = min(1.0, max(0.0, contrast) / 60.0)
    # Either crushed blacks or blown highlights count as clipped pixels.
    exposure_quality = max(0.0, 1.0 - clipped / 0.25)

    score = 100.0 * (
        0.65 * detection_rate
        + 0.15 * marker_fraction
        + 0.10 * sharpness_quality
        + 0.05 * contrast_quality
        + 0.05 * exposure_quality
    )

    return TrialSummary(
        frames=total,
        frames_with_target=len(detected),
        detection_rate=detection_rate,
        median_marker_count=median_count,
        marker_fraction=marker_fraction,
        median_sharpness=sharpness,
        median_contrast=contrast,
        median_clipped_fraction=clipped,
        score=score,
    )
