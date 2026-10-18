"""Test kit for the vision recorder -> LogBench vision dashboard path.

Builds match-shaped bundles (a .wpilog plus the Orange Pi recorder's `<log>.vision/<camera>/
boot####-<timestamp>/` folders) with no robot, no Pi and no camera, so Fetch/pairing and the
dashboard can be tested against the *shapes* real recordings take, including their failures.
See docs/logbench-e2e-test-plan.md (Tier 1) and testkit/README.md.

Stdlib only (plus wpilog_utils for reading a real log's mode spans).
"""
