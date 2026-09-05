# Vision Analyzer vs. Match Player — what question each one answers

## Executive summary

They're not two views of the same data — they answer two different classes of question,
computed from different signal families:

- **`vision-analyzer`** answers *"was vision good over the whole match/log, in aggregate,
  and why not?"* It's a statistics tool: it walks every sample in a `.wpilog`, buckets and
  aggregates it (acceptance rate %, FPS mean/min, latency histogram, stddev-over-time,
  acceptance-by-motion-state), and gives you numbers and distributions you can compare
  log-vs-log (it has a built-in A/B diff mode). This is the tool for **"is our vision
  pipeline healthy, and did P2-filter-change X make it better or worse?"**

- **`match-player`** answers *"what was happening at this specific moment, and can I watch
  it happen?"* It's a scrubbable 60fps timeline: robot pose, camera-estimated poses, visible
  tags, and a live per-camera 0–100 health score (with 8 named factors: stillness, tag area,
  ambiguity, FPS, jitter, acceptance, latency, multi-tag) all moving together against a field
  view. This is the tool for **"why did the pose estimate glitch at 1:47, and which camera
  caused it?"**

Put differently: vision-analyzer is the *report card*; match-player is the *instant replay*.

## Evidence

### Different source signals

- vision-analyzer's `metrics.py` (`compute_camera_metrics`) reads raw per-loop vision
  signals directly: `rawEstimatedPoses`, `rawAmbiguities`, `rawSumTagAreas`,
  `PoseStdDevXMeters`, `rejectionCount*`, `estimateTimestampsSec`, etc. — the low-level
  telemetry `Vision.java` logs every loop, pre-aggregation.
- match-player's `camera_health.py` reads a *different, higher-level* signal family:
  `Vision/<cam>/Health/ScorePercent` and `Vision/<cam>/Health/<Factor>Percent`
  (`StillnessPercent`, `AreaPercent`, `AmbiguityPercent`, `FpsPercent`, `JitterPercent`,
  `AcceptanceRateFactorPercent`, `LatencyPercent`, `MultiTagRatioPercent`) — pre-computed by
  `VisionHealth.java` on the robot as a single calibration-diagnostic score, plus
  `Drivetrain/Pose` and `AcceptedPoses` for the field view.
- **Consequence:** a log recorded before `VisionHealth.java`'s scoring existed has *nothing*
  for match-player to show (it explicitly warns `"No Vision/*/Health/* signals in this
  log... record a fresh log to replay health here"`), but vision-analyzer works fine on it
  since it only needs the raw per-loop signals every log has always had.

### Different notion of "camera health"

- vision-analyzer has no single health score. It gives you separate, independent metrics:
  acceptance rate, FPS mean/min, connection uptime, latency distribution, rolling pose
  stddev (a proxy for solve repeatability, explicitly modeled on PhotonVision's
  multi-tag-stddev panel), and "stationary quality" (acceptance rate with motion held
  constant, to separate a camera-intrinsic problem from a motion-blur problem).
- match-player's health score is a single 0–100 number per camera, explicitly documented in
  its own code as **"a calibration diagnostic, not a match-accuracy score"** — it's the
  eight factors above multiplied together, meant for spotting a mis-mounted/misconfigured
  camera while watching it live or in replay, not for judging match performance.

### Odometry / pose-quality questions

- **"How good was our odometry/pose estimate over the match?"** → vision-analyzer:
  acceptance rate %, rejection breakdown (velocity/boundary/ambiguity), pose stddev over
  time, acceptance-rate-by-motion-state chart, field-coverage map of accepted vs. rejected
  poses. Also the only one of the two with A/B log comparison, for "did this filter change
  help."
- **"Why was odometry wrong at this specific timestamp?"** → match-player: scrub to that
  second and watch the fused odometry marker, each camera's estimated pose, which tags were
  visible, and each health factor's value all at once — the field panel plots accepted vs.
  rejected-by-reason poses spatially, and the per-camera trend panel shows the factor curves
  around that moment.

### Tooling / mechanics (secondary, but real)

- vision-analyzer is a Streamlit app: every interaction is a server round-trip; fine for
  aggregate charts, was actually unusable for smooth playback (this is *why* match-player
  exists — see its README: the old Streamlit-based replay tab took seconds per frame on
  ~135k points; match-player's browser-side playback is 0.09ms/frame on the same data).
- match-player is a Vite/React/TypeScript front end + FastAPI backend, exportable as a
  single offline HTML file; the player core itself is metric-agnostic (camera health is
  just one `server/specs/*.py` builder) — a shooter or swerve-module replay view would be
  another builder, no front-end change.

## Bottom line

Use **vision-analyzer** first when the question is about overall trends, comparing two
configurations/logs, or hunting for a systemic problem across a whole match. Drop into
**match-player** once you've found a moment (or a camera) that looks bad and need to see
*what the robot actually saw* at that instant.
