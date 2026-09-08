# Two-Orange-Pi Vision A/B Test

## Recommendation

Use the second Orange Pi as another PhotonVision **client** on the robot network and run one
camera on each board. Do not add a second NetworkTables instance or change the robot-side pose
estimator. The current robot code already constructs `PhotonCamera` objects named `Left` and
`Right`; PhotonLib finds those globally unique camera nicknames regardless of which PhotonVision
host publishes them.

This makes the physical A/B switch small:

- **A — one board:** Left and Right USB cameras connected to Pi A.
- **B — split:** Left remains on Pi A; move only Right's USB cable to Pi B.

Keep both Pis powered and connected to Ethernet in both configurations. This holds boot state,
network topology, roboRIO code, and most thermal conditions constant.

## Expected difficulty and likely value

- Already-imaged spare Pi: approximately 1–2 hours to configure and verify.
- Fresh image, regulator, switch wiring, and config transfer: approximately half a day.
- Robot Java changes required: none for the basic experiment.

Splitting should help if the current board is CPU-saturated, throttling, dropping frames, or
putting both cameras on a constrained USB path. It will not improve pose accuracy by itself if
both cameras already sustain their configured FPS with stable latency. At the 800x600, 100 FPS,
MJPEG settings recorded in `notes/9-5.md`, measure rather than assume the gain.

## One-time setup

1. Connect the roboRIO, both Pis, and the radio through the robot Ethernet switch. Do not use a
   USB hub for the cameras.
2. Give the PhotonVision hosts unique names, for example `photon-left` and `photon-right`.
3. Give them unique static addresses, for example `10.14.5.11` and `10.14.5.12`, and set team
   number `1405` on both.
4. Disable PhotonVision's **NetworkTables Server** option on both boards. They must both be NT
   clients of the roboRIO.
5. Install the exact same PhotonVision version as PhotonLib in `vendordeps/photonlib.json`
   (currently `v2026.2.2`). Do not upgrade only one side for this experiment.
6. Export Pi A's PhotonVision settings as the control backup. Import/copy the Right camera's
   calibration and AprilTag pipeline to Pi B. Confirm its camera nickname is exactly `Right`.
   Leave Pi A's other nickname exactly `Left`.
7. Never allow two active publishers named `Right` (or `Left`) at once. In configuration B,
   unplug Right from Pi A before attaching it to Pi B.
8. Install the metrics publisher on both Pis. Put
   `ORANGEPI_METRICS_NAME=LeftPi` in `/etc/default/orangepi-nt-publisher` on Pi A and
   `ORANGEPI_METRICS_NAME=RightPi` on Pi B, then restart the service.
9. Disable the vision recorder and close live camera streams during measured runs. They add work
   and network traffic. Apply this identically to A and B.
10. Use stable, adequately sized 5 V regulators for both Pis. Check for undervoltage or thermal
    throttling before interpreting FPS results.

Before driving, use Glass/OutlineViewer to confirm all of these simultaneously:

- two distinct PhotonVision NT clients;
- `/photonvision/Left` and `/photonvision/Right` both updating;
- both cameras report connected in `/Vision/Left/connected` and `/Vision/Right/connected`;
- `/OrangePi/LeftPi/*` and `/OrangePi/RightPi/*` update independently;
- each camera produces plausible poses while the robot is stationary.

## Fast A/B procedure

Use the same autonomous routine, starting pose, field/tag placement, pipeline settings, robot
build, and camera mounts. Mark the wheels' starting locations and robot heading on the floor.

Run an **ABBA** block to reduce battery, lighting, and temperature drift:

1. A1: both cameras on Pi A.
2. B1: move Right USB to Pi B.
3. B2: repeat split configuration.
4. A2: move Right USB back to Pi A.

Power-cycle PhotonVision after each USB topology change if the camera does not rematch cleanly.
Wait until both camera FPS values have stabilized before enabling. Run at least three ABBA blocks
(six runs per topology); alternating single runs is much more trustworthy than doing all A runs
before all B runs. Use batteries at comparable state of charge.

Immediately after each run, download the WPILog with the Vision Log Dashboard and give it a
suffix such as `one_pi_A1` or `split_B1`. The analyzer already supports Log A versus Log B:

```bash
python -m streamlit run tools/vision-analyzer/analyze.py
```

## Metrics and decision rule

Compare each camera separately; Right is the moved/treatment camera and Left is a useful control.

Primary compute metrics:

- mean, minimum, and variability of `Vision/<camera>/currentFps`;
- mean and tail result latency from `rawTimestampsSec` / `LatencyMsLatest`;
- results per loop and accepted poses per second;
- connection uptime and longest result gap;
- Pi CPU percentage and temperature, especially late in each run.

Odometry/autonomous metrics:

- physically measured final X/Y/heading error (do not use the fused pose as its own ground truth);
- autonomous path tracking error if a reference trajectory is logged;
- vision acceptance/rejection rate during motion;
- correction spikes and camera-to-camera pose disagreement;
- run-to-run spread, not just the single best run.

Adopt the split when it produces a repeatable improvement such as at least 10% higher low-percentile
FPS or 10 ms lower tail latency, without worse connection uptime, physical endpoint error, or pose
disagreement. If FPS and latency are already flat near the configured target, prefer one Pi: the
extra board adds power, Ethernet, boot, and failure-point complexity without an odometry benefit.

## Important controls and pitfalls

- Keep camera calibration, nickname, pipeline, exposure, gain, resolution, AprilTag family, and
  field layout identical when Right moves. Importing settings and then changing pipeline tuning
  makes this a camera-config test, not a compute-topology test.
- Validate the real camera mode in PhotonVision. `VisionConstants` contains 1280x800 intrinsics,
  while `notes/9-5.md` records 800x600 operation. This mismatch is independent of the two-Pi test,
  but it can affect robot-side single-tag fallback and should be resolved before judging absolute
  odometry accuracy.
- Camera nicknames are global across all coprocessors. Hostnames and IPs must also be unique, but
  robot code keys off `Left` and `Right`, not `photon-left` and `photon-right`.
- Camera stream port numbers repeat on separate hosts; that is fine. A stream is identified by
  host plus port.
- The 7 Mbps field limit matters mainly for streamed video. PhotonLib result traffic is much
  smaller, but leave streams closed during the experiment and competition.
