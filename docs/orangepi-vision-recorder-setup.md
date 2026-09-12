# Setting Up the Orange Pi Vision Recorder

Installs `coprocessor/orangepi-vision-recorder.py` as a systemd service on the PhotonVision Orange Pi. It samples PhotonVision's raw (pre-AprilTag-processing) camera stream at low rate while the robot is enabled, and saves timestamped JPEGs locally — so a missed detection in a match can be looked up and inspected visually afterward, instead of guessed at.

This shares the `pyntcore` dependency and venv already set up for `orangepi-nt-publisher` — see `docs/orangepi-nt-publisher-setup.md` first if that hasn't been installed yet. No new Python packages are required.

**Current bench Pi reference:** `photon@192.168.1.252`, password `vision` (shown in the SSH banner), `/home/photon/.venv-ntpublisher`. If this is a different Pi/image, confirm the SSH user and venv path match before following these steps literally.

## 1. Two things to verify on the bench before trusting this script

These aren't configurable guesses — they're facts about a specific PhotonVision install and WPILib version, and both are easy to get wrong silently:

**a. Confirm the raw stream port.** In the PhotonVision web UI (`http://<pi-ip>:5800`), open the Dashboard tab and toggle "Stream Display" to show RAW alongside PROCESSED. Right-click → Inspect (or use browser devtools) on the two `<img>` elements to read their `src` URLs — the port serving the *unprocessed* feed (no AprilTag overlay drawn) is what `CAMERA_STREAM_URL` in the script must point at. On this team's bench Pi, port `1181` was confirmed as RAW and `1182` as PROCESSED for `Cam1` — but re-verify if cameras are added/reordered, since PhotonVision assigns port pairs per camera index.

Right Cam live raw stream: http://photonvision.local:1181/stream.mjpg
Left Cam live raw stream: http://photonvision.local:1183/stream.mjpg

**b. Confirm the `/FMSInfo` enabled-bit decoding.** With `./gradlew simulateJava` running and the Driver Station GUI open, use a throwaway NT4 client (or run the real script with extra print statements) to watch the `/FMSInfo/FMSControlData` topic while toggling Enabled/Disabled and Autonomous/Teleop in the DS GUI. The script assumes `enabled = bool(raw_value & 1)` per WPILib's standard `HAL_ControlWord` bit order — confirm this bit actually flips with Enabled before relying on it, since a wrong bit means the recorder either never runs or runs constantly.

## 2. Copy the script and service file to the Pi

From the laptop, in the repo root:

```bash
scp coprocessor/orangepi-vision-recorder.py photon@192.168.1.252:/home/photon/
scp coprocessor/orangepi-vision-recorder.service photon@192.168.1.252:/tmp/
```

## 3. Point the service at the venv's Python

```bash
sudo sed -i 's|/usr/bin/python3|/home/photon/.venv-ntpublisher/bin/python3|' /tmp/orangepi-vision-recorder.service
```

If team number ever changes from 1405, also update `TEAM_NUMBER` in `/home/photon/orangepi-vision-recorder.py`.

## 4. Install and start the service

```bash
sudo cp /tmp/orangepi-vision-recorder.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable orangepi-vision-recorder.service
sudo systemctl start orangepi-vision-recorder.service
```

## 5. Verify it's working

```bash
sudo systemctl status orangepi-vision-recorder.service
sudo journalctl -u orangepi-vision-recorder.service -f
```

You want `Active: active (running)`. A healthy run prints `Connecting to roboRIO (team 1405)…` once, then `Enabled — starting session ...` / `Disabled — session ended` as the robot state changes — it should otherwise stay quiet.

While the robot is enabled (sim or real), confirm on the Pi:

```bash
ls /home/photon/vision-recordings/
cat /home/photon/vision-recordings/<latest-session>/manifest.jsonl
```

You should see JPEGs accumulating at roughly `SAMPLE_HZ` (default 3/sec) and a `manifest.jsonl` line per frame with a `t_sec` timestamp. **Also watch PhotonVision's own dashboard FPS/latency counters while this runs** — they shouldn't visibly regress, since the whole point of tapping the existing MJPEG stream instead of the camera device is to avoid competing with the detection pipeline.

## 6. Storage cap

Total recordings are capped at 5GB (`MAX_STORAGE_BYTES` in the script) by deleting the oldest whole session directories — never partial sessions, so every remaining `manifest.jsonl` stays consistent with the frames next to it. To test this on the bench, temporarily lower `MAX_STORAGE_BYTES` to a few MB, cycle the robot enabled/disabled a few times to generate multiple sessions, and confirm old sessions disappear as the cap is exceeded.

Recordings currently live on the Pi's internal storage (confirmed ~11GB free at last check, separate from PhotonVision's own ~139MB footprint — match logs themselves live on the roboRIO, not this Pi). `RECORDINGS_DIR` at the top of the script is a single constant specifically so this can be pointed at a USB drive's mount path later without any other changes, once one is attached.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'ntcore'` | Service's `ExecStart` still points at `/usr/bin/python3` instead of the venv | Re-check step 3, `systemctl daemon-reload`, restart the service |
| Service stuck in `activating (auto-restart)` | Script is crashing every loop, or the MJPEG stream URL/port is wrong | `journalctl -u orangepi-vision-recorder.service -f` and read the traceback |
| No sessions ever start | `/FMSInfo` bit decoding is wrong, or the Pi isn't reaching the roboRIO's NT4 server | Re-do the bench check in step 1b; confirm `TEAM_NUMBER` and that the Pi/roboRIO are on the same network |
| Sessions start but no JPEGs appear | `CAMERA_STREAM_URL` port doesn't match the RAW stream for this camera | Re-do the bench check in step 1a |
| PhotonVision's dashboard FPS/latency visibly drops while this runs | Unexpected — the recorder is only supposed to add a second consumer to an already-encoded stream | Lower `SAMPLE_HZ`, or fall back to Approach B/C discussed when this feature was scoped (direct camera tap, or a PhotonVision fork) — see the plan history for this feature if it's checked into notes |
