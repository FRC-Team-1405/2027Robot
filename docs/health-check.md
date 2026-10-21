# Health Check

LogBench's **Health Check** page (it replaced "Pit Check") answers one question: *is everything on the
robot OK?* Scroll it and look for anything that is not a green tick. It works two ways, from the same
list of checks:

- **Live robot**, in the pits: connect over NetworkTables, enable and disable the robot, and watch each
  row. A row that goes red keeps a note ("was problem since reset, peak 95 %") even after it recovers,
  until you press **Reset**.
- **Match log**, afterwards: pick a `.wpilog` and see what stood out in that match, with the worst
  reading and when it happened ("at 61.5 s into the log").

Open it from the **Health Check** tab, or `?view=health` (the old `?view=pit` still works). A log can be
opened directly with `?view=health&log=<name>.wpilog`.

Missing camera numbers (including JSON `null`) show **n/a**, rather than zero.
Request, response-data, reset, and rendering failures appear in a notification directly
below the page heading. A bad health section or camera does not take down the rest of
the page. Unexpected rendering failures have a **Retry** button.

Live requests time out after ten seconds and retry automatically, with one request at
a time per endpoint. The initial NT handshake gets ten seconds; after the first valid
response a gap must last **five seconds** before an outage notification appears.
Brief missed polls and NT reconnects retain the last good report/camera readings without
flashing a warning or an offline camera. A sustained failure marks those readings as
retained and shows their last-received time; **two consecutive good polls** clear it.
Either live endpoint can confirm robot contact, so a camera-only request failure does
not relabel a working health connection as disconnected. This grace applies to live
transport/response failures; published check failures, configuration errors, reset
errors and rendering errors still appear directly.

The live status panel reserves its height to avoid moving the controls/results when
connection messages change. A section/group opened for a problem stays open when it
recovers; explicit expand/collapse choices remain in control. Disconnecting or leaving
the page cancels pending requests so late responses cannot restore an old connection.
Failed log rechecks retain the last report for that same file; selecting a different
file clears the old report. **Retry page data** retries log-list and score-color loads.

## Reading the page

| Icon | Meaning |
|---|---|
| ✔ green | within its limits |
| ▲ amber | warning: outside the normal range, not a failure |
| ✖ red | problem |
| ? grey | no data: the check could not be made (the row says why) |
| – | not applicable here (hidden by default; **Show not applicable** reveals them) |

The banner at the top rolls everything up: **All checks passing / Nothing stands out**, **Check these
before going** (warnings), **Problems found**, or **Incomplete** (nothing wrong, but some checks had no
data). Sections (Vision, Orange Pis, roboRIO, Robot) contain groups (one per camera, Pi, subsystem...),
which contain rows. Anything amber or red opens by default; anything fine stays collapsed to one line
with its own icon, so you can scan the page for the first non-green icon. **Problems only** hides every
green row.

Every row shows what was measured, the value, **the rule that was applied in words** ("warn above 70 %,
fail above 90 %") and detail. Hover for the check's help text.

## What is checked out of the box

| Section | Checks |
|---|---|
| **Vision** | per camera: connected to robot code, frame rate; live only: tags in view, tag-detection health score and why it is low, camera agreement. The old per-factor tag-detection cards are under **Tag detection detail**. |
| **Vision recording** | log only, and only for a log opened with its `.vision` folder. Per camera: share of the enabled (auto + teleop) time within 0.5 s of a recorded frame (warn below 90 %, fail below 50 %) and the longest stretch with no frame (warn above 10 s, fail above 60 s; the largest gaps, in seconds into the log, are in the row's detail). A camera the robot logged with no recording folder fails. Computed from the bundle's files, not health_checks.toml (`server/vision_coverage.py`). |
| **Orange Pis** | per Pi: reporting (silent over 5 s fails), CPU, RAM, disk, temperature, and the diagnostics below. Per recorder: state (idle/recording ok; no_stream/error not), camera stream delivering frames, stream rate, share of an enabled match that was recorded (log), disk free, errors, clock synced to the robot, version. |
| **roboRIO** | CAN utilization (worst), bus-off, TX-full, RX/TX errors; battery voltage (lowest while enabled, and now), brownout, rail faults, comms disables; PDH faults and peak current; controller CPU temperature, loop time (worst and mean), logging backlog, radio; CAN utilization while disabled (the idle baseline) and mean while enabled, used to A/B the CAN-load switches in [can-bus-load-ab-test.md](can-bus-load-ab-test.md); an optional loop-time breakdown per section when `LOG_SUBSYSTEM_TIMINGS` is on; errors/warnings/PhotonVision alerts logged by robot code. |
| **Robot** | one group per subsystem, one cluster per motor: responding on CAN, newest status age, last status, temperature, undervoltage, time at the current limit, peak supply current. |

### When the Pi's cameras and clients all drop at once: reboot, link flap or camera loss?

PhotonVision's own NetworkTables client, every recorder and the metrics publisher live on the same Pi, so a
drop usually takes them all down together. Which kind of drop it was is what these rows say:

| Cause | What shows it |
|---|---|
| **The board rebooted** (power loss, crash) | **Rebooted during the match** goes red: `BootId` (the kernel's per-boot id) changed. Live, **Time since the board booted** is small. |
| **A service restarted** (recorder or PhotonVision, board still up) | `BootId` unchanged and `SystemUptimeSec` still counting, but the recorder's **Recorder process uptime** is small. |
| **The network link flapped** (cable, connector, switch/radio port or its power) | **Network link flaps while enabled** (`NetCarrierChanges` climbing) and each recorder's **NetworkTables drops / time disconnected while enabled** (counted by the Pi itself and published after the reconnect), with `BootId` unchanged. Live, **Network link** and **link speed** show the port's state. |
| **One camera fell off USB** | **USB camera count changed** (`UsbCameras` dropped) while the link rows are clean and the other camera's recorder is fine; that recorder's `StreamOk` goes false. |

Published by `orangepi-nt-publisher.py` (`SystemUptimeSec`, `BootId`, `NetIface`, `NetCarrierChanges`,
`NetOperState`, `NetSpeedMbps`, `VideoDevices`, `UsbCameras`; set `ORANGEPI_NET_IFACE` to pick the interface if the
default route is not the one that reaches the robot) and by the recorder heartbeat (`NtDisconnects`, `NtDownSec`,
`NtLongestOutageSec`). The recorder samples its connection about three times a second, so each outage is good to
about a third of a second. Only logs recorded after the robot code's `CoprocessorHealthLogger` mirror and these
Pi changes have these rows; older logs show them as grey "no data".

### Where the data comes from

- **roboRIO and robot rows** read what AdvantageKit already logs (`SystemStats/*`, `PowerDistribution/*`,
  `Power/Motors/*`, `RealOutputs/*`), live from `/AdvantageKit/...` or from the log.
- **Orange Pi rows** read `/OrangePi/...`. `orangepi-nt-publisher.py` publishes CPU/RAM/disk/temperature;
  `orangepi-vision-recorder.py` publishes a heartbeat per camera under
  `/OrangePi/[<board>/]Recorders/<camera>/`: `State`, `Recording`, `StreamOk`, `StreamAgeSec`, `StreamFps`,
  `SessionFrames`, `Sessions`, `TotalFrames`, `Errors`, `LastError`, `DiskFreeGB`, `RecordingsUsedGB`,
  `ClockSynced`, `UptimeSec`, `HeartbeatSec`, `Version`, `BootId`, `SampleHz`. It reports even while the robot is
  disabled, so the camera stream and the disk can be checked in the pits.
- **In a match log**, those Pi topics are only there if the robot code copies them in:
  `CoprocessorHealthLogger` mirrors `/OrangePi/**` into the AdvantageKit log (`RealOutputs/OrangePi/...`)
  twice a second. Logs recorded before that change show the Orange Pi section as grey "no data".

Nothing reaches the robot's Pis or the robot until you deploy it: re-run `Bootstrap-OrangePi.ps1` for each
Pi (it installs the updated recorder) and deploy the robot code.

## Adding a metric (no code)

Everything is in `tools/logbench/server/health_checks.toml`. Add a block, save, refresh the page (the file
is re-read when it changes). Mistakes are listed at the top of the page and the other checks still run.

Track something new before you know what "too much" is: a check with no rule is informational and never
red. For example, how long the shooter was spinning (this one ships as an example):

```toml
[[check]]
id = "example.shooter_spin_time"
section = "Robot"
group = "Shooter"
label = "Shooter wheels spinning (time while enabled)"
signal = "Shooter/Motor1VelocityRPS"
measure = "seconds_above"     # how long the value was above `above`
above = 5
window = "enabled"            # only count auto + teleop
unit = "s"
mode = "log"                  # needs a log: live has no history
# warn_above = 90             # add this once you know what a normal match looks like
```

Why the shooter running long matters is battery draw; the check is the same idea for anything else:
swap `signal`, pick a `measure`, add a threshold.

### The vocabulary

- **`signal`**: a log/NetworkTables key. `RealOutputs/`, a leading `/`, and the AdvantageKit root are optional.
  A `*` matches one path segment and produces **one row per match**; `{1}`, `{2}` in `group`, `subject` and
  `label` are what the first and second `*` matched. `lookup = { name = "Power/Motors/{1}/Name" }` pulls
  display text (`{name}`) from another signal of the same item.
- **`measure`** (how a log collapses to one number): `last`, `first`, `max`, `min`, `mean` (time-weighted),
  `seconds_above` / `seconds_below` (need `above` / `below`), `seconds_true`, `seconds_false`,
  `fraction_true`, `fraction_false`, `seconds_equals`, `fraction_equals` (need `equals`), `any_true`,
  `all_true`, `changes`, `delta`, `max_len`, `last_len` (lists and text: alerts). A log is a sample-and-hold
  series, so durations are real time, not record counts. Live always uses the current value; measures
  that need history are shown as "log only" there.
- **`window`**: which part of a log counts: `all` (default), `enabled`, `auto`, `teleop`, `disabled`.
- **Rules**: `warn_above`, `fail_above`, `warn_below`, `fail_below` (on the scaled value);
  `expect = true | false | number | "text"` or `expect_in = [...]` (with `severity = "warn"` to make a violation
  amber); `stale_after = seconds` (live: fail if the topic stopped updating); `scale` multiplies the value
  first (CAN utilization is 0-1, so `scale = 100`, `unit = "%"`).
- **Missing data**: `missing = "nodata"` (grey, default), `"ok"` (alerts: nothing published means nothing
  wrong), `"warn"`, `"fail"`. `expect_items = ["LeftCam", "RightCam"]` on a `*` check fails if one of those
  is absent, when others reported.
- **`mode`**: `both` (default), `live`, or `log`.

The full reference is the docstring at the top of `server/health/config.py`; a mis-spelled field is an error
(`warn_abve` is reported, not silently ignored).

## How the defaults were calibrated

Run against the seven Ruckus 2026 AdvantageKit logs (Q1, Q6, Q17, Q20, Q24, Q28, plus Q24's bundle):

- Healthy motors report `SignalStatus == OK` for 99-100 % of enabled time; two configured motors that were
  not on the bus (since removed from the code) reported 0 % in every match (`RxTimeout`, status age of
  hundreds of seconds). That is the "responding on CAN" check, and it flagged exactly those two motors and
  nothing else. (The `Valid` flag is *not* used: it only
  means "data fresher than 100 ms" and is false most of the time for healthy motors.)
- Drive motors sit at their stator-current limit 15-20 % of an enabled match, so that warning is set at 35 %.
- Every log shows CAN utilization reaching 100 %, battery dips to about 7 V, loop times of 100+ ms and the
  camera dropping connection during teleop. These are real findings in those matches, not noise.

## For developers

- `server/health/config.py` loads and validates the TOML; `engine.py` evaluates (`LogSource` for a parsed
  log, `SnapshotSource` for live values, `Latch` for the worst-since-reset memory) and returns one
  report: sections -> groups -> subjects -> checks.
- API: `GET /api/health/config`, `GET /api/health/log?path=...`, `GET /api/health/live`,
  `POST /api/health/live/reset`. The live view uses the connection `POST /api/live/connect` opens.
- Tests: `tests/test_health_config.py`, `test_health_engine.py`, `test_health_api.py`, `test_live_nt.py`;
  `web/src/health/healthView.test.ts`; `CoprocessorHealthLoggerTest.java`; the recorder side is
  `coprocessor/tests/test_recorder_heartbeat.py`.
