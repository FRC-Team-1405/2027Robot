# Validation record — draft 0.1

Verified 2026-10-18 in a headless Linux environment with OpenJDK 17.0.20 using Java source-file launching. These results verify the supplied teaching simulator, not the proposed WPILib project.

- Student source launches and writes a manual scenario CSV.
- The unmodified student file intentionally fails each unfinished lesson check group (02,03,04,07,08) with exit status 1.
- The reference controller passes all 17 checks across those groups; output is in reference/checks.txt.
- Reference auto/manual/disabled runs each produce 600 finite samples over 12 simulated seconds; physical height remains in 0..1.50 m.
- Disabled reference output is zero in every sample for both requested and applied voltage.
- The module 06 interface refactor was compiled/run in a temporary copy; its automatic CSV matches the reference byte for byte.
- Fourteen lesson files contain 42 checkpoint briefs.

## Measured reference response
From the rounded four-decimal CSV values; dt=0.020 s. Nominal kP=8, kD=3, kG=0.5. Values are for the teaching model only.

| Start s | Target m | Settle s | Overshoot m | Final error m | Peak speed m/s | Max abs requested V | Result |
|---|---|---|---|---|---|---|---|
| 0.00 | 0.80 | 1.60 | 0.0000 | 0.0001 | 0.8274 | 5.300 | Pass |
| 4.00 | 1.20 | 1.42 | 0.0000 | 0.0001 | 0.5517 | 3.700 | Pass |
| 8.00 | 0.30 | 1.78 | 0.0000 | -0.0001 | 1.2403 | 6.000 | Pass |

## Remaining validation
The Swing GUI has not been visually exercised in this headless environment. Pilot controls, display scaling, file export, and graph usability on student Windows/macOS/Linux machines. No WPILib project is included, built, or tested here; mentor preparation in wpilib/BRIDGE.md is required. Installation timing, reading level, checkpoint duration, and real-robot transfer remain classroom pilot work.
