---
id: RIO-2026-11-03-loop-overruns
title: roboRIO loop overruns — what takes the 20 ms away
area: roborio
date: 2026-11-03            # written 11-03; first runs 11-07 (folder keeps the written date)
status: running             # planned | running | analyzed | decided
decision: pending           # not dashboards, not extended vision logging; the CPU is ~80% busy
robot_code: 11-07 L1–L3 338bcfa (old!), L5 vision-throughput-10-27 a9925d1+edits, L4'/L4''/L2' beta d0b8b2c+edits
logs: logs/offseason/11-7/
analysis: analyze.py → results.json
raw_notes: notes/11-7/myNotes.md
---

# roboRIO loop overruns: what takes the 20 ms away

## In short

The robot code is supposed to finish each loop in 20 ms. In every vision test so far it didn't in
**5–29% of loops** while driving the `CircleFacingTag` auto. When a loop runs long, commands,
odometry and vision updates all arrive late. The logs we already have show that on a slow loop,
*everything* gets slower by about the same factor, not just one subsystem. So something is
taking CPU time away from the robot code. This experiment finds out what.

**11-07 (L1–L5 plus four more runs): it isn't the dashboards and it isn't the extended vision
logging.** The roboRIO's CPU is **72–84% busy** (median per run, peaks to 92%) while driving the
auto, so a normal 12–13 ms loop has little room before something pushes it past 20 ms. The share
of slow loops swung from 4% to 20% between runs with the *same* setup, which is bigger than any
difference between setups. Garbage collection makes a loop about 10× more likely to be slow, but
most slow loops have no GC in them. Next step: find out which process is using the CPU
(see "What would answer it next").

## What we're testing

1. **Is the roboRIO's CPU actually full?** The new `RIO/CpuPct` logging answers this directly.
   We don't have it yet because the code that logs it was never deployed. *(L1)*
2. **Do dashboards and other NetworkTables clients cost loop time?** Close everything except the
   Driver Station and compare. *(L2)*
3. **Is it the robot's own work?** Sit still with no command running, and separately turn off
   the extended vision logging (vision is the biggest single section, about 5 ms). *(L3, L5)*
4. **How much is garbage collection?** Java's garbage collector already averages about 2 ms per
   loop. We measure it in every run. *(all runs)*

What would change what we do:

| If we see | Then |
|---|---|
| roboRIO CPU near 100% in L1 | We're CPU-bound: cut work from the loop, starting with the biggest sections |
| L2 has far fewer slow loops than L1 | Limit dashboards on the robot network, or slow their update rates |
| L5 has far fewer slow loops than L4 | Make extended vision logging cheaper, or turn it off at competition |
| GC time jumps on the slow loops in every run | Cut what we allocate per loop (a code change, measured the same way) |

### Words used here

- **Loop / cycle**: one pass of the robot code. It should run every 20 ms.
- **Slow loop**: one where `LoggedRobot/FullCycleMS` (robot code plus AdvantageKit logging) is
  over 20 ms. Same as an "overrun".
- **Section**: a part of the loop timed by `LOG_SUBSYSTEM_TIMINGS`, logged as
  `RealOutputs/Timing/<Name>Ms`.
- **GC**: Java's garbage collector, which pauses the program to free memory.
  `LoggedRobot/GCTimeMS` is how long it took in that loop.
- **NT client**: anything connected to the robot's NetworkTables: AdvantageScope, Elastic,
  LogBench live, the Pis, PhotonVision.

## Baseline (from logs we already have)

From `analyze.py` over the 10-27 and 11-03 vision runs (about 20 s enabled each, T7 150 s):

| Run | Slow loops | Robot code, normal → slow loop | GC, normal → slow | Vision, normal → slow | NT clients |
|---|---|---|---|---|---|
| 10-27 T1 | **28.9%** | 12.8 → 22.6 ms | 2.3 → 4.4 ms | 5.5 → 9.6 ms | 11 |
| 10-27 T2 | **25.6%** | 12.4 → 23.5 | 2.2 → 6.2 | 4.9 → 9.0 | 9 |
| 10-27 T3 | 12.1% | 12.1 → 22.8 | 2.3 → 4.5 | 4.8 → 8.2 | 9 |
| 10-27 T7 (driven) | 5.8% | 12.0 → 23.3 | 2.4 → 6.1 | 5.1 → 10.6 | 9 |
| 11-03 R1 | 12.2% | 13.2 → 23.3 | 2.3 → 4.7 | 5.6 → 9.0 | 8 |
| 11-03 R2 | 12.0% | 12.2 → 22.6 | 1.8 → 5.9 | 5.0 → 8.4 | 8 |
| 11-03 R3 | 4.8% | 12.7 → 20.8 | 2.9 → 4.9 | 5.7 → 8.4 | 8 |

What it already tells us:

- **A normal loop uses about 12–13 ms of its 20.** There isn't much spare time.
- **On a slow loop every section stretches by about 1.6–1.8×**: the scheduler, vision, odometry
  and logging alike. One subsystem having a bad loop would look different (that one section would
  jump and the rest wouldn't move). This looks like the robot code losing the CPU partway through
  the loop.
- **GC averages 2 ms per loop** and roughly doubles on slow loops.
- **The worst runs (10-27 T1, T2) had LogBench live connected**, which was fixed afterwards
  (`7363770`). That fits question 2, but it isn't proof.
- **Vision results/s isn't the cause.** 11-03 R2 (54 results/s) and R3 (101/s) had the same
  vision time per loop.

## The runs

Every run: robot on the floor, `CircleFacingTag` auto unless stated, about 20 s enabled, the
same battery for L1–L3. The camera settings don't matter here; keep them the same in every run
and write them down.

| Run | What changes | What it checks | Status |
|---|---|---|---|
| L1 | Baseline: AdvantageScope + Elastic connected as usual | roboRIO CPU (question 1), with the new logging | ✅ `18-04-56`, but on the **old code** (no `RIO/*`) |
| L2 | Close AdvantageScope, Elastic and LogBench; only the Driver Station | Dashboards' cost (question 2) | ✅ `18-13-22` (old code) |
| L3 | Enabled in teleop, sticks untouched, no auto | The background cost with no command running (question 3) | ✅ `18-16-38` (old code) |
| L4 | Repeat L1 | Drift, and the reference for L5 | ✅ as L4' `19-03-35` and L4'' `19-10-49` (beta, extended logging off, camera @120) |
| L5 | Deploy with `VISION_EXTENDED_NT_LOGGING = false`, then as L1 | Extended vision logging's cost (question 3) | ✅ `18-22-17` (branch `vision-throughput-10-27`) |
| L6 | Repeat L5 | Second sample, since L5 needs its own deploy | covered by L4'/L4'' (same switch) |
| L2' | Repeat L2 on beta | Second sample of "Driver Station only" | ✅ `19-13-10` |

**What the robot was actually running** (read from `RealMetadata` in each log, not the notes):
L1–L3 ran the code deployed on 10-27 (`338bcfa`), with `VISION_EXTENDED_NT_LOGGING = true` and no
`RIO/*` stats. L5 ran branch `vision-throughput-10-27` (`a9925d1` + uncommitted edits) with the
switch off. Everything from 19:03 on ran `beta` (`d0b8b2c` + uncommitted edits) with the switch
off. So L1 vs L5 changes both the switch and the code version, and L1–L3 have no roboRIO CPU
numbers.

The slow-loop share varied from 5% to 12% between identical 11-03 runs, so one run per setting
isn't enough for small effects. L1/L4 and L5/L6 give two runs each for the switch; repeat L2 if
it's close.

### Before the session

- [ ] Deploy code from `beta` (has `RioSystemStats`, `RIO_SYSTEM_STATS_LOGGING = true`). Check that
  `RIO/CpuPct` shows up (check 2a in [notes/11-7](../../../../notes/11-7/notes.md)).
- [ ] Note which dashboards are open in each run. The log lists NT clients under
  `SystemStats/NTClients/`, and `analyze.py` counts them.
- [ ] Have a second deploy ready with `VISION_EXTENDED_NT_LOGGING = false`, for L5–L6.

## Results (11-07)

From `analyze.py` → `results.json`. Each run is about 20 s enabled (~1000 loops). "Dashboards"
means connected when the run started: the log keeps every client that ever connected, so the
plain list over-counts. LogBench was never connected live during a run.

| Run | Dashboards | Ext. vision logging | Slow loops | roboRIO CPU, median / max | Robot code, normal → slow | GC in slow / normal loops |
|---|---|---|---|---|---|---|
| L1 | AS + Elastic | on (old code) | **18.1%** | – | 13.6 → 21.9 ms | 19% / 3% |
| L2 | none | on (old code) | **7.6%** | – | 12.1 → 22.7 | 42% / 3% |
| L3 (teleop, idle) | none | on (old code) | **4.3%** | – | 11.5 → 23.5 | 52% / 4% |
| L5 | AS + Elastic | off | **15.6%** | 84 / 92% | 13.4 → 23.0 | 25% / 3% |
| L4' | AS + Elastic | off | **7.8%** | 80 / 83% | 12.8 → 23.0 | 51% / 3% |
| L4'' | AS + Elastic (+ LogBench Fetch Bundle page) | off | **16.6%** | 80 / 88% | 13.5 → 22.9 | 28% / 2% |
| L2' | none | off | **19.6%** | 78 / 86% | 13.5 → 22.1 | 23% / 3% |
| R6 (vision dec 1) | AS + Elastic | off | 5.9% | 72 / 79% | 11.2 → 23.1 | 49% / 3% |
| R13 (vision 1280x800) | AS + Elastic | off | 12.2% | 78 / 85% | 12.4 → 21.7 | 26% / 3% |

### Answers so far

| Question | Answer | Evidence |
|---|---|---|
| 1. Is the roboRIO's CPU full? | **Nearly: 72–84% median, peaks 92%.** Not pinned at 100%, but a 2-core CPU at 80% leaves little room for a burst | `RIO/CpuPct` in every run from L5 on |
| 2. Do dashboards cost loop time? | **Not measurably.** Driver Station only: 7.6% and 19.6%. With AS + Elastic: 7.8–18.1% | L2 and L2' alone differ by 12 points with the same setup |
| 3a. Is it the robot's own work? | **Partly.** Idle teleop had the fewest slow loops (4.3%) but not zero | L3 |
| 3b. Does extended vision logging cost time? | **No visible effect.** The vision section took 5.9 ms per normal loop with it on (L1) and off (L5) | L1 vs L5, L4' |
| 4. How much is GC? | **A trigger, not the main cause.** A loop with a GC is ~10× more likely to be slow (19–52% of slow loops have one, 2–4% of normal loops). But 70–90% of slow loops are still over 20 ms with their GC time taken out | `GCCounts`, `GCTimeMS` |

Also checked, from the same logs:

- **Slow loops don't follow a 1-second rhythm**, so the new once-a-second `RioSystemStats` read,
  the radio status poll and the Pi publishers aren't the cause.
- **Slow loops come in bursts of up to 6–7 in a row** (120–140 ms). Something holds the CPU for
  a while, which fits another process or a GC pause better than one slow command.
- **Per-second roboRIO CPU barely tracks the slow-loop share** (correlation 0–0.35). One sample a
  second is too coarse to catch a 100 ms burst.
- **The slow loops are only just slow**: 22.5–24.6 ms median. The worst loop in any run was
  50–111 ms.

### What would answer it next

1. **Log our own process's CPU next to the total** (`/proc/self/stat` in `RioSystemStats`, plus
   the busiest other process). If the robot program is most of the 80%, it's our own work and the
   fix is a per-section budget; if another process (NetComm, the NT server, the web server) spikes
   during the bursts, it's that.
2. **Longer runs, fewer settings.** With a 4–20% spread between identical 20 s runs, a few-point
   effect needs several minutes per setting. Two 2-minute runs of the same setup would show how
   much of the spread is plain noise.
3. **GC as one A/B**: different JVM GC flags in `build.gradle`, since GC is in a quarter to half
   of the slow loops.

## Next experiment

Depends on the answer. If it's GC, an allocation hunt in the loop. If it's the CPU being full, a
section-by-section budget. If it's NT clients, rate limits for dashboards.

## Reproduce

```bash
python docs/experiments/roborio/2026-11-03-loop-overruns/analyze.py
```

---

## Background

<details>
<summary><b>Earlier work on loop time</b></summary>

- [console-load-ab-test.md](../../../console-load-ab-test.md) (10-20): watchdog warnings and
  console traffic. That's where `QUIET_JOYSTICK_WARNINGS` and `QUIET_SCHEDULER_OVERRUN_WARNINGS`
  came from. It notes that the watchdog's elapsed times include GC and scheduling pauses, which
  matches what the baseline above shows.
- [can-bus-load-ab-test.md](../../../can-bus-load-ab-test.md): CAN bus load, a separate question.
- The 10-27 vision write-up found LogBench live stalling vision; fixed in `7363770`.

</details>
