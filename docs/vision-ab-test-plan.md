# Vision Feature Switch A/B Test Plan

> Systematic methodology for evaluating every vision feature switch in the 2027 codebase.  
> Companion to: [vision-testing-protocol.md](./vision-testing-protocol.md) (experiment setup), [vision-improvements-2027.md](./vision-improvements-2027.md) (design rationale).

---

## Overview

Six behavioral feature switches live in `FeatureSwitches.java`. All are OFF by default (preserving 2026 behavior). This plan defines what to measure, how to collect data, how to analyze it, and when to promote a switch to ON permanently.

**Golden rule:** Exactly one behavioral switch changes between control and treatment runs. `VISION_EXTENDED_NT_LOGGING` stays `true` for every run — it is required for metric collection.

---

## Feature Switch Test Matrix

| Switch | Default | Priority | Hypothesis | Primary Metric | Pass Threshold |
|--------|---------|----------|-----------|----------------|---------------|
| `VISION_FIELD_BOUNDARY_REJECTION` | OFF | P1 | Eliminates glitch estimates from physically impossible poses | Outlier correction events > 1.0 m (count/min) | ≥ 50% reduction |
| `VISION_SMOOTH_THETA_STDDEV` | OFF | P1 | Smooth heading trust curve reduces heading noise from low-quality estimates | σθ (°) while stationary | ≥ 20% reduction |
| `VISION_DISTANCE_BASED_STDDEV` | OFF | P2 | Distance-based trust is more principled than area-proxy, better separation at range | σX + σY (m) at 3–4 m from tag | ≥ 15% reduction |
| `VISION_TAG_RANKINGS_FILTER` | OFF | P2 | Scoring-zone-only trust improves `PidToPoseCommand` alignment | Final alignment error (m) | ≥ 30% reduction |
| `VISION_AMBIGUITY_THRESHOLD` | OFF | P3 | Rejects ambiguous single-tag poses that introduce outlier corrections | Correction magnitude spikes > 0.5 m (count/min) | ≥ 40% reduction |
| `DISABLE_VISION_ODOM_NEAR_AUTOPILOT_TARGET` | ON | baseline | Prevents odometry jitter during final approach — already on, quantify benefit | Final position σ (mm) over 10 AutoPilot runs | ≥ 20% better with ON |

---

## Pre-Test Checklist

Complete before every test session:

- [ ] `VISION_EXTENDED_NT_LOGGING = true` — verify in `FeatureSwitches.java` (already default)
- [ ] All other behavioral vision switches at baseline state (see matrix)
- [ ] AdvantageScope connected and actively recording to `.wpilog`
- [ ] Robot on tape-marked positions on field floor (sub-centimeter accuracy)
- [ ] PhotonVision dashboard open — confirm both cameras streaming and tag detections live
- [ ] Tag layout in PhotonVision matches current field JSON (`src/main/deploy/`)
- [ ] Battery ≥ 12.4 V (low battery changes camera exposure)
- [ ] Note the git commit hash and PhotonVision version for the log template

---

## Autonomous Robot Test Routine

A `VisionTestAuto` command sequence provides repeatable, driver-independent data collection. Run once for the control baseline and once per switch under test.

### Field Setup — Tape-Mark Positions

Measure these positions relative to a **known April Tag** face center. Use a tape measure and painter's tape.

| Position | Distance | Angle from tag | Tags visible | Purpose |
|----------|----------|---------------|--------------|---------|
| P1 | 1.5 m | 0° (direct) | 1 (single-tag) | Close-range noise floor |
| P2 | 3.0 m | 0° (direct) | 1–2 | Mid-range noise floor |
| P3 | 4.5 m | 0° (direct) | 1–2 | Long-range noise floor |
| P4 | 3.0 m | 30° left | 1 (off-axis) | Off-axis quality — Left cam |
| P5 | 3.0 m | 30° right | 1 (off-axis) | Off-axis symmetry — Right cam |
| P6 | varies | field center | 3+ | Multi-tag zone |

### Routine Sequence (≈ 3 minutes)

```
Robot manually driven to P1 → enable auto mode.

1. Hold P1 for 20 s  (vision accumulates samples at 1.5 m, direct)
2. Drive to P2, hold 20 s
3. Drive to P3, hold 20 s
4. Drive to P4, hold 20 s  (off-axis, single-tag Left camera exposure)
5. Drive to P5, hold 20 s  (off-axis, single-tag Right camera exposure)
6. Drive to P6, hold 20 s  (multi-tag zone)
7. Return to start, disable.
```

Save the wpilog immediately after. Name it `baseline.wpilog` for the control run, or `<switch_name>_on.wpilog` for treatment runs.

### Java Implementation Notes

```java
// VisionTestAuto.java — register as "Vision Test Auto" in SendableChooser
new SequentialCommandGroup(
    driveToKnownPose(P1), new WaitCommand(20),
    driveToKnownPose(P2), new WaitCommand(20),
    driveToKnownPose(P3), new WaitCommand(20),
    driveToKnownPose(P4), new WaitCommand(20),
    driveToKnownPose(P5), new WaitCommand(20),
    driveToKnownPose(P6), new WaitCommand(20)
);
```

Use `PidToPoseCommand` or `PathPlannerAuto` to drive between points. Hard-code P1–P6 as field-relative `Pose2d` constants in `VisionTestConstants.java`.

### Post-Run Analysis

```bash
# Download log from roboRIO
scp admin@10.14.5.2:/home/lvuser/logs/latest.wpilog logs/ab-testing/

# Single-log dashboard (existing tool)
python3 tools/vision-analyzer/analyze.py logs/ab-testing/baseline.wpilog

# A/B comparison (new tool — see Metrics Collection section)
python3 tools/ab-metrics/compare.py \
    --control  logs/ab-testing/baseline.wpilog \
    --treatment logs/ab-testing/smooth_theta_on.wpilog \
    --switch VISION_SMOOTH_THETA_STDDEV
```

---

## Switch-by-Switch Test Procedures

### SW-01 · VISION_FIELD_BOUNDARY_REJECTION

**What it does:** Rejects vision estimates whose reconstructed 3D pose places the robot outside field boundaries.  
**Risk:** Could reject valid near-boundary poses (e.g., robot backed against a wall).

**Control state:** `VISION_FIELD_BOUNDARY_REJECTION = false`  
**Treatment state:** `VISION_FIELD_BOUNDARY_REJECTION = true`

**Steps:**
1. Run full autonomous routine for control, then treatment.
2. **Edge-case teleop:** Drive robot to within 10 cm of each field boundary wall. Confirm `AcceptedPoses` still receives samples — a valid pose should not be rejected.
3. **Fault inject:** Block one camera while at the boundary (see FI-03). Confirm second camera still accepts boundary-adjacent poses.

**Metrics to compare via `compare.py`:**

| Metric | NT Source | Expected Direction |
|--------|-----------|-------------------|
| Correction events > 1.0 m (count/min) | `/Vision/CorrectionMagnitude` | ↓ |
| Boundary rejection counter | `/Vision/Left/RejectedBoundary`, `Right` | ↑ (new counter fires) |
| Total accepted poses (Left) | `/Vision/Left/AcceptedPoses` array count | Neutral or < 5% drop |
| σX stationary (all positions) | Accepted pose X std dev | ↓ or neutral |

**Pass criteria:** Outlier events ≥ 50% reduction AND acceptance rate drops < 5%.

---

### SW-02 · VISION_SMOOTH_THETA_STDDEV

**What it does:** Replaces the binary heading trust rule (`weight > 0.9 → 10.0 rad, else 99999.0`) with a smooth monotonically decreasing LerpTable.  
**Risk:** Mid-quality estimates that were fully ignored at `99999` now contribute some heading correction — if the LerpTable is too aggressive, this could introduce noise.

**Control state:** `VISION_SMOOTH_THETA_STDDEV = false`  
**Treatment state:** `VISION_SMOOTH_THETA_STDDEV = true`

**Steps:**
1. Run full autonomous routine.
2. **Teleop — spin recovery test:** Robot at P2. Drive teleop to spin the robot ~180° and stop. Time how long until heading stabilizes (watch field-pose heading in AdvantageScope).
3. Repeat spin test 5 times per config.

**Metrics:**

| Metric | NT Source | Expected |
|--------|-----------|---------|
| σθ stationary at P1 (1.5 m) | Accepted pose rotation std dev | ↓ |
| σθ stationary at P3 (4.5 m) | Same | ↓ (larger delta expected at range) |
| `/Vision/ThetaStddev` values during stationary | NT topic | Smooth curve instead of 10/99999 |
| Heading recovery time after spin | Manual timing (s) | ↓ |
| σX, σY (should not regress) | Accepted pose X/Y std dev | Neutral |

**Pass criteria:** σθ at P3 improves ≥ 20% AND σX/σY do not regress > 10%.

---

### SW-03 · VISION_DISTANCE_BASED_STDDEV

**What it does:** Computes XY standard deviation from actual camera-to-tag distance via a LerpTable instead of the `0.1 / area_proxy` formula.  
**Risk:** LerpTable constants need tuning. Misconfigured values could over-trust far-field estimates or under-trust close-range ones.

**Control state:** `VISION_DISTANCE_BASED_STDDEV = false`  
**Treatment state:** `VISION_DISTANCE_BASED_STDDEV = true`

**Steps:**
1. Run full autonomous routine — all six positions.
2. Inspect `/Vision/XYStddev` logged values across P1–P3. They should increase monotonically with distance.
3. Sanity check: at P1 (1.5 m) the stddev should be smaller than at P3 (4.5 m). If the opposite is true, the LerpTable is inverted.

**Metrics:**

| Metric | Source | Expected |
|--------|--------|---------|
| σX at P1 (1.5 m) | Accepted pose X std dev | Neutral or slight ↑ (higher stddev → less aggressive correction, which is correct) |
| σX at P3 (4.5 m) | Same | ↓ (better noise rejection at range) |
| `/Vision/XYStddev` at P1 | NT topic | Lower than P3 value |
| `/Vision/XYStddev` at P3 | NT topic | Higher than P1; should scale physically with distance |
| σX at P2 control vs treatment | Comparison | Treatment < control at P2 |

**Pass criteria:** σX at 3–4 m range improves ≥ 15% AND σX at < 2 m does not regress > 10%.

---

### SW-04 · VISION_TAG_RANKINGS_FILTER

**What it does:** Applies `TAG_RANKINGS` map to zero-weight non-scoring tags. Only reef-zone tags (IDs 6–12, 17–22) contribute full trust; other tags are ignored.  
**Risk:** Reduces pose coverage in zones where only non-scoring tags are visible (e.g., far side of field). Could hurt auto paths that traverse non-reef zones.

**Control state:** `VISION_TAG_RANKINGS_FILTER = false`  
**Treatment state:** `VISION_TAG_RANKINGS_FILTER = true`

**Steps:**
1. **Position robot at P6 (multi-tag zone)** where both scoring and non-scoring tags are visible simultaneously. Run routine hold for 60 s per config.
2. **`PidToPoseCommand` alignment runs:** Select a reef scoring branch target. Run AutoPilot or `PidToPoseCommand` from the same starting pose 10 times per config. Record final position with tape measure.
3. **Non-scoring zone check:** Drive robot to a field position where only non-scoring tags are visible (e.g., opposite side of field). Confirm acceptance rate in NT — with switch ON, it should drop significantly, indicating the filter is working.

**Metrics:**

| Metric | Source | Expected |
|--------|--------|---------|
| Mean final X error (tape measure) | Tape over 10 runs | ↓ |
| Mean final Y error | Tape | ↓ |
| σ of final position (repeatability) | Std dev of 10 runs | ↓ |
| Accepted poses at P6 | AcceptedPoses count | May ↓ (non-scoring tags filtered) |
| Accepted poses in non-scoring zone | AcceptedPoses when only non-scoring tags visible | ↓↓ (expected, intended behavior) |

**Pass criteria:** Mean alignment error improves ≥ 30% AND accepted pose count in scoring zone does not drop > 20%.

---

### SW-05 · VISION_AMBIGUITY_THRESHOLD

**What it does:** Rejects single-tag estimates where PhotonVision's ambiguity score ≥ 0.2. Multi-tag estimates are unaffected.  
**Risk:** Significantly reduces detection coverage in zones with only one visible tag, particularly at off-axis angles where ambiguity is naturally higher.

**Control state:** `VISION_AMBIGUITY_THRESHOLD = false`  
**Treatment state:** `VISION_AMBIGUITY_THRESHOLD = true`

**Steps:**
1. Run autonomous routine at P4 and P5 (off-axis, single-tag — highest natural ambiguity).
2. **Camera removal test (FI-01):** Remove Left camera. Run P2 position with only Right camera providing single-tag estimates. Measure acceptance rate and correction magnitude with switch ON vs OFF.
3. Watch `/Vision/Left/RejectedAmbiguity` counter — confirm it fires under treatment.

**Metrics:**

| Metric | Source | Expected |
|--------|--------|---------|
| Ambiguity rejections at P4/P5 | `/Vision/*/RejectedAmbiguity` | ↑ (counter fires) |
| Accepted poses at P4 (off-axis) | AcceptedPoses count | ↓ (some rejected — acceptable) |
| σX at P4 | Accepted pose X std dev | ↓ (fewer bad estimates) |
| Correction magnitude > 0.5 m events | `/Vision/CorrectionMagnitude` | ↓ |
| Acceptance rate in P6 (multi-tag) | AcceptedPoses count | Neutral (multi-tag unaffected) |

**Pass criteria:** Correction magnitude spikes (> 0.5 m) reduce ≥ 40% AND acceptance rate in multi-tag zones does not drop > 5%. If single-tag acceptance drops > 30%, investigate whether the ambiguity threshold of 0.2 is too aggressive.

---

### SW-06 · DISABLE_VISION_ODOM_NEAR_AUTOPILOT_TARGET

This switch is already `true`. The test quantifies the benefit to confirm it should remain enabled.

**Control state:** `DISABLE_VISION_ODOM_NEAR_AUTOPILOT_TARGET = false` (vision stays on during final approach)  
**Treatment state:** `DISABLE_VISION_ODOM_NEAR_AUTOPILOT_TARGET = true` (current behavior — vision suspended near target)

**Steps:**
1. **`PidToPoseCommand` runs:** Use a reef scoring branch target. Run AutoPilot from the same starting pose 10 times with switch OFF, then 10 times with switch ON.
2. Spotter at reef measures final position (bumper to tape).
3. In AdvantageScope: overlay odometry pose timeline during final 0.5 m of approach. Look for correction magnitude spikes that could cause jitter.

**Metrics:**

| Metric | Source | Expected |
|--------|--------|---------|
| Final position σX (10 runs) | Tape measure | ↓ with switch ON |
| Final position σY (10 runs) | Tape measure | ↓ with switch ON |
| CorrectionMagnitude during final 0.5 m | NT topic | ↓ with switch ON |
| Odometry discontinuities in last 0.3 m | AdvantageScope visual | Fewer with switch ON |

**Pass criteria:** Final position σ improves ≥ 20% with switch ON. If < 10%, revisit the beeline radius constant in `AutoPilotV2Command.java`.

---

## Teleop Test Cards

Run these after each autonomous routine. They capture real-world driver behavior that the auto routine cannot replicate.

### TC-01 · AutoPilot Alignment Consistency

**Goal:** Measure scoring accuracy under driver control.

**Setup:** Tape a scoring template on the floor at the reef branch target (drawn to bumper tolerance).

**Procedure:**
1. Driver starts from alliance station entrance (same starting pose each run).
2. Press AutoPilot button to reef scoring branch.
3. Let it complete — do not override.
4. Spotter records: X error (mm), Y error (mm), θ error (°), Success (within ±25 mm / ±3°).
5. Driver resets to start. Repeat 10 times.

**Record:** Mean error, std dev, success count / 10.

---

### TC-02 · Vision Recovery After Obstruction

**Goal:** Confirm the estimator recovers cleanly when a tag is blocked mid-run.

**Procedure:**
1. Robot stationary at P2, facing a scoring tag.
2. Team member stands in front of the Left camera for 5 seconds.
3. Step away. Time how long until `AcceptedPoses` (Left) resumes in NT.
4. Note `/Vision/CorrectionMagnitude` spike on re-acquisition.
5. Repeat with Right camera blocked.

**Pass:** CorrectionMagnitude spike < 0.5 m within 2 robot loop cycles of re-acquisition. No runaway odometry drift.

---

### TC-03 · High-Speed Cross-Field Accuracy

**Goal:** Confirm latency compensation is correct at max drive speed.

**Procedure:**
1. Robot starts against alliance station wall (known position, tape-marked).
2. Driver floors it to the opposite wall in a straight line.
3. Stop. Check SmartDashboard reported pose vs. physical position.
4. Log `/Vision/CorrectionMagnitude` during drive — expect a U-shape: low at rest, rises at speed, falls at maximum speed as trust weights approach zero.

**Pass:** Reported pose within 15 cm of physical position after full-speed cross-field drive.

---

### TC-04 · Post-Disable Pose Recovery

**Goal:** Verify pose snaps back to correct position after being disabled (simulates between-match conditions).

**Procedure:**
1. Robot enabled, positioned at P2 (known position).
2. Disable robot for 30 seconds.
3. Re-enable. Wait 5 seconds.
4. Compare SmartDashboard pose to known physical position.

**Pass:** Pose recovers to within 10 cm within 5 seconds of re-enable.

---

### TC-05 · Spinning Heading Recovery

**Goal:** Quantify how quickly the heading estimator converges after a rapid spin.

**Procedure:**
1. Robot at P2. Record initial heading.
2. Driver executes a fast full spin (≈ 360° in < 2 seconds).
3. Stop. Time from stop to heading stabilizing within ±2°.
4. Repeat 5 times per config.

**Record:** Mean recovery time (s), max recovery time (s). Run for control and treatment when testing `VISION_SMOOTH_THETA_STDDEV`.

---

## Camera Fault Injection Tests

These tests verify system robustness under camera failure. Run during Session 4.

### FI-01 · Left Camera Removed (Single-Camera Coverage)

**Setup:** Physically unplug the Left camera USB from the coprocessor.

**Procedure:**
1. Verify `/Vision/Left/isConnected` = false in NT (SmartDashboard).
2. Run TC-01 (5 runs, not 10) — AutoPilot alignment with Right camera only.
3. Run autonomous routine positions P1–P3.

**Record:**
- Left isConnected: ✓ false
- Right acceptance rate (both cameras): ___/s
- Right acceptance rate (Left removed): ___/s
- TC-01 success rate (Right only): ___/5

**Expected:** Right camera continues accepting normally. Acceptance rate similar to a single camera's share from dual-camera baseline. AutoPilot succeeds but with more variance.

---

### FI-02 · Right Camera Removed

Symmetric to FI-01. After collecting data, run:

```bash
python3 tools/vision-analyzer/analyze.py logs/ab-testing/fi02_right_removed.wpilog
```

Open the HTML report. Check the **Field Coverage Map** section — identify which field zones lose detection coverage when the Right camera is absent.

---

### FI-03 · Partial Field-of-View Obstruction

**Setup:** Tape a strip of black construction paper over approximately 50% of one camera lens. Do not remove the camera — this tests graceful degradation without breaking calibration.

**Procedure:**
1. Run autonomous routine at P2 and P4.
2. Compare acceptance rate and σX to full-camera baseline.

**Goal:** Characterization only (no pass threshold). Document how steeply acceptance rate falls and whether σX degrades. This informs whether any redundancy is needed in camera mounting.

---

### FI-04 · Camera Reconnect Under Motion

**Goal:** Confirm the velocity-rejection filter fires on stale estimates after a reconnect.

**Setup:** During TC-03 (high-speed cross-field drive), a second team member momentarily disconnects and reconnects the Left camera USB.

**Observe:**
- Duration of connection drop (count seconds).
- Size of CorrectionMagnitude spike when camera comes back online.
- Whether `RejectedVelocity` counter increments on the first stale estimate after reconnect.

**Pass:** CorrectionMagnitude spike < 1.0 m. Velocity rejection fires. Robot does not visibly jerk or lurch.

---

## Metrics Collection Script

`tools/ab-metrics/compare.py` processes a paired set of wpilog files and prints a comparison table directly in the terminal. It reads the same wpilog binary format used by `analyze.py`.

### Usage

```bash
cd /path/to/2027Robot

# Basic comparison — prints table to stdout
python3 tools/ab-metrics/compare.py \
    --control  logs/ab-testing/baseline.wpilog \
    --treatment logs/ab-testing/smooth_theta_on.wpilog

# Label the switch under test (adds to report header)
python3 tools/ab-metrics/compare.py \
    --control  logs/ab-testing/baseline.wpilog \
    --treatment logs/ab-testing/boundary_on.wpilog \
    --switch VISION_FIELD_BOUNDARY_REJECTION

# Save results to CSV for spreadsheet comparison
python3 tools/ab-metrics/compare.py \
    --control logs/ab-testing/baseline.wpilog \
    --treatment logs/ab-testing/boundary_on.wpilog \
    --output results/boundary_results.csv
```

### Output

```
A/B Comparison: VISION_SMOOTH_THETA_STDDEV
═════════════════════════════════════════════════════════════════════
Control:   baseline.wpilog         (1247 samples — Left: 634, Right: 613)
Treatment: smooth_theta_on.wpilog  (1231 samples — Left: 621, Right: 610)

Metric                         Control    Treatment   Delta      Verdict
──────────────────────────────────────────────────────────────────────────
σX all positions               0.032 m    0.029 m    −9.4%      ✓ improved
σY all positions               0.028 m    0.026 m    −7.1%      ✓ improved
σθ all positions               0.041°     0.028°     −31.7%     ✓ PASS
Acceptance rate                84.2%      83.9%      −0.3%      ✓ neutral
CorrectionMagnitude > 1.0 m   3 /min     2 /min     −33.3%     ✓ improved
CorrectionMagnitude > 0.5 m   11/min     8 /min     −27.3%     ✓ improved
Velocity rejections (Left)     24         22         −8.3%      ✓ neutral
Boundary rejections (Left)     0          0          —          n/a
Ambiguity rejections (Left)    0          0          —          n/a
Mean XY stddev logged          0.311      0.294      −5.5%      ✓ improved
Mean θ stddev logged           52184      31.2       −99.9%     ✓ expected (smooth)
```

---

## Results Recording Template

Fill in one block per switch per session. Store completed blocks in `docs/ab-test-results/`.

```
═══════════════════════════════════════════════════════════════════
Switch:             VISION_SMOOTH_THETA_STDDEV
Date:               
Git commit:         
PhotonVision ver:   
Battery start/end:  /
Field location:     
Lighting notes:     

Baseline wpilog:    logs/ab-testing/baseline.wpilog
Treatment wpilog:   logs/ab-testing/smooth_theta_on.wpilog

compare.py output:
  σθ change:           ___% (pass threshold: ≥ 20% reduction)
  σX change:           ___% (must not regress > 10%)
  Acceptance delta:    ___%

TC-01 (10 runs):
  Control mean error:   (___mm X, ___mm Y, ___° θ)  success: ___/10
  Treatment mean error: (___mm X, ___mm Y, ___° θ)  success: ___/10

TC-05 heading recovery:
  Control mean:   ___s     Treatment mean:   ___s

FI tests run: _______________

Primary metric passed?  [ ] Yes  [ ] No
Secondary regressions?  [ ] None  [ ] Yes — _______________

Decision:   [ ] ENABLE  [ ] TUNE & RETEST  [ ] HOLD
Reviewer:   
Notes:      
═══════════════════════════════════════════════════════════════════
```

---

## Decision Rubric

| Verdict | Criteria | Action |
|---------|----------|--------|
| **Enable** | Primary metric hits pass threshold AND no secondary metric regresses > 10% | Set switch to `true` in `FeatureSwitches.java`, commit |
| **Tune & Retest** | Primary metric improves but misses threshold, OR a secondary metric regresses 10–25% | Adjust LerpTable constants or threshold; schedule a follow-up session |
| **Hold** | Primary metric shows < 5% improvement across all positions | Leave switch OFF; document reason; revisit if field conditions change |
| **Disable Candidate** | Secondary metric regresses > 25% or introduces a new failure mode | Do not enable; open an issue with the compare.py CSV attached |

When multiple switches pass independently, enable them one at a time with a brief re-run between each to confirm no unexpected interactions.

---

## Test Session Schedule

```
Session 1 — Baseline (30 min)
  · All switches OFF
  · Full autonomous routine (all 6 positions)
  · Save as: baseline.wpilog
  · Run analyze.py to confirm logging looks healthy

Session 2 — P1 Switches (45 min)
  · SW-01: VISION_FIELD_BOUNDARY_REJECTION
    - Autonomous routine → boundary_on.wpilog
    - Teleop: boundary edge check (see SW-01 steps)
    - compare.py → decision
  · SW-02: VISION_SMOOTH_THETA_STDDEV
    - Autonomous routine → smooth_theta_on.wpilog
    - TC-05 spin recovery (5 runs each)
    - compare.py → decision

Session 3 — P2 Switches + Alignment (60 min)
  · SW-03: VISION_DISTANCE_BASED_STDDEV
    - Autonomous routine → distance_stddev_on.wpilog
    - Inspect XYStddev values across positions
    - compare.py → decision
  · SW-04: VISION_TAG_RANKINGS_FILTER
    - Autonomous routine → tag_rankings_on.wpilog
    - TC-01 x 10 (control) + TC-01 x 10 (treatment) — tape measure
    - compare.py → decision

Session 4 — P3 + Fault Injection (60 min)
  · SW-05: VISION_AMBIGUITY_THRESHOLD
    - Autonomous routine (P4, P5 emphasis) → ambiguity_on.wpilog
    - FI-01 (Left removed) while switch ON
    - compare.py → decision
  · SW-06: DISABLE_VISION_ODOM_NEAR_AUTOPILOT_TARGET
    - TC-01 x 10 with switch OFF, then ON
    - Tape measure final positions
    - Decision: confirm switch stays ON
  · FI-02 (Right removed), FI-03 (partial obstruction), FI-04 (reconnect during motion)

Session 5 — Combination (30 min)
  · Enable all switches that passed individually
  · Full autonomous routine → all_approved_on.wpilog
  · TC-01 (5 runs) — confirm no regression from interactions
  · analyze.py → final dashboard
  · Document final FeatureSwitches state
```

---

## Quick Reference — NT Topics for AdvantageScope

```
/Vision/CorrectionMagnitude          — distance between vision estimate and current odometry
/Vision/XYStddev                     — XY uncertainty applied to Kalman filter
/Vision/ThetaStddev                  — heading uncertainty applied to Kalman filter

/Vision/Left/isConnected             — Left camera connection health
/Vision/Right/isConnected            — Right camera connection health

/Vision/Left/RejectedVelocity        — velocity-jump rejection counter (Left)
/Vision/Left/RejectedBoundary        — boundary rejection counter (Left)
/Vision/Left/RejectedAmbiguity       — ambiguity rejection counter (Left)
/Vision/Left/AcceptedPoses           — Pose3d[] of estimates that made it through all filters

/Vision/Right/RejectedVelocity       — (same, Right camera)
/Vision/Right/RejectedBoundary
/Vision/Right/RejectedAmbiguity
/Vision/Right/AcceptedPoses
```

In AdvantageScope, add `/Vision/Left/AcceptedPoses` and `/Vision/Right/AcceptedPoses` as **3D Poses** on the field view to visually inspect pose scatter during each test position.
