# Logbench

Play back a `.wpilog` and watch metrics move against the robot's position on the field —
smoothly, at 60fps, with a play button that actually plays.

Built for camera health, but the player itself knows nothing about cameras. "Metrics over
a match timeline" is a shape we keep wanting (shooter tuning, swerve module health, intake
state), so the domain knowledge is isolated in one file per view.

## Why this exists

The Replay tab in the camera-calibration Streamlit app had the right features and was
unusable. It drove playback with `st.fragment(run_every=0.2)`, so every frame was a full
server round-trip: re-run Python, rebuild two Plotly trend figures containing *every
sample of all nine health traces per camera* (~135k points), rebuild the field figure,
rescan the whole pose series three times for a 3-second trail, serialize it all to JSON,
ship it over the websocket, re-render. Seconds per frame.

Streamlit's execution model is request/response. The fix was not a faster Streamlit — it
was to send the data to the browser **once** and animate client-side with no round-trips
at all.

Measured on a 5.5-minute log with 26 tracks and 199k samples:

| | before | after |
|---|---|---|
| per frame | seconds | **0.09 ms** mean, 1.3 ms worst |
| data sent | all traces, 5×/second | 0.47 MB gzipped, once |
| trail lookup | O(N) scan ×3 per tick | O(1) amortized |

## Running it

Three ways, one codebase.

**Standalone file** — no server, no Node, no network. Hand it to a teammate on a USB stick.

```bash
python server/export.py path/to/log.wpilog
```

**Server app** — browse the logs on disk and pick one.

```bash
pip install -r requirements.txt
cd web && npm install && npm run build && cd ..
python server/main.py --logs ../../logs
```

Install NPM if you see an error indicating NPM missing: `winget install OpenJS.NodeJS.LTS`

**Inside the calibration app** — Tab 6 of `tools/camera-calibration/calibrate.py` embeds
the player and offers the standalone file as a download. Needs no npm: the built bundle is
committed at `server/assets/player.singlefile.html`.

**Developing the front end:**

```bash
cd web && npm run dev          # http://localhost:5173, proxies /api to port 8765
```

Add `?debug=1` to any of them for an fps counter and a `window.__player` handle.

Keyboard: `space` play/pause · `←`/`→` 1s · `shift+←`/`→` 10s · `,`/`.` one frame · `0`
restart.

## Layout

```
server/
  model.py            PlayerSpec / Track / Panel / Group  -- generic, no domain concepts
  encode.py           columnar + delta + RLE wire format
  export.py           inline a spec into the single-file bundle
  main.py             FastAPI: log listing, spec endpoint, static hosting
  dump_spec.py        CLI: wpilog -> spec JSON (+ --stats). Headless, no browser needed.
  specs/
    camera_health.py  THE vision-aware module. Log keys, health factors, field geometry.
  assets/
    player.singlefile.html   committed build output (see "Committed build" below)
web/src/
  player/   clock.ts (rAF, plain class), cursor.ts (monotonic lookup), decode.ts, types.ts
  panels/   FieldPanel, TimeSeriesPanel, ReadoutPanel, PanelHost
  controls/ TransportBar
  loader/   useSpec (inlined vs fetched vs picker), LogPicker
```

## Adding a new kind of playback

Write one module in `server/specs/` exposing `NAME`, `LABEL`, and
`build(signals, title=...) -> (PlayerSpec, data)`, then register it in
`server/specs/__init__.py`. Declare your groups (the entities), tracks (the metrics),
panels, and a layout. Nothing in `web/` changes.

`camera_health.py` is the worked example: it maps `Vision/*/Health/*` log keys onto
generic scalar/string/pose2d/intset tracks and lays them out as a field panel, a readout,
and one trend chart per camera.

To add a new *kind of panel* instead: write the component and add one line to
`web/src/panels/PanelHost.tsx`.

## Design notes

**React never re-renders during playback.** The clock is a plain class holding a mutable
`time`; panels subscribe with `useFrame` and draw straight to canvas. React renders only
for things a human did — play/pause, speed, a legend toggle. The one DOM panel (the health
readout) is throttled to 10Hz, because text changing 60 times a second is unreadable
anyway. Measured: 6 DOM mutations across 120 frames.

**Static content is rasterized once.** A trend chart's traces are identical on every frame;
only the playhead moves. They are drawn into an offscreen canvas and blitted, so a frame
costs one `drawImage` plus a line and a few dots. Redrawing the polylines per frame is
exactly what made the old version unusable. The buffer is invalidated only by a resize or
a legend toggle.

**Lookups remember where they were.** Time almost always advances by one frame, so
`Cursor` walks forward a sample or two and only binary-searches on a discontinuity
(a scrub). Trails use two cursors for the window bounds and draw straight out of the typed
arrays — no per-frame allocation.

**Time comes from the wall clock.** `t += realElapsed * speed`, not a fixed step per frame,
so a slow frame costs smoothness rather than sync. Frame deltas are clamped so returning to
a backgrounded tab doesn't teleport the playhead.

**NaN means "could not measure", not zero.** The robot publishes NaN when a health factor
is unmeasurable. It survives encoding as JSON `null`, decodes back to NaN, and every
consumer renders it as a gap or `n/a` — never as a value, and never as a stale previous
reading. Samples further from the playhead than `staleness_sec` are treated as absent too,
matching `vision_analyzer.metrics.nearest_value`.

## Committed build

`server/assets/player.singlefile.html` is a build artifact and is checked in on purpose:
the Streamlit calibration app and the standalone export both need it, and teammates running
the calibration tool should not need Node installed. **Rebuild and commit it whenever
`web/src` changes:**

```bash
cd web && npm run build:single
```

## Tests

```bash
python -m pytest tests -q     # wire format, spec builder  (28)
cd web && npm test            # decode, cursor, clock      (20)
```

The Python and TypeScript suites pin the two halves of the same wire format; if
`server/encode.py` changes shape, `web/src/player/decode.ts` changes with it.

## Known limits

- Field geometry and AprilTag positions come from `vision_analyzer.constants`, which is
  still 2026 Reefscape. Update there for 2027.
- No live NetworkTables mode yet. `PlayerProvider` is structured to take a live source, and
  a FastAPI websocket is the natural next step — at which point the calibration app's
  separate Live Health tab could fold into this.
