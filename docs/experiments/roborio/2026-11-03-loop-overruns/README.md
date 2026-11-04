---
id: RIO-2026-11-03-loop-overruns
title: roboRIO loop overruns — what takes the 20 ms away
area: roborio
date: 2026-11-03            # written; rename the folder to the day it runs
status: planned             # planned | running | analyzed | decided
decision: pending
robot_code: needs RioSystemStats (branch vision-throughput-10-27) deployed
logs: logs/offseason/<run date>/
analysis: analyze.py → results.json (already computes the baseline from 10-27 and 11-03)
raw_notes: notes/<run date>/notes.md
---

# roboRIO loop overruns: what takes the 20 ms away

## In short

The robot code is supposed to finish each loop in 20 ms. In every vision test so far it didn't in
**5–29% of loops** while driving the `CircleFacingTag` auto. When a loop runs long, commands,
odometry and vision updates all arrive late. The logs we already have show that on a slow loop,
*everything* gets slower by about the same factor, not just one subsystem. So something is
taking CPU time away from the robot code. This experiment finds out what.

**Not run yet.** The baseline below comes from logs we already have.

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
| L1 | Baseline: AdvantageScope + Elastic connected as usual | roboRIO CPU (question 1), with the new logging | to do |
| L2 | Close AdvantageScope, Elastic and LogBench; only the Driver Station | Dashboards' cost (question 2) | to do |
| L3 | Enabled in teleop, sticks untouched, no auto | The background cost with no command running (question 3) | to do |
| L4 | Repeat L1 | Drift, and the reference for L5 | to do |
| L5 | Deploy with `VISION_EXTENDED_NT_LOGGING = false`, then as L1 | Extended vision logging's cost (question 3) | to do |
| L6 | Repeat L5 | Second sample, since L5 needs its own deploy | to do |

The slow-loop share varied from 5% to 12% between identical 11-03 runs, so one run per setting
isn't enough for small effects. L1/L4 and L5/L6 give two runs each for the switch; repeat L2 if
it's close.

### Before the session

- [ ] Deploy code with `RioSystemStats` and `RIO_SYSTEM_STATS_LOGGING = true` (branch
  `vision-throughput-10-27`, or `beta` once it's merged). Check that `RIO/CpuPct` shows up.
- [ ] Note which dashboards are open in each run. The log lists NT clients under
  `SystemStats/NTClients/`, and `analyze.py` counts them.
- [ ] Have a second deploy ready with `VISION_EXTENDED_NT_LOGGING = false`, for L5–L6.

## Results

Not run yet. Add the runs to `RUNS` in `analyze.py`. It already reports the slow-loop share, the
slow vs normal time of each section, GC, NT clients and (once logged) roboRIO CPU.

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
