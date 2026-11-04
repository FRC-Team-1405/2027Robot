---
id: VIS-2026-10-28-pv-frame-pacing
title: PhotonVision frame pacing — Low Latency Mode, detector threads, streams
area: vision
date: 2026-11-03            # R1–R3 run 11-03; folder keeps the planned date so existing links work
status: running             # planned | running | analyzed | decided
decision: pending           # Low Latency Mode off is a clear win so far; decide after R4+
robot_code: beta @338bcfa (has Pi Net* logging; did NOT have RIO/* logging yet)
logs: logs/offseason/11-3/
analysis: analyze.py → results.json
raw_notes: notes.md (this folder)
---

# PhotonVision frame pacing: Low Latency Mode, detector threads, streams

## In short

On 10-27, any camera setting heavier than our baseline cut vision results to **exactly half** the
camera's frame rate (about 50 per second instead of 100). We suspected one PhotonVision setting,
**Low Latency Mode**, which is on by default.

**So far (R1–R3, 11-03): confirmed.** With Low Latency Mode off, decimate 2 runs at the full
101 results/s with no dropped frames, where it got 54/s with the mode on. Latency stayed about the
same and pose accuracy didn't change. The remaining runs find out how far we can push it: finer
decimate, more or fewer detector threads, and higher resolution.

## What we're testing

1. **Is Low Latency Mode the cause of the half-rate cliff?** Turn it off at decimate 2 and see
   whether results/s goes from ~50 back to ~100. *(R1–R3, done)*
2. **How much detail can we afford now?** With the cliff gone, try decimate 1, the 120 fps mode,
   and 1280x800, and see which still keep up with the camera. *(R4, R6, R12–R14)*
3. **Do other PhotonVision settings help?** The number of detector threads, a smaller stream
   resolution, and whether the vision recorder costs frames. *(R7–R11)*

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
| R4 | dec 3, LL off | Does LL off also remove R1's 1.6% dropped frames? | to do |
| R5 | repeat R3 later in the session | That R3 holds once the Pis are warm | to do |
| R6 | dec 1, LL off | Can we look at the full image and still keep up? (10-27 T3: 50/s with LL on) | to do |
| R7 | dec 1, LL off, threads 4 | Detector threads matter most at dec 1. The Pis were set to 8, not the default 4 | to do |
| R8 | same, threads 2 | | to do |
| R9 | same, threads 1 | An outside test found 1 thread *faster* on a Pi 5 | to do |
| R10 | best so far, stream resolution ¼ | Does a smaller UI/recorder stream free up the Pi? | to do |
| R11 | best so far, recorder stopped | What the recorder costs, separate from R10 | to do |
| R12 | 800x600 **@120**, dec 2, LL off | dec 2 fit in 10 ms per frame; does it fit in 8.3 ms? | to do |
| R13 | **1280x800** @100, dec 2, LL off | Is the higher resolution usable now? | to do |
| R14 | 1280x800 **@120**, best dec, LL off | The camera offers it (`v4l2-ctl`, notes.md) | to do |

R4–R14 replace the original R4–R12. The original plan repeated R2/R3 twice more (A/B/A/B). R3's
effect (54 → 101/s) is about 50 times the run-to-run drift, so one repeat (R5) is enough.

### Before the next session

- [ ] **Deploy robot code from `beta`** (merged 11-04, now has `RioSystemStats` for roboRIO CPU,
  memory and network). R1–R3 have no roboRIO CPU numbers; they don't need to be redone. The
  11-7 checklist is [notes/11-7/notes.md](../../../../notes/11-7/notes.md).
- [ ] Confirm in the PhotonVision UI that R3 was Low Latency off. The notes don't say; the data
  leave no doubt (see "How we know R3 was Low Latency off").
- [ ] Set Low Latency Mode **off** on both Pis. It's per pipeline, so check every pipeline in use.
- [ ] Close every PhotonVision browser tab before enabling.

## Results so far (R1–R3)

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

**Range** ([PhotonVision range vs decimate and resolution](../2026-11-03-pv-range/README.md)):
now that decimate 2 (and maybe 1) runs at full rate, does the finer image actually see tags
further away, and how accurate is it there? Higher resolution only earns its CPU at range.

ArUco detector (L6 below) stays parked unless the AprilTag detector can't keep up.

## Reproduce

```bash
python docs/experiments/vision/2026-10-28-pv-frame-pacing/analyze.py
```

Reads the WPILog Janitor-trimmed logs in `logs/offseason/11-3/` and writes `results.json`. Uses the
same metric code as the 10-27 experiment, plus the gap histogram and the network numbers.

| Run | Log |
|---|---|
| R1 | `akit_26-11-03_23-38-42` |
| R2 | `akit_26-11-03_23-58-01` |
| R3 | `akit_26-11-04_00-18-32` |

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
