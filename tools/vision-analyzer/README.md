# Vision Log Analyzer

Interactive Streamlit dashboard for analyzing WPILib `.wpilog` files from the vision subsystem.

## Setup (one time)

```
python -m pip install streamlit plotly
```

## Run

```
python -m streamlit run tools/vision-analyzer/analyze.py
```

A browser window opens. Enter the path to a `.wpilog` file in the sidebar and press Enter.
The log is cached in memory — switching tabs is instant.

## Tabs

| Tab | Contents |
|-----|----------|
| **Summary** | Per-camera metrics table + stationary quality score |
| **Health** | FPS timeline, connection status, result latency distribution |
| **Acceptance** | Rolling acceptance rate over time, rejection breakdown (velocity / boundary / ambiguity) |
| **Geometry** | Distance, tag area, Z-height, ambiguity histograms |
| **Field** | Field coverage map — tag detection frequency + robot path |
| **Motion** | Acceptance rate bucketed by robot motion state (requires drivetrain speed signals) |

## Key metric: stationary quality score

```
stationary_quality = accepted / raw   (loops where |v| < 0.2 m/s AND |ω| < 0.3 rad/s only)
```

Removes motion as a confounder. > 80% is healthy; < 60% at rest points to a calibration
or hardware problem independent of robot behaviour.

## Getting log files

```bash
# From roboRIO over SSH
scp admin@10.14.5.2:/home/lvuser/logs/*.wpilog logs/
```

## Signal format

The dashboard auto-detects old vs. new log format. New-format logs (from this codebase)
include raw pre-filter data (`RawEstimatedPoses`, `RawAmbiguities`, etc.) and computed
outputs (`AcceptedPoses`, `RejectedBoundary`, etc.) under `RealOutputs/Vision/<camera>/`.

## AdvantageScope native signals

The robot also logs computed metrics viewable directly in AdvantageScope's Line Graph
and Statistics tabs:

- `Vision/<camera>/AcceptanceRatePercent` — per-loop acceptance rate (0–100)
- `Vision/<camera>/ResultsPerLoop` — raw estimates received this loop
- `Vision/<camera>/LatencyMsLatest` — coprocessor-to-robot latency of most recent result

## Probe mode (signal dump)

```
python tools/vision-analyzer/analyze.py --probe path/to/log.wpilog
```

## Legacy CLI mode

```
python tools/vision-analyzer/analyze.py path/to/log.wpilog
```

Prints a summary to stdout and writes a lightweight HTML file (summary table only).
For the full interactive dashboard, use `streamlit run` instead.
