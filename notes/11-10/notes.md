# 11-10 (Tue) session: re-bootstrap, frame-budget runs, leftover 11-07 checks

About 1 h 40 min, in this order. Tick the boxes and fill the blank columns as you go.

**The main event is Part 3**, the [frame-budget experiment](../../docs/experiments/vision/2026-11-10-pv-frame-budget/README.md):
can fewer detector threads or turning off output drawing make PhotonVision faster per frame?
Background on why, in one line: each camera handles one frame at a time, so results/s = 1 ÷ time
per frame, and idle CPU can't help.

## Part 1: before enabling (about 20 min)

- [ ] **Pull `beta`** on the laptop (has the bootstrap wizard, `robots.json` and the team SSH key).
- [ ] **Leave the robot code alone.** It's `beta` from 11-07 with `VISION_EXTENDED_NT_LOGGING = false`;
      no robot-code change is needed, and a redeploy mid-experiment changes the conditions.
- [ ] **Re-bootstrap both Pis.** In `coprocessor`: `.\Bootstrap-OrangePi.ps1`, then **1** (every board)
      and **1** (straight through). Check in the output:
  - [ ] RightPi, step 10 or 11: `CAMERA_STREAM_URL=http://localhost:1181/stream.mjpg` (it was `rightpi.local`).
  - [ ] Both Pis end with "This Pi is set up."
  - [ ] On a laptop other than the one that made the key: "Copied the team key" and **no** password prompt.
- [ ] **Set both Pis to B1's settings** in the PhotonVision UI:
      camera **800x600 MJPG @100** (it was @120), Low Latency Mode **off**, decimate **1**, threads **8**,
      output drawing **on**.
- [ ] **Close every PhotonVision browser tab.** Same before every enable today.
- [ ] AdvantageScope live, with `Vision/LeftCam/CurrentFps` and `Vision/RightCam/CurrentFps` on a
      graph. That's results/s; you'll read it during each run.

## Part 2: one quick check left over from 11-07 (about 5 min)

On each Pi: `ssh -i ~/.ssh/id_ed25519_orangepi pi@LeftPi.local`, then the same with `RightPi.local`
(the `-i` part uses the team key, so no password):

| Check | How | Pass if | LeftPi | RightPi |
|---|---|---|---|---|
| PhotonVision still saves settings (11-07 check 2b) | `sudo journalctl -u photonvision --since "2 hours ago" \| grep -i locked` (with **sudo** this time; without it the journal is hidden) | prints nothing | [ PASS ] | [ PASS ] |

## Part 3: frame-budget runs (about 45 min)

Each run: set the settings **on both Pis**, close the PhotonVision tab, enable the
`CircleFacingTag` auto (about 20 s), read `CurrentFps` near the end, write it and the log name
below. One change per run.

| Done | Run | Camera | Dec | Threads | Drawing | Expect | CurrentFps L / R | Log (`akit_26-11-10_…`) |
|---|---|---|---|---|---|---|---|---|
| [x] | B1 | 800x600 @100 | 1 | 8 | on | ~67 | 68 / 67 | akit_26-11-10_23-14-41-bundle |
| [x] | B2 | 800x600 @100 | 1 | **4** | on | ~75 | 69 / 68 | akit_26-11-10_23-27-02-bundle |
| [x] | B3 | 800x600 @100 | 1 | **3** | on | ~75 | 69 / 67 | akit_26-11-10_23-30-18-bundle |
| [x] | B4 | 800x600 @100 | 1 | **1** | on | ~35 (worse) | 41 / 37 | akit_26-11-10_23-32-43-bundle |
| [x] | B5 | 800x600 @100 | 1 | 1 (not best, see below) | **Raw stream** | ? | 41 / 39 | akit_26-11-10_23-38-26-bundle |
| [x] | RESET bot to BASELINE | 800x600 @100 | 2 | 8 | on | ? | 101 / 101 | akit_26-11-10_23-43-08-bundle |
| [-] | B6 | 800x600 **@120** | **2** | best | best | ≥108 to pass | skipped | |
| [-] | B7 | 800x600 @100 | 2 | best | best | 101 | skipped (RESET is the same settings) | |

`CurrentFps` filled in afterwards from the logs: median over the ~21 s the auto was enabled
(`Vision/<cam>/CurrentFps`). Camera mode, decimate, threads and Low Latency (off) were confirmed
from the Pi publisher's `OrangePi/<Pi>/PhotonVision/<cam>/*` entries in each log, and match the
table. Results/s from `analyze.py` agrees within ~1/s (B1 68.7 / 67.6, B2 69.2 / 69.3, B3 69.9 /
69.7, B4 40.9 / 37.6, B5 40.8 / 40.6, RESET 101.0 / 101.0).

**"Best" threads** (after B4): the run with the highest `CurrentFps`. If none beats B1 (8 threads)
by at least 3/s, use 8. Best threads: **8**. B3 (3 threads) was highest, but only +1 / +1 over B1;
3, 4 and 8 threads are all ~68. Only 1 thread hurts (−27 / −30).

**"Best" drawing** (after B5): off, if B5 is at least 3/s faster than the run with best threads.
Otherwise on. Best drawing: **on** (Processed stream). B5 ran at 1 thread, so the fair comparison
is B4, not the best-threads run: +0.5 / +2.6, under the 3/s bar.

**Turning off drawing**: look in PhotonVision's pipeline settings (Output tab) for drawing on the
processed image. If there's no such switch, turn off the processed (output) stream instead and
write which you did here: **Dashboard page: deselected Processed, selected Raw** (both Pis). The
log shows what that changed: the pipeline's `outputShouldShow` went true → false and
`inputShouldShow` false → true; `outputShouldDraw` stayed **true**. So B5 tested streaming the raw
image instead of the processed one, not turning drawing off. Threads were still 1 from B4.

*Afterwards:* the instruction above was the problem, not how it was followed. PhotonVision's UI
has no drawing switch for AprilTag pipelines, Processed/Raw doesn't affect it, and drawing runs on
a separate stream thread anyway, so it was never likely to shorten the frame. Details in the
write-up's "What output drawing really is".

## Part 4: LogBench checks left over from 11-07 (about 10 min)

Settings stay as B7. These come after the experiment on purpose: LogBench live is what stalled
vision on 10-27, so it mustn't overlap the B runs.

| Done | Check | How | Pass if | Result |
|---|---|---|---|---|
| [ ] | LogBench live (11-07 check 2c) | Start LogBench, connect live, leave the Health Check open 2 min, then one more `CircleFacingTag` run | That run's `CurrentFps` matches B7, and later: no camera gap over 80 ms in its log | PASS |
| [ ] | Optional, 2 min: the rest of a log (2d) | Restart robot code, fetch the newest log again | The full log downloads (bigger than the first copy), no "still writing" note | PASS |

Fetching a log that's still being written already passed on 11-07: all nine bundles were taken
while the robot was writing them, and all finished.

## Before leaving

- [ ] **Both Pis on the race setting**: 800x600 @100, decimate 2, Low Latency off, threads = best,
      drawing = best (B7's settings).
- [ ] **Fetch the bundles** into `logs/offseason/11-10/`.

## If there's time: range

The [range experiment](../../docs/experiments/vision/2026-11-03-pv-range/README.md) needs taped floor
marks at 2 / 4 / 6 / 8 m and one pipeline per setting. Better as its own session after this one.

## Afterwards (at home)

- Put the B-run logs in `RUNS` in `docs/experiments/vision/2026-11-10-pv-frame-budget/analyze.py`
  and run it; it prints each run's time per frame split into main thread and detector work.
- Open an 11-07 log (from `18-22-17` on) in LogBench's Health Check and see whether the roboRIO
  CPU / memory, radio and Pi network rows have values (11-07 check 2e).

## Recorded

<!-- One line per log: time, run, anything that went differently from the plan. -->

- 23-14-41, B1: as planned. 68 / 67/s, 14.6 ms per frame (7.8 main thread + 4.8 detector).
- 23-27-02, B2: as planned. 69 / 68/s.
- 23-30-18, B3: as planned. 69 / 67/s.
- 23-32-43, B4: as planned. 41 / 37/s; with 1 thread the main thread waits ~24–27 ms per frame.
- 23-38-26, B5: threads left at 1 (plan said "best"); "drawing off" was done as Processed → Raw
  on the dashboard, which leaves drawing on (see above). 41 / 39/s, no real change from B4.
- 23-43-08, RESET: dec 2, threads 8, drawing on, @100. 101 / 101/s, same as 11-07 R5. This is the
  B7 setting, so B7 wasn't needed.
- B6 (@120, dec 2) and B7 not run.

**Takeaway:** at decimate 1 the frame takes ~14.4 ms at 3, 4 or 8 threads, so ~69/s is
the ceiling there; threads don't buy anything and the raw-vs-processed stream doesn't either.
Decimate 2 drops the frame to ~9.9 ms and the camera's 100/s becomes the limit. Not tested yet:
B6 (whether dec 2 keeps up with @120). `outputShouldDraw` off isn't worth a run (see above).
