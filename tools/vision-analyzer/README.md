# Vision Log Analyzer

Zero-dependency Python tool that reads AdvantageKit `.wpilog` files and produces a
self-contained interactive HTML dashboard for reviewing vision odometry health.

## What it answers

- Is this camera performing well? Is it better or worse than another camera?
- Are there calibration issues (Z-height drift, aspect ratio distortion)?
- Is the coprocessor keeping up (FPS drop, latency spikes)?
- When the robot was stationary and pointed at a tag, did we still miss it?
- How does acceptance rate correlate with robot speed?
- Which tags are we detecting well vs. poorly given where we drove?

## Output sections

| Section | What you see |
|---------|-------------|
| Camera Summary | Acceptance rate, FPS, rejection mix, mean distance per camera |
| Acceptance Rate Over Time | Rolling 3 s acceptance rate, colored by camera |
| FPS Timeline | Coprocessor frame rate over match time |
| Rejection Breakdown | Stacked bars — velocity / boundary / ambiguity rejection mix |
| Field Coverage Map | Tags colored green/yellow/red by detection frequency; robot path overlay |
| Distance & Weight Histograms | Distribution of accepted estimate distances and trust scalars |
| Velocity Correlation | Acceptance rate bucketed by motion state (if drivetrain logged) |
| Z-Height & Ambiguity | Raw pre-filter distributions (new-format logs only) |

## Usage

```bash
# Single log
python3 analyze.py path/to/match.wpilog

# All logs in a directory
python3 analyze.py logs/off-season/

# Write output to a specific directory
python3 analyze.py match.wpilog --output /tmp/

# Probe signal names only — useful for debugging format detection
python3 analyze.py --probe match.wpilog

# Filter to specific cameras
python3 analyze.py match.wpilog --cameras Left,Right
```

Output is written next to each input file as `<logname>_vision_dashboard.html`.
Open it in any browser — Plotly.js loads from CDN (internet required).

## Getting log files

**From USB drive (post-match):**
```bash
sudo mount /dev/sdc1 /mnt/frc1405
cp /mnt/frc1405/off-season/*.wpilog logs/off-season/
```

**From roboRIO over SSH:**
```bash
scp admin@10.14.5.2:/home/lvuser/logs/*.wpilog logs/
```

## Log format detection

The tool auto-detects two formats:

**Old format** (pre-June 2026 refactor): post-filter `estimatedPoses` (Pose2d[]) +
`rejectionCountVelocity` / `rejectionCountBoundary`. Shows what was accepted.

**New format** (post-refactor): raw pre-filter `rawEstimatedPoses` (Pose3d[]) plus
per-result geometry values (ambiguity, areas, pixel offsets, aspect ratios). Enables
full filter replay and per-type rejection breakdown.

## Dependencies

None. Python 3.8+ stdlib only. No pip install required.
