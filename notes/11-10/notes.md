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
| PhotonVision still saves settings (11-07 check 2b) | `sudo journalctl -u photonvision --since "2 hours ago" \| grep -i locked` (with **sudo** this time; without it the journal is hidden) | prints nothing | [ ] | [ ] |

## Part 3: frame-budget runs (about 45 min)

Each run: set the settings **on both Pis**, close the PhotonVision tab, enable the
`CircleFacingTag` auto (about 20 s), read `CurrentFps` near the end, write it and the log name
below. One change per run.

| Done | Run | Camera | Dec | Threads | Drawing | Expect | CurrentFps L / R | Log (`akit_26-11-10_…`) |
|---|---|---|---|---|---|---|---|---|
| [ ] | B1 | 800x600 @100 | 1 | 8 | on | ~67 | | |
| [ ] | B2 | 800x600 @100 | 1 | **4** | on | ~75 | | |
| [ ] | B3 | 800x600 @100 | 1 | **3** | on | ~75 | | |
| [ ] | B4 | 800x600 @100 | 1 | **1** | on | ~35 (worse) | | |
| [ ] | B5 | 800x600 @100 | 1 | best | **off** | ? | | |
| [ ] | B6 | 800x600 **@120** | **2** | best | best | ≥108 to pass | | |
| [ ] | B7 | 800x600 @100 | 2 | best | best | 101 | | |

**"Best" threads** (after B4): the run with the highest `CurrentFps`. If none beats B1 (8 threads)
by at least 3/s, use 8. Best threads: ____

**"Best" drawing** (after B5): off, if B5 is at least 3/s faster than the run with best threads.
Otherwise on. Best drawing: ____

**Turning off drawing**: look in PhotonVision's pipeline settings (Output tab) for drawing on the
processed image. If there's no such switch, turn off the processed (output) stream instead and
write which you did here: ____

## Part 4: LogBench checks left over from 11-07 (about 10 min)

Settings stay as B7. These come after the experiment on purpose: LogBench live is what stalled
vision on 10-27, so it mustn't overlap the B runs.

| Done | Check | How | Pass if | Result |
|---|---|---|---|---|
| [ ] | LogBench live (11-07 check 2c) | Start LogBench, connect live, leave the Health Check open 2 min, then one more `CircleFacingTag` run | That run's `CurrentFps` matches B7, and later: no camera gap over 80 ms in its log | |
| [ ] | Optional, 2 min: the rest of a log (2d) | Restart robot code, fetch the newest log again | The full log downloads (bigger than the first copy), no "still writing" note | |

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
