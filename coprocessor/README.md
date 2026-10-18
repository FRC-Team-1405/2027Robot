# Coprocessor scripts

Python scripts that run on the Orange Pi alongside PhotonVision, each installed as a
systemd service. Full bench-verification/install walkthroughs live in
`docs/orangepi-nt-publisher-setup.md` and `docs/orangepi-vision-recorder-setup.md` — this
file is just "what's in this folder and why."

## `Bootstrap-OrangePi.ps1` (runs on the LAPTOP, PowerShell)

Not the same thing as `setup-orangepi.sh` below, which runs on the Pi. This is the one-time,
guided setup of a **new** Pi from the Windows laptop. It explains each step, reports PASS / FAIL /
"needs you", and is safe to re-run:

```powershell
cd coprocessor
.\Bootstrap-OrangePi.ps1                    # fully interactive
.\Bootstrap-OrangePi.ps1 -Address 192.168.137.241 -BoardName LeftPi -Cameras left
```

It finds the Pi (mDNS, the Internet-Connection-Sharing subnet, the bench address), creates and
installs an SSH key (you type the Pi password into ssh itself; the script never sees it), offers
passwordless sudo, checks the Pi (OS, Python, disk, internet), checks the camera is activated in
PhotonVision and finds its raw stream port, checks PhotonVision's team number is 1405, copies the
scripts, runs `setup-orangepi.sh` unattended and verifies the services. Things only a person can
do (enable Internet Connection Sharing, press ACTIVATE on the camera in PhotonVision) stop the
script with exact instructions. `Get-Help .\Bootstrap-OrangePi.ps1 -Full` lists the parameters.

`setup-orangepi.sh` also has an opt-in unattended mode used by this script
(`SETUP_UNATTENDED=1 SETUP_CHOICE SETUP_BOARD_NAME SETUP_CAMERAS SETUP_STREAMS`); without
`SETUP_UNATTENDED` it behaves exactly as before.

## `sim/` simulated match

Verify the recorder end to end with no roboRIO: `sim\Run-SimulatedMatch.ps1` plays pre-match,
auto, pause, teleop and post-match on a real Pi and checks the recordings. See `sim/README.md`.

## `setup-orangepi.sh`

After copying this folder to the Pi, run the installer **on the Pi**, from your normal
SSH account `pi` (do not run the whole script with `sudo`):

```bash
cd ~/coprocessor
bash setup-orangepi.sh
```

Choose metrics, recorders, or both. The installer creates/reuses
`$HOME/.venv-ntpublisher`, installs `pyntcore` through that venv's Python, checks the
import, copies the selected Python scripts to your home directory, and renders both
systemd units with that interpreter and home path. It enables/restarts the selected
services and checks for immediate crashes/restarts. It uses `sudo` for OS installation
and `/etc` only. Internet is needed if OS/Python dependencies are missing; an existing
working venv can be reused offline.

Setup asks for a **unique board name**, stored as `ORANGEPI_METRICS_NAME` in
`/etc/default/orangepi-nt-publisher`. The metrics topics are
`/OrangePi/<board-name>/CPU_Pct`, `Temp_C`, etc. Use a distinct name on every board
connected to the same roboRIO; changing only the NT client name does not separate
topic paths. Setup defaults to the existing board name on reruns and preserves other
settings in the file. It cannot compare names with other boards on the network.

When installing recorders, enter the camera instance names on **this board**, separated
by spaces. Names may contain letters, digits, `_` or `-`; there is no default camera
selection or assumed board count. One board may record `front`, another `rear`, or one
board may record several cameras. Existing instances not selected for update are kept;
retire an unwanted instance with:

```bash
sudo systemctl disable --now orangepi-vision-recorder@<instance>.service
```

Example for the current robot (two boards, one camera each):

| Board | Board NT name | Camera instances | Metrics topics |
|---|---|---|---|
| Left camera board | `LeftPi` | `left` | `/OrangePi/LeftPi/*` |
| Right camera board | `RightPi` | `right` | `/OrangePi/RightPi/*` |

The recorder clients become `OrangePiVisionRecorder-LeftPi-left` and
`OrangePiVisionRecorder-RightPi-right`. Both read `/FMSInfo` and `/RobotTime`; they do
not publish values there. Recording files stay on each board's own disk.

Rerunning setup copies the latest selected Python scripts and rendered service units,
then calls `systemctl daemon-reload`, enables them at boot, and restarts them. Existing
working dependencies are reused; this is not a forced package upgrade. Copy updated
repo files to the Pi first, then select the services you want to update.

For each new camera configuration, enter a **confirmed raw MJPEG URL on that board**.
Port numbers depend on each board's PhotonVision configuration; do not reuse the old
one-board left/right port mapping without checking it. Blank skips that camera.
Existing camera env files are preserved. New camera env files set `RECORDINGS_DIR` to your account's
`vision-recordings` directory; existing files get this setting only if it is missing,
and the installer requires the `pi` login for installation and diagnostics. A bounded
HTTP check tests whether the stream responds; it cannot distinguish raw from processed video.
Existing recordings and venv packages are retained on reruns. Existing env files with
custom storage paths remain authoritative; ensure those paths exist and have space.

```bash
bash setup-orangepi.sh --status  # board identity, Python, disk, PhotonVision, installed instances
bash setup-orangepi.sh --logs    # recent journal entries, no live tail
```

Diagnostics do not change configuration or restart services. An install failure reports
the failed step and journal entries; fix the issue and rerun. Checks show service health,
not proof of roboRIO connectivity or recording correctness: bench-verify NT metrics,
enabled-bit decoding, raw frames, and PhotonVision FPS/latency using the setup guides.
Each camera has a 5GB storage cap. Remove temporary internet/Wi-Fi access when finished.

## `sync-to-orangepi.bat`

On Windows, double-click this batch file (or run it from a Command Prompt) to copy the
entire `coprocessor` folder, including subfolders, to `/home/pi/coprocessor` using SCP.
It needs the Windows OpenSSH Client (`ssh` and `scp`); no archive utility is required.
It defaults to `pi@photonvision.local` and requires the `pi` user. It checks SSH access
and that `/home/pi` is writable before transferring. Matching remote files are replaced;
extra remote files are retained. You can run it from any working directory, including
when the repository path contains spaces. After copying, it normalizes the Bash
installer's line endings on the Pi so an older Windows checkout can run it.

```bat
sync-to-orangepi.bat
sync-to-orangepi.bat pi@192.168.1.252
sync-to-orangepi.bat pi@192.168.1.252 --setup
```

Copying alone does not reload or restart services. Add `--setup` to open the guided
Pi-side installer over SSH after a successful transfer. Select the services to update;
the installer applies their latest files and restarts/checks them. If copying fails,
the installer does not run. Without `--setup`, SSH in as `pi` and run
`cd ~/coprocessor && bash setup-orangepi.sh` afterward. A fresh install may still need
temporary internet for dependencies; updating an existing working venv can be offline.

## `orangepi-nt-publisher.py` / `orangepi-nt-publisher.service`

Publishes the Pi's CPU/RAM/disk/temp to NT4 under `/OrangePi/` once a second. One process,
one plain (non-templated) systemd service on each board. The installer sets
`ORANGEPI_METRICS_NAME` to separate each board's topics and metrics client identity.
Launching the Python script outside this setup with no name still uses the legacy
`/OrangePi/*` topics; multiple unnamed publishers would share those topics.

## `orangepi-vision-recorder.py` / `orangepi-vision-recorder@.service`

Samples PhotonVision's raw (pre-AprilTag) camera stream at low rate while the robot is
enabled and saves timestamped JPEGs locally, for post-match vision diagnosis. See the
script's own module docstring for how session folders are named and clock-synced.

Each `manifest.jsonl` row now contains a real per-frame UTC date/time, not just
the NT seconds embedded in its filename. Recorder version `2026.10.18.1` adds:

```json
{"frame":"frame_12.500000.jpg","t_sec":12.5,"timestamp_utc":"2026-10-18T14:00:00.500Z","timestamp_unix_ms":1792332000500,"timestamp_source":"roborio_wall_clock","timestamp_basis":"recorder_receive","timestamp_status":"synced"}
```

The recorder maps the robot's published `RobotTime/WallClockMs` and its atomic NT
server timestamp to each frame's NT receipt time. This accounts for elapsed time
since publication without relying on the Orange Pi's batteryless wall clock.
Accuracy follows the roboRIO clock supplied by the Driver Station; millisecond
formatting does not promise millisecond capture accuracy. These are recorder receipt
timestamps, **not camera exposure timestamps**: this MJPEG reader has no exposure
timestamp metadata. `t_sec` and filenames stay compatible with WPILog replay.

When disconnected, awaiting NT clock sync, or lacking a valid robot clock sample
within five seconds of the frame, `timestamp_utc`, `timestamp_unix_ms` and
`timestamp_source` are `null`. `timestamp_status` states why (`nt_disconnected`,
`nt_clock_unsynced`, `robot_clock_unavailable`, or `robot_clock_stale`). Frames still
record; the recorder never substitutes an unverified Pi date. Install the updated
script on every camera instance via `bash setup-orangepi.sh`. Existing manifests
are not rewritten: their original rows did not record this clock correlation.

Each new session also contains `recorder.log`: recorder version, board/camera/stream
configuration, NT connection and enabled/control-word changes, ten-second progress
reports (frames, errors, NT timestamp and clock-sync status), exception tracebacks,
and the final frame/error count on disable or clean shutdown. These messages still go
to the systemd journal. The file stays open while disabled until the next session,
so a missing teleop enable can be investigated from the previous recording. The last
100 diagnostic events are carried into the next session for startup/transition context.
Logs rotate at 1 MiB with one backup (`recorder.log.1`) per session and are removed with
their session under the normal storage cap. Wall-clock log timestamps use the Pi's OS
clock (which may be stale); progress reports also include NT-server-domain time.

Logbench **Fetch Bundle** already downloads every flat file in a selected session,
including both diagnostic files, alongside `manifest.jsonl` and the JPEGs. Find them
under `<match>.vision/<camera>/boot.../` beside the downloaded `.wpilog`. Install the
updated recorder with `bash setup-orangepi.sh` (select all camera instances on this
board); historical recordings cannot acquire diagnostics retroactively. These are
application diagnostics, not an export of the full systemd journal: abrupt power loss,
OS kills and failures before recorder startup may still require `journalctl`.

### Why the `@` in the filename

`orangepi-vision-recorder@.service` is a **systemd template unit**, not a typo or a
version number placeholder. The `@` marks the file as a template — you never install or
run it under that literal name. Install one instance per camera hosted on that board.
The same template supports one camera on each of several boards, or multiple cameras
on one board.

To use it, install the file as-is (still named `orangepi-vision-recorder@.service`) to
`/etc/systemd/system/`, then enable/start it with an **instance name** appended after the
`@` — a short string you choose, not a number:

```bash
sudo systemctl enable --now orangepi-vision-recorder@left.service
sudo systemctl enable --now orangepi-vision-recorder@right.service
```

These are examples: enable only `left` on the Left board and only `right` on the Right
board for the current robot. A different setup can choose its own names.

Whatever you put after the `@` (here, `left`/`right`) is substituted for every `%i` inside
the unit file — see `Environment=CAMERA_NAME=%i` and
`EnvironmentFile=/etc/orangepi-vision-recorder/%i.env`. The template also reads the board
name from `/etc/default/orangepi-nt-publisher`. `CAMERA_NAME` namespaces that
instance's session folders and boot-id counter (`RECORDINGS_DIR/<CAMERA_NAME>/...`) so the
two instances never collide, and the per-instance `.env` file is where you set that
instance's `CAMERA_STREAM_URL` (which raw MJPEG port it taps). Pick instance names that
mean something to you — `left`/`right` here, but it could as easily be `cam0`/`cam1`.

### Pi-side setup this needs before it'll work

- `"$HOME/.venv-ntpublisher/bin/python3" -m pip install pyntcore` (shared venv
  with `orangepi-nt-publisher`; create it with the installer or its setup doc first).
- One `/etc/orangepi-vision-recorder/<instance>.env` file per camera instance, at minimum
  setting `CAMERA_STREAM_URL` to that camera's confirmed *raw* (pre-detection) MJPEG port
  — bench-verify this per camera, ports are not guaranteed stable across PhotonVision
  reconfigs.
- `RECORDINGS_DIR` (default `/home/pi/vision-recordings`) needs to actually exist and
  have free space; override per-instance via the same `.env` file if needed.
- The `/FMSInfo` enabled-bit decoding the script relies on should be bench-verified once
  (shared across both instances, not per-camera).

Full steps, exact bench values, and troubleshooting: `docs/orangepi-vision-recorder-setup.md`.
