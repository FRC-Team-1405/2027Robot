# ADR 0002: What limits PhotonVision's results/s on our Orange Pi 5s, and what could raise it

- **Status:** Accepted as our current understanding. The options under "What could raise it" are
  proposals, gated on the range experiment and the two bench tests in "Next steps".
- **Date:** 2026-11-11
- **Scope:** PhotonVision v2026.1.1 on 2× Orange Pi 5 (RK3588S), one Arducam OV9281 (USB, MJPEG)
  per Pi, AprilTag 36h11 pipeline, 3D mode. Robot side: `Vision.java`.
- **Triggering evidence:** the three PhotonVision experiments,
  [throughput (10-27)](../experiments/vision/2026-10-27-pv-throughput/README.md),
  [frame pacing (11-03, 11-07)](../experiments/vision/2026-10-28-pv-frame-pacing/README.md) and
  [frame budget (11-10)](../experiments/vision/2026-11-10-pv-frame-budget/README.md), plus the
  PhotonVision and WPILib (cscore) source.

## Summary

**The question:** higher resolution and lower decimate cut results/s badly (1280x800 dec 2: 63/s;
800x600 dec 1: 69/s; 800x600 dec 2: 101/s), yet the Pi's CPU is mostly idle. Is the Pi limited
by its fastest core, and is it true that nothing can be spread over the other cores?

**Answers, each backed by a measurement or the source code:**

1. **No single core is maxed out.** PhotonVision's busiest thread used 54–74% of one core in
   every run, except when we forced all detector work onto it (B4, 1 detector thread: 99.8%). The
   4 fast cores sat at 50–65% busy, and the 4 slow cores were nearly idle.
2. **What limits us is how PhotonVision is built, not how much compute the Pi has.**
   PhotonVision processes **one frame per camera at a time**: the next frame doesn't start until
   the previous one is published. So **results/s = 1 ÷ time per frame**, and the time per frame
   is a chain of steps that can't overlap. Some steps run on one thread (decode, colour → grey,
   parts of the detector, pose solve). One step is spread over cores (the middle of the AprilTag
   search), and the main thread sits idle waiting for it. Cores that aren't on that chain can't
   help.
3. **"It can't be spread across cores" is true only of PhotonVision as it is today.** Nothing
   about the problem forces it. Each frame is independent: detecting tags in frame N+1 doesn't
   need anything from frame N. Two well-known techniques would use the idle cores. Neither is in
   PhotonVision v2026.1.1:
   - **Pipelining the steps:** decode frame N+1 on one thread while frame N is being detected on
     another. 6328's Northstar does a simple version of this: capture on one thread, detection on
     another.
   - **Several frames in flight:** frame N on one core, N+1 on the next, and so on. Our own data
     says one 800x600 dec 1 frame takes 24.4 ms on a single fast core (B4). Four fast cores each
     working on their own frame would allow up to ~160 frames/s, more than the camera's 100–120.
     That is a ceiling worked out from the numbers, not a measurement. Memory bandwidth, heat
     and the camera feed could each lower it.
4. **"A bit later, but more of them" works for the robot.** With several frames in flight, each
   result arrives about one frame-processing time after capture (~25 ms, about what we see now),
   and more results arrive. PhotonVision stamps each result with the **camera capture time**, and
   WPILib's pose estimator accepts measurements with past timestamps. One catch on our side: if
   results ever arrive **out of order**, `Vision.java`'s velocity filter compares against the last
   accepted timestamp, gets a negative `dt` and rejects the result. That would need a change.
5. **The work on the one main thread mostly grows with image size.** It takes ~6 ms per 800x600
   frame whatever the decimate, and 11.8 ms at 1280x800. The source shows that thread decodes the
   camera's MJPEG into a **colour** image and then converts it to grey, even though the OV9281 is
   a mono camera. How the time divides between decode, grey conversion and detection has **not
   been measured**. It's the first thing to measure (next steps, bench test 1).

6. **2D mode wouldn't speed us up much.** Detection is identical in 2D and 3D. 3D only adds the
   pose solve: small fixed math per tag, not per pixel. A camera runs one pipeline at a time.
   Switching pipelines from robot code only helps at heavier settings than we run now. See "2D vs
   3D mode" below. The ML-assisted detector makes a frame cheaper but doesn't put more frames in
   flight.

**Decision:** for 2027 competition we stay on stock PhotonVision at **800x600 @100, decimate 2,
Low Latency Mode off, threads 8**. That's the only setting at the full 101/s. Whether to chase
higher resolution at all depends on the
[range experiment](../experiments/vision/2026-11-03-pv-range/README.md). If a finer image doesn't
see tags meaningfully farther or more accurately, none of the options below are worth doing.

## The frame, step by step (PhotonVision v2026.1.1)

One camera, one frame. Everything in the left column happens one after another on that camera's
`VisionRunner` thread. Only the step marked "parallel" uses more than one core.

| # | Step | Thread | Grows with | Source |
|---|---|---|---|---|
| 1 | Wait for a new camera frame (with Low Latency Mode off: take the newest frame already received) | main | – | [`USBFrameProvider`](https://github.com/PhotonVision/photonvision/blob/v2026.1.1/photon-core/src/main/java/org/photonvision/vision/frame/provider/USBFrameProvider.java) |
| 2 | **Decode MJPEG → colour (BGR) image** with OpenCV `imdecode` | main (cscore runs it in the caller's thread) | pixels | cscore [`RawSinkImpl::GrabFrameImpl`](https://github.com/wpilibsuite/allwpilib/blob/v2026.2.1/cscore/src/main/native/cpp/RawSinkImpl.cpp) → [`Frame::ConvertMJPEGToBGR`](https://github.com/wpilibsuite/allwpilib/blob/v2026.2.1/cscore/src/main/native/cpp/Frame.cpp) |
| 3 | **Colour → grey** (`cvtColor`) | main | pixels | [`CpuImageProcessor`](https://github.com/PhotonVision/photonvision/blob/v2026.1.1/photon-core/src/main/java/org/photonvision/vision/frame/provider/CpuImageProcessor.java), `GrayscalePipe` |
| 4 | AprilTag detector: decimate the image, then the **serial** steps | main | pixels ÷ decimate² | WPILib `AprilTagDetector` (`quadDecimate`, `numThreads`) |
| 5 | AprilTag detector: threshold, segment, fit quads, decode tags | **parallel**, `threads` workers; main waits | pixels ÷ decimate², tags | same |
| 6 | Pose solve: per tag, then multi-tag PnP | main | number of tags | [`AprilTagPipeline`](https://github.com/PhotonVision/photonvision/blob/v2026.1.1/photon-core/src/main/java/org/photonvision/vision/pipeline/AprilTagPipeline.java) |
| 7 | Publish result over NetworkTables, hand the frame to the stream thread | main | – | [`VisionModule`](https://github.com/PhotonVision/photonvision/blob/v2026.1.1/photon-core/src/main/java/org/photonvision/vision/processes/VisionModule.java) |
| – | Draw outlines, encode and serve the dashboard streams | **stream thread**, off the chain; drops frames if behind | pixels | `VisionModule.StreamRunnable`, `OutputStreamPipeline` |

Then back to step 1. There's one `VisionRunner` per camera, so a **second camera** gets its own
chain and its own core. That's the only way stock PhotonVision uses more cores for more results.

## Evidence

### Measured (from our logs)

Per-thread CPU comes from the Pi publisher's top-8 PhotonVision threads, sampled about once a
second (good to ~1 ms per frame). The fast cores are 4–7. "Detector CPU" is all the other
`VisionRunner` threads added together.

| Run | Setting | Results/s | Time per frame | Main thread | Main thread, ms per frame | Detector CPU, ms per frame | Fast cores busy |
|---|---|---|---|---|---|---|---|
| R5 (11-07) | 800x600 @100, dec 2, 8 threads | 101 | 9.9 ms (camera-paced) | 65% | 6.4 | ~7 | 50–65% (11-07 runs) |
| R13 (11-07) | **1280x800** @100, dec 2, 8 threads | 63 | 15.9 ms | **74%** | 11.8 | ~12 | 51–61% |
| B1 (11-10) | 800x600 @100, **dec 1**, 8 threads | 68 | 14.6 ms | **54%** | 7.9 | ~19 | 61–66% |
| B3 (11-10) | 800x600 @100, dec 1, 3 threads | 70 | 14.3 ms | – | 6.7 | ~24 | – |
| B4 (11-10) | 800x600 @100, dec 1, **1 thread** | 41 | 24.4 ms | **99.8%** | 24.4 | ~4 (not detector; see below) | – |
| reset (11-10) | 800x600 @100, dec 2, 8 threads | 101 | 9.9 ms (camera-paced) | – | 6.4 | ~7 | – |

What these show:

- **The main thread is busy for only part of each frame** (54–74%). The rest of the time it
  waits for the detector workers. The frame is limited by a *chain* of steps, not by one core
  running flat out.
- **With 1 thread, the whole frame takes 24.4 ms on one core** (B4). With 3–8 threads, 14.3–14.6
  ms. Spreading the detector over cores saves ~10 ms of waiting, but costs more total CPU
  (~27 ms vs 24.4 ms per frame). That's overhead from splitting the work up.
- **More detector threads past 3 change nothing** (B1–B3 within 1/s). Within one frame, there's
  nothing more to spread.
- **The main thread's share grows with pixels, not decimate.** 6.0 ms at dec 3, 6.4 ms at dec 2,
  7.8 ms at dec 1 (800x600). It's 11.8 ms at 1280x800 dec 2, with 2.1× the pixels. Decimate
  shrinks the image only *after* steps 2–3, so those steps cost the same at every decimate.
- **Nothing outside PhotonVision is the limit:** no thermal throttling (max 65 °C, clock never
  capped), radio under 1 Mbit/s, and the Left Pi's 100 Mbit/s link performed the same as the
  Right Pi's 1000 Mbit/s.
- **Low Latency Mode and streams are settled.** Low Latency Mode on halves results/s whenever a
  frame takes longer than the camera's frame gap (R2 vs R3). The dashboard streams and drawing
  run on their own thread (11-10, B5).

One measurement wrinkle: two `VisionRunner` threads keep running at 1 detector thread (~7.5% each
at 41/s in B4, ~19% at 101/s in R5). They're probably the stream thread and one other per-frame
helper, not detector workers, so "detector CPU" above slightly overstates the detector (by up to
~4 ms per frame). The conclusions don't change.

### From the source code

- One `VisionRunner` thread per camera, looping grab → process → publish (`VisionRunner.update()`).
  There is no queue of frames and no second processing thread per camera.
- cscore decodes MJPEG in the thread that asks for the frame (`RawSinkImpl::GrabFrameImpl` calls
  `Frame::GetImage`, which calls `cv::imdecode`). For PhotonVision that's the `VisionRunner`
  thread.
- PhotonVision asks cscore for **BGR** (`PixelFormat.kBGR` in `USBFrameProvider`), then converts
  to grey itself. cscore can decode MJPEG straight to grey (`Frame::ConvertMJPEGToGray`), but
  PhotonVision doesn't ask for that. The colour image also feeds the input stream. See "A grey
  camera in a colour pipeline" below.
- No hardware JPEG decoding: `cv::imdecode` runs on the CPU. The RK3588's video unit can decode
  JPEG (Rockchip MPP; Radxa's docs list 1080p at 280 frames/s), but PhotonVision doesn't use it.

### A grey camera in a colour pipeline

The OV9281 is a mono (grey-only) global-shutter sensor. The pipeline still turns its image into
colour and back, because PhotonVision and cscore are written for colour cameras:

1. **On the camera:** the camera's USB chip compresses each frame as a JPEG before sending it. A
   grey image can be stored as a 1-channel JPEG, or as a normal 3-channel colour JPEG whose colour
   channels are all neutral. **We haven't checked which the OV9281 sends.** That needs one frame
   captured straight from the camera, with PhotonVision stopped (bench test 1).
2. **Decode, on the main thread:** cscore calls OpenCV `imdecode(IMREAD_COLOR)`. That outputs a
   3-channel colour image (BGR, 3 bytes per pixel), whatever the JPEG held. If the JPEG has colour
   channels, it decodes them too and converts every pixel from YCbCr to BGR. If the JPEG is
   1-channel, it copies the grey value into all 3 channels.
3. **Colour → grey, on the main thread:** PhotonVision's `GrayscalePipe` (`cvtColor`) reads the 3
   channels back and computes one grey value per pixel. That just recovers what the sensor
   measured in the first place.
4. **The colour copy is kept for the input stream**, which re-compresses it as a colour JPEG. Our
   recorder saves frames from that stream. Their colour channels are neutral in 99% of pixels
   (checked on three 11-10 frames); the rest is PhotonVision's crosshair overlay. So the picture
   is grey all the way through, just carried in a colour container.

**What it costs:** steps 2–3 do about 3× the memory traffic of a grey-only path. If the camera's
JPEG has colour channels, there's also the colour decode and conversion work. All of it scales
with pixel count, which matches the main thread's time growing with resolution, not decimate.
**How many milliseconds it is hasn't been measured.** Decoding straight to grey with libjpeg is
typically noticeably cheaper than decoding to colour, but that's a general expectation, not our
number. That's option O2, and bench test 1 measures it on the Pi.

**Can we turn it off?** Not in stock PhotonVision; there's no setting for it. cscore already has a
grey decode path (`Frame::ConvertMJPEGToGray`, `imdecode(IMREAD_GRAYSCALE)`). The change would be
in PhotonVision's `USBFrameProvider`: ask for `kGray` instead of `kBGR` when the pipeline only
needs grey, and skip the `GrayscalePipe`. The input stream would then be grey, which is all a mono
camera has anyway. Two other users of the colour image need checking first: colour pipelines,
which need real colour but don't apply to a mono camera, and the ML-assisted detector (O6), which
runs its model on the colour frame.

### What other systems do

- **6328 Northstar:** a capture loop and a separate AprilTag worker thread, connected by a
  one-frame queue. If the worker is busy, the new frame is dropped
  ([`northstar/__init__.py`](https://github.com/Mechanical-Advantage/RobotCode2025Public/blob/main/northstar/__init__.py)).
  So capture overlaps detection, but there's still one frame in detection at a time. They run it
  on much faster single-core hardware rather than spreading the work out.
- **ML-assisted AprilTag detection (community fork, aimed at PhotonVision 2027):** a neural
  network on the Pi's NPU finds where the tags are, then the normal AprilTag detector runs only on
  those regions, at decimate 1. Details under "The ML-assisted detector" below.
- **GPU detectors:** a team reported a CUDA AprilTag detector on a Jetson Orin Nano at ~36 fps
  per camera with two 1280x800 OV9281s, against 18 fps for the CPU pipeline on the same board
  ([Chief Delphi](https://www.chiefdelphi.com/t/cuda-apriltag-detection-with-photonvision/483803)).
- **Limelight:** the Limelight 3G lists a 1280x800 @120 camera mode. The Limelight 4 uses a
  Raspberry Pi CM5 and offers a Hailo-8 accelerator for AprilTags ("2–3× faster" by a third-party
  account). We found no published frame rates for either at full resolution.
- **PhotonVision's docs** suggest 1280x800, decimate 2 for an Orange Pi 5 with an OV9281, and
  quote AprilTag streams "at 1280x800 (30fps)". Our 63/s already beats that, so we aren't doing
  anything unusually wrong.

### The ML-assisted detector

From the [Chief Delphi thread](https://www.chiefdelphi.com/t/apriltag-cv-dataset-photonvision-experimental-apriltag-acceleration/512444)
and the fork's code ([`DoctorFogarty/photonvision`, branch `apriltag-ml-experimental`](https://github.com/DoctorFogarty/photonvision/tree/apriltag-ml-experimental),
last commit 2026-02-20):

- **Who:** a community member's fork, not the PhotonVision team. In August 2026, people replying
  in the thread said it's expected in PhotonVision for 2027, together with optimizations from the
  Rubik Pi group. No release date.
- **What it does, per frame** (`AprilTagPipeline.processMLHybrid`):
  1. A YOLOv11 model runs on the **colour** frame through PhotonVision's existing
     object-detection support (the NPU on an RK3588 or a Rubik Pi's QCS6490). It returns boxes
     around likely tags.
  2. Each box is padded, cropped out of the **full-resolution grey** image, and given to the
     normal AprilTag detector at **decimate 1**.
  3. If the model finds nothing and fallback is on, the normal full-frame detector runs as well.
  4. The pose step afterwards is unchanged, so **it works in 3D mode** too.
- **What it changes:** steps 4–5 (the detector) run only on small patches of the image instead of
  the whole frame. That's why decimate 1 becomes affordable, and decimate 1 is what sees small,
  far-away tags.
- **What it doesn't change:**
  - Steps 2–3 (decode, grey) still run on the whole frame on the main thread, and the model
    needs the colour image.
  - The model call runs on the main thread too, which waits for the NPU's answer.
  - There's still **one frame in flight per camera**.

  So this is a cheaper frame, not more frames at once, as you guessed. Whether the frame comes
  out faster depends on whether the NPU call plus the patch detection beats the full-frame
  detector. Nobody has published numbers with it on yet. The thread's baseline without it shows
  our pattern: 1600x1200 gave 18 / 24 / 34 fps at decimate 1 / 2 / 3.
- **Risks:** a tag the model misses isn't detected at all (unless fallback is on, which costs
  both). Far tags are exactly where a model is least sure, and the dataset is one person's
  practice-field footage. The model also needs retraining or checking each game year.

### 2D vs 3D mode, and running more than one pipeline

**What the two modes do** ([`AprilTagPipeline.process`](https://github.com/PhotonVision/photonvision/blob/v2026.1.1/photon-core/src/main/java/org/photonvision/vision/pipeline/AprilTagPipeline.java)):

- **Detection is identical.** Decode, grey, and the AprilTag detector (steps 1–5) run the same
  way in both modes. Every result reports each tag's ID, corners, yaw, pitch, area and skew in
  both modes.
- **3D mode adds only step 6**, the pose solve (`solvePNPEnabled`). Our settings, from the log:
  multi-tag on, "single-tag always" on, 100 iterations.
  - **Multi-tag PnP:** one OpenCV solve over the corners of every visible tag, giving the camera's
    field pose.
  - **Single-tag pose:** WPILib's `AprilTagPoseEstimator`, 100 iterations, once per tag. Because
    "always" is on, it runs even for tags the multi-tag solve already used.
  - **The cost of these hasn't been measured.** It's small, fixed math on 4 corners per tag, not
    work on pixels. It doesn't grow with resolution or decimate. Our own data puts an upper bound
    on it: at 800x600 dec 3, the main thread's whole share of a frame was 6.0 ms, including the
    decode, grey conversion and the detector's serial steps. Bench test 1 will measure it.
- **So 2D mode wouldn't help much.** What makes 1280x800 or decimate 1 slow is steps 2–5, which
  2D mode still does. The most it can save is step 6, likely well under a millisecond per frame.
  If we want to trim step 6 in 3D mode, turning off "single-tag always" (`doSingleTargetAlways`)
  and lowering the iteration count are the levers. That's only worth doing if bench test 1 shows
  it's more than about 0.5 ms.
- **2D data is already in every 3D result.** Aiming or lining up on a tag can use the target's
  yaw and pitch (`PhotonTrackedTarget.getYaw()` / `getPitch()`) from the 3D pipeline we already
  run. We don't need a separate 2D pipeline for that.

**More than one pipeline:**

- **A camera runs one pipeline at a time.** Robot code can switch it
  (`PhotonCamera.setPipelineIndex`), and a few frames are lost around the switch. Two pipelines
  can't run on the same camera at once.
- **Switching gains nothing at our current setting.** 800x600 @100 dec 2 is already limited by
  the camera's 100 frames/s, not by processing. A lighter pipeline can't produce more frames than
  the camera sends.
- **It could matter at heavier settings**, if the range experiment says we want them. For example,
  a "far" pipeline at 1280x800 dec 1 for shooting from range, and a "near" one at dec 2 or 3 for
  lining up close. Changing decimate between pipelines is cheap. Changing resolution switches the
  camera's video mode, which interrupts the stream for longer.
- **A second camera is the other way to get "both at once".** Each camera has its own pipeline and
  its own thread (option O1).

## What could raise results/s at higher resolution

Roughly from least to most work. "Gain" is a rough guess unless marked as measured.

| # | Option | What it does | Expected gain | Cost / risk |
|---|---|---|---|---|
| O1 | **Second camera per Pi** | A second `VisionRunner` on the idle fast-core capacity (~1.5–2 cores free) | More results per robot, not per camera | Hardware, mounting, calibration. Works in stock PhotonVision |
| O2 | **Decode straight to grey** (the OV9281 is mono) | Skip the colour decode and the colour → grey step; see "A grey camera in a colour pipeline" | Part of steps 2–3: unmeasured, maybe 1–3 ms at 1280x800 | PhotonVision change (input stream would be grey; fine for a mono camera) |
| O3 | **Decode on a separate thread** (pipelining) | Step 2 for frame N+1 overlaps steps 3–7 for frame N | Up to all of step 2's time | PhotonVision change, moderate |
| O4 | **Several frames in flight** | Frame N on core A, N+1 on core B | Large. Ceiling ~160/s at 800x600 dec 1 from B4's 24.4 ms per single-thread frame | Big PhotonVision change (or our own vision software). Results can arrive out of order. `Vision.java` velocity filter needs a change |
| O5 | **Hardware JPEG decode** (RK3588 MPP) | Takes step 2 off the CPU entirely | Up to all of step 2's time | Native code, Rockchip-specific; nobody in FRC seems to do it |
| O6 | **ML-assisted detector** (community fork, aimed at PhotonVision 2027) | NPU finds tags; the detector runs only on those patches, at decimate 1 | Unknown; makes decimate 1 cheaper, but still one frame in flight and steps 2–3 unchanged | Missed tags; model per game year. Test the fork on a spare Pi, or wait for the release |
| O8 | **Per-situation pipelines** (switch from robot code) | Heavier pipeline only when range matters | Only at heavier settings; none at 800x600 dec 2 (camera-paced) | Frames lost at each switch; resolution switches are slower than decimate switches |
| O7 | **Own vision software** (Northstar-style) | Full control of the steps above | Any of O2–O5 | Large build and maintenance burden, and we lose PhotonVision's UI, calibration and PhotonLib |

O2–O5 are changes inside PhotonVision. They'd be best done as an upstream contribution, so we
don't maintain a fork. Whether any is worth it depends on the range experiment, and on bench
tests 1–2 below, which put numbers on steps 2–3 and on frames in flight.

## Next steps

1. **Range experiment** ([plan](../experiments/vision/2026-11-03-pv-range/README.md)). Does
   1280x800 or decimate 1 see tags meaningfully farther or more accurately than 800x600 dec 2? If
   not, stop here: the current setting is the right one.
2. **Bench test 1: where the main thread's time goes.** No robot needed. On a Pi, record a few
   hundred raw MJPEG frames straight from the OV9281 (PhotonVision stopped) at 800x600 and
   1280x800 (`ffmpeg -f v4l2 -input_format mjpeg`). That also shows whether the camera's JPEG is
   1-channel or 3-channel. Then time each step with the same libraries PhotonVision uses: OpenCV
   decode to colour, decode straight to grey, colour → grey, and WPILib's `AprilTagDetector` at
   decimate 1/2/3 with 1 and 4 threads. Add the 3D pose step (multi-tag `solvePnP`, and
   `AprilTagPoseEstimator` at 100 and 40 iterations) on the detected tags; that's the whole
   difference between 2D and 3D mode. This turns answer 5 from an inference into numbers, and
   sizes O2, O3 and O5.
3. **Bench test 2: frames in flight.** On the same recorded frames, run 1, 2, 3 and 4 worker
   processes, each doing decode + detect on its own frames (1 detector thread each), pinned to
   the fast cores. Measure frames/s and per-frame time. This tests O4's ~160/s ceiling directly.
   If it holds near the camera rate at 1280x800, O4 is real. If memory bandwidth or heat caps it
   well below, it isn't.
4. **O1, second camera**, if the range experiment says we want more results rather than finer
   ones.
5. **Optional: try the ML-assisted fork (O6) on a spare Pi** with recorded frames, if the range
   experiment says decimate 1 is worth having. Measure time per frame and tags missed against the
   normal detector.

## What we still don't know

- How the main thread's ~6 / 12 ms splits between decode, grey conversion and the detector's
  serial steps (bench test 1).
- Whether 4 frames in flight scale anywhere near 4× on the RK3588S, or whether shared memory
  bandwidth or heat limits them first (bench test 2).
- Whether higher resolution is worth anything on the field (range experiment).
- What PhotonVision 2027 will change. Re-check this ADR against its release notes.
