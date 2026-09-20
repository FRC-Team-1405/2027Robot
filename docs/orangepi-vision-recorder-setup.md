# Setting Up the Orange Pi Vision Recorder

Installs `coprocessor/orangepi-vision-recorder.py` as a systemd service on the PhotonVision Orange Pi. It samples PhotonVision's raw (pre-AprilTag-processing) camera stream at low rate while the robot is enabled, and saves timestamped JPEGs locally — so a missed detection in a match can be looked up and inspected visually afterward, instead of guessed at.

This shares the `pyntcore` dependency and venv already set up for `orangepi-nt-publisher` — see `docs/orangepi-nt-publisher-setup.md` first if that hasn't been installed yet. No new Python packages are required.

**Current bench Pi reference:** `photon@192.168.1.252`, password `vision` (shown in the SSH banner), `/home/photon/.venv-ntpublisher`. If this is a different Pi/image, confirm the SSH user and venv path match before following these steps literally.

**Path convention.** Everything below uses the `photon` account (`/home/photon/...`), matching this Pi's actual login and confirmed bench free space (~11GB) — not `/home/pi`, which was a leftover from an earlier draft and does not exist on this image. `RECORDINGS_DIR` in the script defaults to `/home/photon/vision-recordings` and can be overridden per instance via `RECORDINGS_DIR=` in that instance's `EnvironmentFile` (see step 3) if a future Pi/image uses a different account. This is also the path `tools/logbench/server/remote_config.json` must point its `pi.recordings_path` at when fetching bundles remotely — keep the two in sync.

## Two cameras, one Pi, two service instances

Both robot cameras (`Left`, `Right`) run through PhotonVision on this **same** Orange Pi — there is only one Pi, not one per camera. So this script runs as two systemd service *instances* of one templated unit, `orangepi-vision-recorder@.service`, each pointed at its own raw MJPEG stream via `%i` (the instance name, `left` or `right`) and an `EnvironmentFile`. Each instance gets `CAMERA_NAME` set automatically from `%i`, which namespaces its session folders and boot-id counter under `RECORDINGS_DIR/<CAMERA_NAME>/` so the two instances never race on the same `.boot_id` file or collide on an identical session folder name (see the script's module docstring). Running only one camera? Everything below still works with a single instance — just skip the other `.env` file and `systemctl enable/start` call.

## 1. Two things to verify on the bench before trusting this script

These aren't configurable guesses — they're facts about a specific PhotonVision install and WPILib version, and both are easy to get wrong silently:

**a. Confirm the raw stream port for each camera.** In the PhotonVision web UI (`http://<pi-ip>:5800`), open the Dashboard tab and toggle "Stream Display" to show RAW alongside PROCESSED. Right-click → Inspect (or use browser devtools) on the two `<img>` elements to read their `src` URLs — the port serving the *unprocessed* feed (no AprilTag overlay drawn) is what each instance's `CAMERA_STREAM_URL` must point at. On this team's bench Pi, these were confirmed:

Right Cam live raw stream: http://photonvision.local:1181/stream.mjpg
Left Cam live raw stream: http://photonvision.local:1183/stream.mjpg

Re-verify if cameras are added/reordered, since PhotonVision assigns port pairs per camera index.

**b. Confirm the `/FMSInfo` enabled-bit decoding.** With `./gradlew simulateJava` running and the Driver Station GUI open, use a throwaway NT4 client (or run the real script with extra print statements) to watch the `/FMSInfo/FMSControlData` topic while toggling Enabled/Disabled and Autonomous/Teleop in the DS GUI. The script assumes `enabled = bool(raw_value & 1)` per WPILib's standard `HAL_ControlWord` bit order — confirm this bit actually flips with Enabled before relying on it, since a wrong bit means the recorder either never runs or runs constantly. This only needs checking once — it's shared by both camera instances.

## 2. Copy the script and unit file to the Pi

From the laptop, in the repo root:

```bash
scp coprocessor/orangepi-vision-recorder.py photon@192.168.1.252:/home/photon/
scp "coprocessor/orangepi-vision-recorder@.service" /tmp/orangepi-vision-recorder@.service
scp /tmp/orangepi-vision-recorder@.service photon@192.168.1.252:/tmp/
```

If team number ever changes from 1405, also update `TEAM_NUMBER` in `/home/photon/orangepi-vision-recorder.py`.

## 3. Point the unit at the venv's Python and create per-instance env files

```bash
sudo sed -i 's|/usr/bin/python3|/home/photon/.venv-ntpublisher/bin/python3|' "/tmp/orangepi-vision-recorder@.service"
sudo mkdir -p /etc/orangepi-vision-recorder
```

Create `/etc/orangepi-vision-recorder/left.env`:

```
CAMERA_STREAM_URL=http://localhost:1183/stream.mjpg
```

Create `/etc/orangepi-vision-recorder/right.env`:

```
CAMERA_STREAM_URL=http://localhost:1181/stream.mjpg
```

(Substitute the ports confirmed in step 1a if they differ. Add `RECORDINGS_DIR=...` to either file to override the storage location for that camera specifically — not normally needed, since both cameras share one Pi and namespace under the same base directory by `CAMERA_NAME`.)

## 4. Install and start both instances

```bash
sudo cp "/tmp/orangepi-vision-recorder@.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now orangepi-vision-recorder@left.service
sudo systemctl enable --now orangepi-vision-recorder@right.service
```

## 5. Verify it's working

```bash
sudo systemctl status orangepi-vision-recorder@left.service orangepi-vision-recorder@right.service
sudo journalctl -u "orangepi-vision-recorder@*.service" -f
```

You want `Active: active (running)` for both. A healthy run prints `Connecting to roboRIO (team 1405)… [camera left] ...` once per instance, then `Enabled — starting session ...` / `Disabled — session ended` as the robot state changes — it should otherwise stay quiet.

While the robot is enabled (sim or real), confirm on the Pi:

```bash
ls /home/photon/vision-recordings/left/
ls /home/photon/vision-recordings/right/
cat /home/photon/vision-recordings/left/<latest-session>/manifest.jsonl
```

You should see JPEGs accumulating at roughly `SAMPLE_HZ` (default 3/sec) per camera and a `manifest.jsonl` line per frame with a `t_sec` timestamp. **Also watch PhotonVision's own dashboard FPS/latency counters while this runs** — they shouldn't visibly regress, since the whole point of tapping the existing MJPEG stream instead of the camera device is to avoid competing with the detection pipeline.

**Session folder names.** This Pi has no RTC battery, so its wall clock can reset to a stale build-image date on any power cycle that doesn't reach NTP (typical on a field network). Folders are named `<CAMERA_NAME>/boot<NNNN>-<timestamp>`, where `<NNNN>` is a counter in `RECORDINGS_DIR/<CAMERA_NAME>/.boot_id` that increments once per service instance start — so folders from the current power-on are always distinguishable from an older one even if the timestamp half of the name is wrong, and the `left`/`right` counters never interfere with each other.

For the timestamp itself: robot code (`RobotContainer.publishRobotData()`) publishes the roboRIO's system clock — which the Driver Station sets on every connect, so it's accurate — to NT under `RobotTime/WallClockMs`. This script reads it once per session start and uses the offset to render the folder timestamp in America/New_York, without ever changing the Pi's own OS clock. The startup log line for each session says `(synced to roboRIO, offset +N.Ns)` when this worked, or `(NOT synced to roboRIO — using Pi's own possibly-stale clock)` if the Pi hadn't connected to NT yet when the session started (e.g. robot code isn't running, or the Pi came up before the radio/roboRIO did) — in that case trust the boot number, not the timestamp.

## 6. Storage cap

Total recordings are capped at 5GB (`MAX_STORAGE_BYTES` in the script) **per camera instance** by deleting the oldest whole session directories within that camera's own namespaced folder — never partial sessions, so every remaining `manifest.jsonl` stays consistent with the frames next to it, and one camera filling up can't evict the other camera's history. To test this on the bench, temporarily lower `MAX_STORAGE_BYTES` to a few MB, cycle the robot enabled/disabled a few times to generate multiple sessions, and confirm old sessions disappear as the cap is exceeded.

Recordings currently live on the Pi's internal storage (confirmed ~11GB free at last check, separate from PhotonVision's own ~139MB footprint — match logs themselves live on the roboRIO, not this Pi). `RECORDINGS_DIR` at the top of the script (env-overridable, see the path convention note above) is specifically so this can be pointed at a USB drive's mount path later without any code change, once one is attached.

## Single-camera / legacy deployments

If only one camera is ever recorded on a given Pi, `CAMERA_NAME` can be left unset: run the unit directly as `orangepi-vision-recorder.service` (a plain, non-templated copy of the `@.service` file with `Environment=CAMERA_NAME=` removed, or just invoke the script directly with no `CAMERA_NAME` in its environment) and sessions land straight under `RECORDINGS_DIR/boot####-<timestamp>/` as before — no `<camera>/` path segment, and no other change needed downstream (bundling in `tools/logbench` handles both layouts).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'ntcore'` | Unit's `ExecStart` still points at `/usr/bin/python3` instead of the venv | Re-check step 3, `systemctl daemon-reload`, restart the instance |
| Instance stuck in `activating (auto-restart)` | Script is crashing every loop, or that instance's MJPEG stream URL/port is wrong | `journalctl -u orangepi-vision-recorder@<left\|right>.service -f` and read the traceback |
| No sessions ever start (either instance) | `/FMSInfo` bit decoding is wrong, or the Pi isn't reaching the roboRIO's NT4 server | Re-do the bench check in step 1b; confirm `TEAM_NUMBER` and that the Pi/roboRIO are on the same network |
| Sessions start but no JPEGs appear for one camera | That instance's `CAMERA_STREAM_URL` in `/etc/orangepi-vision-recorder/<name>.env` doesn't match the RAW stream for that camera | Re-do the bench check in step 1a |
| Both instances write into the same session folder / `.boot_id` collides | `CAMERA_NAME` isn't actually reaching the process (e.g. running the script by hand without the env var, or an env file typo) | Confirm `systemctl show orangepi-vision-recorder@left.service -p Environment` includes `CAMERA_NAME=left`, and that `RECORDINGS_DIR/left/` and `RECORDINGS_DIR/right/` exist as separate folders |
| PhotonVision's dashboard FPS/latency visibly drops while this runs | Unexpected — the recorder is only supposed to add a second consumer to an already-encoded stream | Lower `SAMPLE_HZ`, or fall back to Approach B/C discussed when this feature was scoped (direct camera tap, or a PhotonVision fork) — see the plan history for this feature if it's checked into notes |
