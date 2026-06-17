# Vision Log Analyzer

Interactive Streamlit dashboard for analyzing WPILib `.wpilog` files from the vision subsystem.

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run analyze.py
```

A browser window opens. Drop a `.wpilog` file in the sidebar or enter a path, select a time range, and click **Analyze**.

## CLI usage

```bash
# Probe mode — dump all signal names and types
python analyze.py --probe path/to/log.wpilog

# Legacy mode — write a summary HTML file
python analyze.py path/to/log.wpilog
python analyze.py path/to/log.wpilog --output /tmp/reports/
```

## Tabs

| Tab | Contents |
|-----|----------|
| **Summary** | Per-camera metrics table + stationary quality KPI |
| **Health** | FPS timeline, connection status, result latency distribution |
| **Acceptance** | Rolling acceptance rate over time; rejection breakdown by reason |
| **Geometry** | Distance, tag area, Z-height, ambiguity histograms; single vs multi-tag |
| **Field** | Field coverage map — tag detection frequency + robot path |
| **Motion** | Acceptance rate bucketed by robot motion state |
| **Signals** | Raw signal index — searchable tree of every signal in the log (for debugging) |

## Adding a tab

1. Create `vision_analyzer/tabs/my_tab.py` with:
   ```python
   LABEL = "My Tab"   # shown in st.tabs()

   def render(ctx: dict) -> None:
       import streamlit as st
       # ctx keys: metrics, signals, fmt, cameras, committed, duration
       ...
   ```
2. Append the module to `TABS` in `vision_analyzer/tabs/__init__.py`:
   ```python
   from . import my_tab
   TABS = [..., my_tab]
   ```

The `ctx` dict contains:
- `metrics` — list of per-camera metric dicts (output of `compute_camera_metrics`)
- `signals` — raw `{signal_name: [(timestamp, value), ...]}` dict from the parser
- `fmt` — `'new'` or `'old'` (log format auto-detected)
- `cameras` — list of camera name strings
- `committed` — `(float, float)` selected time window in relative seconds
- `duration` — total log duration in seconds

## Package layout

```
vision_analyzer/
    constants.py        — field geometry, tag positions, camera colors
    parser.py           — WPILog binary parser
    metrics.py          — compute_camera_metrics, signal discovery, chart helpers
    robot.py            — roboRIO SSH download
    app.py              — Streamlit app (_streamlit_app, sidebar, time-range selector)
    cli.py              — probe_signals, _write_legacy_html, _cli_main
    tabs/
        __init__.py     — TABS registry (ordered list of tab modules)
        summary.py      — key metrics table
        health.py       — FPS, connection, latency
        acceptance.py   — rolling acceptance rate, rejection breakdown
        geometry.py     — distance, area, Z-height, ambiguity
        field_coverage.py — field map
        motion.py       — velocity-bucketed acceptance
        signals_browser.py — raw signal index (searchable)
```

## Key metric: stationary quality score

```
stationary_quality = accepted / raw   (loops where |v| < 0.2 m/s AND |ω| < 0.3 rad/s only)
```

Removes motion as a confounder. >80% is healthy; <60% at rest points to a calibration or hardware problem.

## Getting log files

```bash
# From roboRIO over SSH
scp lvuser@10.14.5.2:/home/lvuser/logs/*.wpilog logs/
```

Or use the **Download from Robot** button in the sidebar (requires `paramiko`).

## TODO
- export high level vision analysis data to .csv and .md files for quick analysis and visual comparison.
- identify how to compare non-identical runs (same auto routine but vastly different behavior because of PID/Vision changes). filter out noise and focus in on camera/vision differences.
- accepted poses over time chart, with average accepted poses per second (do we already have this metric?). what is a useful bucket? 1s?
- It would be potentially insightful to show velocity rejected poses on the field tab so i can consider if our velocity threshold is too conservative.
- It would be helpful to add a table to ambiguous and out of bounds estimates that were rejected. shown on a field (not the same field or able to toggle off) can help me better understand why they were rejected.
- Left camera is out of focus likely. right camera is sharper.
- figure out what this is exactly: Multi-tag pose standard deviation over the last 100/100 samples
- would it be useful to give a left and right camera "trust" or weight output over time? would it be useful to graph the standard deviations over time?
