"""Streamlit UI for comparing PhotonVision camera input settings."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import time

import streamlit as st

from .metrics import FrameMetrics, summarize
from .mjpeg import MjpegFrameReader


DICTIONARIES = {
    "AprilTag 36h11 (recommended)": "DICT_APRILTAG_36h11",
    "AprilTag 16h5": "DICT_APRILTAG_16h5",
    "ChArUco/Aruco 4x4 50": "DICT_4X4_50",
    "ChArUco/Aruco 4x4 1000": "DICT_4X4_1000",
    "ChArUco/Aruco 5x5 100": "DICT_5X5_100",
    "ChArUco/Aruco 5x5 1000": "DICT_5X5_1000",
    "ChArUco/Aruco 6x6 250": "DICT_6X6_250",
    "ChArUco/Aruco 6x6 1000": "DICT_6X6_1000",
}


def _opencv():
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV is not installed. Run `python3 -m pip install -r requirements.txt`."
        ) from exc
    if not hasattr(cv2, "aruco"):
        raise RuntimeError("This tool needs opencv-contrib-python-headless, not plain opencv-python.")
    return cv2, np


def _analyze(jpeg: bytes, dictionary_name: str):
    cv2, np = _opencv()
    image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Camera returned a JPEG that OpenCV could not decode")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    dictionary_id = getattr(cv2.aruco, dictionary_name)
    dictionary = cv2.aruco.getPredefinedDictionary(dictionary_id)
    detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
    corners, ids, _rejected = detector.detectMarkers(gray)
    marker_count = 0 if ids is None else len(ids)

    # Whole-frame values catch clipping and lighting changes. Sharpness is
    # measured on detected marker bounding boxes when possible so background
    # texture cannot make a bad target image look artificially sharp.
    contrast = float(gray.std())
    clipped = float(np.mean((gray <= 5) | (gray >= 250)))
    sharp_regions = []
    for corner in corners:
        pts = corner.reshape(-1, 2)
        x0, y0 = np.floor(pts.min(axis=0)).astype(int)
        x1, y1 = np.ceil(pts.max(axis=0)).astype(int)
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(gray.shape[1], x1), min(gray.shape[0], y1)
        if x1 - x0 >= 8 and y1 - y0 >= 8:
            sharp_regions.append(gray[y0:y1, x0:x1])
    sharpness = (
        float(np.median([cv2.Laplacian(r, cv2.CV_64F).var() for r in sharp_regions]))
        if sharp_regions else 0.0
    )

    preview = image.copy()
    if corners:
        cv2.aruco.drawDetectedMarkers(preview, corners, ids)
    return FrameMetrics(marker_count, sharpness, contrast, clipped), preview


def _record(url: str, duration_sec: float, warmup_sec: float, dictionary_name: str):
    frames = []
    preview = None
    started = time.monotonic()
    with MjpegFrameReader(url) as reader:
        while time.monotonic() - started < duration_sec + warmup_sec:
            jpeg = reader.read()
            if time.monotonic() - started < warmup_sec:
                continue
            metric, preview = _analyze(jpeg, dictionary_name)
            frames.append(metric)
    return frames, preview


def _trial_row(trial: dict) -> dict:
    s = trial["summary"]
    return {
        "score": round(s["score"], 1),
        "exposure": trial["settings"]["exposure"],
        "brightness": trial["settings"]["brightness"],
        "gain": trial["settings"]["gain"],
        "detection %": round(100 * s["detection_rate"], 1),
        "median markers": round(s["median_marker_count"], 1),
        "sharpness": round(s["median_sharpness"], 1),
        "contrast": round(s["median_contrast"], 1),
        "clipped %": round(100 * s["median_clipped_fraction"], 1),
        "frames": s["frames"],
        "note": trial["note"],
    }


def _group_trials(trials: list[dict]) -> list[dict]:
    """Combine repeated A/B trials so hand motion averages out of the ranking."""
    groups = {}
    for trial in trials:
        settings = trial["settings"]
        key = (
            settings["exposure"],
            settings["brightness"],
            settings["gain"],
            trial["dictionary"],
            trial["expected_markers"],
        )
        groups.setdefault(key, []).append(trial)

    ranked = []
    for key, runs in groups.items():
        frame_metrics = [
            FrameMetrics(**frame)
            for run in runs
            for frame in run["frames"]
        ]
        summary = summarize(frame_metrics, key[4])
        ranked.append({
            "key": key,
            "runs": len(runs),
            "summary": summary,
            "settings": runs[0]["settings"],
        })
    return sorted(ranked, key=lambda group: group["summary"].score, reverse=True)


def _group_row(group: dict) -> dict:
    settings = group["settings"]
    summary = group["summary"]
    return {
        "score": round(summary.score, 1),
        "exposure": settings["exposure"],
        "brightness": settings["brightness"],
        "gain": settings["gain"],
        "runs": group["runs"],
        "detection %": round(100 * summary.detection_rate, 1),
        "median markers": round(summary.median_marker_count, 1),
        "sharpness": round(summary.median_sharpness, 1),
        "contrast": round(summary.median_contrast, 1),
        "clipped %": round(100 * summary.median_clipped_fraction, 1),
        "frames": summary.frames,
    }


def main() -> None:
    st.set_page_config(page_title="AprilTag Camera Tuner", page_icon="📷", layout="wide")
    st.title("📷 AprilTag Camera Tuner")
    st.write(
        "Compare manual-exposure settings from PhotonVision's raw camera stream. "
        "Detection reliability dominates the score; sharpness, contrast, and clipping break ties."
    )

    if "camera_tuning_trials" not in st.session_state:
        st.session_state.camera_tuning_trials = []

    with st.sidebar:
        st.header("Camera and target")
        url = st.text_input("Raw MJPEG stream", "http://photonvision.local:1181/stream.mjpg")
        dictionary_label = st.selectbox("Marker dictionary", list(DICTIONARIES))
        expected_markers = st.number_input("Markers on target", 1, 100, 6)
        duration = st.slider("Measured seconds", 3, 30, 10)
        warmup = st.slider("Warm-up after changing settings", 0.0, 5.0, 1.5, 0.5)

        st.header("Trial label")
        st.caption("Set these same values in PhotonVision before recording.")
        exposure = st.number_input("Exposure", 0, 10000, 100)
        brightness = st.number_input("Brightness", -100, 255, 60)
        gain = st.number_input("Camera gain", 0, 255, 60)
        note = st.text_input("Note", placeholder="left camera, overhead lights")

    st.info(
        "Keep the camera fixed. Hold the rigid target near the same marked distance and gently "
        "move/tilt it through the guide area. Small motion is intentional; pause if your hands "
        "produce obvious blur. Use the same path and duration for every trial."
    )

    if st.button("Record trial", type="primary"):
        try:
            with st.spinner(f"Warming up, then measuring for {duration} seconds…"):
                frames, preview = _record(
                    url, float(duration), float(warmup), DICTIONARIES[dictionary_label]
                )
            summary = summarize(frames, int(expected_markers))
            trial = {
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "stream_url": url,
                "dictionary": DICTIONARIES[dictionary_label],
                "expected_markers": int(expected_markers),
                "duration_sec": duration,
                "settings": {
                    "auto_exposure": False,
                    "exposure": exposure,
                    "brightness": brightness,
                    "gain": gain,
                },
                "note": note,
                "summary": summary.to_dict(),
                "frames": [asdict(f) for f in frames],
            }
            st.session_state.camera_tuning_trials.append(trial)
            st.success(f"Recorded {summary.frames} frames; score {summary.score:.1f}/100.")
            if preview is not None:
                st.image(preview, channels="BGR", caption="Last analyzed frame and detections")
        except Exception as exc:
            st.error(str(exc))

    trials = st.session_state.camera_tuning_trials
    if trials:
        st.subheader("Settings ranking")
        grouped = _group_trials(trials)
        st.caption("Repeated trials with identical settings are combined before ranking.")
        st.dataframe([_group_row(g) for g in grouped], use_container_width=True, hide_index=True)
        best = grouped[0]
        settings = best["settings"]
        st.success(
            "Current leader: "
            f"exposure {settings['exposure']}, brightness {settings['brightness']}, "
            f"gain {settings['gain']} ({best['summary'].score:.1f}/100 across "
            f"{best['runs']} run(s))."
        )
        with st.expander("Individual runs"):
            ranked_trials = sorted(trials, key=lambda t: t["summary"]["score"], reverse=True)
            st.dataframe(
                [_trial_row(t) for t in ranked_trials], use_container_width=True, hide_index=True
            )
        st.download_button(
            "Download trials as JSON",
            json.dumps(trials, indent=2),
            file_name="camera-tuning-trials.json",
            mime="application/json",
        )
        if st.button("Clear trials"):
            st.session_state.camera_tuning_trials = []
            st.rerun()


if __name__ == "__main__":
    main()
