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

<!-- Write this for a team member who has never read one of these. The first screen should tell
     them what we're doing and what we found, without scrolling into the details. -->

## In short

Three or four sentences: the problem, what we're trying, and the answer so far ("not run yet"
is fine). Someone who reads only this paragraph should know the result.

## What we're testing

A numbered list of the questions, in plain words, each with the runs that answer it:

1. **<Question>?** <One sentence on how we'll tell.> *(R1–R3)*

A setting **passes** if:

| Check | Pass if | Why |
|---|---|---|
| | | |

Write criteria relative to the setup (e.g. "results/s ≥ 90% of the camera's fps", not a fixed
number).

### Words used here

Define every term a new student wouldn't know (e.g. decimate, results/s, dropped frame) and any
short form used in the tables.

## The runs

What every run has in common (maneuver, camera mode, what to keep closed), in one or two lines.
**Write each run's settings in this table before enabling.**

| Run | What changes | What it checks | Status |
|---|---|---|---|
| R1 | baseline | | to do |

Change one thing per run. A run added mid-session gets a decimal ID (R2.1) and a line saying why.
Interleave A/B/A/B only when the expected effect is about as small as the run-to-run drift.

### Before the session

- [ ] Code deployed (branch @ sha) with the logging this experiment needs
- [ ] ...

## Results

One table, one column per run, rows = metrics. Bold the rows the pass criteria use.

### Verdicts

| Run | Compared with | Verdict (gain / loss / same) | Why (numbers) |
|---|---|---|---|

### What we learned

What we now know that we didn't, including surprises and anything that affects other areas.

## Next experiment

Open questions, each phrased so it can become the next experiment's question. Link the new
experiment once it exists.

## Reproduce

The command that regenerates every number in this file, and a table of run → log file.

---

## Background

<!-- Source-code reading, option surveys, metric definitions, logging details. Put each in a
     <details> block so the page stays short. -->
