---
id: VIS-2026-11-11-pv-frame-cost
title: PhotonVision frame cost on the Pi — where a frame's time goes, and whether frames in flight scale
area: vision
date: 2026-11-11
status: analyzed            # planned | running | analyzed | decided
decision: pending           # waits on the range experiment: does a finer image see tags farther or more accurately?
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
**Run 2026-11-14 on both Pis; all 22 steps passed.**

**Result in three lines:** the bench matches the robot (within 13%). Four frames in flight at
once give 2-2.8x the frames/s of PhotonVision's one-at-a-time setup, but each frame spends about
11 ms longer in the pipeline. That is *feasible*, but **we have not shown it makes odometry
better**: at our competition setting (800x600 dec 2) we are already at the camera's 100/s, so it
only pays if the range experiment shows a finer image is worth having. See "What we learned".

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
| S0 | Self-test on synthetic frames: the bundle and PhotonVision's libraries load | – | done |
| C1 | Capture 300 frames, 800x600 MJPG @100, 2+ tags in view | 2 | done |
| C2 | Capture 300 frames, 1280x800 MJPG @100, same view | 2 | done |
| T1 | Per-step time on C1's frames | 1, 3, 4 | done |
| T2 | Per-step time on C2's frames | 1, 3, 4 | done |
| F0a | PhotonVision-like: 1 frame at a time, 8 detector threads, 800x600 dec 1 | 6 | done |
| F0b | PhotonVision-like: 1280x800 dec 2 | 6 | done |
| F1 | 1–4 frames in flight, 800x600 dec 1, colour decode | 5 | done |
| F2 | Same, grey decode | 3, 5 | done |
| F3 | 1–4 frames in flight, 1280x800 dec 2, colour decode | 5 | done |
| F4 | 1–4 frames in flight, 1280x800 dec 1, grey decode | 5 | done |

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

All numbers are medians from `data/`, both Pis; the two Pis agree within about 10%. 2 tags in
view in every frame. Regenerate with `analyze.py`.

**The camera sends colour JPEGs** (3 channels, 2x1 chroma sampling) at both resolutions, so
decoding straight to grey really skips work.

**Where a frame's time goes** (ms, LeftPi; RightPi is 0-15% slower on detection):

| Step | 800x600 | 1280x800 |
|---|---|---|
| Decode to colour (what PhotonVision does) | 2.4 | 5.1 |
| Decode straight to grey | 1.2 | 2.7 |
| Colour to grey | 0.2 | 0.5 |
| Detect, dec 1, 4 threads | 9.4 | 20.4 |
| Detect, dec 2, 4 threads | 3.3 | 7.1 |
| Detect, dec 3, 4 threads | 1.9 | 3.6 |
| 3D pose (per-tag + multi-tag) | 1.0 | 1.2 |

Detect with 8 threads is 2-10% *slower* than with 4 (only 4 fast cores).

**PhotonVision-like baseline** (1 frame at a time, 8 threads) vs the robot: 800x600 dec 1:
14.2 / 14.7 ms vs 14.6 (x0.97-1.00); 1280x800 dec 2: 13.8 / 14.0 ms vs 15.9 (x0.87-0.88).
Both inside +-25%. That setup does 68-72 frames/s.

**Frames in flight** (frames/s, each worker 1 detector thread, cores 4-7; Left / Right):

| Setting | 1 worker | 2 | 3 | 4 | 4 vs 1 | Time per frame |
|---|---|---|---|---|---|---|
| F1: 800x600 dec 1, colour decode | 39 / 37 | 85 / 80 | 124 / 115 | **159 / 151** | 4.1x / 4.1x | 24-27 ms |
| F2: 800x600 dec 1, grey decode | 41 / 42 | 90 / 85 | 132 / 124 | **174 / 164** | 4.3x / 3.9x | 22-24 ms |
| F3: 1280x800 dec 2, colour decode | 52 / 47 | 101 / 101 | 154 / 145 | **199 / 190** | 3.8x / 4.1x | 19-21 ms |
| F4: 1280x800 dec 1, grey decode | 19 / 21 | 42 / 41 | 62 / 63 | **79 / 79** | 4.1x / 3.8x | 47-52 ms |

The one-at-a-time baseline takes ~14 ms per frame, so frames in flight make each frame about
5-11 ms later (F1/F3) in exchange for 2-2.8x the frames/s.

**The checks:**

| Check | Result |
|---|---|
| Bench matches the robot (+-25%) | **Yes** (x0.87-1.00) |
| Grey decode saves >= 0.5 ms | **Yes**: 1.3 ms at 800x600, 2.8 ms at 1280x800 |
| 2D mode worth it (3D pose >= 0.5 ms) | **Yes, but small**: 0.9-1.2 ms of a 14 ms frame |
| Frames in flight scale (4 workers >= 3x and >= 100/s) | **Yes** for F1-F3. **F4 scales (3.8-4.1x) but only reaches 79/s**, so 1280x800 dec 1 stays out of reach |

### What we learned

In plain terms:

1. **The Pi has spare compute; PhotonVision just doesn't use it.** One frame at a time leaves the
   other fast cores idle. Four separate workers, each handling its own frame, used them and got
   about four times the frames/s of one worker. Scaling was nearly linear; memory bandwidth and
   heat did not stop it.
2. **The price is time per frame, not accuracy.** Each worker gets one core instead of
   spreading a frame over all of them, so an individual frame takes longer to finish: ~25 ms
   instead of ~14 ms (800x600 dec 1). You get more frames, each one a little later. Detection
   itself is the same, so each result is no less accurate.
3. **Where the time goes:** the detector is the biggest piece (about two thirds at 800x600 dec 1,
   about half at 1280x800 dec 2). Decode is next (a sixth to a third). Pose is small (~1 ms).
4. **Free wins that need no architecture change:** decode straight to grey saves 1.3-2.8 ms per
   frame (10-20%); 4 detector threads is as good as 8; 2D mode saves about 1 ms.
5. **The bench is trustworthy**, so these are real numbers for the robot, not just for the lab.

**Does it make odometry better or worse? Not shown either way.** What we measured is how many
frames the Pi can process, not how good the robot's pose is. Reasoning from the numbers:

- *Accuracy of each measurement:* unchanged. Same detector, same image.
- *Age of each measurement:* about 10 ms older. PhotonVision stamps each result with the time
  the camera took the picture, and WPILib's pose estimator applies it at that time, so the
  extra age costs little. It is not free: if results arrive out of order, `Vision.java`'s
  velocity filter would reject them (negative `dt`), so the code would need a change.
- *Number of measurements:* this is the benefit, but **only where we are below the camera's rate.**
  At our competition setting (800x600, dec 2) we already get 101/s, the camera's limit. More
  workers add nothing there. They matter only for finer settings that today fall short: dec 1
  (68/s) and 1280x800 (63/s).

So the real question is whether finer settings improve odometry at all, which is the **range
experiment**. If they don't, stay on stock PhotonVision at 800x600 dec 2. If they do, several
frames in flight is how to get them at full rate.

**Not tested:** more than 2 tags in view (more tags make detection slower); the recorder, NT
publishing and streams running alongside; a mix such as 2 workers x 2 threads (it might get
most of the throughput with less added delay); a stock PhotonVision change to do any of this.

## Next experiment

Frames in flight scale and the bench matches the robot, so:

1. **Run the range experiment.** It decides whether anything here is worth doing.
2. If a finer image helps: try 2 workers x 2 threads and 3 x 1 on the bench (less added delay),
   then decide whether to take O4 upstream to PhotonVision, and what `Vision.java` needs for
   out-of-order results.
3. Grey decode (O2) is cheap and safe whatever the range result says: propose it upstream.
4. Re-run F1-F3 with more tags in view, and with the recorder and NT running.

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
