# Reference: vision tuning log and current camera settings

> Draft distilled from notes 6-16 → 9-19. Suggested home: `docs/vision/tuning-log.md`.
> Keep this as a running log: add a row for each change, name the log file, and write down the result.

## Current settings (as of 9/15)

**Camera (both), 800×600 @ 100 FPS, MJPEG**

| Setting | Value | Why |
|---|---|---|
| Auto exposure | **Off** | With AE on, the overhead LED lights flickered and hurt calibration (9/5) |
| Exposure | 86 | |
| Brightness | 0 | Was 41 or ~50. Lowering it gave a large FPS and jitter improvement (6/20, 9/5) |
| Camera gain | 25 | Was 76 or ~50 |
| Auto white balance | On | |
| Low latency mode | On | |

**AprilTag pipeline:** 36h11 (6.5 in), decimate **3**, blur 0, threads **7**, decision margin cutoff
**30**, pose-estimation iterations 100, refine edges on.

**Robot code:** `PhotonPoseEstimator` with `MULTI_TAG_PNP_ON_COPROCESSOR` and a `LOWEST_AMBIGUITY`
fallback (`Camera.java`). **Keep it.** Both alternatives tried on 9/19 scored worse (see below).

> **Check that decimate is actually 3 again.** The 9/19 logs run at ~35–40 FPS, which is the
> decimate-1 rate (9/15 run 3), not the ~73–84 FPS seen with decimate 3. It looks like decimate
> was left at 1 after the 9/15 test.

All comparisons below are logbench **auto-period** comparisons. The trimmed logs and the
HTML/JSON reports are committed under `notes/<day>/trimmed/` and `notes/<day>/analysis/`.

## Change log

| Date | Change | Log | Result |
|---|---|---|---|
| 6/16 | Vision feature switches OFF → ON, multi-tag route | `akit_26-06-16_22-27-57_FSOFF_MultTag` → `22-33-24_FSON_MultTag` | Slightly better: right FPS 70→85, left longest gap 229→40 ms, acceptance flat. This log format predates the health scores, so there's no composite score |
| 6/16 | Feature switches OFF → ON, single-tag route | `22-59-58_FSOFF_SglTag` → `23-17-10_FSON_SglTag` | Neutral. Acceptance flat, left latency +3 ms, right FPS min 72→62 |
| 6/16 | High resolution (FS on, multi-tag) | `22-33-24_FSON_MultTag` → `23-46-28_FS_ON_MultTag_HighRes` | **Worse:** FPS 78/85→50/50, latency +3 to +7 ms, acceptance flat. Don't use high resolution |
| 6/20 | Decimate 3→1, threads 3→7, margin 35→30 | `akit_26-06-20_14-22-29_cameraConfigChange` | **Worse:** FPS ~71→36 and latency 29→38 ms. Decimate went back to 3; threads 7 and margin 30 were kept |
| 6/20 | Decimate back to 3 | `akit_26-06-20_15-20-19_decimateBack` | FPS recovered (L 65 / R 61) |
| 6/20 | Right cam brightness 41→0, gain 76→25 | `akit_26-06-20_15-36-04_rightCameraBrightnessGainChange` | **Better:** right FPS 60.6→80.1, accepted poses/s +20, pose σXY −65 to −74 mm |
| 9/5 | Both cams AE off, exposure 86. Left brightness 41→0, gain 76→25 | `akit_26-09-05_14-27-33_CircleFacingTag_PreCalibration` → `15-37-05` | **Mixed.** Quality better: left quality score +27%, left acceptance 91→99.9%. **FPS cost** (not in the 9/5 notes): 74/69→59/61, availability −17 to −19%. Fixed exposure 86 is probably longer than what AE picked, which caps the frame rate. Try a lower fixed exposure |
| 9/8 | ChArUco recalibration (below) | — | Mean reprojection error 0.27 / 0.36 px |
| 9/12 | "Post-calibration" circle auto | `15-37-05` → `akit_26-09-12_13-26-03_CircleFacingTag_PostCalibration` | **Not a calibration test.** It still used the old intrinsics (see commit `efa3776`). Left FPS 59→82 but left acceptance 99.9→87%. Something else changed between days |
| 9/15 | New intrinsics deployed, circle auto | `9-12 PostCalibration` → `akit_26-09-15_22-01-04_visionRecorder1` | **Better:** health +19% L / +25% R, left acceptance 87→97%, right FPS 60→74. The run was 49 s vs 23 s, so the windows differ |
| 9/15 | Left AE off, brightness ~50→0, gain ~50→25 (had drifted back) | `visionRecorder1` → `visionRecorder2` | **Better:** left health +12%, quality +12%, longest gaps 59/63→37/27 ms, FPS unchanged |
| 9/15 | Decimate 3→1 (again) | `visionRecorder2` → `visionRecorder3` | **Much worse:** FPS 84/73→47/47, latency +5/+10 ms, availability −45%, quality unchanged. This confirms 6/20. **Keep decimate at 3** |
| 9/19 | Pose strategy `MULTI_TAG_PNP_ON_RIO` | `visionRecorder3` → `akit_26-09-19_15-29-36_MULTI_TAG_PNP_ON_RIO` | **Worse:** health −19%/−25%, FPS 47→39/35, latency +10/+6 ms. **The robot loop overran:** 710 cycles in 22.5 s (~32 ms per cycle vs the normal 20 ms). Solving PnP on the rio costs loop time |
| 9/19 | Pose strategy `LOWEST_AMBIGUITY` | `MULTI_TAG_PNP_ON_RIO` → `akit_26-09-19_15-38-07_LOWEST_AMBIGUITY` | **Worst of the three:** tag-in-view 93/91→79/71%, acceptance 99.5/100→95.7/97.8%, health −15%/−24%. The loop was back to a normal 20 ms |

The 9/15 row shows the left camera settings had gone back to ~50/~50 at some point. **After any
reflash or PhotonVision update, re-check the settings against the table above.** Better still,
export the PhotonVision settings file and commit it.

## Lessons so far
- **Decimate 1 roughly halves FPS on this Orange Pi 5 at 800×600 and doesn't improve quality.**
  Tested twice (6/20, 9/15) with the same result. Keep decimate at 3.
- **High resolution costs ~40% FPS with no acceptance gain** (6/16).
- **Lower brightness and gain (0 / 25) help consistently:** tighter poses, shorter gaps, and higher FPS on the right camera
  (6/20, 9/15).
- **Turn auto exposure off under shop LEDs to stop flicker, but fixed exposure 86 cost ~15% FPS** (9/5).
  The next test is a lower fixed exposure.
- **The 9/8 intrinsics helped:** left acceptance 87→97% and health up on both cameras (9/15).
- **Keep `MULTI_TAG_PNP_ON_COPROCESSOR`.** Running PnP on the rio made the robot loop overrun (~32 ms
  cycles). `LOWEST_AMBIGUITY` lost tags and acceptance. The 9/19 runs had no same-day coprocessor
  baseline, and were likely on decimate 1, so a clean re-run on decimate 3 would firm this up.
- Every test changed one thing and named the log, and that's the reason these results can be trusted.
  Keep doing that. Where comparisons span different days (9/5 → 9/12), something else changed that
  nobody wrote down.

## Camera calibration data

### Intrinsics (9/8, 800×600, ChArUco). Deployed in `VisionConstants.java`
| | Left | Right |
|---|---|---|
| fx / fy | 690.33 / 689.95 | 687.70 / 687.42 |
| cx / cy | 400.09 / 327.97 | 417.59 / 290.14 |
| Distortion | `[0.035, -0.026, 0, 0, -0.035, -0.002, 0.001, 0.001]` | `[0.047, -0.094, 0, 0, 0.059, -0.001, 0.004, -0.002]` |
| Mean error | 0.36 px | 0.27 px |
| HFOV / VFOV / DFOV | 60.18° / 47.00° / 71.84° | 60.37° / 47.15° / 72.05° |

The full PhotonVision exports are in `notes/9-8/*_photon_calibration_*.json`. Consider moving them to
`docs/vision/calibration/` so they sit next to the values in code.

### Mount-transform tape-measure runs (for `tools/camera-calibration`)
Setup constants: robot half-length **13.5 in**, bumper rail width **27 in**, tag **32**, tag center
height **41.125 in**. All distances are in inches.

A 6/23 attempt used a fixed floor grid, rows 3 ft and 6 ft from the wall. It was harder to
repeat. "Drive anywhere, then measure to the wall and to the centerline" was easier:

| Run | Pos | To wall | To centerline | L | R |
|---|---|---|---|---|---|
| 6/23 | 1 | 27 | 10.5 | 31.5 | 22.5 |
| 6/23 | 2 | 48 | 8 | 50.25 | 45.5 |
| 6/23 | 3 | 56 | 14.5 | 51.5 | 60.5 |
| 6/23 | 4 | 33 | 14.5 | 26.5 | 39 |
| 7/28 | 1 | 30 | 19.5 | 31.75 | 28.25 |
| 7/28 | 2 | 60.75 | 15.25 | 61 | 59.75 |
| 7/28 | 3 | 57.5 | 14.5 | 56 | 59 |
| 7/28 | 4 | 19.25 | 11.5 | 15.75 | 22.25 |
