# ADR 0001: Separate availability from quality, keep context out of the score, and stop logging artifacts and route geometry from deciding comparisons

- **Status:** Proposed. D1 (logbench half) and D2 are implemented in logbench; the robot-side changes and D3 are not. See "Implementation status".
- **Date:** 2026-09-21
- **Scope:** `VisionHealth.java` / `Vision.java` (on-robot health signals), `tools/logbench` (`core/metrics.py`, `core/composites.py`, `core/compare.py`, compare page and export)
- **Triggering evidence:** `logs/offseason/9-15/compare-akit_26-09-15_22-01-04_visionRecorder1-vs-akit_26-09-15_23-08-34_visionRecorder2.json`

## Summary

A logbench comparison of two "circle facing tag" autos reported the **Right** camera improving by
**+124%** after we changed only **Left** camera settings. We ruled out a Left/Right mix-up (see
Context, "What we ruled out") and found the +124% is produced by the metric itself. Four problems
combined, and they share one root cause: **the health score mixes different kinds of question into
one number, then counts them wrongly.**

1. "Did a tag arrive?" (availability) and "how good was the solution?" (quality) are folded into one
   product, and a single dropout is counted once *per factor*.
2. AdvantageKit logs a value only when it *changes*, and logbench averages **records** rather than
   **time**, so a strictly alternating 0/100 series always averages to exactly 50.
3. Conditions of the run (robot speed, range to the tags) sit inside or beside the score, so a
   different route reads as a different camera.
4. Comparisons are a single ratio with a fixed 10% band, with no allowance for two autos being
   different lengths on different paths.

This ADR proposes sorting every metric into **Availability**, **Quality** or **Context**; scoring
only the first two; never letting Context into a score; and fixing the mechanisms rather than
retuning constants. **No curve, weight, or threshold value is changed by this ADR.**

## Context

### What the metric is for

`VisionHealth.java` describes itself as a tuning aid: "does this camera look healthy right now, with a
tag in view and the robot held still." The multiplicative score is the product of stillness, area,
ambiguity, fps, jitter, acceptance, latency and multi-tag factors. logbench's `motion_score` reuses
six of those factors to score autonomous runs, where the robot is moving the whole time.

### What we ruled out: a Left/Right naming mix-up

`new PhotonCamera("Left")` binds to whichever camera carries that nickname in the PhotonVision UI; the
robot only supplies the mount transform. For all three 9-15 logs we compared each camera's raw pose
estimate with the fused `Drivetrain/Pose`, once with names as labelled and once assuming they are
swapped:

| Assumption | Left error | Right error |
|---|---|---|
| Names as labelled | 0.02-0.04 m, under 1 deg | 0.01-0.02 m, under 0.5 deg |
| Names swapped | 0.54-0.56 m, 20 deg | 0.56 m, 20 deg |

The swapped hypothesis is off by exactly the lateral and yaw offset between the two mounts. The names
are correct in every log.

### Finding 1: the "no tag in view" gate is right, but it is counted wrongly

Each loop, `Vision.java` builds every factor from 0.5-1 s windows, then calls
`computeCameraHealthFromFactors(connected, inputs[i].visibleTagIds.length > 0, ...)`. `visibleTagIds`
is rebuilt every loop, so on any 20 ms loop with no tag-bearing result `VisionHealth.java:108` returns
`unmeasurableCamera("No tag in view")` and **every factor and the score are logged as 0**.

**Zeroing a loop with no tag is a reasonable thing to do.** There is nothing to grade on that loop and
the live pit display should say so. It is not a bug in itself, and the gap carries real information: in
the auto windows the gate was closed 3-5% of the time. Every closed span was short (median 20 ms, i.e.
one loop; maximum 63 ms; none of 281 spans reached 100 ms), so in these runs the camera never really
lost the tags. We cannot tell from the log whether a one-to-three-loop gap is a missed detection or
delivery jitter.

The harm is in what happens *after* the zero is logged:

- **One dropout is counted six times.** The gate zeroes every factor at once, and `motion_score`
  multiplies six factor averages, so each carries the same ~4% penalty: 0.96^6 = 0.78, a ~22% score
  loss for a 4% dropout. This holds even after averaging is fixed:

  | Motion score, gate handling only | Each factor time-averaged | Dropout counted once |
  |---|---|---|
  | Run 1 Left | 33.4 | 42.2 |
  | Run 1 Right | 30.8 | 37.0 |
  | Run 2 Left | 36.5 | 46.8 |
  | Run 2 Right | 33.9 | 39.3 |

- **It merges two different questions.** *Availability* ("how often do I have a tag?") and *quality*
  ("when I do, how good is the solution?") have different causes and different fixes. A camera that
  drops out 20% of the time but is otherwise perfect, and a camera that is always present but noisy,
  can score identically. A phone is the analogy: dropped-call rate and audio quality are separate
  numbers, and nobody multiplies the dropped-call penalty into every audio metric.
- **Its timescale is one 20 ms loop**, a weak basis for wiping out a whole second of quality
  measurements.

### Finding 2: change-only logging plus a record-mean

AdvantageKit writes a record only when a value changes (e.g. Right `Health/MultiTagRatio` has one
record for the entire 110 s run). `logbench/server/core/metrics.py:49` (`_mean_in_window`) averages the
*records* in the window. For a two-state series that strictly alternates 0,100,0,100 the record-mean
is 50 by construction, independent of how long the value sat at 100.

We reproduced all 24 factor values in the comparison JSON to within 0.1 point using this exact
computation, then recomputed with a time-weighted (sample-and-hold) mean:

| Factor (run 1, Right) | JSON / record-mean | Time-weighted, as logged | Tag-in-view only (proposed) |
|---|---|---|---|
| ambiguity | 50.00 | 96.4 | 100.0 |
| latency | 50.00 | 96.4 | 100.0 |
| multi-tag | 50.00 | 96.4 | 100.0 |

The middle column is the gate's duty cycle showing through: 96.4 is "fraction of loops with a fresh
tag result", not ambiguity, latency or multi-tag ratio.

**Correction to an earlier explanation:** we first described this as a *median*. The code takes a
*mean*, over records. It is the same phenomenon with the precise mechanism given above.

**The multi-tag boolean itself is not the problem and is not being smoothed away.** The per-result
"2+ tags" flag is averaged over 1 s into `MultiTagRatio` (a fraction like 0.94), which is logged
un-gated and is real information; Right was genuinely 100% multi-tag in run 1. The 0/100 flicker on
`MultiTagRatioPercent` is the *output* of the gated function, not that flag.

### Finding 3: tag area is dominated by range (a condition, not a health signal)

Tag area is a legitimate quality signal (a camera that sees smaller tags at the same range has worse
optics, focus or exposure), but the raw value mostly reports how close the route brought the robot:

- Within a run, log(area) vs log(range) has r = -0.99 (slope -1.7; pinhole physics predicts -2).
- Median range dropped from 1.89 m to 1.56 m (Left) and 1.86 m to 1.61 m (Right) between runs,
  because the two autos took different paths (window 48.7 s vs 24.8 s).
- Raw median tag area rose 38% on Left (1.46 to 2.01). After scaling each result to a common range
  (`area * (d/d0)^2`) it *fell* 6% (2.76 to 2.59 per-tag).

**Update: most of that range difference was where the robot was hand-placed.** The CircleFacingTag
auto orbits *wherever the robot starts*, so placement shifts the whole circle. Across nine logged
runs the start distance to tag 10 ranged from 1.53 m to 1.77 m; run 1 started at 1.77 m and run 2 at
1.53 m, a 24 cm difference against the ~30 cm change in median range. Both cameras moved together
(raw median area +38% Left, +33% Right; range -18% and -13%), so the "Left improved, Right neutral"
labels came from the +/-10% cut falling between +11.9% and +8.7% on the area factor, not from a
Left-specific effect. A matched-range test found none: at the same range the Left/Right area ratio
changed by +0.4% on average (every bin within +/-2%), and the difference-in-differences on
range-normalised area was -0.7% with a 95% CI of -10% to +10%. That CI is wide enough that a small
Left-only effect cannot be excluded, and tag *area* is the wrong instrument for an exposure change
anyway (exposure changes whether a tag is detected, not how large it is).

The auto now drives to a fixed spot in front of the tag before orbiting (see Implementation status),
which removes this cause for this test. D3.3 (range normalisation) stays in scope, but its job
narrows: guarding comparisons between *different* routes and autos, where range will differ by
construction, rather than rescuing a test that should hold range constant.

### Finding 4: single-point comparison with a fixed threshold

`compare` reports one ratio per metric and calls it improved/regressed at +/-10%. There is no
uncertainty estimate, no notion of how many independent observations sit behind each side (48.7 s vs
24.8 s), and no check that the two runs sampled the same range or speed conditions.

## Decision

Fix each mechanism where it lives. In priority order:

### D1. Sort every metric into Availability, Quality or Context, and score only the first two

The test for a category is **whether a low reading tells you what to fix**. Two metrics belong in
different categories if their remedies differ.

| Category | Question it answers | Metrics | A low reading points to |
|---|---|---|---|
| **Availability** | Does usable data arrive when it should? | connection uptime, FPS, latency, **tag-in-view fraction**, **longest gap**; later: detection rate vs expected (below) | connection, mount and field of view, exposure, lighting, USB or network |
| **Quality** | When a tag is seen, how good is the solution? | area, ambiguity, jitter, acceptance, multi-tag ratio | calibration, focus, tag threshold, decimate |
| **Context** | What conditions was this measured under? **Never scored.** | stillness, median range to tags, robot speed | nothing. It explains the other numbers |

Rules that follow:

1. **Context never enters a score.** It is displayed beside the scores so a reader can see that two
   runs were driven differently, and it is excluded structurally (a test asserts no scored composite
   depends on a Context metric), not by convention. Context metrics get no improved/regressed verdict:
   "less range" is neither better nor worse.
2. **Availability is counted once, as availability.** Tag-in-view fraction (fraction of time a tag-bearing
   result was in view) and longest gap are reported as their own metrics. The 20 ms "no tag" zero is
   kept for the live display but is no longer multiplied into every factor.
3. **Quality factors are measured only over the times a tag was in view.** Conditioning on tag-in-view is
   equivalent to the robot's own un-gated windowed value (recomputed factors match the robot's logged
   ones to 0.000 points on every loop where the gate was open), so this needs no new constants.
4. **Availability is not one metric.** Tag-in-view fraction alone is route-dependent (facing away from
   the tags lowers it without any camera fault) and hides the shape of gaps (fifty 20 ms gaps and one
   1 s gap look identical, but the long gap is far worse for odometry drift). It is the right *first*
   availability metric because it can be computed from existing logs today, and the UI states that it
   depends on the route. Longest gap is added beside it for the shape.
5. **Headline numbers are per category, side by side, not one product.** The blended product is what
   hid which axis moved in the +124% result. `availability_score` and `quality_score` are each shown.
   An optional `health_score = availability x quality` (still excluding Context) exists for
   convenience but is secondary. Each category gets its own verdict in a comparison.
6. **Composites that mix categories, or include Context, are kept but marked legacy.** `motion_score`
   (mixes availability and quality factors) and `still_score` (includes stillness) stay registered so
   existing scripts and exports keep working, and are labelled as such.
7. **Categories are defined by remedy, not by data.** We do not move a metric between categories
   because a particular log looks better or worse.

On the robot (Java, follow-up to this ADR): keep zero-when-no-tag for the live display; additionally
log `Health/TagInViewFraction` and `Health/LongestGapMs` as their own signals, so logs record
availability natively instead of relying on logbench to derive it. Until then logbench derives both
from the raw per-loop results already in every log, so existing logs are covered. Because
`Vision.periodic()` computes health after the `Logger.processInputs()` replay boundary, Java changes
can also be applied to old logs by replay (`./gradlew simulateJava`).

**Future work (not part of this ADR's implementation): detection rate against expected visibility.**
The route-independent availability metric is *tags detected / tags that should have been visible*.
"Should have been visible" is computable from the fused pose, the camera mount transform and
intrinsics (field of view), and the tag layout. It answers "of the tags this camera could see, how
many did it see?", so a robot facing away from the tags no longer looks like a camera fault. It is
documented here and deliberately **not** built now. Things to resolve when it is built: fused-pose
error near the field-of-view edge, tag occlusion by field elements or the robot itself, frame/pose
timestamp alignment (latency), and how to treat tags at extreme viewing angles that no camera could
detect. The same expected-visibility idea would also give a fairer multi-tag metric ("multi-tag rate
*given two or more tags expected in view*"); multi-tag is filed under Quality for now with the caveat
that it partly reflects route geometry.

### D2. logbench: time-weight every windowed aggregate

`_mean_in_window` and any other window statistic over a logged series must use sample-and-hold
(time-weighted) semantics: carry the last value from before the window in, weight each value by how
long it held, and never average records. Array-valued signals that AdvantageKit de-duplicates
(`RawTagCountsPerResult`) get the same hold treatment. Required regression test: a signal at 100 for
90% of the window that alternates 0/100 must aggregate to 90, not 50.

### D3. logbench compare: block statistics, uncertainty, and range normalisation

1. **Blocks, not windows.** Split each window into fixed 2 s blocks and compute every metric per
   block. Window length then only affects how many blocks exist, so a 49 s and a 25 s auto are
   directly comparable. Do not compare counts or sums across windows.
2. **Uncertainty and a three-state verdict.** Bootstrap over blocks for a 95% CI on the change. Report
   `improved` / `regressed` only if the CI excludes zero *and* the effect exceeds the noise floor;
   report `inconclusive` when the CI straddles the noise floor; otherwise `neutral`. The noise floor
   stays at the current 10% until we measure it from repeated same-config autos (see Validation),
   rather than being tuned against this comparison.
3. **Range-normalised area in the Quality score.** Score the area factor at the area the camera would
   have reported at a fixed reference range `d0 = 2.0 m` (`area * (d/d0)^2` per result). `d0` shifts
   the level, not the ranking (see sensitivity below), and is a physical convention, not a fitted
   parameter. Keep the raw area factor available as a separate diagnostic.
4. **Covariates shown, overlap checked.** Every comparison shows per-run window length, median range
   and robot speed side by side (the Context category from D1 carries this), and warns when the two
   runs' range distributions barely overlap. Confounders are surfaced, not silently absorbed.

### What this ADR does not change

No LerpTable, weight, threshold, `TARGET_FPS`, or factor formula. If, after D1-D3, a factor still
looks wrong, that is a new ADR with its own evidence.

## How this would have changed the 9-15 comparison

Motion score, run 1 to run 2, 24 blocks vs 12 blocks. CI is a 95% block bootstrap. The tag-in-view-only
factors were recomputed from the robot's own un-gated `Scoring*` signals; on loops where the gate was
open they reproduce the robot's logged factors to 0.000 points, so the recomputation is faithful.

| Camera | Current (as reported) | D1 + D2 (raw area) | D1 + D2 + D3 (range-normalised) |
|---|---|---|---|
| Left | 7.4 to 7.9 (**+7%**, neutral) | 42.8 to 46.7 (+9%, CI -4..+24) | 39.8 to 39.3 (**-1%**, CI -4..+2) |
| Right | 3.6 to 8.0 (**+124%, improved**) | 37.7 to 39.1 (+4%, CI -8..+16) | 35.3 to 33.8 (**-4%**, CI -9..+1) |

- The Right "+124%" is entirely the two 50.0 placeholders (multi-tag 50 to 83, ambiguity 50 to 61
  multiplied through). With honest factors the score is about 40 in both runs; the absolute level is
  now a plausible reading for a camera with tags locked, instead of about 7.
- Availability, reported on its own: tag-in-view fraction was 95.5% / 96.4% (run 1 Left / Right) and
  95.0% / 97.1% (run 2), i.e. no availability change, and all gaps were 1-3 loops. Separating it shows
  that neither camera had an availability problem in either run.
- Sensitivity to `d0` (1.5 / 2.0 / 2.5 / 3.0 m): Left -2 / -1 / -1 / -1%, Right -5 / -4 / -4 / -4%.
  Every CI includes zero. The conclusion does not depend on the reference range chosen.
- The range confound is real but D3.3 is not the main effect: fixing the gate accounting and the
  averaging (D1 + D2) already removes the false +124%. Range normalisation moves both cameras from
  "slightly better" to "no change".

**What the corrected data does show:** multi-tag fraction fell on *both* cameras (Left 98% to 94%,
CI on change -8.6..-0.6%; Right 100% to 94%, CI -11.2..-1.9%), while median range fell 14-16%. That
is a shared shift, not a Left-specific one, and is consistent with two different routes rather than a
camera effect. FPS did not change (Left 84.5 to 84.3; Right 73.9 to 72.7, CIs include zero).

**What it means for the Left exposure change:** neither the old nor the corrected metric shows any
effect of it. That is not evidence it did nothing: both runs already had 94-100% multi-tag solves at
1.5-2 m, so there was little headroom for exposure to help. This metric is insensitive to it. The
vision recorder frames (before/after brightness, missed detections at range) are the right instrument
for exposure, and the `visionRecorder1` frames we have are the **Right** camera (default port 1181),
so the Left frames have not yet been examined.

## How this guards against overfitting

- Every change is justified by a **mechanism** we can point to in code or physics (a gate counted
  six times, a record-mean of change-only data, the inverse-square scaling of tag area), not by
  nudging a value until the verdict looks right. The ADR's headline result is "no measurable
  difference", not a rescued improvement.
- Category membership is decided by the "different remedy" test, before looking at any run's numbers.
- `d0` is a convention, and the result was checked across 1.5-3.0 m.
- The noise floor is not being tuned on this pair. It is calibrated separately (below).
- Only one pair of runs was used to *find* the problems. The validation plan tests them on data the
  fixes were not developed against.
- The physical range scaling is approximate (measured exponent -1.7 vs -2). A distance-binned
  comparison (compare medians within 0.5 m range bins, average over bins both runs share) needs no
  physics and should be run as a cross-check before D3.3 is trusted; a large disagreement between the
  two would mean the normalisation is not adequate and needs replacing, not tuning.

## Consequences

**Good**
- A comparison can no longer be won or lost by a logging artifact; the same signal aggregates the same
  way regardless of how often it changes.
- You can see *which axis* moved: a dropout problem and a noisy-solution problem are different
  numbers with different fixes, and route/speed conditions sit beside them instead of inside them.
- Autos of different length and route become comparable through blocks and covariates; verdicts
  carry uncertainty and can say "inconclusive".

**Costs / risks**
- Historical `motion_score` and any stored baselines change; earlier comparisons must be re-read with
  that in mind. Absolute values move from single digits to tens. `motion_score` / `still_score` remain
  available as legacy composites.
- The JSON export gains a category on every metric and a new `context` verdict value, so its schema
  version moves from `v1` to `v2`.
- Robot-side `TagInViewFraction` / `LongestGapMs` need a deploy for future logs (old logs are covered
  by logbench's derivation and by replay).
- Block bootstrap on 12 blocks gives wide intervals. That is the honest answer for a 25 s auto, but
  it will produce more `inconclusive` verdicts than the old +/-10% rule did. Several similar autos per
  configuration is the way to tighten them.
- Range normalisation removes real information if a change genuinely alters detection range; keep the
  raw area diagnostic beside it.

## Alternatives considered

- **Keep the per-loop zero and just fix the averaging (D2 only).** Rejected as sufficient: the dropout
  would still be counted six times (0.96^6 = 0.78) and availability would stay buried in every factor.
- **Window the gate over 1 s** (the earlier D1 in this ADR). Rejected: it hides real dropouts instead
  of reporting them, and still leaves availability and quality as one number.
- **One blended score with weights.** Rejected: a product of everything hides which axis moved, and
  weights are exactly the kind of knob that gets tuned to the data.
- **Switch the aggregate from mean to median.** Rejected: on a strictly alternating series the median
  is arbitrary (it flips to 0 or 100 on one record). It hides the mechanism rather than removing it.
- **Retune the LerpTables until this run "looks right".** Rejected: a direct route to overfitting, and
  the curves are not the cause.
- **Reimplement the factor curves in logbench from raw signals.** Rejected: `metrics.py` documents that
  `nt_client.py` did exactly this and silently drifted from `VisionConstants.java`. Read the values
  the robot logs, and condition them on tag-in-view instead.
- **Require identical autos before comparing.** Rejected: autos will not be identical in practice;
  the goal is to extract signal despite that.

## Validation plan (before promoting from Proposed)

1. Unit tests: 90%-duty 0/100 signal aggregates to 90 (D2); carry-in of a pre-window value; an
   all-`None` series stays `None`, not 0; no scored composite depends on a Context metric (D1).
2. Replay the three 9-15 logs with the Java change and confirm the robot-logged `TagInViewFraction`
   agrees with logbench's derived value.
3. **A/A calibration:** collect at least three autos of the *same* route and configuration; the spread
   of block-level scores across them sets the noise floor used in D3.2, replacing the inherited 10%.
   In this pair, run 1's first half vs second half differ by up to 8% (Right), which suggests 10% is
   about right, but that is a single draw.
4. **Held-out check:** run the corrected comparison on logs not used above (9-15 run 3 differs only in
   AprilTag decimate 3 to 1; the 9-19 pose-strategy logs) and confirm results are stable and
   explainable, and that the binned-range cross-check agrees with `area * d^2`.
5. Confirm the false positive is gone on the trigger pair (Right no longer `improved`) *and* that
   the method can still detect a known-large effect (e.g. a deliberately unplugged camera or a
   covered lens) as `regressed`, so we know we did not just make the metric blind.

## Open questions

- Should tag-in-view fraction and longest gap feed `availability_score`, or only be reported? (The
  first implementation scores tag-in-view, FPS and latency and reports longest gap alongside.)
- Jitter physically rises with motion. It is filed under Quality but excluded from `quality_score`
  for the same reason `motion_score` excludes it; is there a motion-aware treatment, or should it stay
  a still-only diagnostic?
- What is the right block length? 2 s was chosen to give roughly 110 camera results per block (about
  55 results/s per camera); shorter blocks give more of them but more autocorrelation.
- Should the comparison support explicit covariate-matched sampling (compare only blocks in an
  overlapping range/speed band) in addition to showing the covariates?

## Limitations of the evidence

- One pair of runs with different routes; the corrected numbers are a retrospective computation, not
  a replay of fixed Java.
- The analysis scripts were ad hoc and are not committed; the D2 regression tests are what make the
  central claim (change-only + record-mean) permanent.
- Which physical camera the recorder frames come from was inferred from tag reprojection (Right
  clearly closer than Left, neither exact) plus the setup doc's port table; treat as likely, not
  proven.

## Implementation status

As of 2026-09-21, in `tools/logbench`. Nothing on the robot (Java) has changed yet.

**Done**
- **D1 (logbench half).** `core/categories.py` defines the three categories and the scored/unscored
  rule. Every metric and composite declares a category. New availability metrics `tag_in_view_pct`
  and `longest_gap_ms` and new context metrics `range_median_m` and `speed_mean_mps` are derived
  from the raw log, so existing logs are covered without a deploy. New composites
  `availability_score`, `quality_score` and `health_score`; `motion_score`, `still_score` and
  `score_pct` are filed as legacy. Context metrics get verdict `context`, never a judgement.
  Whole-run metrics appear once, as camera `All`. The compare page lays availability and quality
  out as score cards with A-vs-B bars, context beside them as a dashed, unscored card, then a
  detail table per category with each metric's plain-language meaning; the HTML and JSON exports
  carry the same categories (JSON schema is now `logbench.compare/v2`).
- **D2.** Health-factor averages are time-weighted (`signals.hold_intervals`) and cover only the
  times a tag was in view. Both are pinned by tests, including the 90%-duty regression test, and
  both tests were checked to fail when the behaviour is removed. A structural test asserts no
  availability / quality / overall composite reaches a context metric, directly or transitively.

**On the 9-15 pair, with only the above** (auto windows, run 1 to run 2):

| | Left | Right |
|---|---|---|
| Availability score | 80.5 to 80.3 (neutral) | 71.2 to 70.6 (neutral) |
| Quality score | 52.3 to 58.6 (**improved**) | 52.0 to 55.8 (neutral) |
| Tag in view | 95.5% to 95.0% | 96.3% to 97.1% |
| Median range (context) | 1.90 m to 1.56 m | 1.87 m to 1.62 m |

The Right "+124%" is gone. The independently computed figures earlier in this ADR are reproduced
(tag-in-view 95.5 / 96.3 / 95.0 / 97.1; run 1 Left health 42.1 vs 42.2).

**Known gaps in what is implemented** (each is a deliberate deferral, not an oversight):
- **Left quality still reads "improved" (+12%).** It is the raw area factor rising because the
  route got closer, which is exactly what D3.3 (range normalisation) removes and the ADR predicts
  (-1% once normalised). Until then the page shows the median-range change right beside it and the
  area description says it is range-dependent, but the headline quality number is not yet trustworthy
  across different routes.
- **Verdicts are still the fixed +/-10% rule (D3.2 not done).** It calls a one-loop (22 ms)
  difference in `longest_gap_ms` "improved". The metric description says differences of a loop or two
  are noise, but the chip does not. Block bootstrap intervals will fix this properly; a per-metric
  absolute dead band was not added because it would be a tuned constant.
- **Jitter** is filed under quality but excluded from `quality_score` and from the default metric
  set, because it rises with motion.

**Robot code, not yet run on a robot:** `CircleFacingTagCommand.atFixedStart` drives to a fixed spot
1.75 m straight out from tag 10 (the 9/5 baseline's start), then orbits that spot; the circle is
centered on the fixed spot, not on where positioning settled. It logs `CircleFacingTag/Phase`
("Positioning", "Circle", "Done"). It compiles against the project's dependencies (checked with
`javac`; Gradle would not start in the authoring environment) and the start-pose geometry has a
JUnit test that has not been run. Open: logbench cannot yet window a comparison to the "Circle"
phase, so the positioning move (whose length depends on placement) is still inside the auto window
until it can.

**Not started**
- Robot-side `Health/TagInViewFraction` and `Health/LongestGapMs` logging (Java), and replaying old
  logs through it to confirm they agree with logbench's derived values.
- D3: 2 s blocks and bootstrap CIs, three-state verdict, range-normalised area, covariate-overlap
  warning, distance-binned cross-check.
- **Detection rate against expected visibility** (see D1, future work). Deliberately deferred.
- A/A calibration of the noise floor, and the held-out and known-large-effect validation checks.
