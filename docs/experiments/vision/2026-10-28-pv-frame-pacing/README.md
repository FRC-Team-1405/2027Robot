---
id: VIS-2026-10-28-pv-frame-pacing
title: PhotonVision frame pacing — Low Latency Mode, detector threads, streams
area: vision
date: 2026-11-03            # R1–R3 run 11-03, R5/R6/R12/R13 run 11-07; folder keeps the planned date
status: analyzed            # planned | running | analyzed | decided
decision: 800x600 @100, decimate 2, Low Latency Mode off (both Pis). Pushing further continues in 2026-11-10-pv-frame-budget
robot_code: 11-03 beta @338bcfa; 11-07 see the runs table (L-runs on 338bcfa, R-runs on beta @d0b8b2c + local edits)
logs: logs/offseason/11-3/, logs/offseason/11-7/
analysis: analyze.py → results.json
raw_notes: notes.md (this folder), notes/11-7/myNotes.md
---

# PhotonVision frame pacing: Low Latency Mode, detector threads, streams

## In short

On 10-27, any camera setting heavier than our baseline cut vision results to **exactly half** the
camera's frame rate (about 50 per second instead of 100). We suspected one PhotonVision setting,
**Low Latency Mode**, which is on by default.

**R1–R3 (11-03): confirmed.** With Low Latency Mode off, decimate 2 runs at the full
101 results/s with no dropped frames, where it got 54/s with the mode on. Latency stayed about the
same and pose accuracy didn't change.

**11-07: decimate 2 at 800x600 @100 is the most the Pis can do at full rate.** It held in four more
runs (R5). Everything heavier now slows down smoothly instead of halving, but still falls short:

| Setting (all Low Latency off) | Results/s (of camera fps) | Latency at the roboRIO | Verdict |
|---|---|---|---|
| **800x600 @100, dec 2** (R3, R5 ×4) | **101 (100%)** | **23–25 ms** | **Best so far, use this** |
| 800x600 @120, dec 2 (R12 ×3) | 112–113 (94%) | 27–28 ms | 11% more results, but 1 gap in 7 is doubled and each result is ~4 ms older. No gain |
| 800x600 @120, dec 1 (R6) | 67–68 (56%) | 36 ms | Too slow. Better than 10-27 (50/s with the mode on) |
| 1280x800 @100, dec 2 (R13) | 63 (63%) | 39 ms | Too slow. Better than 10-27 (49/s) |

**Why heavier settings can't keep up, even with the Pi's CPU only ~30% busy:** PhotonVision
handles one frame per camera at a time, and most of each frame runs on a single thread. See
"Where a frame's time goes" below. Whether the time per frame can be shortened is its own
experiment, planned for 11-10: [PhotonVision frame budget](../2026-11-10-pv-frame-budget/README.md).

## What we're testing

1. **Is Low Latency Mode the cause of the half-rate cliff?** Turn it off at decimate 2 and see
   whether results/s goes from ~50 back to ~100. *(R1–R3, done)*
2. **How much detail can we afford now?** With the cliff gone, try decimate 1, the 120 fps mode,
   and 1280x800, and see which still keep up with the camera. *(R4, R6, R12–R14)*
3. **Do other PhotonVision settings help?** Moved to the
   [frame-budget experiment](../2026-11-10-pv-frame-budget/README.md), which is built around the per-frame numbers found here.

A setting **passes** if all four hold:

| Check | Pass if | Why |
|---|---|---|
| Results/s | ≥ 90% of the camera's fps | The point of the experiment |
| Dropped frames | ≤ 3% | A dropped frame is a pose update we never get |
| Cross-camera agreement | median ≤ 5 cm (as on 10-27) | Proves accuracy didn't get worse |
| Latency at the roboRIO | within +10 ms of 800x600@120 dec 3 (10-27: 22.7 ms median) | Fresher data is the point; don't trade it away |

### Words used here

- **Results/s**: pose estimates per second that reach the robot, per camera. The camera sends
  100 frames/s (or 120), so 100 is the most we can get.
- **Decimate**: how much PhotonVision shrinks the image before searching for tags. Decimate 3 is
  fastest but sees small (far) tags worst; decimate 1 looks at the full image.
- **Low Latency Mode** (PhotonVision Input tab): when on, PhotonVision always waits for the *next*
  camera frame. If processing a frame takes even slightly longer than the gap between frames,
  every other frame is thrown away. That is the half-rate cliff. When off, it takes the newest
  frame that has already arrived. Background at the end.
- **Dropped frame**: a gap between results longer than the camera should leave (1.6× the normal
  gap) while a tag is in view.
- **LL**: short for Low Latency Mode in the tables.

## The runs

Every run: 800x600 @100 fps unless stated, recorder on, `CircleFacingTag` auto (about 20 s
enabled), no PhotonVision browser tab open while enabled. **Write each run's settings in the
table before enabling**; PhotonVision settings are not in the robot log.

| Run | What changes | What it checks | Status |
|---|---|---|---|
| R1 | dec 3, LL on (baseline, = 10-27 T1) | That 11-03 matches 10-27 | ✅ 99/s |
| R2 | dec 2, LL on (= 10-27 T2) | The cliff is still there | ✅ 54/s, cliff present |
| R3 | dec 2, **LL off** | **Does the cliff disappear?** | ✅ **101/s, cliff gone** |
| R4 | dec 3, LL off | Does LL off also remove R1's 1.6% dropped frames? | skipped (dec 3 is no longer a candidate) |
| R5 | repeat R3 later in the session | That R3 holds once the Pis are warm | ✅ 11-07, four repeats (the loop-overrun runs L1–L5 used R3's settings): 101/s every time |
| R6 | dec 1, LL off | Can we look at the full image and still keep up? (10-27 T3: 50/s with LL on) | ✅ 11-07, but at **@120** (the camera mode had changed; the log shows it): **67/s**, fails |
| R7–R9 | detector threads | | moved to the [frame-budget experiment](../2026-11-10-pv-frame-budget/README.md) (B2–B4) |
| R10 | stream resolution ¼ | Does a smaller UI/recorder stream free up the Pi? | not planned: streams run on their own thread, not the bottleneck one |
| R11 | recorder stopped | What the recorder costs | not planned, same reason |
| R12 | 800x600 **@120**, dec 2, LL off | dec 2 fit in 10 ms per frame; does it fit in 8.3 ms? | ✅ 11-07, three runs (by accident: meant as loop-overrun runs, camera was at @120): **112/s**, fails on dropped frames |
| R13 | **1280x800** @100, dec 2, LL off | Is the higher resolution usable now? | ✅ 11-07: **63/s**, fails |
| R14 | 1280x800 **@120**, best dec, LL off | The camera offers it (`v4l2-ctl`, notes.md) | dropped: 1280x800 can't keep up at @100 |

R4–R14 replace the original R4–R12. The original plan repeated R2/R3 twice more (A/B/A/B). R3's
effect (54 → 101/s) is about 50 times the run-to-run drift, so one repeat (R5) is enough.

Nothing left to run here. The next robot session's steps are in
[notes/11-10/notes.md](../../../../notes/11-10/notes.md).

## Results, 11-07 (R5, R12, R6, R13)

From 11-07 on, the logs record each Pi's PhotonVision settings and real camera mode, and the
table below uses them. The L-runs (R5) ran before the Pis were re-bootstrapped, so their settings
are inferred: 100.9 fps camera, PhotonVision's processing time 16.7 ms (the dec 2 value), and 100%
one-frame gaps (Low Latency off).

| | R5 (×4) 800x600 @100, dec 2 | R12 (×3) 800x600 **@120**, dec 2 | R6 800x600 @120, **dec 1** | R13 **1280x800** @100, dec 2 |
|---|---|---|---|---|
| **Results/s** | **100.9–101.1** | 111.8–113.4 (94%) | 67.0 / 68.5 (56%) | 62.7 / 62.9 (63%) |
| **Dropped frames** (gap ≥ 1.6 frames) | 0–0.15% | **6.2–7.4%** | (most gaps are 2 frames) | (most gaps are 2 frames) |
| Gaps of 1 frame / 2 frames | 100% / 0% | 85–87% / 5–7% | 18–21% / 66–69% | 39% / 56% |
| Longest gap | 12–20 ms | 20 ms | 28–32 ms | 32 ms |
| **Latency at the roboRIO**, median / p95 | 23.0–25.0 / 28.6–31.5 ms | 27.0–27.7 / 33.8–36.0 ms | 36.5 / 45.3 ms | 38.7 / 48.9 ms |
| PhotonVision processing time, median | 16.1–16.8 ms | 19.8–20.2 ms | 26.5 ms | 28.6 ms |
| **Cross-camera agreement**, median | 4.8–5.1 cm | 4.7–5.0 cm | 4.7 cm | 4.3 cm |
| Pi CPU used by PhotonVision (of 800%) | 194–206% | 228–232% | 252–254% | 232–234% |
| Busiest PhotonVision thread (of one core) | 62–66% | 72–74% | 54% | 74% |
| Pi max temperature | 58 °C | 62 °C | 65 °C | 62 °C |
| Radio bandwidth, median | 0.09–0.38 Mbit/s | 0.09–0.46 | 0.32 | 0.37 |

One R5 run (L3) stood still in teleop, so its cross-camera agreement (0.7 cm) is left out of that
row. R6 has a 2.6 s enable before the real run (auto enabled without a routine); only the 20.6 s
run counts.

### Verdicts, 11-07

| Run | Results/s ≥ 90% | Dropped ≤ 3% | Agreement ≤ 5 cm | Latency ≤ 32.7 ms | Verdict |
|---|---|---|---|---|---|
| R5 | ✅ | ✅ | ✅ (one run 5.05) | ✅ | **Same as R3.** It holds with warm Pis (56–58 °C) and over a whole afternoon |
| R12 | ✅ 94% | ❌ 6–7% | ✅ | ✅ +4.5 ms | **Fails.** 11% more results than R5, but each is about 4 ms older and the gaps are uneven. Not worth it |
| R6 | ❌ 56% | – | ✅ | ❌ +14 ms | **Fails.** One dec 1 frame takes about 15 ms, so ~67/s at any camera rate |
| R13 | ❌ 63% | – | ✅ (best, 4.3 cm) | ❌ +16 ms | **Fails.** About 16 ms per frame |

### What we learned, 11-07

- **Without Low Latency Mode, a heavy setting costs results in proportion instead of halving
  them.** Dec 1 went from 50/s (10-27, mode on) to 67/s; 1280x800 dec 2 from 49/s to 63/s. That
  is the frame time showing through directly: about 15 ms per frame at dec 1 and 16 ms at
  1280x800.
- **800x600 @100 dec 2 has about 1–2 ms to spare; @120 doesn't.** At @120 a frame arrives every
  8.3 ms. PhotonVision's own processing time went up from 16.7 to 20.2 ms (frames wait for the
  previous one), and 1 gap in 7 was two frames.
- **The Pis have CPU to spare in every setting** (at most 254% of 800%, 65 °C, never throttled).
  The limit is the single per-camera loop, not total CPU. That's why detector threads (R7–R9)
  are the one lever left for dec 1.
- **Higher resolution was slightly more consistent between the cameras** (4.3 vs 4.8 cm). That's a
  hint that it helps accuracy, small enough to be noise. The range experiment measures it properly.
- **The new settings logging paid off on its first day.** It showed the camera mode had changed to
  @120 between 18:22 and 19:03, which the notes don't mention. Without it, R6 and the L4'/L2'
  runs would have been read as @100.

### Where a frame's time goes

The Pi publisher logs PhotonVision's 8 busiest threads (name, % of a core, which core) about once
a second. Until 11-07 our log parser dropped the names (`string[]`); `analyze.py` now uses them.

- **PhotonVision ran only on the 4 fast cores** (cores 4–7, 50–65% busy). The 4 slow cores sat at
  3–6%. So the "~30% CPU" is an average over cores PhotonVision doesn't use.
- **It works on one frame per camera at a time.** The main `VisionRunner` thread decodes the
  MJPEG, converts to grey, runs the detector's serial parts, solves the pose, draws and
  publishes. Only the detector's middle phases run on the worker threads (`threads` = 8). A new
  frame isn't started until the last one is published, so **results/s = 1 ÷ time per frame**,
  however many cores are free.
- **Frame time ≈ main thread + detector work spread over 4 fast cores**, within 1–2 ms in every run:

| Setting | Frame time (1 ÷ results/s) | Main thread, alone | Detector workers (CPU ÷ 4) | Sum |
|---|---|---|---|---|
| R1 dec 3, @100 | 10.1 ms (camera-paced) | 6.0 ms | 1.4 ms | 7.4 ms |
| R3/R5 dec 2, @100 | 9.9 ms (camera-paced) | 6.4 ms | 1.8 ms | 8.2 ms |
| R2 dec 2, @100, **LL on** | 18.6 ms | 6.5 ms | 1.7 ms | 8.2 ms: the other 10 ms is waiting for the next frame |
| R12 dec 2, @120 | 8.9 ms | 6.5 ms | 1.8 ms | 8.3 ms, just over the 8.3 ms frame gap |
| R6 dec 1, @120 | 14.9 ms | 8.1 ms | 4.8 ms | 13.0 ms |
| R13 1280x800 dec 2 | 15.9 ms | **11.8 ms** | 3.1 ms | 14.9 ms |

What that means:

- **The main thread costs ~6 ms per 800x600 frame whatever the decimate** (6.0 at dec 3, 6.4 at
  dec 2). That's work on every pixel: decode, grey conversion, drawing. It's why 1280x800 costs
  ~12 ms before detection does much, and why idle cores can't help.
- **Dec 1 at 100/s needs a 10 ms frame.** The main thread alone takes 8 ms, so the detector would
  have to finish in under 2 ms; it takes about 5. More cores don't help; fewer detector threads
  fighting over 4 fast cores (R7–R8) and less work on the main thread (R15) might.
- **The spare fast-core capacity (~1.5–2 cores) is better spent on a second camera** than on one
  camera's frame rate: each camera gets its own main thread. That's a separate test.
- These come from once-a-second samples of the top 8 threads, so they're good to about a
  millisecond, not exactly.

## Results, 11-03 (R1–R3)

Numbers from `analyze.py` → `results.json`, Left / Right camera where both are shown.

| | R1 dec 3, LL on | R2 dec 2, LL on | **R3 dec 2, LL off** |
|---|---|---|---|
| **Results/s** | 99.4 / 99.3 | 53.9 / 55.2 | **101.0 / 101.0** |
| **Dropped frames** | 1.6% / 1.7% | 0 (every other frame skipped on purpose) | **0 / 0** |
| Gaps of 1 frame / 2 frames | 98% / 2% | 15% / 85% | **100% / 0%** |
| Longest gap | 20 ms | 20 ms | **12 ms** |
| **Latency at the roboRIO**, median / p95 | 22.6 / 29.2 ms | 28.0 / 37.2 ms | 24.2 / 30.1 ms |
| PhotonVision processing time, median | 15.2 ms | 16.6 ms | 16.8 ms |
| **Cross-camera agreement**, median | 4.6 cm | 4.6 cm | 4.5 cm |
| Pi CPU used by PhotonVision (of 800%) | 164% | 110% | 206% |
| Busiest PhotonVision thread (of one core) | 60% | 34% | 66% |
| Pi max temperature | 52 °C | 47 °C | 56 °C |
| Radio bandwidth, median / max | 0.35 / 0.38 Mbit/s | 0.33 / 0.49 | 0.38 / 0.63 |

### Verdicts

| Run | Compared with | Verdict | Why |
|---|---|---|---|
| R1 | 10-27 T1 | Same | 99/s vs 98/s; 11-03 is comparable to 10-27 |
| R2 | 10-27 T2 | Same | 54/s vs 53/s; the cliff is real and repeatable |
| R3 | R2 | **Gain** | 54 → 101 results/s; every gap went from 2 frames to 1 |
| R3 | R1 | **Gain** | Same results/s at a finer decimate (better range), and R1's 1.6% dropped frames are gone. Latency +1.6 ms median, inside the limit |

**R3 passes all four checks.** R2 fails on results/s.

### What we learned

- **Low Latency Mode was the whole cliff.** At decimate 2, a frame takes a little *less* than
  the gap between camera frames on average, but not always. With the mode on, any frame that
  arrived while the previous one was still being processed was thrown away, and at decimate 2
  that was most of them. With the mode off, nothing is thrown away.
- **Turning Low Latency Mode off lowered latency** compared with R2 (28.0 → 24.2 ms median at the
  roboRIO), because results arrive twice as often. The latency the mode is meant to save (at
  most one frame) is smaller than the wait it causes.
- **It costs Pi CPU, and there's room for it.** PhotonVision went from 164% to 206% of one core
  (out of 800%), 4 °C warmer, no throttling. The busiest thread is at 66% of a core, so there's
  room to try decimate 1.
- **The network isn't a concern.** Twice the results/s didn't measurably change radio bandwidth
  (under 0.7 Mbit/s; the field limit is 7). Each Pi sent about 0.9 Mbit/s.
- **The camera's frame gaps alternate 8 ms / 12 ms** (10 ms on average). Because of that,
  `frame_ms_median` reads 8.0 ms at 100 fps. The dropped-frame check (a gap ≥ 1.6 × the median,
  12.9 ms) still works, but with little margin; use the 1-frame / 2-frame row instead.
- **The 1280x800 mode also does 120 fps** on both cameras (`v4l2-ctl` output in notes.md), so the
  slow 1280x800 runs on 10-27 were PhotonVision's limit, not the camera's.
- **The roboRIO missed its 20 ms loop in 5–12% of cycles** (52 / 52 / 15 overruns per run), and it
  didn't get worse when vision results doubled. That's not caused by this experiment; it gets its
  own experiment ([roboRIO loop overruns](../../roborio/2026-11-03-loop-overruns/README.md)).

### How we know R3 was Low Latency off

The notes name R1 and R2 but not R3's change. Two things in the data settle it:

- PhotonVision's own processing time (16.8 ms) is the decimate 2 value. Decimate 3 is 15.2 ms.
- The gaps between results went from 85% two-frame gaps to 100% one-frame gaps. Turning off Low
  Latency Mode would do exactly that; no other setting we've changed does.

## Next experiment

**Frame budget** ([PhotonVision frame budget](../2026-11-10-pv-frame-budget/README.md), 11-10): can fewer detector threads or
turning off output drawing shorten the time per frame enough for decimate 1 or @120?

Then **range** ([PhotonVision range vs decimate and resolution](../2026-11-03-pv-range/README.md)):
now that decimate 2 (and maybe 1) runs at full rate, does the finer image actually see tags
further away, and how accurate is it there? Higher resolution only earns its CPU at range.

ArUco detector (L6 below) stays parked unless the AprilTag detector can't keep up.

## Reproduce

```bash
python docs/experiments/vision/2026-10-28-pv-frame-pacing/analyze.py
```

Reads the WPILog Janitor-trimmed logs in `logs/offseason/11-3/` and `11-7/` and writes
`results.json`. Uses the same metric code as the 10-27 experiment, plus the gap histogram, the
network numbers and (from 11-07) the PhotonVision settings read from the log.

| Run | Log |
|---|---|
| R1 | `11-3/akit_26-11-03_23-38-42` |
| R2 | `11-3/akit_26-11-03_23-58-01` |
| R3 | `11-3/akit_26-11-04_00-18-32` |
| R5a–d | `11-7/akit_26-11-07_18-04-56`, `18-13-22`, `18-16-38`, `18-22-17` (loop-overrun L1, L2, L3, L5) |
| R12a–c | `11-7/akit_26-11-07_19-03-35`, `19-10-49`, `19-13-10` (loop-overrun L4', L4'', L2') |
| R6 | `11-7/akit_26-11-07_19-19-16` |
| R13 | `11-7/akit_26-11-07_19-23-31` |

---

## Background

Details behind the plan. You don't need these to follow the runs or results.

<details>
<summary><b>What the PhotonVision source says (v2026.1.1, the version on both Pis)</b></summary>

**1. The cliff comes from "Low Latency Mode" (`blockForFrames`), which is on by default.**
Each camera has one processing thread
([`VisionRunner.update()`](https://github.com/PhotonVision/photonvision/blob/v2026.1.1/photon-core/src/main/java/org/photonvision/vision/processes/VisionRunner.java)).
It loops: grab a frame, run the pipeline, publish. How it grabs depends on `blockForFrames`
([`USBFrameProvider`](https://github.com/PhotonVision/photonvision/blob/v2026.1.1/photon-core/src/main/java/org/photonvision/vision/frame/provider/USBFrameProvider.java)):

- **On** (`CVPipelineSettings.blockForFrames = true`, the default): `cvSink.grabFrame(mat, 0.25)`.
  cscore blocks until the camera delivers a *new* frame after the call. If one loop takes 10.5 ms
  and the camera sends a frame every 10 ms, the frame that arrived during processing is skipped,
  and the thread waits for the next one. The rate snaps to camera fps ÷ 2, then ÷ 3, and so on.
- **Off**: `CscoreExtras.grabRawSinkFrameTimeoutLastTime(..., lastTime)` returns the first frame
  newer than the last one processed. A frame that arrived during processing is used right away.
  The rate becomes 1 ÷ (loop time), with no snapping.

The UI shows it as the **Low Latency Mode** switch on the **Input** tab ("When enabled, USB
cameras wait for the next camera frame for lowest latency",
[`InputTab.vue`](https://github.com/PhotonVision/photonvision/blob/v2026.1.1/photon-client/src/components/dashboard/tabs/InputTab.vue)).
It is a per-pipeline setting.

**2. Everything in the loop is serial, so anything in it costs frames.** One frame's loop is the
MJPEG decode (cscore, on the CPU), the colour → grey conversion, AprilTag detection, PnP, and the
NetworkTables and UI publish. For AprilTag pipelines the streams are handed to a separate
`StreamRunnable` thread
([`VisionModule`](https://github.com/PhotonVision/photonvision/blob/v2026.1.1/photon-core/src/main/java/org/photonvision/vision/processes/VisionModule.java)),
so they compete for CPU but don't block the loop. The decode and grey conversion scale with
resolution and are untouched by decimate, which is why 1280x800 costs about 6 ms more per frame
even at decimate 3.

</details>

<details>
<summary><b>Every setting we could change, roughly by expected effect</b></summary>

| # | Lever | Where | Expected effect | Cost / risk |
|---|---|---|---|---|
| L1 | **Low Latency Mode off** | Input tab, per pipeline | Removes the ÷2 cliff. *Confirmed by R3.* | Up to one frame period more latency per frame; in practice total latency went down |
| L2 | **Detector threads** (`threads`, default 4; ours were 8) | AprilTag tab | An outside test on a Pi 5 with an OV9281 ([wifijt/photonvision-tools#1](https://github.com/wifijt/photonvision-tools/pull/1)) found threads=1 *faster* than 4 per camera (14.9 vs 15.6 ms). Best value for us unknown | None |
| L3 | **Streams** (`streamingFrameDivisor`; which streams are shown) | Input tab | The same PR measured +34% fps with both streams off. On 10-27, stopping the recorder cut drops from 4–10% to about 2% | The UI requires at least one stream; the recorder needs the input stream |
| L4 | **Refine edges** (default on) | AprilTag tab | Saves part of the detect time; matters more at decimate 1 | Slightly worse corner accuracy |
| L5 | **Blur / decision margin / pose iterations** | AprilTag tab | Small; mostly change false positives | Leave alone unless L1–L4 aren't enough |
| L6 | **ArUco detector** | Pipeline type | PV docs: about 2× fps, half the latency, less accurate ([detector types](https://docs.photonvision.org/en/latest/docs/apriltag-pipelines/detector-types.html)) | Accuracy loss; separate experiment |
| L7 | **Camera mode fps** | Resolution list | 800x600 and 1280x800 both offer 100 and 120 fps (notes.md). YUYV is 10 fps, unusable | None |

Ruled out by the 10-27 data: CPU frequency or temperature (never capped, max 56 °C) and the Pi's
network link (the cliff was identical on the 1000 Mbit/s Right Pi and the 100 Mbit/s Left Pi).

</details>

<details>
<summary><b>Bandwidth on the field</b></summary>

Not a cause of the cliff, but it matters at competition: R704 caps robot ↔ Driver Station traffic
at 7 Mbit/s through the radio. The logs carry the radio's own measurement (`RadioStatus/Status` →
`networkStatus6.bandwidthUsedMbps`). On 10-27, run T5.1 went over the limit (7.2 median / 8.7 max),
almost certainly from a PhotonVision stream open in a browser. That's why every run needs the
browser tabs closed. On 11-03 all three runs stayed under 0.7 Mbit/s.

Logging added for this experiment:

- Pi: `OrangePi/<Pi>/NetRxMbps`, `NetTxMbps`, `NetRxErrors`, `NetTxErrors`, `NetRxDropped`
  (orangepi-nt-publisher, needs `Bootstrap-OrangePi.ps1`). **Working on 11-03.**
- roboRIO: `RIO/CpuPct`, `RIO/CpuCorePct`, `RIO/MemUsedPct`, `RIO/MemAvailableMB`, `RIO/NetRxMbps`,
  `RIO/NetTxMbps`, `RIO/NetRxErrors`, `RIO/NetRxDropped` (`RioSystemStats`, switch
  `RIO_SYSTEM_STATS_LOGGING`). **On `beta` since 11-04, not deployed yet.**
- Health Check rows for all of the above.

</details>
