# Camera auto-calibration ("spin & drive")

Status: **built and tested on simulated data; not yet run on the robot.** Written 2026-11-14.

## In short

The manual calibration tool (`tools/camera-calibration`, tabs "Manual 1-4") needs tape measurements
of where the robot sits in front of a tag. This is a second way, in the same app, that needs
almost none: the robot runs an autonomous (**CalibrateCameras**) that spins and drives a little in
front of a tag, and the tool solves each camera's position on the robot from the log.

The goal is the one thing the 11-14 discussion kept coming back to: **both cameras should agree
about where the robot is at a standstill**, because the odometry comparison between camera
settings is only as good as the camera mounts.

The manual tabs stay as they are (renamed "Manual 1-4"). Use them when you want a tape-measured
reference or to cross-check this one.

## How it works

While the robot moves with vision corrections **off**, we have two records of the same motion:

- the **camera's** pose in the field frame, from the tag (PhotonVision's raw estimate, with the
  mount that was configured at the time undone exactly: `solver.recover_camera_pose`);
- the **robot's** pose from wheels + gyro (`Drivetrain/Pose`), good only relatively, in its own
  frame.

The tool fits the camera mount, the transform between the two frames, and the clock offset
between vision and odometry together (robust least squares, `camera_calibration/autocal.py`).

| What | Comes from | Needs |
|---|---|---|
| Camera height, roll, pitch | Read off the tag view | Robot level on the floor |
| Camera x, y on the robot | **Spin**: the camera swings around the robot's rotation centre | A spin of a few tens of degrees with the tag in view |
| Camera yaw | **Straight drives**: the camera moves along the robot's own x / y axes, which says which way the robot points | At least ~0.5 m of driving with the tag in view |

Why driving is needed: spinning only tells you the camera's yaw relative to a starting heading
nobody knows. A straight drive is the cheapest absolute heading reference.

Two side effects worth knowing:

- **Both cameras are solved against the same rotation centre and gyro**, so they agree by
  construction (up to noise). That is the standstill disagreement.
- **The origin it calibrates is the robot's rotation centre**, i.e. what the swerve odometry uses,
  not necessarily the bumper centre. If the modules are centred in the frame these are the same.
- **The vision-vs-odometry clock offset is fitted** (it comes out near the camera latency error).
  At 20 deg/s, 20 ms of timestamp error is 0.4 deg of yaw, so this matters.

## What the robot does

`CalibrateCamerasCommand` (`src/main/java/frc/robot/commands/CalibrateCamerasCommand.java`), run
as the **CalibrateCameras** auto from the chooser. About 25 s, robot-relative, stays within about
0.6 m of where it started:

1. Hold 2 s.
2. Sweep in place: +25 deg, -50 deg, +25 deg at 20 deg/s.
3. Drive 0.6 m forward and back, then 0.6 m left, 1.2 m right, 0.6 m left (back to the start),
   at 0.4 m/s.
4. Hold 1 s.

It switches vision corrections off for the run (`setVisionOdometryUpdatesEnabled(false)`) and
restores them after, also if interrupted. It logs `Calibration/Phase` and
`Calibration/VisionCorrectionsOff`, which the tool uses to find the run. The sweep, drive length
and speeds are constants at the top of the file.

## How to run it

1. Robot **level**, about 2-2.5 m from the tag pair, roughly facing it, ~1 m clear all around.
   Both cameras should see the pair at the start. Cover every other tag.
2. Check the tags (below).
3. Deploy, enable **autonomous** with CalibrateCameras selected. Disable when it stops.
4. Fetch the log (LogBench, or the roboRIO's `/home/lvuser/logs/`).
5. `streamlit run calibrate.py` in `tools/camera-calibration`. Load the log. **Quick · Spin &
   drive** tab. The cameras are the ones found in the log (any name), and their current mounts
   are read from `VisionConstants.java` automatically, so there is nothing to enter. Pick the tag
   IDs (it suggests the ones the camera saw most). Solve.
6. Do the same for the other camera, from the **same log**. The agreement table then appears.
7. Paste the Java snippets into `VisionConstants.java`. Re-run the auto and check that the
   agreement and the camera-vs-camera difference at a standstill are small.

Read the result like this:

- **Warnings** (yellow) mean do not trust it yet.
- **Repeatability** (the two halves of the run solved separately) is the number to trust; the
  ±1σ is optimistic because the samples are correlated.
- **Agreement:** after calibration, the camera-vs-camera difference should be clearly lower than
  with the old mounts. A single frame is noisy (20-30 mm), so compare medians, not frames.

## Checking the tags (about 5 minutes)

A tag pair placed a bit sideways or rotated does **not** matter: it shifts every camera pose the
same way and the solver absorbs it. These do matter, because they change what the camera
appears to see:

| Check | How | Good enough |
|---|---|---|
| **Height of the tag centres** (both, from the floor) | Tape, floor to the middle of each black square. Hub tags are 1.124 m (44.25 in) in the field layout | within 5 mm, or **enter the measured height in the tool** (it corrects the camera height) |
| **Tilt** (leaning toward or away from you) | A small level or a phone level app on the tag face, or a plumb line beside it | under 0.5 deg: 1.5 mm over the 165 mm tag |
| **Same plane and direction** | Hold a straightedge across both tag faces: they should touch it | no gap over 1-2 mm; both facing the same way |
| **Spacing between the tag centres** | Tape, centre to centre. The layout has **0.356 m (14.0 in)** for the hub pairs | within 3 mm |
| **Tag size** | Edge to edge of the black square. PhotonVision assumes **6.5 in (165.1 mm)** | within 1 mm |

**Lab check, 2026-11-14 (hub pair):** height, tilt, same plane and tag size all good. **Spacing is
14.25 in (362 mm), not the layout's 14.0 in (356 mm)**: 6 mm wider, over the 3 mm limit. The tool has
no override for it. PhotonVision places the camera assuming the layout spacing, so this can bias the
camera pose a little (we have not measured how much). Fix: slide one tag 0.25 in toward the other,
or accept it for the first run and look at the repeatability and residuals.

The tool takes the tag IDs from what the cameras saw; the field layout is
`src/main/deploy/field_calibration.json`.

## Limits and risks

- **Not yet validated on the robot.** On simulated runs (15 mm / 0.7 deg of vision noise per frame,
  a deliberately wrong starting mount, a 30 ms timestamp offset) it recovers x, y within 2-7 mm,
  z within 1 mm and angles within 0.2 deg, over 8 seeds. Real noise is not Gaussian, odometry
  slips, and intrinsics are never perfect, so treat this as the best case. **Validate once**
  against a tape-measured calibration with the manual tabs.
- **Camera intrinsics must be calibrated at the resolution used** (800x600). A wrong focal length
  or distortion shows up as a wrong mount.
- **Straight drives assume the modules are zeroed.** A module-angle error shows up as a heading
  error in the camera yaw (roughly 1 deg per 1 deg).
- **The routine assumes the cameras see the pair over a wide enough sweep.** Angled cameras see it
  over a narrower range; if the tool says the robot turned or drove too little, shorten the
  distance or reduce `SWEEP_DEG`.
- **Single-tag noise** is larger than a pair's. Use the pair (the multi-tag pose), with every other
  tag covered.
- **Not built yet:** the optional heading cross-check from two wall distances (front-left and
  front-right bumper corner to the tag wall). Add it if the drive-based heading looks suspect.

## Files

| File | What |
|---|---|
| `src/main/java/frc/robot/commands/CalibrateCamerasCommand.java` | the routine |
| `commands/Autos/CommandsForAutos.java`, `Full_Autos.java`, `AutoCommands.java` | registers it as the **CalibrateCameras** auto |
| `tools/camera-calibration/camera_calibration/autocal.py` | the solver, split-half repeatability, camera-vs-camera agreement |
| `.../autocal_io.py` | reads a log: camera poses, tag filter, odometry, the run's time window |
| `.../tabs/auto_tab.py` | the **Quick · Spin & drive** tab |
| `tools/camera-calibration/tests/test_autocal.py` | simulated-run tests: `python -m pytest tests -q` |

## Decisions (2026-11-14)

- Spin & drive is the main method; the manual tape-measure tabs stay for cross-checks.
- Run it as an auto from the chooser.
- Camera resolution stays 800x600 with decimate 2.
- Lab setup: the hub tag pair, 2-2.5 m away, ~2 m clear floor each side; other tags covered.

## Next

- [ ] Run it on the robot; validate once against a tape-measured calibration.
- [ ] Use the calibrated mounts for the camera crossover odometry experiment
      ([plan](experiments/vision/2026-11-14-pv-crossover-odometry/README.md)).
- [ ] Optional: the wall-distance heading cross-check; a live (NetworkTables) mode.
