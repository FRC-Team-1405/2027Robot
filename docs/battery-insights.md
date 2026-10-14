# Battery Insights

Open **Battery Insights** in Log Bench (`?view=battery`). Choose a log, then an enabled
session, autonomous/teleop interval, the whole match, or a custom time range. The default
warning is 8 V and is configurable: it is the margin we want to keep above a brownout, not a
motor-control setting.

The page opens with **findings**: a few sentences on how the battery held up and what was
drawing when it dipped, then the match context (event, match, alliance), brownout and dip
counts, and time spent below 10/9/8/7 V. **Battery at rest and recovery** gives the voltage at rest
(disabled) before the match, under the last load, and 10/30/60/120 s after the match; the
drop is measured at the latest of those (the battery keeps recovering for a minute or two,
so a drop measured 10 s after overstates it — about 0.41 V vs 0.25 V at 2 min on an Albany
match). A fitted recovery curve V(t) = V_rest − A·e^(−t/τ) gives a time constant and a
projected resting voltage. That is exploratory: internal resistance is the established
battery-health measure, recovery rate may also track charge and health, so it is recorded
to compare across batteries and matches. Logs trimmed by the WPILog Janitor keep the battery
voltage and match info for the whole log by default, so trimming does not lose these. **Dips below the warning level** lists each episode
(dips less than 1 s apart are one) with its game period and the current signals peaking
during it. **Current by signal** lists every current signal in the log, found by name, so
legacy logs (including plain WPILib `FRC_*.wpilog` competition logs) get the same analysis.

The page shows PDH power, motor supply current, subsystem totals, sampled limiting
events, motor requests and response, and recorded state/allocation changes on a shared
playhead. Click a chart or event to seek; **Surrounding interval** selects two seconds
on either side of an event. Shift-scroll on a chart zooms its view. Expand a subsystem
and select a motor for detailed traces and source keys. Comparison and HTML/JSON
downloads retain each selected window and its coverage.

## How to interpret evidence

- **Supply current** is battery-side draw. **Stator/torque current** describes motor
  loading; do not add it to the battery total. PDH channels and motor telemetry are
  separate views of the same power, not additional loads to sum together.
- A voltage/velocity/duty-cycle request is not a request for a known number of amps.
  The page displays the request in native units. `RequestedAmps` is available only
  for a direct torque-current request. Closed-loop reference is the controller's
  reference, not its hypothetical unrestricted current demand.
- **Configured limit** does not mean **limiting occurred**. Active Phoenix supply
  and stator fault signals are sampled evidence of limiting. Sticky flags mean it
  occurred previously; they do not establish a duration or exact time. Brief events
  can occur between samples. Missing flags mean unknown, not zero limiting.
- A **brownout** is the battery voltage below the brownout threshold, or the roboRIO's
  `SystemStats/BrownedOut` flag where the log has it: at that voltage the roboRIO browns out.
  The recorded threshold is used when the log has one (`SystemStats/BrownoutVoltage` or
  SmartDashboard `Battery/BrownoutVoltage`); otherwise the roboRIO 2 default, 6.75 V, and
  the page says so. Counts are episodes: dips less than 1 s apart count once.
- **What drove a dip** is each current signal's peak from 0.5 s before the dip to its
  end. Stator and torque current are reported by size (they include braking); supply
  current keeps its sign. Signals of different kinds are never added together. A reading
  logged more than 0.5 s before the lowest point is marked old: SmartDashboard telemetry in
  legacy logs is often logged only a few times a second.
- Ah and Wh are timestamp-integrated over valid recorded intervals. Wh uses PDH
  bus voltage, including for subsystem battery-energy attribution. Neither is a
  state-of-charge estimate. Coverage below 100% means consumption may be understated.
  Motor totals represent only instrumented motors; the PDH-minus-motor difference
  includes missing motors, other loads, sensor error, and timing differences.
- Values persist through change-only AdvantageKit records. Explicit invalidity,
  loop-heartbeat gaps over 250 ms, and WPILog Janitor trim seams prevent false integration.
  Legacy acquisition health is unknown. PDH zero voltage while the roboRIO remains
  powered is excluded as inconsistent evidence. PDH packet age is not exposed by
  the captured API, so a plausible PDH sample does not prove freshness.
- Comparisons report observations, not causal savings. Compare equivalent routines,
  battery condition, duration and robot states, and inspect tracking error alongside
  current consumption. Lower current at the expense of missed shots is not success.

## Robot telemetry contract (version 1)

`PowerTelemetry` observes the existing TalonFX instances without changing current
limits or requests. It requests at least 50 Hz for its fast status signals, preserving
existing faster signals. Data and non-sticky faults share a validity assessment:
refresh status must be good and the oldest required signal must be at most 100 ms old.
Temperature and sticky faults use 4 Hz updates and a separate one-second freshness
check. Every physical motor is registered once by CAN bus
and ID. Drive and steer modules, all three shooter motors, deploy/pickup, hopper,
indexer, and climber/grabber are covered.

| Namespace | Contents |
|---|---|
| `Power/SchemaVersion`, `Power/HeartbeatSeconds` | Schema and loop acquisition heartbeat |
| `Power/Distribution/*` | PDH ID/channel count, plausibility validity, validity basis, battery ID |
| `Power/Motors/<bus>-<id>/*` | Identity, subsystem, aliases, follower, supply/stator/torque current, voltage, duty cycle, motion, error/reference, request, status and limiting flags |
| `Power/State/*` | Active named state, selection reason, definitions and subsystem priority tiers |
| `Power/Allocation/<subsystem>/*` | Optional future policy/version, mode, requests/grants, proposals, applied limits, status and reason |

Existing `SystemStats` and `PowerDistribution` inputs remain the primary whole-robot
measurements. Set the persistent robot preference `Power/BatteryId` to the physical
battery label before use; `Unknown` is the default. PDH channels are displayed as
unmapped channel numbers; do not guess the wiring from CAN IDs. Hood servo and
accessory power can only be attributed at the available PDH-channel resolution.

Intake and Pickup both instantiate CAN ID 29 in the existing robot. This change
preserves their control behavior and counts the motor once under Pickup. Call-site
observation records the most recent software request from either owner, including
the owner and timestamp, while retaining the original request object. The hardware
control response is shown separately. Historical aliases that disagree are flagged;
the `Pickup` path takes precedence. This instrumentation does not fix the underlying
dual ownership.

Configuration is read back **after all constructors finish**. Supply/stator enable
flags, amperage limits, lower supply limit/time and readback status are recorded.
Existing mechanism configuration calls record their actual application status;
configuration performed inside the swerve library has unknown application status
and is checked by readback. If future code changes a configuration, call
`PowerTelemetry.recordConfigurationApplication(motor, status)` with the apply result,
then `PowerTelemetry.refreshConfiguration(motor)` outside a
time-critical control loop. A failed readback is unknown, not a disabled limit.
Request observation should wrap new mechanism requests just like existing IO methods:

```java
motor.setControl(PowerTelemetry.request(motor, request));
```

The wrapper returns the same object unchanged. Requests from the swerve library are
observed through its existing motor objects. The timestamp for those observations
is the polling time, not proof of a fresh CAN command. IO inputs are passed through
`Logger.processInputs` for replay. Simulation without recorded power inputs reports
unknown power instead of inventing a whole-robot electrical model.

### Generic states and priorities

Define application states in robot code and select them from the robot's coordinated
state logic. Names are not tied to a specific game. Lower integers mean higher
priority; equal tiers are allowed. Omitted subsystems have no declared priority.
`Unassigned` is reserved and has no priorities. Definitions are immutable and a
duplicate or unknown state is rejected rather than silently changing meaning.

```java
PowerStates.define("Scoring", Map.of("Shooter", 0, "Indexer", 0,
                                     "Drivetrain", 1, "Pickup", 2));
PowerStates.select("Scoring", "Entering scoring routine");
// On exit, the coordinating robot state machine selects its next state.
PowerStates.select("Unassigned", "Scoring routine ended");
```

These calls only log intent. They do not allocate current or change actuator behavior.
The example is not installed as an automatic robot policy.

`PowerStates.recordAllocation(...)` provides the future allocator contract. Mode must
be `off`, `shadow`, or `enforced`. Report **proposed** and **successfully applied**
limits separately, preserving actual application status and reason. Use NaN for an
unknown numerical value. In shadow mode, an applied-limit field can describe the
existing hardware limit, but must never report the proposal as applied. Missing
allocation telemetry remains unknown. Replay of recorded responses cannot predict
the physical outcome of new limits; validate an allocator in shadow mode and then
with controlled hardware tests before match use.

## Battery care and current-limit tuning

1. Label batteries and record their test results. Use a charged, known-good battery
   for each competition match. Inspect terminals, crimps, connectors, main breaker
   and PDH connections. A worn battery or resistive connection can cause brownouts
   even when software limits look reasonable.
2. Let batteries cool after use before charging. Rotate enough batteries for the
   match schedule and use appropriate chargers. Periodic load/capacity tests are
   more informative than open-circuit voltage alone; do not infer capacity or
   health solely from one idle-voltage reading.
3. Establish a repeatable baseline with separate drive acceleration, steering,
   shooter spin-up, mechanism operation, then combined loads. Log the battery ID.
4. Tune swerve stator current to measured wheel-slip onset, using a controlled test
   and CTRE's procedure. The current source configuration is 65 A stator and 45 A
   supply per drive motor, with 50 A steer stator. This feature does not change them.
5. Evaluate supply limits empirically for sustained battery load. Log the entire
   Phoenix supply-limit configuration, including its lower-limit timer. Do not
   assume vendor defaults mean "unlimited" or that four motors draw their configured
   maxima continuously. Check tracking error and actual mechanism performance as
   limits are reduced, then leave operating margin.
6. Repeat a full match-length routine with comparable batteries. Compare voltage
   margin, energy, limiting duration, spin-up/response and successful operation.
   Investigate simultaneous loads and binding before choosing an allocation policy.

Sources:

- [WPILib Robot Battery Basics](https://docs.wpilib.org/en/stable/docs/hardware/hardware-basics/robot-battery.html)
- [WPILib roboRIO brownouts and power budgeting](https://docs.wpilib.org/en/stable/docs/software/roborio-info/roborio-brownouts.html)
- [CTRE current limits and wheel-slip testing](https://v6.docs.ctr-electronics.com/en/stable/docs/hardware-reference/talonfx/improving-performance-with-current-limits.html)
- [Phoenix current-limit configuration](https://api.ctr-electronics.com/phoenix6/stable/java/com/ctre/phoenix6/configs/CurrentLimitsConfigs.html)
- [Phoenix motor status signals](https://api.ctr-electronics.com/phoenix6/stable/java/com/ctre/phoenix6/hardware/core/CoreTalonFX.html)

## Acceptance and commissioning

Software checks: Log Bench pytest suite, frontend typecheck/Vitest/build,
`npm run build:single`, robot compile and `PowerStatesTest`. Fixtures cover
change-only samples, gaps, trim seams, motor aliasing/followers, state and policy
changes, active versus sticky limiting, strict exports and endpoint validation.

Before relying on new telemetry in a match, verify the connected PDH ID and channel
wiring, compare motor/channel readings, check effective limits and flags in Tuner,
and measure CAN utilization plus robot loop time during combined loads. Confirm
that the requested 50 Hz rates are achieved and that logging does not disturb
control. Confirm battery IDs and perform the repeatable full-match routine above.
These checks require the robot; desktop compilation and synthetic logs cannot
establish electrical performance or prove that brownouts are solved.

API: `GET /api/battery?log=...&window=lo,hi&low_voltage=8` uses seconds relative to
the log start. Omitting `window` selects the whole log. Exports add `format=html|json`
at `/api/battery/export`; comparison exports also supply `log_b`, `window_b` and
`low_voltage_b`. The page's `/api/battery` response (`logbench.battery/v1`) carries the
timeline it draws; the **exports carry the insights, not the data**: JSON
(`logbench.battery-insights/v2`, or `logbench.battery-insights-comparison/v2`) for LLMs, with
the findings, context, summary, a 1 s minimum-voltage profile, each dip episode with its
contributors and about a second of evidence either side, the current-by-signal table and a
`how_to_read` guide; HTML for people, with the findings, a voltage chart and close-ups of
the worst dips. A match export is tens of KB. All numerical unknowns are JSON null.
Built in `tools/logbench/server/battery_insights.py` and `battery_export.py`.
