# Running and Watching a Real-Robot Log Replay

AKit replay lets you take a `.wpilog` file recorded on the real robot and run
the current code against it on your laptop — hardware inputs are fed from the
log, all subsystem logic re-executes live, and the output is a new `_sim.wpilog`
you can open in AdvantageScope side-by-side with the original.

---

## How the pieces fit together

**One-shot replay** (`replayLog` VS Code task — use this most of the time):
```
.vscode/tasks.json  (VS Code "replayLog" task)
    └─ ./gradlew simulateJava   (AKIT_LOG_PATH env var set)
           └─ Robot()  →  setUseTiming(false)
                       →  WPILOGReader(logPath)
                       →  WPILOGWriter(*_sim.wpilog)
           └─ Gradle exits cleanly when replay finishes
```

**Continuous live-reload** (`replayLogWatch` VS Code task — for active tuning):
```
.vscode/tasks.json  (VS Code "replayLogWatch" task)
    └─ ./gradlew replayWatch   (AKIT_LOG_PATH env var set)
           └─ ReplayWatch.main()  →  runs simulateJava once
                                  →  watches src/ for changes
                                  →  re-runs simulateJava on every save
                                  →  runs forever until Ctrl+C
```

> **Why two tasks?** `replayWatch` is a file-watcher daemon — it never exits
> on its own. For a one-click "replay and done" workflow, calling `simulateJava`
> directly is cleaner. Use `replayLogWatch` when actively iterating on code
> against a fixed log.

---

## Prerequisites

- AdvantageScope installed and on your PATH (or launched from your
  Applications folder — the binary location doesn't matter for replay itself)
- Gradle build tools available (`./gradlew build` succeeds)
- A `.wpilog` AKit log from the real robot in the `logs/` tree

> The log used in the steps below:  
> `logs/offseason/6-13-26/akit_26-06-13_17-05-06.wpilog`

---

## Step 1 — Verify the VS Code task targets the right log

Open `.vscode/tasks.json`. The `replayLog` task already points to the
offseason log:

```json
{
    "label": "replayLog",
    "type": "shell",
    "command": "./gradlew",
    "args": ["replayWatch"],
    "options": {
        "env": {
            "AKIT_LOG_PATH": "logs\\offseason\\6-13-26\\akit_26-06-13_17-05-06.wpilog"
        }
    }
}
```

To replay a different log, change `AKIT_LOG_PATH` to any path relative to the
project root (or use an absolute path).

---

## Step 2 — Open the source log in AdvantageScope first

Before starting replay, open the original log so you have something to
compare against:

1. Launch AdvantageScope.
2. **File → Open Log** → select
   `logs/offseason/6-13-26/akit_26-06-13_17-05-06.wpilog`.
3. Set up the views you care about (pose, shooter speed, vision, etc.) and
   leave AdvantageScope open.

> Do NOT close this log during replay — keeping it open is fine. AdvantageScope
> no longer triggers accidental replay mode; the robot code now only reads
> `AKIT_LOG_PATH` from the environment, not from AdvantageScope's temp file.

---

## Step 3 — Run the replay task

In VS Code:

```
Ctrl + Shift + P  →  Tasks: Run Task  →  replayLog
```

Or from the terminal at the project root:

```
AKIT_LOG_PATH=logs/offseason/6-13-26/akit_26-06-13_17-05-06.wpilog ./gradlew simulateJava -x test
```

No simulation GUI opens — replay runs headlessly at full CPU speed. A typical
2-minute match log completes in a few seconds. Gradle exits with `BUILD
SUCCESSFUL` when done.

> The sim GUI and DriverStation extensions are automatically skipped when
> `AKIT_LOG_PATH` is set (enforced in `build.gradle`). AKit throws a hard
> error if those extensions are present during replay.

---

## Step 4 — Open the replay output in AdvantageScope

The replay produces a new file next to the source log:

```
logs/offseason/6-13-26/akit_26-06-13_17-05-06_sim.wpilog
```

In AdvantageScope:

1. **File → Open Log in New Window** → select `*_sim.wpilog`.
2. Now you have two AdvantageScope windows: original on the left, replay
   on the right.
3. Use **File → Synchronize → By Timestamp** (if available) to lock
   playback position.

Alternatively, drag both logs into a single window and overlay signals on the
same graph using the `+` button — useful for A/B comparisons of a single
signal (e.g., `Shooter/velocityRPS` original vs. `Shooter/velocityRPS` replay).

---

## Step 5 — Iterate with live reload (optional)

For active tuning sessions, use the `replayLogWatch` task instead:

```
Ctrl + Shift + P  →  Tasks: Run Task  →  replayLogWatch
```

Or from the terminal:

```
AKIT_LOG_PATH=logs/offseason/6-13-26/akit_26-06-13_17-05-06.wpilog ./gradlew replayWatch
```

Make a code change, save the file, and within a few seconds the terminal shows:

```
[AdvantageKit] Starting replay...
```

A new `_sim.wpilog` is written automatically. Refresh AdvantageScope
(**Ctrl+R** or close and reopen the `_sim` log) to see the effect.

When done, stop the task with **Ctrl+C** in the terminal — `replayWatch` runs
indefinitely watching for changes and will not exit on its own.

---

## What IS replayed

| Signal source | In replay? | Why |
|---|---|---|
| `io.updateInputs(inputs)` result | Overwritten from log | `Logger.processInputs` replaces inputs with logged values |
| `@AutoLogOutput` fields | Re-computed by new code | Subsystem logic runs fresh |
| `Logger.recordOutput(...)` | Re-computed by new code | Same |
| Driver inputs (joysticks) | Yes, from `.hoot` via `HootAutoReplay` | Timestamps and buttons replayed |
| Robot match time | Yes, from `.hoot` | Same as above |

## What is NOT replayed

| Thing | Why |
|---|---|
| Swerve odometry (CTRE internal) | Runs inside `TunerSwerveDrivetrain`, bypasses IO layer. Replayed from `.hoot` via `HootAutoReplay`. |
| `SmartDashboard.put*` calls | Go directly to NT, not captured in the `.wpilog`. Use `Logger.recordOutput` or `@AutoLogOutput` instead. |
| Raw camera frames | Not logged — only processed pose estimates in `VisionIOInputs`. |

---

## Changing which log to replay

Edit `.vscode/tasks.json` — update `AKIT_LOG_PATH`:

```json
"AKIT_LOG_PATH": "logs\\offseason\\6-13-26\\akit_26-06-13_17-05-06.wpilog"
```

Paths are relative to the project root. Use forward or back slashes (both
work on Windows under Git Bash / PowerShell). Save and re-run the task.

---

## Troubleshooting

### Replay output is all zeros / signals missing

The Logger key in `processInputs("Foo", inputs)` must exactly match the key
written during the original run. Check for typos or renamed subsystems.

### `_sim.wpilog` is not being created

Confirm `AKIT_LOG_PATH` points to a real `.wpilog` file — if the path is
wrong, `WPILOGReader` will throw at startup and the file is never written.
The Gradle output will show a Java exception.

### Sim window opens and immediately crashes

Run `./gradlew build` first to ensure generated AKit classes
(`*IOInputsAutoLogged`) are up to date. A stale build can fail at class-load
time before the replay even starts.

### Live sim (simulateJava) still not showing NT entries

Make sure `AKIT_LOG_PATH` is NOT set in your shell environment when running
`simulateJava` directly. If it is, the robot enters replay mode and skips the
NT4Publisher. Unset it with `unset AKIT_LOG_PATH` (bash) or
`$env:AKIT_LOG_PATH = $null` (PowerShell).
