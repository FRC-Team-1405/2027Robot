# AprilTag Camera Tuner

This tool compares PhotonVision exposure, brightness, and camera-gain settings over a multi-frame
sample. It is meant to replace judging settings from one visually appealing frame.

## Run

```bash
cd tools/camera-tuning
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run tune.py
```

Open PhotonVision in another browser tab. Disable auto exposure, enter the same exposure,
brightness, and gain shown in the tuner, wait for the image to settle, and click **Record trial**.
The initial fields are the current bench leader: exposure 100, brightness 60, gain 60.

The default stream is port 1181, which was previously confirmed as the raw stream for Cam1 on the
team's bench Pi. Reconfirm the raw stream URL in browser developer tools when changing cameras or
camera order. Do not use the processed stream: drawn detection outlines corrupt sharpness and
contrast measurements.

## Collection procedure

1. Fix the camera in its final focus and resolution. Mark a repeatable standing position.
2. Use a rigid, flat target under the lighting being tested. An AprilTag 36h11 grid is preferred
   for tuning AprilTag performance. The same ChArUco board used for intrinsics is acceptable for a
   preliminary comparison when its actual ArUco dictionary is selected.
3. Hand-hold the target and repeat the same slow center/edge/tilt motion for every 10-second trial.
   Small variation is useful; fast motion that visibly smears the target is not.
4. Change one setting at a time near 100/60/60. Repeat the leading settings in interleaved order
   (A, B, A, B) so hand motion and lighting drift do not choose the winner by accident.
   The tuner automatically combines repeated runs with identical settings in its main ranking.
5. Prefer settings with consistently high detection rate. Treat the composite score as a ranking
   aid, and inspect its detection, marker-count, sharpness, contrast, and clipping columns.
6. Download the JSON before closing or refreshing the browser session.

This first version labels settings but does not change PhotonVision itself. That is deliberate:
PhotonVision does not document a stable external API for editing pipeline input settings. Once the
measurement and scoring loop has been validated on the real cameras, a version-specific settings
adapter can automate the sweep without changing the evaluator.

## Calibration versus tuning

Camera input tuning and camera-intrinsics calibration are related but separate. Tune the image
first, then perform the full ChArUco intrinsic calibration using
[`docs/photonvision-camera-intrinsics-calibration.md`](../../docs/photonvision-camera-intrinsics-calibration.md).
Keep the camera fixed and move the board during intrinsic collection. Only capture a calibration
view when the board is momentarily sharp; the optimizer intentionally samples gentle motion because
the robot's AprilTag camera must also work while things move.
