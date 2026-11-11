---
id: VIS-2026-11-11-pv-frame-cost
title: PhotonVision frame cost on the Pi — where a frame's time goes, and whether frames in flight scale
area: vision
date: 2026-11-11
status: planned             # planned | running | analyzed | decided
decision: pending
robot_code: none (bench test on the Pis; no robot code involved)
logs: data/ next to this file (fetched by tools/exprunner); frames stay on the Pis in ~/bench/frames
analysis: analyze.py → results.json
raw_notes: manifest.json (written by the runner)
---

# PhotonVision frame cost on the Pi

## In short

[ADR 0002](../../../adr/0002-photonvision-throughput-limit.md) concluded that PhotonVision is
limited by one frame per camera in flight, not by the Pi's compute. Two of its claims are
inferences, not measurements:

- where the main thread's ~6 ms (800x600) and ~12 ms (1280x800) per frame go;
- that several frames in flight would scale to ~160 frames/s.

This bench test measures both on the Pis, with real camera frames and the same libraries
PhotonVision uses. No robot is needed. It's also the first experiment run with the
[experiment runner](../../../../tools/exprunner/README.md), so it checks the runner too.
**Not run yet.**

## What we're testing

1. **Where does a frame's time go?** Time each step separately at 800x600 and 1280x800: decode
   to colour (what PhotonVision does), decode straight to grey, colour → grey, the detector at
   each decimate and thread count, and the 3D pose step. *(T1, T2)*
2. **Is the camera's JPEG colour or grey?** Read the JPEG header of frames captured straight from
   the camera. *(C1, C2)*
3. **Would decoding straight to grey save meaningful time?** (ADR 0002 option O2) *(T1, T2; F1 vs
   F2)*
4. **Is 2D mode worth anything?** The 3D pose step is the whole difference. *(T1, T2)*
5. **Do several frames in flight scale?** 1–4 workers, each with its own detector (1 thread),
   pinned to the 4 fast cores. (ADR 0002 option O4) *(F1–F4)*
6. **Is the bench trustworthy?** A PhotonVision-like run (1 frame at a time, 8 detector threads)
   should take about as long per frame as the robot measured. *(F0a, F0b)*

| Check | Counts as yes if | Why |
|---|---|---|
| Bench matches the robot (F0a, F0b) | time per frame within ±25% of the robot's (B1 14.6 ms, R13 15.9 ms) | The robot also publishes over NetworkTables and streams; the bench doesn't. Outside ±25%, the bench is measuring something else |
| Grey decode is worth it (O2) | decode to grey + nothing saves ≥ 0.5 ms per frame over decode to colour + colour → grey | 5× the 0.1 ms run-to-run noise seen on the robot |
| 2D mode is worth it | 3D pose (single-tag all tags + multi-tag) ≥ 0.5 ms per frame | Same bar |
| Frames in flight scale (O4) | 4 workers give ≥ 3× the frames/s of 1 worker, **and** ≥ 100 frames/s at the setting tested | 3× = 75% scaling efficiency; 100/s = the camera's rate |

### Words used here

- **Decode**: turning the camera's compressed JPEG into pixels. **To colour** = 3 bytes per pixel
  (what PhotonVision asks for); **to grey** = 1 byte per pixel.
- **Detector threads**: worker threads *inside* one detection (PhotonVision's Threads setting).
- **Workers / frames in flight**: separate frames being processed at the same time, each with its
  own detector. PhotonVision has 1.
- **Fast cores**: cores 4–7 on the RK3588S; PhotonVision ran only on these.
- **Median / p95**: the middle value, and the value 95% of frames beat.

## The runs

Both Pis, the same runs. Every timing step stops PhotonVision while it runs (so it doesn't
compete for CPU), pins to cores 4–7, and starts PhotonVision again afterwards. Frames are captured
once (C1, C2) and reused by every timing run. The runner shows a prompt before C1.

| Run | What it does | Answers | Status |
|---|---|---|---|
| S0 | Self-test on synthetic frames: the bundle and PhotonVision's libraries load | – | to do |
| C1 | Capture 300 frames, 800x600 MJPG @100, 2+ tags in view | 2 | to do |
| C2 | Capture 300 frames, 1280x800 MJPG @100, same view | 2 | to do |
| T1 | Per-step time on C1's frames | 1, 3, 4 | to do |
| T2 | Per-step time on C2's frames | 1, 3, 4 | to do |
| F0a | PhotonVision-like: 1 frame at a time, 8 detector threads, 800x600 dec 1 | 6 | to do |
| F0b | PhotonVision-like: 1280x800 dec 2 | 6 | to do |
| F1 | 1–4 frames in flight, 800x600 dec 1, colour decode | 5 | to do |
| F2 | Same, grey decode | 3, 5 | to do |
| F3 | 1–4 frames in flight, 1280x800 dec 2, colour decode | 5 | to do |
| F4 | 1–4 frames in flight, 1280x800 dec 1, grey decode | 5 | to do |

The exact options for each run are in [runs.toml](runs.toml); `python -m exprunner check` prints
the command each one runs.

### Before the session

- [ ] Both Pis on the network, reachable as `LeftPi.local` / `RightPi.local` (the robot can be
      off, with the Pis on bench power, or on with the robot disabled).
- [ ] This laptop has the team SSH key (`~/.ssh/id_ed25519_orangepi`; the bootstrap copies it).
- [ ] WPILib installed and the robot code built once (the runner compiles the bench program
      against WPILib's jars).
- [ ] 2+ AprilTags placed 1–3 m in front of both cameras, for C1 and C2.

### Running it

From `tools/exprunner`:

```bash
python -m exprunner check ../../docs/experiments/vision/2026-11-11-pv-frame-cost/runs.toml
```

```bash
python -m exprunner run ../../docs/experiments/vision/2026-11-11-pv-frame-cost/runs.toml
```

`run` copies the bench bundle to both Pis, then runs S0, C1, … in order. It waits at C1's prompt,
fetches each run's results into `data/<run>/<board>/`, and records it in `manifest.json`. If it
stops, run it again: it skips what's done. `status` shows where it is. The whole plan takes about
15 minutes.

Then, from the repo root:

```bash
python docs/experiments/vision/2026-11-11-pv-frame-cost/analyze.py
```

## Results

Not run yet.

### What we learned

Not run yet. Laptop dry run of the program, synthetic frames only, not Pi numbers: decode to
grey was 3.6× faster than decode to colour (0.7 vs 2.6 ms at 800x600), and 4 workers gave 3.3×
the frames/s of 1.

## Next experiment

Depends on the answers:

- If frames in flight scale: whether to take O4 upstream to PhotonVision, and what the robot code
  needs (`Vision.java`'s velocity filter with out-of-order results).
- If grey decode saves ≥ 0.5 ms: propose it upstream (ADR 0002 option O2).
- If the bench doesn't match the robot: find what the robot does that the bench doesn't (NT
  publishing, streams, the recorder) before trusting the other numbers.

## Reproduce

```bash
python docs/experiments/vision/2026-11-11-pv-frame-cost/analyze.py
```

Reads `data/` and writes `results.json`. To re-run a step on the Pis: `python -m exprunner run
<plan> T1` (from `tools/exprunner`).

---

## Background

<details>
<summary><b>How the bench program matches PhotonVision</b></summary>

`coprocessor/bench/java/FrameCost.java`, run on the Pi with PhotonVision's own jar on the
classpath and loaded through PhotonVision's own `LibraryLoader.loadWpiLibraries()`. So the OpenCV
build (and its JPEG decoder) and the AprilTag detector are exactly the ones PhotonVision runs.

- **Decode:** `Imgcodecs.imdecode(..., IMREAD_COLOR)`, the same call cscore makes for PhotonVision
  (`Frame::ConvertMJPEGToBGR`). The grey variant is `IMREAD_GRAYSCALE` (cscore's
  `ConvertMJPEGToGray`).
- **Colour → grey:** `Imgproc.cvtColor(BGR2GRAY)`, as PhotonVision's `GrayscalePipe`.
- **Detector:** the config PhotonVision v2026.1.1 sets (`AprilTagPipeline.setPipeParamsImpl`):
  refine edges on, blur 0, the same quad-threshold parameters, tag36h11. Then the same filter as
  our pipelines: decision margin ≥ 30, hamming 0.
- **3D pose:** undistort + `AprilTagPoseEstimator.estimateOrthogonalIteration` for every tag
  ("single-tag always" is on in our pipelines), and one `solvePnP` (SQPNP) over every tag in the
  2026 field layout, as PhotonVision's multi-tag step. Intrinsics are approximate (they don't
  change the time).

Not included: NetworkTables publishing, the stream thread (drawing, JPEG encode for the
dashboard), and the camera wait. That's why F0a/F0b are checked against the robot.

</details>

<details>
<summary><b>Frames in flight, as measured here</b></summary>

`inflight` starts N worker threads in one JVM. Each has its own detector (1 detector thread)
and pose estimator, and they take frames from a shared counter. Each worker decodes, converts,
detects and solves the pose for its frame. Frames/s is counted over `seconds` after a 2 s
warm-up. It's the throughput a PhotonVision with N frames in flight could reach on these cores,
before the cost of putting results back in order.

</details>
