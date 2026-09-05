"""Tab 6 — Replay: play/pause/scrub a .wpilog and watch camera health track the robot's
position on the field, together, instead of as two separate disconnected numbers.

Uses whatever log is already loaded in the sidebar (same uploader every other tab reads
from) -- there's no separate file picker here.

This tab used to build the whole view server-side: on every 200ms `st.fragment` tick it
rebuilt two Plotly trend figures containing every sample of all nine health traces per
camera (~135k points), rebuilt the field figure, rescanned the full pose series three
times for the trail, and shipped the lot over the websocket. Streamlit's execution model
is request/response, so each "frame" cost seconds and playback was unwatchable.

The player is now the logbench front end (tools/logbench), embedded as one
self-contained HTML document with this log's data baked in. The data crosses the wire
once, at render time; play/pause/scrub/legend all happen inside the iframe at 60fps with
no round-trip to Streamlit at all. Everything domain-specific -- which signals to read,
what the eight health factors are, the severity thresholds -- lives in logbench's
specs/camera_health.py, so the same player also drives the standalone export below and
the logbench server app.
"""
import logging
import pathlib

import streamlit as st
import streamlit.components.v1 as components

log = logging.getLogger(__name__)

LABEL = '6 · Replay'

# Field (430) + the two trend panels with their legends + transport + header. Generous
# enough that the iframe doesn't get its own inner scrollbar at the common window size.
_IFRAME_HEIGHT = 1180


def render(ctx: dict) -> None:
    signals = ctx.get('signals')
    if not signals:
        st.info('Load a `.wpilog` file in the sidebar to replay it here.')
        return

    # Imported here rather than at module scope so a missing or unbuilt logbench only
    # breaks this tab, with an actionable message, instead of the whole app's import.
    try:
        import export
        import specs
        from encode import spec_to_dict
    except ImportError as exc:
        st.error(
            'Could not import the logbench tool from `tools/logbench/server` '
            f'({exc}). It is bridged onto sys.path by camera_calibration/logger.py.'
        )
        return

    builder = specs.get(specs.DEFAULT)
    spec, data = builder.build(signals, title=ctx.get('log_name') or 'Replay')
    payload = spec_to_dict(spec, data)

    for warning in payload['warnings']:
        st.warning(warning)
    if not payload['data']:
        return

    if not export.bundle_exists():
        st.error(
            'The logbench bundle has not been built yet, so there is nothing to '
            f'embed.\n\n```\ncd tools/logbench/web && npm install && '
            f'npm run build:single\n```\n\nExpected at `{export.bundle_path()}`.'
        )
        return

    st.caption(
        'Play/pause/scrub through this log while watching camera health and the robot\'s '
        'field position together — useful for tying a health dip to what was actually '
        'happening at that point in a match or practice run. Playback runs entirely in '
        'the browser; the log is sent once. Keyboard: space, ←/→, 0.'
    )

    try:
        html = export.render_single_file(payload)
    except Exception as exc:
        log.exception('Failed to render the logbench bundle')
        st.error(f'Could not build the replay view: {exc}')
        return

    components.html(html, height=_IFRAME_HEIGHT, scrolling=True)

    # The same bytes that are embedded above -- a file you can hand to a teammate, open
    # with no Python, no Node and no network, and scrub through on a laptop in the pit.
    stem = pathlib.Path(ctx.get('log_name') or 'replay').stem
    st.download_button(
        '⬇ Download this replay as a standalone .html',
        data=html,
        file_name=f'replay-{stem}.html',
        mime='text/html',
        help='Self-contained: opens offline, no server needed.',
    )
