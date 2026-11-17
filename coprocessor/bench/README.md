# Bench steps for the Orange Pis

Small tests that run on a Pi itself, with no robot: capture frames straight from the camera, and
time what PhotonVision does to each frame. The [experiment runner](../../tools/exprunner/README.md)
copies this folder to `~/bench/code` on each Pi and calls `run.sh` over SSH. Nothing here is
installed; a sync just replaces `~/bench/code`.

| File | What |
|---|---|
| `run.sh` | Entry point: `bash ~/bench/code/run.sh <step> --results DIR [options]`. The steps and options are listed at its top |
| `java/FrameCost.java` | The timing program. Compiled on the laptop by the runner; on the Pi it runs with PhotonVision's own jar, so it uses exactly PhotonVision's OpenCV and AprilTag libraries |

Steps: `env` (the Pi's clocks, temperatures, PhotonVision version), `capture` (frames from the
camera via `v4l2-ctl`), `selftest`, `inspect`, `steps`, `inflight` (see `FrameCost.java`'s header).

Things worth knowing:

- **PhotonVision is stopped during a step** (it holds the camera, and it would compete for CPU)
  and started again afterwards, also if the step fails. `--stop-pv no` leaves it running for the
  timing steps; capture always stops it. If a Pi is left without PhotonVision (e.g. power was cut
  mid-step): `sudo systemctl start photonvision`.
- **Frames are kept** in `~/bench/frames/<name>.mjpg` and reused by later steps (`--frames <name>`).
  300 frames at 1280x800 is about 30 MB.
- **By hand**, without the runner: copy the folder over with a sync (`python -m exprunner sync
  <plan>`), then `ssh pi@LeftPi.local` and run `bash ~/bench/code/run.sh selftest --results
  ~/bench/results/manual`.
- Needs `v4l-utils` (for `v4l2-ctl`) for `capture`; the 10-28 notes show it's on both Pis.
- **`pi` must be in the `video` group** for `capture`, or `v4l2-ctl` fails with permission denied
  (the run exits 1 right after stopping PhotonVision). `setup-orangepi.sh` (so the bootstrap) now
  does this; on a Pi set up earlier, run `sudo usermod -aG video pi` once and log in again.
