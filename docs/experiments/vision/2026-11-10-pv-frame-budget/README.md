---
id: VIS-2026-11-10-pv-frame-budget
title: PhotonVision frame budget — can fewer detector threads or no output drawing shorten each frame?
area: vision
date: 2026-11-10
status: analyzed            # planned | running | analyzed | decided
decision: keep threads 8 and drawing as is; decimate is the lever (B6 @120 dec 2 still open)
robot_code: beta @ d0b8b2c (dirty), same in every run; no robot-code change needed
logs: logs/offseason/11-10/
analysis: analyze.py → results.json
raw_notes: notes/11-10/notes.md
---

# PhotonVision frame budget: detector threads and output drawing

## In short

The [frame-pacing experiment](../2026-10-28-pv-frame-pacing/README.md) settled on 800x600 @100,
decimate 2, Low Latency Mode off: 101 results/s. Anything heavier (decimate 1, @120, 1280x800)
falls short, **even though the Pi's CPU is only ~30% busy**. The reason: PhotonVision handles one
frame per camera at a time, and **results/s = 1 ÷ time per frame**. Each frame is about 6–8 ms of
work on one main thread plus the AprilTag detector's work spread over the 4 fast cores (details
under "Where a frame's time goes" below). Idle cores can't shorten that.

This experiment tried the two settings we thought could: **fewer detector threads** (8 threads
share 4 fast cores with the main thread) and **turning off drawing on the output image**. If either
saved enough, decimate 1 (sees farther) or @120 (more results) might keep up.

**What we found (11-10):**

- **Threads don't help.** At decimate 1, 3, 4 and 8 threads all give ~68–69 results/s
  (~14.4 ms per frame). Only 1 thread hurts (~39/s). Keep 8.
- **Drawing was never on the main thread.** We assumed it was; PhotonVision's source says
  otherwise (see "What output drawing really is" below). It runs on a separate stream thread, so it
  can only cost frames by competing for CPU. There's also no switch for it in the UI for AprilTag
  pipelines, so B5 ended up testing the Raw vs Processed stream instead, which changed nothing.
- **Decimate is the lever.** Decimate 2 brings the frame to ~9.9 ms and the camera's 100/s becomes
  the limit (101/s, same as 11-07).
- B6 (@120, decimate 2) and B7 weren't run. B7's settings are the same as the reset run, which gave
  101/s. B6 is still open.

## What we're testing

1. **Does a different number of detector threads shorten the frame?** At decimate 1, where the
   detector does the most work, try 8 (now), 4, 3 and 1. *(B1–B4)*
2. **Does turning off output drawing shorten the main thread?** *(B5)* The question was wrong:
   drawing isn't on the main thread. See "What output drawing really is".
3. **With the best of both, does 800x600 @120, decimate 2 keep up now?** It missed by ~0.6 ms
   per frame on 11-07. *(B6)*
4. **Is the main setting (800x600 @100, decimate 2) still fine with the new settings?** *(B7)*

How we tell: **time per frame** (1000 ÷ results/s), and how it splits into main thread and
detector work (`analyze.py` prints this for every run). Run-to-run noise in time per frame was
about 0.1 ms on 11-07, so:

| Check | Counts as a gain if | Why |
|---|---|---|
| **Time per frame** | at least 0.5 ms shorter than the run it's compared with | 5× the 11-07 run-to-run noise |
| Cross-camera agreement | median still ≤ 5 cm | A faster frame mustn't cost accuracy |
| For B6 (@120) only: the frame-pacing checks | results/s ≥ 108 (90%), dropped frames ≤ 3%, latency ≤ 32.7 ms | Same bar as frame pacing |

### Words used here

- **Results/s**: pose estimates per second reaching the robot, per camera. Live in AdvantageScope
  as `Vision/LeftCam/CurrentFps` (it matched results/s within 1/s in every 11-07 run).
- **Time per frame**: 1000 ÷ results/s, in ms. 101/s = 9.9 ms; 67/s = 14.9 ms.
- **Main thread**: PhotonVision's `VisionRunner` thread for a camera. It decodes the camera's
  JPEG, converts to grey, runs the detector's one-at-a-time steps, solves the pose and publishes.
  Only one frame at a time. It does **not** draw (we thought it did when planning this).
- **Stream thread**: a second thread per camera (`StreamRunnable`) that takes each finished frame,
  draws on it and feeds the dashboard streams. If it falls behind it skips frames; the main thread
  never waits for it.
- **Detector threads**: the AprilTag tab's **Threads** setting. Those threads split up the middle
  of the tag search; the main thread waits for them.
- **Fast cores / slow cores**: the Orange Pi 5 has 4 fast cores (4–7) and 4 slow ones (0–3).
  PhotonVision ran only on the fast ones on 11-07.
- **Decimate**: how much PhotonVision shrinks the image before searching for tags. 1 = full image
  (sees farthest, slowest).
- **Output drawing**: the pipeline setting `outputShouldDraw`. PhotonVision drawing tag outlines,
  IDs, 3D boxes and a crosshair onto the processed image for the dashboard. It changes only the
  picture people see, never the results sent to the robot.
- **Processed / Raw**: the stream buttons on the PhotonVision Dashboard page. They set
  `outputShouldShow` / `inputShouldShow`, i.e. which picture is streamed. They don't turn drawing
  off.

## The runs

Every run: both Pis set the same, Low Latency Mode **off**, `CircleFacingTag` auto (~20 s
enabled), recorder on, Driver Station + AdvantageScope + Elastic open, **no PhotonVision browser
tab open while enabled**. Change one thing per run, on both Pis. The settings are also in the log,
but **write them in this table first**.

| Run | Camera | Decimate | Threads | Output drawing | What it checks | Expect | Status |
|---|---|---|---|---|---|---|---|
| B1 | 800x600 @100 | 1 | 8 | on | Baseline. R6 was the same at @120 | ~67/s (14.9 ms) | done 11-10 |
| B2 | 800x600 @100 | 1 | **4** | on | Fewer threads than fast cores | ~75/s (13.3 ms) | done 11-10 |
| B3 | 800x600 @100 | 1 | **3** | on | One fast core left free for the main thread | ~75/s | done 11-10 |
| B4 | 800x600 @100 | 1 | **1** | on | Checks our model: all detector work on one thread | ~35/s (worse) | done 11-10 |
| B5 | 800x600 @100 | 1 | best of B1–B4 | **off** | What drawing costs the main thread | unknown | ran as Raw stream at threads 1 (see Results) |
| B6 | 800x600 **@120** | **2** | best | best of B5 | Does @120 keep up now? | passes if B5 saved ≥ 0.6 ms | not run |
| B7 | 800x600 @100 | 2 | best | best | The main setting with the new settings: still 101/s, with more spare time | 101/s | not needed (reset run = same settings) |

**Picking "best"**: after B4, take the thread count with the highest `CurrentFps`. If none beats 8
by at least 3/s, keep 8. For B5 → B6/B7, use drawing off only if B5 was at least 3/s faster than
the run it copied.

**Turning off output drawing**: this instruction was wrong. There's no such switch for AprilTag
pipelines (see "What output drawing really is"), and turning off the processed stream doesn't
turn drawing off. The log records `outputShouldDraw` and `outputShouldShow`, which is how we
caught it.

### Before the session

- [ ] Both cameras back to **800x600 @100** (they were @120 from 19:03 on 11-07).
- [ ] Low Latency Mode off, threads 8, decimate 1 on both Pis (B1's settings).
- [ ] Both Pis re-bootstrapped with the current `beta` (the 11-10 notes cover this).
- [ ] Every PhotonVision browser tab closed before each enable. Set settings between runs, close
  the tab, then enable.

## Results

All runs on 11-10, robot code `beta` @ `d0b8b2c` (dirty) in every log. Settings below are read
from each log (the Pi publisher's PhotonVision entries), not from the notes; they match the notes
except where marked. `CurrentFps` is the median over the ~21 s enabled; results/s and the frame
split are from `analyze.py`. Low Latency Mode was off in every run.

| Run | Dec | Threads | `outputShouldDraw` | Stream | CurrentFps L / R | Results/s L / R | Time per frame, Left (main + detector) |
|---|---|---|---|---|---|---|---|
| B1 | 1 | 8 | on | Processed | 68 / 67 | 68.7 / 67.6 | 14.6 ms (7.8 + 4.8) |
| B2 | 1 | 4 | on | Processed | 69 / 68 | 69.2 / 69.3 | 14.4 ms (6.8 + 6.1) |
| B3 | 1 | 3 | on | Processed | 69 / 67 | 69.9 / 69.7 | 14.3 ms (6.7 + 6.0) |
| B4 | 1 | 1 | on | Processed | 41 / 37 | 40.9 / 37.6 | 24.4 ms (24.4 + 1.1) |
| B5 | 1 | **1** (plan: best) | **on** (plan: off) | **Raw** | 41 / 39 | 40.8 / 40.6 | 24.5 ms (24.5 + 1.1) |
| reset | 2 | 8 | on | Processed | 101 / 101 | 101.0 / 101.0 | 9.9 ms (6.4 + 1.7), camera-paced |

- **Threads**: 3 and 4 threads are within ~1/s of 8, under the 3/s bar, so keep 8. Fewer threads
  move time from detector to main thread rather than saving it; the frame stays ~14.4 ms. With 1
  thread everything lands on one thread and the frame grows to ~25 ms, as the model predicted.
- **B5**: "drawing off" was done as Processed → Raw on the Dashboard page, and threads were still 1
  from B4. The log shows `outputShouldDraw` stayed on. Compared with B4 (same threads):
  +0.5 / +2.6 per s, no real change, as expected from the source (below).
- **Decimate 2** gives 101/s with ~1.7 ms to spare per frame, the same as 11-07 R5.

### What output drawing really is

From PhotonVision v2026.1.1's source (the version on both Pis):

- After the main thread publishes a frame's results, it hands the frame to the camera's **stream
  thread** ([`VisionModule.StreamRunnable`](https://github.com/PhotonVision/photonvision/blob/v2026.1.1/photon-core/src/main/java/org/photonvision/vision/processes/VisionModule.java))
  and starts the next frame. The stream thread runs
  [`OutputStreamPipeline`](https://github.com/PhotonVision/photonvision/blob/v2026.1.1/photon-core/src/main/java/org/photonvision/vision/pipeline/OutputStreamPipeline.java),
  which does the drawing when `outputShouldDraw` is on, then feeds the streams. If it's still busy
  when the next frame arrives, it drops the older one. So drawing can only slow results/s by
  taking CPU from the fast cores, not by adding to the main thread's time.
- It draws every frame whether or not anyone is watching the stream.
- **Processed / Raw** only sets `outputShouldShow` / `inputShouldShow`. For USB cameras the request
  this makes to the camera code is a no-op ([`CpuImageProcessor.requestFrameCopies`](https://github.com/PhotonVision/photonvision/blob/v2026.1.1/photon-core/src/main/java/org/photonvision/vision/frame/provider/CpuImageProcessor.java):
  "We don't actually do zero-copy"), so it changes which picture is streamed, not the work done.
- **The UI has no switch for `outputShouldDraw` on AprilTag pipelines.** The only place the UI sets
  it is colour picking on the Threshold tab of colour pipelines, and only while picking.
- To turn it off anyway (unsupported, untested): stop PhotonVision and edit `"outputShouldDraw"`
  in the camera's `pipeline_jsons` in `/opt/photonvision/photonvision_config/photon.sqlite`, or
  send the setting by name over PhotonVision's websocket (the backend accepts any pipeline field).
  Check it in the log: `OrangePi/<Pi>/PhotonVision/<cam>/PipelineJson` shows
  `"outputShouldDraw":false`, and the Processed stream shows no tag outlines.

Given the above, we're not planning a drawing-off run.

## Next experiment

The big picture across all the PhotonVision experiments (what limits results/s and what could
raise it) is in [ADR 0002](../../../adr/0002-photonvision-throughput-limit.md).

**Range** ([PhotonVision range vs decimate and resolution](../2026-11-03-pv-range/README.md)),
with whatever this experiment shows each setting can sustain.

B6 (800x600 @120, decimate 2, threads 8) is still open from this experiment: it missed by
~0.6 ms per frame on 11-07, and neither lever here buys that back.

Neither threads nor drawing shortens the frame, so the main thread is the wall. A **second camera
per Pi** is a better use of the spare fast cores than a faster single camera. That's a separate
test.

## Reproduce

```bash
python docs/experiments/vision/2026-11-10-pv-frame-budget/analyze.py
```

Reads the WPILog Janitor-trimmed logs in `logs/offseason/11-10/` (unzip each bundle into a
folder of the same name first).

| Run | Log |
|---|---|
| B1 | `akit_26-11-10_23-14-41` |
| B2 | `akit_26-11-10_23-27-02` |
| B3 | `akit_26-11-10_23-30-18` |
| B4 | `akit_26-11-10_23-32-43` |
| B5 | `akit_26-11-10_23-38-26` |
| reset | `akit_26-11-10_23-43-08` |

---

## Background

<details>
<summary><b>Where a frame's time goes (from the 11-07 logs)</b></summary>

The Pi publisher logs PhotonVision's 8 busiest threads (name, % of a core, which core) about once
a second. Splitting them into the main thread and the detector workers, then into milliseconds
per frame:

| 11-07 run | Time per frame | Main thread, alone | Detector workers (CPU ÷ 4 fast cores) | Sum |
|---|---|---|---|---|
| dec 2, @100 (R5) | 9.9 ms (camera-paced) | 6.4 ms | 1.8 ms | 8.2 ms |
| dec 2, @120 (R12) | 8.9 ms | 6.5 ms | 1.8 ms | 8.3 ms, just over the 8.3 ms frame gap |
| dec 1, @120 (R6) | 14.9 ms | 8.1 ms | 4.8 ms | 13.0 ms |
| 1280x800, dec 2 (R13) | 15.9 ms | 11.8 ms | 3.1 ms | 14.9 ms |

- The fast cores were 50–65% busy and the slow ones 3–6%. The "~30% CPU" averages in cores
  PhotonVision doesn't use.
- The main thread costs ~6 ms per 800x600 frame whether decimate is 3 or 2, so it's work on
  every pixel (decode, grey), not the tag search. (Drawing turned out to be on the stream
  thread, not here.)
- For decimate 1 at 100/s the frame has to fit in 10 ms; the main thread alone is 8 ms. B2–B5
  could only close that if threads and drawing together saved ~3 ms. (Planning guess: 67 toward
  80/s was realistic. Measured: 69/s at best.)
- PhotonVision doesn't start a camera's next frame until the current one is published, so more
  cores can't overlap frames. That's built into PhotonVision (`VisionRunner`, one per camera).

The numbers are from once-a-second samples of the top 8 threads, good to about a millisecond.

</details>

<details>
<summary><b>Why fewer threads might be faster</b></summary>

With threads = 8, eight detector threads plus the main thread and the stream thread share 4 fast
cores. The detector hands each thread a slice of the image and waits for all of them; when there
are more threads than cores, the last slices wait their turn, and the main thread waits with
them. On 11-07 at decimate 1 the detector used 19 ms of CPU per frame; spread perfectly over 4
cores that's 4.8 ms, which is about what we saw, so there may be only ~1 ms to win. Threads = 1
puts all 19 ms on one thread, which our numbers say is much worse. An outside test on a Pi 5
([wifijt/photonvision-tools#1](https://github.com/wifijt/photonvision-tools/pull/1)) found 1
thread slightly faster than 4 at its settings; B4 checks which applies here.

</details>
