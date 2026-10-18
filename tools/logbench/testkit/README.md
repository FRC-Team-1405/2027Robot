# testkit -- bundles for testing the recorder -> LogBench vision path

Builds a `.wpilog` plus the Orange Pi recorder's `<log>.vision/<camera>/boot####-<timestamp>/`
folders from a match timeline, in the exact on-disk shape `server/bundles.py` reads. No robot, Pi
or camera is needed. Part of the plan in `docs/logbench-e2e-test-plan.md` (Tier 1).

```
cd tools/logbench
python testkit/build_bundle.py --list
python testkit/build_bundle.py --out <dir> --scenario clean
python testkit/build_bundle.py --out <dir> --scenario nt-flap --log <real akit_*.wpilog>
python server/main.py --logs <dir>          # open it in LogBench
python -m pytest tests/test_vision_scenarios.py
```

Without `--log` a small synthetic match log is written (`synth_log.py`). With `--log`, the log's own
driver-station spans and cameras are used and the file is hard-linked (or copied) into `--out`
unmodified. Recording `t_sec` values are on the log's own clock; session folder names come from the
log's wall-clock name rendered in US Eastern, like the recorder's. Each bundle also gets a
`<log>.scenario.json` describing what was built.

Every frame is a real JPEG with its **log time (ms), mode code (0 disabled, 1 auto, 2 teleop) and
frame number** drawn on it, and the same facts in a comment segment (`frames.decode_frame_info`).
Scrub the dashboard video and read the clock off the picture. The burned-in time is absolute log
time, so it equals the transport clock plus the log's first-record time (1.6 s for the synthetic and
real logs); within about 0.1 s (one frame) that is the playhead.

| Scenario | Shape |
|---|---|
| `clean` | one session per enabled window (auto, teleop) per camera |
| `nt-flap` | ~21 s NT dropouts cut teleop into several sessions (modelled on the legacy 10 s hold the field recordings were made with; the default is now 45 s) |
| `partial-auto-only` | a few seconds around auto only, nothing in teleop (the real Q24 shape) |
| `empty-session` | clean, plus a post-match restart session whose manifest is empty |
| `name-mismatch` | folder `Right` vs logged camera `RightCam` |
| `two-boots` | auto and teleop from different boot ids |
| `no-recording` | a log with no `.vision` folder |

New scenarios are a function `Context -> [SessionPlan]` registered in `SCENARIOS`.

`tests/test_vision_scenarios.py` pushes each scenario through bundles, pairing and the camera-health
spec. Its second half is the contract for the dashboard data (all sessions per camera,
mode windows, recording coverage, empty-session warning).
