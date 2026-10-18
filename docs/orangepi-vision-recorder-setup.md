# Setting Up the Orange Pi Vision Recorder

Installs `coprocessor/orangepi-vision-recorder.py` as a systemd service on the PhotonVision Orange Pi. It samples PhotonVision's raw (pre-AprilTag-processing) camera stream at low rate while the robot is enabled, and saves timestamped JPEGs locally — so a missed detection in a match can be looked up and inspected visually afterward, instead of guessed at.

## Recommended: guided installer

Copy the entire `coprocessor` folder to the Pi and run `bash setup-orangepi.sh` from
that folder, as SSH user `pi` without sudo. Choose recorders or both services.
It shares the publisher venv, asks for confirmed raw-stream URLs, preserves existing
camera env files, and renders the unit using your actual home directory. Setup also
asks for a unique board NT name and the camera instances hosted on that board; it
assumes no board count or camera layout. The correct account is `pi`; the installer
requires that login. New camera
configs explicitly set `RECORDINGS_DIR` to `/home/pi/vision-recordings`.

Use `bash setup-orangepi.sh --status` / `--logs` to diagnose the services. These checks
cannot prove raw-stream selection, enabled-bit decoding, or NT connectivity; retain
the bench checks below. The installer adds `RECORDINGS_DIR` for the current login to
existing camera env files if missing, preserving any explicit custom storage path.
Without the installer/override, the script defaults to `/home/pi/vision-recordings`.

This shares the `pyntcore` dependency and venv already set up for `orangepi-nt-publisher` — see `docs/orangepi-nt-publisher-setup.md` first if that hasn't been installed yet. No new Python packages are required.

**Pi reference:** SSH as `pi` (`pi@photonvision.local`, or `pi@192.168.1.252` at the bench address). The shared venv is `/home/pi/.venv-ntpublisher`.

**Path convention.** Use the `pi` account and `/home/pi/...` paths throughout.
`RECORDINGS_DIR` defaults to `/home/pi/vision-recordings` and can be overridden per
instance via `RECORDINGS_DIR=` in that instance's `EnvironmentFile` for a custom
storage mount. `tools/logbench/server/remote_config.json` must use SSH user `pi` and
point each Pi's `recordings_path` at the same recordings directory when fetching bundles.
With more than one board nothing needs listing: LogBench finds each board's name and address from
`/OrangePi/<board-name>/` on NetworkTables (see the logbench README; hand-listing under `"pis"`
is only for pinning a host or path). The recorder instance name (`left`,
`right`, …) becomes the recording folder name; LogBench matches it to the camera name in the
log ignoring case, so it does not have to be capitalized the same way.

**Viewing the video on the laptop needs ffmpeg** on the PATH of the machine running LogBench
(`winget install Gyan.FFmpeg`).


## One recorder instance per camera, on any number of boards

The generic setup supports one or several camera instances per board, with any number
of boards. Each `orangepi-vision-recorder@<instance>.service` reads that camera's env
file and gets `CAMERA_NAME` from `%i`. Local recordings and boot counters live under
`RECORDINGS_DIR/<CAMERA_NAME>/`.

The current robot has two Orange Pis: the Left board runs `@left` and the Right board
runs `@right`. Choose `LeftPi`/`left` in setup on the Left board and `RightPi`/`right`
on the Right board. These names describe this robot, not a required layout. Another
board could run `front rear`, for example.

The template reads `ORANGEPI_METRICS_NAME` from `/etc/default/orangepi-nt-publisher`,
making the NT client identity `OrangePiVisionRecorder-<board-name>-<camera-instance>`.
Recorders read the shared `/FMSInfo` and `/RobotTime` topics without publishing to
them. The metrics publisher writes only under `/OrangePi/<board-name>/`. All boards
connect to the same team 1405 roboRIO NT server; choose a distinct board name for each.

## 1. Two things to verify on the bench before trusting this script

These aren't configurable guesses — they're facts about a specific PhotonVision install and WPILib version, and both are easy to get wrong silently:

**a. Confirm the raw stream port for each camera.** In the PhotonVision web UI (`http://<pi-ip>:5800`), open the Dashboard tab and toggle "Stream Display" to show RAW alongside PROCESSED. Right-click → Inspect (or use browser devtools) on the two `<img>` elements to read their `src` URLs — the port serving the *unprocessed* feed (no AprilTag overlay drawn) is what each instance's `CAMERA_STREAM_URL` must point at. An earlier one-board bench configuration used these ports:

Right Cam live raw stream: http://photonvision.local:1181/stream.mjpg
Left Cam live raw stream: http://photonvision.local:1183/stream.mjpg

Re-verify if cameras are added/reordered, since PhotonVision assigns port pairs per camera index.

**b. Confirm the `/FMSInfo` enabled-bit decoding.** *(Checked against WPILib 2026.2.1's source: `/FMSInfo/FMSControlData` is the raw HAL control word, bit 0 enabled, 1 autonomous, 2 test, 3 eStop, 4 fmsAttached, 5 dsAttached, so the decoding below is right. The live toggle check is still a worthwhile one-time sanity check on the real robot.)* With `./gradlew simulateJava` running and the Driver Station GUI open, use a throwaway NT4 client (or run the real script with extra print statements) to watch the `/FMSInfo/FMSControlData` topic while toggling Enabled/Disabled and Autonomous/Teleop in the DS GUI. The script assumes `enabled = bool(raw_value & 1)` per WPILib's standard `HAL_ControlWord` bit order — confirm this bit actually flips with Enabled before relying on it, since a wrong bit means the recorder either never runs or runs constantly. This only needs checking once — it's shared by both camera instances.

## Verifying without a robot

`coprocessor/sim/Run-SimulatedMatch.ps1` plays a full match (auto, pause, teleop) against the real
service and PhotonVision stream with a fake roboRIO on the Pi, and checks sessions, timestamps,
frame counts and frame freshness. See `coprocessor/sim/README.md`. Run it after any change to the
recorder, and after setting up a new Pi (`coprocessor/Bootstrap-OrangePi.ps1` does the setup).

## How the recorder behaves (worth knowing when reading recordings)

- **Frames are fresh and stamped on arrival.** A background thread drains PhotonVision's stream
  continuously and the sampler takes the newest frame, so `t_sec` is when PhotonVision sent it
  (measured: median frame age under 20 ms). An earlier version read one frame per sample from a
  ~100 fps stream and recorded frames that fell minutes behind real time by the end of a match.
  A frame older than 2 s at write time (stream stalled) is skipped, not recorded.
- **NT dropouts.** A dropout reads as "disabled". The recorder holds the session through a dropout
  shorter than `NT_DROP_GRACE_SEC` (default 45 s; field logs show ~21 s dropouts repeating through teleop) and ignores a stale "disabled" for 2 s after a
  reconnect, so one continuous enabled period stays one session. A dropout longer than the grace
  period ends the session. During a hold, `t_sec` keeps using the last known server clock offset.
- **Auto and teleop are separate sessions** (the pause is a disable), but nothing in a recording
  says which is which; infer it from order and time.
- **Environment overrides** (in the instance's env file): `SAMPLE_HZ`, `MAX_STORAGE_BYTES`,
  `NT_DROP_GRACE_SEC`, and `NT_SERVER` / `NT_PORT` (point at a non-roboRIO NT server, used by the
  simulation).
- The service runs as root, so recordings under `~/vision-recordings` are root-owned (readable by `pi`).
- The drain thread reads the stream even while disabled: about 1.5% of one core measured with
  PhotonVision's 320x240 stream at ~100 fps on an Orange Pi 5. Larger frames cost more.

## 2. Copy the script and unit file to the Pi

From the laptop, in the repo root:

```bash
scp coprocessor/orangepi-vision-recorder.py pi@192.168.1.252:/home/pi/
scp "coprocessor/orangepi-vision-recorder@.service" pi@192.168.1.252:/tmp/
```

If team number ever changes from 1405, also update `TEAM_NUMBER` in `/home/pi/orangepi-vision-recorder.py`.

## 3. Point the unit at the venv's Python and create per-instance env files

```bash
sudo sed -i 's|/usr/bin/python3|/home/pi/.venv-ntpublisher/bin/python3|' "/tmp/orangepi-vision-recorder@.service"
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

Create only the env files for cameras hosted on this board. For the current robot,
create `left.env` on the Left board and `right.env` on the Right board. Substitute each
board's own confirmed raw port; both single-camera boards may use the same local port.
Use `RECORDINGS_DIR=...` for a custom storage mount.

## 4. Install and start the instances hosted on this board

```bash
sudo cp "/tmp/orangepi-vision-recorder@.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now orangepi-vision-recorder@left.service
sudo systemctl enable --now orangepi-vision-recorder@right.service
```

Enable only the instances hosted on this board. The two commands above illustrate a
board hosting both cameras; for the current robot, run only the `@left` command on the
Left board and only the `@right` command on the Right board.

## 5. Verify it's working

```bash
sudo systemctl status orangepi-vision-recorder@left.service orangepi-vision-recorder@right.service
sudo journalctl -u "orangepi-vision-recorder@*.service" -f
```

Check only the instances on this board; each should report `Active: active (running)`. A healthy run prints `Connecting to roboRIO (team 1405)… [camera left] ...` once per instance, then `Enabled — starting session ...` / `Disabled — session ended` as the robot state changes — it should otherwise stay quiet.

While the robot is enabled (sim or real), confirm on the Pi:

```bash
ls /home/pi/vision-recordings/<instance>/
cat /home/pi/vision-recordings/<instance>/<latest-session>/manifest.jsonl
```

You should see JPEGs accumulating at roughly `SAMPLE_HZ` (default 3/sec) per camera and a `manifest.jsonl` line per frame with `t_sec` for WPILog alignment plus `timestamp_utc` and `timestamp_unix_ms` for the real date/time. Check that `timestamp_status` is `synced` and the UTC date/time matches the Driver Station clock (UTC differs from local time). Unsynced or stale clocks produce null wall timestamps and an explicit status; they never use the Pi's unverified date. `timestamp_basis` is `recorder_receive`, not exposure time. See `coprocessor/README.md` for the full schema. **Also watch PhotonVision's own dashboard FPS/latency counters while this runs** — they shouldn't visibly regress, since the whole point of tapping the existing MJPEG stream instead of the camera device is to avoid competing with the detection pipeline.

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
