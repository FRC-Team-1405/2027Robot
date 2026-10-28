---
id: VIS-2026-10-27-pv-throughput
title: PhotonVision throughput vs resolution, decimate, fps and recorder
area: vision
date: 2026-10-27
status: analyzed            # planned | running | analyzed | decided
decision: pending           # filled in once the team picks a setting
robot_code: beta @ 338bcfa7
logs: logs/offseason/10-27/   # gitignored; one bundle per run
analysis: analyze.py → results.json
raw_notes: notes/10-27/notes.md
---

# PhotonVision throughput vs resolution, decimate, fps and recorder

## Question

Can we lower decimate, raise resolution, or both, on one OV9281 per Orange Pi 5 without losing
throughput or throttling the Pi? Follow-up to the 10-24 practice log (`akit_26-10-24_14-59-06`):
at 800x600 / 100 fps / decimate 3 both cameras kept up (~100 results/s, ~2–4% dropped frames),
but Pi CPU and temperature weren't logged, so headroom was unknown.

## Answer (short)

- **No to lower decimate or higher resolution.** Every setting heavier than 800x600 / decimate 3
  cut results/s roughly in half, from ~97 to ~50. PhotonVision processed every other camera frame.
  The Pi was not short on CPU or cooling: CPU use went *down*, and nothing throttled.
- **Yes to 120 fps.** 800x600 @120 fps / decimate 3 gave +13–18% results/s, the same
  PhotonVision processing time, and lower p95 latency (about 30 ms, down from 51 ms).
- **Something costs frames at 120 fps: the recorder, or a browser stream.** With the recorder
  stopped (T6), dropped frames went from 3.9% / 10.0% to 1.7% / 1.9% (left / right). But T5.1 also
  had 7–9 Mbit/s crossing the radio (other runs: about 1), most likely a PhotonVision stream open in
  the browser. So T5.1 → T6 changed two things. T7 (recorder on, no browser stream) still dropped
  about 5% / 9–10%, which points at the recorder. This needs a clean repeat
  ([next experiment](../2026-10-28-pv-frame-pacing/README.md)).
- **Why heavier settings halve throughput:** PhotonVision's *Low Latency Mode* (on by default)
  waits for the next camera frame, so a frame that takes longer than 10 ms skips the following
  frame. Found after this run in the PhotonVision source; see the
  [follow-up](../2026-10-28-pv-frame-pacing/README.md).
- **Heat is not a concern.** In a 150 s driven run at the best setting, temperatures stayed flat
  at 47–54 °C, against a 75 °C passive trip. The CPU clock never dropped, and fps held steady.

## Setup

| | |
|---|---|
| Hardware | 2× Orange Pi 5 (LeftPi, RightPi), one OV9281 each, PhotonVision; roboRIO 2 |
| Robot code | `beta` @ `338bcfa7`, `COPROCESSOR_HEALTH_LOGGING=true` (confirmed in `RealMetadata/FeatureSwitches`) |
| Pi software | recorder + nt-publisher `2026.10.25.1+5d092267189c` on both Pis (confirmed in log) |
| Calibration | 800x600 calibrations from 9-8; 1280x800 calibrations added this session (commit `f25ae4a`) |
| Maneuver | `CircleFacingTag` auto: about 1.5 s positioning, then about 17.6 s orbiting while facing tag 10. Tags 9 and 10 in view, 1.0–2.8 m away, peak 1.3 m/s. Same maneuver every run, so runs are comparable. |
| Window | Enabled time only (WPILog Janitor trim, 2 s padding), about 20.5–22 s per run, 150 s for T7 |

### Pre-test checklist: what the logs confirm

- [x] `COPROCESSOR_HEALTH_LOGGING = true`, Pi CPU, temperature and recorder data present
- [x] Updated recorder and nt-publisher on both Pis (version string above; `CpuCorePct` present)
- [x] 1280x800 calibration done for both cameras
- [ ] Camera mode list (`v4l2-ctl --list-formats-ext`) **not recorded**. This matters: see open question 1.
- [ ] Tags at about 2 / 4 / 6 m with the robot stationary **was not done**. The circle auto ran instead,
      so "farthest tag" and "stationary wobble" could not be measured. See open question 2.
- [~] `top -H` on PhotonVision: not run by hand, but the publisher's `PvTopThread*` data answers it
      (see Learnings §2)
- [?] Cable strain relief and Right Pi ethernet: not visible in the log. **The Left Pi ethernet
      negotiated 100 Mbps in every run** (Right Pi: 1000 Mbps).

Bench notes: the battery was swapped after T1 (T2 ran on a fresh test battery). Robot code was
restarted before T3. T5.1 was added mid-session, after finding that 800x600 offers 120 fps at
decimate 3.

## Results

Values are left / right camera unless one value is shown. "Dropped" counts gaps between pose
timestamps longer than 1.6× the median frame interval. For T2–T5 the median interval is 20 ms, so
0% there means "steady at 50 fps", not "no lost frames".

| | T1 | T2 | T3 | T4 | T5 | T5.1 | T6 | T7 |
|---|---|---|---|---|---|---|---|---|
| Setting | 800x600@100, dec 3 | 800x600@100, dec 2 | 800x600@100, dec 1 | 1280x800, dec 3 | 1280x800, dec 2 | 800x600@120, dec 3 | T5.1, recorder off | T5.1, 150 s driven |
| Log (`akit_26-10-27_…`) | `22-13-27` | `22-37-33` | `22-42-57` | `23-07-45` | `23-21-27` | `23-27-43` | `23-37-01` | `23-42-41` |
| Results/s | 98.4 / 96.1 | 53.1 / 54.1 | 50.4 / 50.3 | 50.5 / 50.5 | 49.4 / 48.2 | **116.1 / 108.7** | **118.7 / 118.5** | 82.9 / 83.3¹ |
| PV-reported fps (median) | 99.2 / 97.4 | 52.8 / 53.5 | 50.5 / 50.3 | 50.6 / 50.4 | 49.5 / 48.2 | 116.5 / 110.4 | 118.3 / 118.5 | 118.6 / 113.7 |
| Steady frame rate | 101 | 53–54 | 50 | 50.5 | 48–49 | 121 | 121 | 121 |
| Dropped frames % | 2.8 / 5.0 | 0 / 0 (at 50 fps) | 0 / 0 | 0 / 0 | 0.1 / 0 | 3.9 / **10.0** | **1.7 / 1.9** | 4.5–7 / 8.7–10.3² |
| Results the robot missed (sequence gaps) | 12 / 4 | 0 | 0 | 0 | 0 | 0 | 0 | — |
| PV processing time, ms (median / p95 / max), left | 15.2 / 16.2 / 21.5 | 16.6 / 17.3 / 29.2 | 22.6 / 24.1 / 30.3 | 21.0 / 21.7 / 26.4 | 24.2 / 25.3 / 30.6 | 15.4 / 16.0 / 22.1 | 15.2 / 15.8 / 21.0 | 15.0 / 15.8 / 23.2 |
| PV processing time, ms (median / p95 / max), right | 15.4 / 16.4 / 19.4 | 16.6 / 17.4 / 33.7 | 22.5 / 24.3 / 29.1 | 21.0 / 21.6 / 27.4 | 25.0 / 25.7 / 30.6 | 15.3 / 16.3 / 22.0 | 15.2 / 15.8 / 22.6 | 15.0 / 16.1 / 24.0 |
| Capture-to-robot latency, ms (median / p95), left | 23.5 / 50.6 | 30.1 / 51.5 | 34.3 / 43.5 | 33.3 / 41.2 | 35.3 / 44.7 | 22.7 / 30.3 | 22.2 / 29.5 | 21.9 / 28.7 |
| PhotonVision CPU, % of one core (median / max), L | 162 / 182 | 108 / 202 | 189 / 246 | 144 / 158 | 184 / 206 | 224 / 240 | 182 / 198 | 214 / 266 |
| PhotonVision CPU, % of one core (median / max), R | 162 / 174 | 110 / 202 | 186 / 266 | 144 / 156 | 184 / 190 | 184 / 204 | 185 / 200 | 184 / 206 |
| Busiest core %, median / max (L) | 47 / 59 | 34 / 60 | 52 / 78 | 47 / 60 | 54 / 68 | 60 / 66 | 51 / 65 | 59 / 84 |
| Busiest core %, median / max (R) | 46 / 53 | 34 / 80 | 51 / 84 | 45 / 67 | 55 / 65 | 52 / 59 | 52 / 60 | 51 / 68 |
| Whole-Pi CPU % (median), L / R | 24 / 24 | 15 / 16 | 26 / 25 | 20 / 21 | 25 / 25 | 30 / 26 | 23 / 27 | 29 / 25 |
| CPU clock, big cores (MHz) | 2256 / 2304, never below max, `CpuThrottled` false in every run | | | | | | | |
| Max temp, °C (L / R) | 48.1 / 47.2 | 42.5 / 45.3 | 51.8 / 50.8 | 49.9 / 48.1 | 50.8 / 49.9 | 56.4 / 50.8 | 51.8 / 50.8 | 54.5 / 50.8 |
| Recorder stream fps (L / R) | 99 / 98 | 53 / 53 | 50 / 50 | 50 / 50 | 50 / 48 | 117 / 109 | off | 119 / 114 |
| Tag range seen, m (L) | 0.98–2.69 | 0.98–2.70 | 0.98–2.69 | 0.95–3.06 | 0.98–2.70 | 0.97–2.69 | 0.97–2.70 | 0.57–3.19 |
| Cross-camera agreement, cm (median / p95) | 5.1 / 11.5 | 4.2 / 9.9 | 4.3 / 10.2 | 4.3 / 9.8 | 4.0 / 10.3 | 4.4 / 10.7 | 4.5 / 10.9 | 5.0 / 39³ |
| Vision correction per update, cm (median) | 5.2 | 5.1 | 5.2 | 5.3 | 5.4 | 3.7 | 3.4 | 4.8 |
| roboRIO vision periodic, ms (median / p95) | 5.6 / 12.0 | 5.0 / 11.9 | 4.7 / 8.1 | 4.6 / 8.2 | 4.8 / 8.2 | 6.3 / 10.7 | 6.2 / 10.4 | 5.3 / 7.9 |
| roboRIO cycles over 20 ms | 29% | 26% | 12% | 10% | 13% | 24% | 18% | 6% |

¹ T7 is driven around the field, so tags are often out of view. Results/s counts only frames with
a tag, which is why it is lower; PhotonVision's own fps stayed at 118 / 114.
² T7 dropped frames: in-view gaps under 50 ms only, per 30 s slice (table below).
³ T7's cross-camera p95 includes fast driving (peak 4.45 m/s) and multi-tag scenes, so it isn't
comparable to the circle runs.

### T7 heat soak, per 30 s slice

| Slice | Left fps (PV) | Left dropped % | Right fps (PV) | Right dropped % |
|---|---|---|---|---|
| 0–30 s | 118.4 | 5.3 | 112.5 | 8.9 |
| 30–60 s | 118.1 | 7.0 | 116.6 | 8.7 |
| 60–90 s | 118.0 | 4.8 | 113.1 | 10.3 |
| 90–120 s | 118.7 | 4.5 | 113.9 | 9.2 |
| 120–150 s | 118.7 | 5.0 | 111.8 | 9.9 |

Temperatures: Left 53.6 → 51.8 °C, Right 49.9 → 47.2 °C, both drifting *down* while driving.
The CPU clock cap never moved from max.

## Run-by-run verdicts (each against the run before, or the stated reference)

| Run | vs | Verdict | Why |
|---|---|---|---|
| T1 baseline | 10-24 log | **neutral** | Matches 10-24: about 97 results/s, 2.8 / 5.0% dropped. New data: busiest core about 47%, max temp 48 °C, no throttling. One 140 ms left-camera stall and 12 missed results, the only run where the robot missed any. |
| T2 dec 2 | T1 | **loss** | Results/s −46% / −44%. PV time rose only 1.4 ms (15.2 → 16.6), but that tipped PhotonVision into handling every other frame (frame intervals: 1061 of 1169 are exactly 20 ms). CPU fell from 162% to 108%. Latency median +7 ms. |
| T3 dec 1 | T2 | **loss** (no further change in rate) | Still 50/s. PV time +6 ms (22.6). CPU back up to 189%. No gain in agreement or range at these distances. |
| T4 1280x800 dec 3 | T1 | **loss** | 50/s. PV time 21 ms (+38% over T1). Tag area in % of image dropped from 1.8 to 1.4, consistent with a wider field of view in that mode. No improvement in cross-camera agreement. |
| T5 1280x800 dec 2 | T4 | **loss** | 48–49/s, PV time 24–25 ms: the slowest setting tested. |
| T5.1 800x600@120 dec 3 | T1 | **gain** | Results/s +18% / +13%. PV time unchanged (15.3). Latency p95 51 → 30 ms. Per-update correction 5.2 → 3.7 cm. Cost: left PV CPU +38%, max temp 56 °C, and right camera drops rose to 10%. |
| T6 recorder off | T5.1 | **gain** (confounded) | Drops 3.9 → 1.7% (L) and 10.0 → 1.9% (R). Results/s 118.7 / 118.5. Left PV CPU −42 points; right PV CPU unchanged. **But** radio traffic also fell from 7.2–8.7 to 0.5 Mbit/s: T5.1 likely had a browser stream open, so this isn't the recorder alone. |
| T7 heat soak | T5.1 (recorder on) | **neutral** | Over 150 s, fps, drop rate and temperature are flat. Drop rate (L about 5%, R about 9–10%) matches T5.1, so it doesn't build up over a match. |

## Learnings

1. **This is a cliff, not a slope.** (Cause, found later: PhotonVision's Low Latency Mode; see the
   [follow-up](../2026-10-28-pv-frame-pacing/README.md).) Throughput doesn't fall off gradually as the work per frame
   rises. Once PhotonVision can't finish a frame before the next one arrives, it skips every other
   frame, and results/s drops to exactly half the camera rate. CPU use goes *down* when that happens,
   so CPU % and temperature are the wrong early warning. The signal to watch is the steady frame
   interval. It should stay at the camera period, 10 ms at 100 fps or 8.3 ms at 120 fps; a 20 ms
   interval means half rate. PV-reported latency is not the per-frame budget on its own: it was
   15 ms while the camera kept up at 100 and 120 fps, and 16.6 ms at decimate 2 was already too much.
2. **"One core or many": many.** PhotonVision spreads over the four big A76 cores (cores 4–7, each
   about 42–56% busy at decimate 3). The four little A55 cores are nearly idle (0–19%). The busiest
   single thread peaks at 74% of a core. Whole-Pi CPU never passed 37%. Headroom exists, but PhotonVision's
   per-frame pipeline can't use it at a heavier setting.
3. **120 fps is free throughput** at 800x600 / decimate 3. PV time is the same, latency is lower,
   and corrections are smaller and more frequent. The Pi has room for it (busiest core about 60%,
   max 56 °C).
4. **The recorder's real cost is the stream, not the saving.** The recorder saves 3 frames/s, but it
   pulls PhotonVision's MJPEG stream at full rate (stream fps about 117). At 120 fps that is where the
   extra drops come from. The right camera is hit harder (10% vs 4%), and so far we don't know why.
5. **No accuracy gain from resolution at 1–3 m.** Cross-camera agreement stayed at 4–5 cm median
   and about 10 cm p95 for every setting. If higher resolution helps, the gain would show at long
   range, which this run didn't test.
6. **Left Pi ethernet is linked at 100 Mbps** in every log. The Right Pi is at 1000 Mbps. The
   checklist pointed at the Right Pi's cable, but the Left Pi is the one to check: cable, jack, or
   switch port.
7. **The roboRIO already overruns, and more vision results cost it time.** Vision periodic median
   is about 4.6 ms at 50 results/s, 5.6 ms at 100 and 6.2 ms at 120. 6–29% of loops ran over 20 ms in
   every run. The correlation with results/s is loose (T2 at 53/s overran as much as T1), so other
   load (live NT clients, logging) matters too. This is relevant to the roboRIO CPU TODO in the notes.
8. **T1 and T2 were disturbed by LogBench's live NetworkTables client (found later).** It was stuck
   in a reconnect loop: connected for about 1.4 s, dropped, and reconnected about 1 s later, every
   2.4 s. About 0.35 s after each connect, both cameras' results reached the robot 100–280 ms late,
   for about a second. That is the periodic dropout in the Vision Logs graphs. In T1's whole log,
   0.2% of results were late before the loop started (at 349 s, disabled), and 10.1% during it. Loop
   p95 went from 19.7 to 33.7 ms. From T3 on (robot code restarted), LogBench connected at boot and
   stayed connected, and the stalls were gone. So T1/T2's higher loop overruns (29% / 26% vs 10–13%),
   p95 latency (about 51 ms vs 41–45 ms) and T1's 12 missed results come from this, not from the
   camera settings. Their throughput and PhotonVision timing (measured on the Pi) are unaffected.
   **Fix (LogBench `live_nt.py`):** the old client subscribed to every AdvantageKit value, and on
   its first Health Check poll (about 0.35 s after connecting, matching the stall onset) it opened
   one more subscription per topic. Now it uses a names-only subscription under the checks'
   prefixes and one value subscription to exactly the checked topics. Against a local NT server
   loaded with T1's 680 topics, that cut requests to the server from 87.8 to 14.7 KiB and data
   to the client from 206 to 97 KiB. The PC was too fast to reproduce the stall itself, so the
   proof is on the robot: connect LogBench live to a running robot and confirm the vision delay
   stays flat (no results over 80 ms late; `stalls.py`-style check).

## Open questions

1. **Was 1280x800 running at 100 fps?** If the camera mode was 50 or 60 fps, T4 and T5 measured the
   camera's limit, not PhotonVision's. Run `v4l2-ctl --list-formats-ext` and note the PhotonVision
   camera mode fps for each run.
2. **Does resolution or decimate improve range?** Run a stationary test with tags at 2 / 4 / 6 / 8 m:
   800x600@120 dec 3 against 1280x800 dec 3, measuring detection rate and pose jitter at each
   distance. This would show whether giving up half the results/s buys anything.
3. **Is the recorder effect real?** It's one run each, and T5.1 also had a browser stream crossing
   the radio (7–9 Mbit/s). Repeat interleaved (on, off, on, off) with no browser tab open.
4. **Can the recorder read a lower-rate stream?** For example, a lower PhotonVision stream fps or
   resolution. That might keep the diagnostic images without the frame cost.
5. **Bandwidth?** Answered since: not the cause of the cliff. It hit the 1000 Mbit/s Right Pi exactly
   like the 100 Mbit/s Left Pi, and decimate changes nothing on the network. The radio carried under
   1.4 Mbit/s in every run except T5.1. Bandwidth logging and Health Check rows have been added; see
   the follow-up.

## Recommendation

Use **800x600 @120 fps, decimate 3**. Keep the recorder on for now, since its diagnostic value is
real and drops are still under 10%. Revisit after open questions 3 and 4. Don't move to 1280x800 or
a lower decimate unless the range test (open question 2) shows a gain worth half the results/s.

## Reproduce

```bash
python docs/experiments/vision/2026-10-27-pv-throughput/analyze.py
```

Reads the trimmed logs under `logs/offseason/10-27/` and rewrites `results.json`. The raw
per-run numbers, including some not shown above (per-core CPU, recorder states, tag IDs), are in
`results.json`.
