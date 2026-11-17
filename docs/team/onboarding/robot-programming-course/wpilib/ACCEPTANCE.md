# Acceptance contract and measurement method
## Nominal lab controller
- Start at height 0.20 m, zero velocity; fixed dt = 0.020 s.
- Enable automatic at t=0; target 0.80 m for [0,4), 1.20 m for [4,8), 0.30 m for [8,12).
- Position tolerance: <=0.03 m. Speed tolerance: <=0.05 m/s. Use absolute values.
- Settling time: first sample at/after a target change after which BOTH tolerances remain true through the end of that segment. Must be <=2.0 s after the change.
- Maximum overshoot: for an upward move, max(0, measured height - target); for a downward move, max(0, target - measured height). Measure over that segment. Must be <=0.08 m.
- Maximum absolute requested and applied voltage <=6 V. Hard physical stops are not a substitute for software direction limits.
- Report final position error and peak speed even though they have no additional acceptance threshold.
- Dwell for command completion in WPILib: at least 0.20 consecutive seconds within both tolerances; reset dwell on leaving tolerance or changing goal. This is distinct from retrospective settling time.

The CSV records completed steps. The first updated target appears at 4.02/8.02 s; measure against intended command times 4.00/8.00 s and report the 20 ms sample resolution. Assertions about between-sample behavior require additional reasoning or faster sampling.

## Fill in for every controller revision
| Segment / starting time | Target m | Settle s | Overshoot m | Final error m | Peak speed m/s | Max abs requested V | Pass? |
|---|---:|---:|---:|---:|---:|---:|---|
| 0.00 s | 0.80 | | | | | | |
| 4.00 s | 1.20 | | | | | | |
| 8.00 s | 0.30 | | | | | | |

## Integration behaviors
| Test | Required behavior | Evidence |
|---|---|---|
| Below 0.05 m, request down/up | Down blocked; up allowed | Direct output test; physics hard stop alone is insufficient |
| Above 1.45 m, request up/down | Up blocked; down allowed | Direct output test |
| Disabled while moving | Requested output zero on the next control iteration; hardware disabled | Log both requested and applied output where possible |
| Out-of-range goal | Clamp finite goals to software range; reject non-finite goals | API test and logged clamped goal |
| Competing commands | One subsystem owner; defined interruption behavior | Lifecycle event log |
| Blocked / stalled movement | Bounded timeout and documented fallback | Injected scenario and command result |
| Independent rerun | Same source and inputs meet criteria | Reviewer name/date |

## WPILib model adaptation
Before tuning, record its parameters and check the mechanism can physically achieve the requested goals with the voltage policy. Start with this nominal contract, but agree on any necessary acceleration, timing, voltage, or tolerance changes **before** evaluating student work. Report the changed contract explicitly; do not compare a real elevator's performance against unexplained teaching-model values. For hardware, use mentor-approved travel and output limits and fresh acceptance values.
