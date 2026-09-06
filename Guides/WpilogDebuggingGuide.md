# .wpilog File Debugging Guide – Team 1405

This guide covers why `.wpilog` files may not be created during FRC competition matches, how to diagnose the issue, and what code changes increase reliability.

---

## Most Likely Causes

### 1. `DataLogManager.start()` Was Never Called *(Root Cause — Now Fixed)*

WPILib's `DataLogManager` will **not** create any `.wpilog` files unless `DataLogManager.start(directory)` is called explicitly at robot startup. Without this call:

- `DataLogManager.getLog()` still returns a log object, but it writes to an in-memory buffer that is never flushed to disk.
- Code that calls `DataLogManager.log(...)` or creates `StringLogEntry` / `DoubleLogEntry` objects will appear to work but nothing will be saved.

**Fix applied in `Robot.java`:**
```java
DataLogManager.start("/home/lvuser/logs");
DriverStation.startDataLog(DataLogManager.getLog());
```

The second line mirrors DriverStation data (match number, alliance, enable/disable events) into the log, which is required to properly timestamp entries.

---

### 2. Log Not Flushed Before Robot Powers Down

Even after `DataLogManager.start()` is called, the log is written in buffered chunks. If the robot loses power or is rebooted before the buffer is flushed, the last portion of the log (or the file header, making it unreadable) may be lost.

**Fix applied in `Robot.java` — `disabledInit()`:**
```java
DataLogManager.getLog().flush();
```

This flushes all buffered log data to disk every time the robot is disabled (end of auto, end of teleop, e-stop).

---

### 3. Confusion Between `.wpilog` and `.hoot` Files

The robot also uses CTRE's `SignalLogger` (started via `SignalLogger.start()` in `Telemetry.java`), which writes **`.hoot`** files, not `.wpilog` files. These are separate systems:

| Logger | File Type | Location | Viewer |
|---|---|---|---|
| WPILib `DataLogManager` | `.wpilog` | `/home/lvuser/logs/` | WPILib Data Log Tool / AdvantageScope |
| CTRE `SignalLogger` | `.hoot` | `/home/lvuser/ctre-logs/` | Tuner X / HootReplay |

If you are looking for `.wpilog` files but only see `.hoot` files, `DataLogManager.start()` was not called.

---

### 4. Wrong Directory or Missing Directory

The logs directory (`/home/lvuser/logs`) must exist on the roboRIO. If it does not exist, `DataLogManager` will fail silently and no file will be created.

**How to check and create the directory via SSH:**
```bash
ssh lvuser@roborio-1405-frc.local
ls -la /home/lvuser/logs
# If the directory is missing:
mkdir -p /home/lvuser/logs
```

---

### 5. Disk Full

A full disk will prevent new log files from being created. Even though a full disk was ruled out in the original incident, this should always be verified.

**How to check disk usage:**
```bash
ssh lvuser@roborio-1405-frc.local
df -h /
```

The roboRIO's internal flash is ~512 MB. Each match log is typically 10–40 MB depending on how much data is logged.

**To free space — remove old logs:**
```bash
ls -lh /home/lvuser/logs/
rm /home/lvuser/logs/FRC_<old_timestamp>.wpilog
```

---

### 6. roboRIO Crash or Watchdog Reset During Match

If the roboRIO restarts mid-match (e.g., a brownout, a Java exception that kills the JVM, or a watchdog timeout), the log file may be partially written and unreadable.

**How to check for crashes:**
- SSH in after the match and look at `/home/admin/NetConsole*.log` or system logs.
- Look for a truncated `.wpilog` file with a size of 0 bytes or just a few KB.
- Check `dmesg` output for brownout/reset events.

```bash
ssh lvuser@roborio-1405-frc.local
ls -lh /home/lvuser/logs/
```

---

## Debugging Checklist

Use this checklist after any match where a log file is missing:

- [ ] **SSH into the roboRIO** and check `/home/lvuser/logs/`:
  - Is the directory present?
  - Are any `.wpilog` files there at all?
  - What is the file size? (0 bytes = crash before flush; small = short match or crash)
- [ ] **Check disk space**: `df -h /` — is the partition full?
- [ ] **Check for roboRIO reboots**: look at system logs or note if the Driver Station reconnected mid-match.
- [ ] **Verify the code deployed** includes the `DataLogManager.start()` fix (see the commit associated with this guide).
- [ ] **Check CTRE logs separately** if you were looking in `/home/lvuser/ctre-logs/` — those are `.hoot` files, not `.wpilog`.

---

## How to Retrieve Logs After a Match

### Method 1: WPILib Data Log Tool (Recommended)

1. Connect your laptop to the robot via USB or Ethernet tether.
2. Open the **WPILib Data Log Tool** (comes with WPILib installation).
3. Enter the roboRIO hostname: `roborio-1405-frc.local` (or IP `10.14.05.2`).
4. Download the `.wpilog` files to your laptop.

See also: `Guides/DownloadMatchLogsForReplay.md`

### Method 2: SCP via SSH

```bash
scp lvuser@roborio-1405-frc.local:/home/lvuser/logs/*.wpilog ./match-logs/
```

---

## Viewing Logs in AdvantageScope

1. Open AdvantageScope.
2. `File > Open Log(s)...`
3. Select the `.wpilog` file.
4. Explore drivetrain telemetry, subsystem states, command scheduling, and more.

---

## Related Code Files

| File | Relevance |
|---|---|
| `src/main/java/frc/robot/Robot.java` | `DataLogManager.start()` and `flush()` added here |
| `src/main/java/frc/robot/Telemetry.java` | `SignalLogger.start()` for CTRE `.hoot` logging |
| `src/main/java/frc/robot/commands/PidToPose/PidToPoseCommand.java` | Uses `DataLogManager.getLog()` for command state logging |
| `src/main/java/frc/robot/lib/FinneyLogger.java` | NT-based logging (does not write to `.wpilog`) |

---

## References

- [WPILib Data Logging Docs](https://docs.wpilib.org/en/stable/docs/software/wpilib-tools/data-logging.html)
- [AdvantageScope](https://docs.advantagescope.org/)
- [CTRE Hoot Logging](https://pro.docs.ctr-electronics.com/en/latest/docs/api-reference/api-usage/signal-logging.html)
