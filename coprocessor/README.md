# Coprocessor scripts

Python scripts that run on the Orange Pi alongside PhotonVision, each installed as a
systemd service. Full bench-verification/install walkthroughs live in
`docs/orangepi-nt-publisher-setup.md` and `docs/orangepi-vision-recorder-setup.md` — this
file is just "what's in this folder and why."

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

- `pip install pyntcore` (shared venv with `orangepi-nt-publisher`, see its setup doc).
- One `/etc/orangepi-vision-recorder/<instance>.env` file per camera instance, at minimum
  setting `CAMERA_STREAM_URL` to that camera's confirmed *raw* (pre-detection) MJPEG port
  — bench-verify this per camera, ports are not guaranteed stable across PhotonVision
  reconfigs.
- `RECORDINGS_DIR` (default `/home/photon/vision-recordings`) needs to actually exist and
  have free space; override per-instance via the same `.env` file if needed.
- The `/FMSInfo` enabled-bit decoding the script relies on should be bench-verified once
  (shared across both instances, not per-camera).

Full steps, exact bench values, and troubleshooting: `docs/orangepi-vision-recorder-setup.md`.
