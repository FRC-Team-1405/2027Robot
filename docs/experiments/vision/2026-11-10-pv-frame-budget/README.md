---
id: VIS-2026-11-10-pv-frame-budget
title: PhotonVision frame budget — can fewer detector threads or no output drawing shorten each frame?
area: vision
date: 2026-11-10
status: planned             # planned | running | analyzed | decided
decision: pending
robot_code: beta (no robot-code change needed; same as 11-07)
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

This experiment tries the two settings that can: **fewer detector threads** (8 threads now share
4 fast cores with the main thread) and **turning off drawing on the output image** (drawing runs
on the main thread). If either saves enough, decimate 1 (sees farther) or @120 (more results)
might keep up. **Not run yet.**

## What we're testing

1. **Does a different number of detector threads shorten the frame?** At decimate 1, where the
   detector does the most work, try 8 (now), 4, 3 and 1. *(B1–B4)*
2. **Does turning off output drawing shorten the main thread?** *(B5)*
3. **With the best of both, does 800x600 @120, decimate 2 keep up now?** It missed by ~0.6 ms
   per frame on 11-07. *(B6)*
4. **Is the race setting (800x600 @100, decimate 2) still fine with the new settings?** *(B7)*

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
  JPEG, converts to grey, runs the detector's one-at-a-time steps, solves the pose, draws and
  publishes. Only one frame at a time.
- **Detector threads**: the AprilTag tab's **Threads** setting. Those threads split up the middle
  of the tag search; the main thread waits for them.
- **Fast cores / slow cores**: the Orange Pi 5 has 4 fast cores (4–7) and 4 slow ones (0–3).
  PhotonVision ran only on the fast ones on 11-07.
- **Decimate**: how much PhotonVision shrinks the image before searching for tags. 1 = full image
  (sees farthest, slowest).
- **Output drawing**: PhotonVision drawing tag outlines onto the processed image for the output
  stream.

## The runs

Every run: both Pis set the same, Low Latency Mode **off**, `CircleFacingTag` auto (~20 s
enabled), recorder on, Driver Station + AdvantageScope + Elastic open, **no PhotonVision browser
tab open while enabled**. Change one thing per run, on both Pis. The settings are also in the log,
but **write them in this table first**.

| Run | Camera | Decimate | Threads | Output drawing | What it checks | Expect | Status |
|---|---|---|---|---|---|---|---|
| B1 | 800x600 @100 | 1 | 8 | on | Baseline. R6 was the same at @120 | ~67/s (14.9 ms) | to do |
| B2 | 800x600 @100 | 1 | **4** | on | Fewer threads than fast cores | ~75/s (13.3 ms) | to do |
| B3 | 800x600 @100 | 1 | **3** | on | One fast core left free for the main thread | ~75/s | to do |
| B4 | 800x600 @100 | 1 | **1** | on | Checks our model: all detector work on one thread | ~35/s (worse) | to do |
| B5 | 800x600 @100 | 1 | best of B1–B4 | **off** | What drawing costs the main thread | unknown | to do |
| B6 | 800x600 **@120** | **2** | best | best of B5 | Does @120 keep up now? | passes if B5 saved ≥ 0.6 ms | to do |
| B7 | 800x600 @100 | 2 | best | best | The race setting with the new settings: still 101/s, with more spare time | 101/s | to do |

**Picking "best"**: after B4, take the thread count with the highest `CurrentFps`. If none beats 8
by at least 3/s, keep 8. For B5 → B6/B7, use drawing off only if B5 was at least 3/s faster than
the run it copied.

**Turning off output drawing**: look for it in PhotonVision's pipeline settings (Output tab). If
there is no such switch, turn off the processed (output) stream instead, and write which you did.
The log records `outputShouldDraw` and `outputShouldShow` in the pipeline settings, so `analyze.py`
can tell either way.

### Before the session

- [ ] Both cameras back to **800x600 @100** (they were @120 from 19:03 on 11-07).
- [ ] Low Latency Mode off, threads 8, decimate 1 on both Pis (B1's settings).
- [ ] Both Pis re-bootstrapped with the current `beta` (the 11-10 notes cover this).
- [ ] Every PhotonVision browser tab closed before each enable. Set settings between runs, close
  the tab, then enable.

## Results

Not run yet. After the session, put each run's log in `RUNS` in `analyze.py` and run it.

## Next experiment

**Range** ([PhotonVision range vs decimate and resolution](../2026-11-03-pv-range/README.md)),
with whatever this experiment shows each setting can sustain.

If B1–B5 show the main thread is the wall (as expected at 1280x800), a **second camera per Pi**
is the better use of the spare fast cores than a faster single camera. That's a separate test.

## Reproduce

```bash
python docs/experiments/vision/2026-11-10-pv-frame-budget/analyze.py
```

Reads the WPILog Janitor-trimmed logs in `logs/offseason/11-10/`. Until the runs exist it prints
the 11-07 reference runs only.

| Run | Log |
|---|---|
| B1–B7 | (fill in after the session) |

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
  every pixel (decode, grey, drawing), not the tag search.
- For decimate 1 at 100/s the frame has to fit in 10 ms; the main thread alone is 8 ms. B2–B5
  can only close that if threads and drawing together save ~3 ms, so a full 100/s at decimate 1
  is unlikely. Getting from 67 toward 80/s is realistic.
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
