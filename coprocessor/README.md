# Coprocessor scripts

Python scripts that run on the Orange Pi alongside PhotonVision, each installed as a
systemd service. Full bench-verification/install walkthroughs live in
`docs/orangepi-nt-publisher-setup.md` and `docs/orangepi-vision-recorder-setup.md` — this
file is just "what's in this folder and why."

## `setup-orangepi.sh`

After copying this folder to the Pi, run the installer **on the Pi**, from your normal
SSH account (do not run the whole script with `sudo`):

```bash
cd ~/coprocessor   # or cd ~ if sync-to-orangepi.bat copied the files there
bash setup-orangepi.sh
```

Choose metrics, recorders, or both. The installer creates/reuses
`$HOME/.venv-ntpublisher`, installs `pyntcore` through that venv's Python, checks the
import, copies the selected Python scripts to your home directory, and renders both
systemd units with that interpreter and home path. It enables/restarts the selected
services and checks for immediate crashes/restarts. It uses `sudo` for OS installation
and `/etc` only. Internet is needed if OS/Python dependencies are missing; an existing
working venv can be reused offline.

For each new camera configuration, enter a **confirmed raw MJPEG URL** (bench references:
left 1183, right 1181). Blank skips that camera. Existing camera env files and metrics
namespaces are preserved. New camera env files set `RECORDINGS_DIR` to your account's
`vision-recordings` directory; existing files get this setting only if it is missing,
so both `pi` and `photon` accounts work. A bounded HTTP
check tests whether the stream responds; it cannot distinguish raw from processed video.
Existing recordings and venv packages are retained on reruns. Existing env files with
custom storage paths remain authoritative; ensure those paths exist and have space.

```bash
bash setup-orangepi.sh --status  # Python import, disk, PhotonVision and installed services
bash setup-orangepi.sh --logs    # recent journal entries, no live tail
```

Diagnostics do not change configuration or restart services. An install failure reports
the failed step and journal entries; fix the issue and rerun. Checks show service health,
not proof of roboRIO connectivity or recording correctness: bench-verify NT metrics,
enabled-bit decoding, raw frames, and PhotonVision FPS/latency using the setup guides.
Each camera has a 5GB storage cap. Remove temporary internet/Wi-Fi access when finished.

## `sync-to-orangepi.bat`

On Windows, double-click this batch file (or run it from a Command Prompt) to copy every
other file in this folder, including subfolders, into the Orange Pi user's home directory.
It defaults to `pi@photonvision.local`; supply a target such as
`sync-to-orangepi.bat photon@192.168.1.252` when the Pi uses a different account/address. It
checks the SSH connection first and reports a clear error if the Pi cannot be reached.

## `orangepi-nt-publisher.py` / `orangepi-nt-publisher.service`

Publishes the Pi's CPU/RAM/disk/temp to NT4 under `/OrangePi/` once a second. One process,
one plain (non-templated) systemd service. `ORANGEPI_METRICS_NAME` env var namespaces the
NT table if you ever run more than one Orange Pi on the same robot.

## `orangepi-vision-recorder.py` / `orangepi-vision-recorder@.service`

Samples PhotonVision's raw (pre-AprilTag) camera stream at low rate while the robot is
enabled and saves timestamped JPEGs locally, for post-match vision diagnosis. See the
script's own module docstring for how session folders are named and clock-synced.

### Why the `@` in the filename

`orangepi-vision-recorder@.service` is a **systemd template unit**, not a typo or a
version number placeholder. The `@` marks the file as a template — you never install or
run it under that literal name. Both robot cameras (Left, Right) run through this same
script on the *same* Pi, as two separate instances, so it's templated once and
instantiated twice.

To use it, install the file as-is (still named `orangepi-vision-recorder@.service`) to
`/etc/systemd/system/`, then enable/start it with an **instance name** appended after the
`@` — a short string you choose, not a number:

```bash
sudo systemctl enable --now orangepi-vision-recorder@left.service
sudo systemctl enable --now orangepi-vision-recorder@right.service
```

Whatever you put after the `@` (here, `left`/`right`) is substituted for every `%i` inside
the unit file — see `Environment=CAMERA_NAME=%i` and
`EnvironmentFile=/etc/orangepi-vision-recorder/%i.env`. `CAMERA_NAME` namespaces that
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
- `RECORDINGS_DIR` (default `/home/photon/vision-recordings`) needs to actually exist and
  have free space; override per-instance via the same `.env` file if needed.
- The `/FMSInfo` enabled-bit decoding the script relies on should be bench-verified once
  (shared across both instances, not per-camera).

Full steps, exact bench values, and troubleshooting: `docs/orangepi-vision-recorder-setup.md`.
