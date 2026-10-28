---
id: <AREA>-YYYY-MM-DD-<slug>     # e.g. VIS-2026-10-27-pv-throughput
title: <one line>
area: <vision | coprocessor | roborio | can | power | drivetrain | mechanisms | tools>
date: YYYY-MM-DD
status: planned               # planned | running | analyzed | decided
decision: pending             # what the team chose, once it chooses
robot_code: <branch> @ <sha>  # from RealMetadata/GitSHA in the log
logs: logs/<season>/<date>/   # logs are gitignored; say where they live
analysis: analyze.py → results.json
raw_notes: notes/<date>/notes.md
---

# <Title>

## Question

What we want to know, and why now (link the log or experiment that raised it).

## Hypothesis and pass criteria

What we expect, and what result would change what we do. Write criteria relative to the setup
(e.g. "results/s ≥ 95% of the camera's frame rate", not a fixed number).

## Setup

| | |
|---|---|
| Hardware | |
| Robot code | branch @ sha, relevant `FeatureSwitches` |
| Coprocessor / PV config | camera mode (resolution, fps, format), exposure, pipeline settings |
| Maneuver | which auto/command, or "stationary at X m". Use the same one for every run |
| Window | which part of each log is measured (e.g. enabled spans > 5 s) |
| Controls | what is held constant; how runs are ordered (interleave A/B/A/B when drift is possible) |

### Pre-test checklist

- [ ] ...
- [ ] Settings for every run written in the run table **before** enabling

## Runs

| ID | Change from previous | Log file | Bench notes (battery, restarts, anything odd) |
|---|---|---|---|
| R1 | baseline | | |

Change one variable per run. Runs added mid-session get a decimal ID (R2.1) and a line saying why.

## Results

One table, one column per run, rows = metrics. Put the signal each metric comes from in the
metric definitions below the table, not in every cell.

## Run-by-run verdicts

| Run | vs | Verdict (gain / loss / neutral) | Why (numbers) |
|---|---|---|---|

## Learnings

What we now know that we didn't, including surprises and anything that affects other areas.

## Open questions

Each one should be phrased so it can become the next experiment's Question.

## Recommendation / decision

## Reproduce

Command that regenerates every number in this file from the logs.
