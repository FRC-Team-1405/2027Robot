# Optional real-robot transfer lab
Prerequisite: completed simulation contract and mentor-approved hardware. No student needs this lab for core completion.

1. Mentor identifies the actual mechanism, controller, sensors, firmware, wiring, travel range, gearing, zero method, inversion, brake behavior, output limits, and an accessible disable control. Record those values in a hardware model card. Use the team's existing supervised robot test procedure.
2. Implement the real IO adapter for that hardware. Keep the controller policy, command interface, and telemetry contract. Do not run simulation-only device mutation calls on hardware.
3. With the mechanism secured and the mentor supervising, verify sensor units/zero and direction before closing the loop. Verify positive requested voltage produces the expected positive measurement. Stop and fix a sign mismatch before increasing output or enabling automatic movement.
4. Test a low-output manual request, then limits and disable. Test one short automatic move with conservative gains/output. Record voltage, position, velocity, goal, error, and command outcomes.
5. Compare against simulation under similar starting conditions. Name at least two differences and propose an experiment to distinguish friction, load, sensor offset, or model errors. Change one parameter at a time.
6. Submit both traces and the approved hardware configuration. Do not reuse teaching-model gains as trusted hardware settings.

A zero-voltage disabled elevator may fall. Any needed mechanical restraint and hardware interlock are part of the mentor's approved setup, not assumptions supplied by this course. The student's learning task is to recognize and measure model limitations while following that setup.
