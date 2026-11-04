# TODO
- [x] Add roboRIO CPU to health check, akit_26-10-27_22-13-27.wpilog shows it consistently high but the health check doesn't surface this.
  - Done (not yet deployed): `RioSystemStats` logs `RIO/CpuPct`, per-core CPU, memory and ethernet once a second; the Health Check has roboRIO CPU mean (warn 70, fail 85 %) and p95 (warn 90, fail 98 %) rows, plus memory. The .wpilog had no CPU signal before, only loop times (the DS log has CPU).
- [x] could network bandwith limiting cause issues? should this be added to the health check? if so what is the threshold? can we currently measure how much bandwith we are using?
  - Not the cause of the half-rate cliff: it hit the 1000 Mbit/s Right Pi exactly like the 100 Mbit/s Left Pi, and decimate doesn't change network traffic. See [the follow-up](../../docs/experiments/vision/2026-10-28-pv-frame-pacing/README.md).
  - We could already measure the radio: AdvantageKit logs `RadioStatus/Status` with `bandwidthUsedMbps`. Under 1.4 Mbit/s in every run except test 5.1 (7.2-8.7 Mbit/s, over the 7 Mbit/s R704 field limit, most likely a PhotonVision browser stream).
  - Added: Health Check radio bandwidth rows (warn 5, fail 7 Mbit/s), Pi `NetTxMbps`/`NetRxMbps`/errors (publisher, needs re-bootstrap), roboRIO ethernet Mbit/s, and Pi link speed on logs (it now flags the Left Pi's 100 Mbit/s link).

# Vision throughput test (10-27)

Full write-up, with every metric, per-run verdicts, learnings and the analysis script:
[docs/experiments/vision/2026-10-27-pv-throughput](../../docs/experiments/vision/2026-10-27-pv-throughput/README.md)

Goal: find out whether we can lower decimate, raise resolution, or both, on one OV9281 per
Orange Pi 5, without losing throughput or throttling the Pi. Each run used the `CircleFacingTag`
auto (about 20 s enabled). Logs are in `logs/offseason/10-27/`.

| Test | Setting | Log bundle | Bench notes | Results/s (L / R) | Dropped % (L / R) | PV ms (median) | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | 800x600 @100, decimate 3 (baseline) | `akit_26-10-27_22-13-27-bundle` | swapped battery after test | 98.4 / 96.1 | 2.8 / 5.0 | 15.2 | neutral (matches 10-24) |
| 2 | 800x600 @100, decimate 2 | `akit_26-10-27_22-37-33-bundle` | "fresh" test battery | 53.1 / 54.1 | 0 / 0 (at 50 fps) | 16.6 | loss: half rate |
| 3 | 800x600 @100, decimate 1 | `akit_26-10-27_22-42-57-bundle` | restarted robot code before test | 50.4 / 50.3 | 0 / 0 | 22.5 | loss |
| 4 | 1280x800, decimate 3 (recalibrated) | `akit_26-10-27_23-07-45-bundle` | | 50.5 / 50.5 | 0 / 0 | 21.0 | loss |
| 5 | 1280x800, decimate 2 | `akit_26-10-27_23-21-27-bundle` | | 49.4 / 48.2 | 0.1 / 0 | 24.2 / 25.0 | loss |
| 5.1 | 800x600 @120, decimate 3 | `akit_26-10-27_23-27-43-bundle` | earlier 800x600 runs were @100 fps; turns out it can go to 120 at decimate 3 | 116.1 / 108.7 | 3.9 / 10.0 | 15.3 | **gain** |
| 6 | best (800x600 @120, dec 3), recorder stopped | `akit_26-10-27_23-37-01-bundle` | | 118.7 / 118.5 | 1.7 / 1.9 | 15.2 | **gain** vs 5.1 |
| 7 | best, recorder running, heat soak (10 s auto + 140 s driven teleop) | `akit_26-10-27_23-42-41-bundle` | | PV fps 118 / 114 throughout | about 5 / 9–10, flat | 15.0 | neutral: no heat build-up |

No run throttled. CPU clock stayed at max (2256 / 2304 MHz big cores). Max temp 56.4 °C, against a
75 °C passive trip. Whole-Pi CPU never passed 37%.

## Conclusion

Setting we're keeping: **800x600 @120 fps, decimate 3** (recommended; team to confirm).

Why: anything heavier halves results/s, because PhotonVision handles every other frame. That
isn't a CPU or heat limit. 120 fps gives +13–18% results/s at the same processing time and lower
latency. At 1–3 m, no setting changed accuracy (cross-camera agreement).

Not measured this session (see "Open questions" in the write-up): camera mode list (`v4l2-ctl`),
stationary range test at 2 / 4 / 6 m, `top -H` by hand (the logged `PvTopThread*` data covers it).
Also found: **Left Pi ethernet is at 100 Mbps** (Right Pi is at 1000 Mbps).
