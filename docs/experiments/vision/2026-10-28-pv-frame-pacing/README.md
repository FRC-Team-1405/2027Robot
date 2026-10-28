---
id: VIS-2026-10-28-pv-frame-pacing
title: PhotonVision frame pacing — Low Latency Mode, detector threads, streams
area: vision
date: 2026-10-28            # planned; rename the folder to the day it actually runs
status: planned             # planned | running | analyzed | decided
decision: pending
robot_code: beta (with RIO/* and Pi Net* logging, see below)
logs: logs/offseason/<run date>/
analysis: reuse ../2026-10-27-pv-throughput/analyze.py (edit RUNS)
raw_notes: notes/<run date>/notes.md
---

# PhotonVision frame pacing: Low Latency Mode, detector threads, streams

## Question

On 10-27, every setting heavier than 800x600 / decimate 3 dropped to exactly half the camera
rate (about 50 results/s; frame intervals almost all 20 ms) while Pi CPU went *down*
([10-27 write-up](../2026-10-27-pv-throughput/README.md)). Is that half-rate cliff a PhotonVision
setting we can change, and how many results/s can we get at decimate 2, decimate 1 or 1280x800
once it is changed?

## What the PhotonVision source says (v2026.1.1, the version on both Pis)

**1. The cliff comes from "Low Latency Mode" (`blockForFrames`), which is on by default.**
Each camera has one processing thread
([`VisionRunner.update()`](https://github.com/PhotonVision/photonvision/blob/v2026.1.1/photon-core/src/main/java/org/photonvision/vision/processes/VisionRunner.java)).
It loops: grab a frame, run the pipeline, publish. How it grabs depends on `blockForFrames`
([`USBFrameProvider`](https://github.com/PhotonVision/photonvision/blob/v2026.1.1/photon-core/src/main/java/org/photonvision/vision/frame/provider/USBFrameProvider.java)):

- **On** (`CVPipelineSettings.blockForFrames = true`, the default): `cvSink.grabFrame(mat, 0.25)`.
  cscore blocks until the camera delivers a *new* frame after the call. If one loop takes 10.5 ms
  and the camera sends a frame every 10 ms, the frame that arrived during processing is skipped,
  and the thread waits for the next one. The rate snaps to camera fps ÷ 2, then ÷ 3, and so on.
  This matches 10-27 exactly: T2–T5 all ran at 48–54 fps with 20 ms intervals.
- **Off**: `CscoreExtras.grabRawSinkFrameTimeoutLastTime(..., lastTime)` returns the first frame
  newer than the last one processed. A frame that arrived during processing is used right away.
  The rate becomes 1 ÷ (loop time), with no snapping. The trade is a few ms more latency, because
  the frame waits while the previous one is processed.

The UI exposes it as the **Low Latency Mode** switch on the **Input** tab. Its tooltip reads "When
enabled, USB cameras wait for the next camera frame for lowest latency"
([`InputTab.vue`](https://github.com/PhotonVision/photonvision/blob/v2026.1.1/photon-client/src/components/dashboard/tabs/InputTab.vue)).
It is a per-pipeline setting.

What to expect, based on the 10-27 data: at 800x600 / 100 fps, decimate 3 just fits in the 10 ms
budget, and decimate 2 just misses it (PV time rose only 1.4 ms, from 15.2 to 16.6). With Low
Latency Mode off, decimate 2 should land near 85–95 fps rather than 53. Decimate 1 and 1280x800
should land near 55–75 fps rather than 50. These are estimates; the test measures them.

**2. Everything in the loop is serial, so anything in it costs frames.** One frame's loop is the
MJPEG decode (cscore, on the CPU), the colour → grey conversion, AprilTag detection, PnP, and the
NetworkTables and UI publish. For AprilTag pipelines the streams are handed to a separate
`StreamRunnable` thread
([`VisionModule`](https://github.com/PhotonVision/photonvision/blob/v2026.1.1/photon-core/src/main/java/org/photonvision/vision/processes/VisionModule.java)),
so they compete for CPU but don't block the loop. The decode and grey conversion scale with
resolution and are untouched by decimate. That is why 1280x800 costs about 6 ms more per frame
even at decimate 3.

**3. Levers, roughly by expected effect.**

| # | Lever | Where | Expected effect | Cost / risk |
|---|---|---|---|---|
| L1 | **Low Latency Mode off** | Input tab, per pipeline | Removes the ÷2 cliff. Rate becomes 1/loop time. | +up to one frame period (≤10 ms) of latency. Results stay correctly timestamped, since the timestamp is the capture time. |
| L2 | **Detector threads** (`threads`, default 4) | AprilTag tab | An outside test on a Pi 5 with an OV9281 ([wifijt/photonvision-tools#1](https://github.com/wifijt/photonvision-tools/pull/1)) found threads=1 *faster* than 4 per camera (14.9 vs 15.6 ms detect). We have one camera per Pi and 4 idle-ish A76 cores, so the best value is unknown. Sweep 1 / 2 / 4. | None, beyond needing a measurement. |
| L3 | **Streams** | Input tab "Stream Resolution" (`streamingFrameDivisor`, default NONE = full res); which streams are shown (`inputShouldShow`/`outputShouldShow`) | The same PR measured +34% fps (frame period 17.4 → 8.7 ms) with both streams off, even with no viewer. On 10-27, stopping the recorder (a viewer of the input stream) cut drops from 4–10% to about 2%. | The UI requires at least one stream; the PR's websocket script turns both off. The recorder needs the input stream. |
| L4 | **Refine edges** (`refineEdges`, default on) | AprilTag tab | Saves part of the detect time; matters more at decimate 1. | Slightly worse corner accuracy. Check cross-camera agreement. |
| L5 | **Blur** (`blur`, default 0) / **decision margin** (35) / **pose iterations** (40) | AprilTag tab | Small; mostly change false positives. | Leave alone unless L1–L4 aren't enough. |
| L6 | **ArUco detector** instead of AprilTag | Pipeline type | PV docs: about 2× fps and half the latency, but less accurate ([detector types](https://docs.photonvision.org/en/latest/docs/apriltag-pipelines/detector-types.html)). | Accuracy loss; a separate experiment. |
| L7 | **Camera mode fps** | Resolution list | Arducam lists MJPG 100 fps at 1280x800 and 800x600; one retailer claims 120. On 10-27, 800x600 offered 120. Run `v4l2-ctl --list-formats-ext` to see whether 1280x800 offers 120. YUY2 is 10 fps, so it's unusable. | None |

Ruled out by the data, not worth testing: CPU frequency or thermal (never capped, max 56 °C) and
the Pi's network link. The cliff appeared identically on the 1000 Mbit/s Right Pi and the
100 Mbit/s Left Pi, and decimate doesn't change anything sent over the network.

## Bandwidth: can it be a factor?

Not for the cliff, for the reasons above. It **is** a factor on the field: R704 caps
robot ↔ Driver Station traffic at 7 Mbit/s through the radio. The 10-27 logs already carry the
radio's own measurement (AdvantageKit `RadioStatus/Status` → `networkStatus6.bandwidthUsedMbps`):

| Run | Radio bandwidth used, Mbit/s (median / max) |
|---|---|
| T1–T5, T7 | 0.8–1.1 / ≤1.4 |
| **T5.1** | **7.2 / 8.7** |
| T6 | 0.5 / 0.5 |

T5.1 went over the field limit, almost certainly from a PhotonVision stream open in the browser
while the fps was changed. This also confounds T5.1 → T6 (see the correction in the 10-27
write-up). From this logging change on, the Health Check flags it, and the Pis' `NetTxMbps` show
which board was sending.

New logging (code on `beta`, not yet deployed):

- Pi: `OrangePi/<Pi>/NetRxMbps`, `NetTxMbps`, `NetRxErrors`, `NetTxErrors`, `NetRxDropped`
  (orangepi-nt-publisher). Needs `Bootstrap-OrangePi.ps1` on both Pis.
- roboRIO: `RIO/CpuPct`, `RIO/CpuCorePct`, `RIO/MemUsedPct`, `RIO/MemAvailableMB`, `RIO/NetRxMbps`,
  `RIO/NetTxMbps`, `RIO/NetRxErrors`, `RIO/NetRxDropped` (`RioSystemStats`, switch
  `RIO_SYSTEM_STATS_LOGGING`). Needs a deploy.
- Health Check: roboRIO CPU (mean, p95), memory, ethernet, radio bandwidth (6 GHz and 2.4 GHz; warn
  at 5, fail at 7 Mbit/s), Pi sent/received and receive errors. Pi link speed now also runs on logs:
  it would have flagged the Left Pi's 100 Mbit/s link on every 10-27 log.

## Setup

| | |
|---|---|
| Maneuver | `CircleFacingTag`, as on 10-27 (comparable to those runs) |
| Controls | Same battery for each pair. **No PhotonVision browser tab open while enabled** (check the Radio bandwidth row). Note the recorder state for every run. |
| Window | Enabled spans > 5 s |
| Order | Interleave A/B/A/B for the main comparison, so drift hits both |

### Pre-test checklist

- [ ] Deploy robot code with `RIO_SYSTEM_STATS_LOGGING = true`, and re-bootstrap both Pis (publisher with `Net*`)
- [ ] `v4l2-ctl -d /dev/video0 --list-formats-ext` on each Pi, pasted into the notes
- [ ] Record the PhotonVision settings for each run in the run table **before** enabling: resolution@fps, decimate, Low Latency Mode, threads, refine edges, stream resolution, recorder on/off
- [ ] Close every PhotonVision browser tab before enabling

## Runs

All runs use 800x600 @100 fps unless stated, so they are comparable to 10-27 T1–T3. Recorder on unless stated.

| ID | Change | Why |
|---|---|---|
| R1 | dec 3, Low Latency **on**, threads 4 | Baseline, repeats 10-27 T1 |
| R2 | dec 2, Low Latency **on** | Repeats 10-27 T2 (expect ~50) |
| R3 | dec 2, Low Latency **off** | **The main test.** Does the cliff disappear? |
| R4 | repeat R2 | A/B/A/B |
| R5 | repeat R3 | A/B/A/B |
| R6 | dec 1, Low Latency off | How far down decimate can go |
| R7 | best of R3/R6, threads 1 | L2 |
| R8 | best of R3/R6, threads 2 | L2 |
| R9 | best so far, stream resolution ¼ | L3 (recorder still works, at lower resolution) |
| R10 | best so far, recorder stopped | Separates the recorder's cost from the stream divisor |
| R11 | 1280x800 dec 2, best of the above | Does 1280x800 become usable? |
| R12 | 800x600 @**120**, dec 3, Low Latency off | Does the 10-27 best setting gain anything more? |

Pass for a setting: results/s ≥ 90% of the camera fps, dropped frames ≤ 3%, cross-camera agreement
no worse than 10-27 (median ≤ 5 cm). It must also keep 800x600@120 dec 3's latency within +10 ms.

## Metrics

Same as 10-27 (`analyze.py`), plus `RIO/CpuPct` and `RIO/NetTxMbps`, the Pis' `NetTxMbps`, and the
radio's `bandwidthUsedMbps`. Add these to `analyze.py` when the logs exist. The frame-interval
histogram is the key plot: with Low Latency on, the intervals cluster at multiples of the camera
period; with it off, they should spread toward 1 ÷ loop time.

## Still open after this

- **Range** (10-27 open question 2): a stationary test at 2 / 4 / 6 / 8 m, run once a fast enough
  decimate 1 or 1280x800 setting exists. Higher resolution only earns its cost at range.
- **ArUco detector (L6)**, if the AprilTag detector can't reach the target rate.
