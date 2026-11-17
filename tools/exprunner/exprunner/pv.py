"""PhotonVision's web socket: change a camera's settings from a script.

The PhotonVision web UI talks to the Pi over ``ws://<pi>:5800/websocket_data`` with MessagePack messages.
We use the same one, for the one message we need: ``changePipelineSetting``. Checked against the PhotonVision
v2026.1.1 source (2026-11-14):

  * ``DataSocketHandler.onBinaryMessage``: a message is a map; ``changePipelineSetting`` holds
    ``{"cameraUniqueName": ..., <field>: <value>, ...}`` and each field becomes one change;
  * ``VisionModuleChangeSubscriber``: a field starting with ``camera`` (cameraVideoModeIndex,
    cameraExposureRaw, cameraGain, ...) calls the camera's setter by reflection, so the value's type
    must match (int for the index and gain, double for exposure); every field is also set on the pipeline;
  * on connect the server sends ``{"fullsettings": {"cameraSettings": [{"uniqueName", "videoFormatList":
    {index: {width, height, fps, pixelFormat}}, ...}], "settings": ...}}``. The server closes an idle
    socket after 5 s, so connect, send, close.

It is not a public API, so everything PhotonVision-specific is in this file and ``settings.py``. If a
release changes it:

  * ``python -m exprunner pv-dump --board LeftPi`` prints the messages PhotonVision sends, to see the
    new shape, and
  * the runner never trusts a send: it reads each setting back from the Pi publisher and, if anything
    did not take, falls back to telling you exactly what to change by hand.
"""
from __future__ import annotations

import time
from typing import Any

from .settings import FIELDS, MODE_KEY, SettingsError, parse_mode

PORT = 5800
PATH = "/websocket_data"


class PvError(RuntimeError):
    pass


def _modules():
    try:
        import msgpack
        from websockets.sync.client import connect
    except ImportError as e:  # pragma: no cover - environment
        raise PvError(f"this laptop's Python is missing {e.name} (it is not a Pi problem; the Pis need nothing). "
                      "Install the runner's requirements with the same Python you run exprunner with: "
                      "python -m pip install -r tools/exprunner/requirements.txt") from None
    return msgpack, connect


class PvClient:
    """One connection to one Pi's PhotonVision. Use as a context manager; close it before a run so the
    PhotonVision UI isn't fighting for settings while the robot drives."""

    def __init__(self, host: str, port: int = PORT, connect_timeout: float = 5.0):
        if ":" in host:                      # "host:port" (the simulator, or a tunnelled Pi)
            host, _, p = host.partition(":")
            port = int(p)
        self.host, self.port, self.timeout = host, port, connect_timeout
        self.ws = None
        self.messages: list[Any] = []

    def __enter__(self) -> "PvClient":
        msgpack, connect = _modules()
        self._msgpack = msgpack
        try:
            self.ws = connect(f"ws://{self.host}:{self.port}{PATH}", open_timeout=self.timeout, max_size=None)
        except Exception as e:  # noqa: BLE001 - any connection problem reads the same to the user
            raise PvError(f"can't reach PhotonVision at ws://{self.host}:{self.port}{PATH}: {e}") from None
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        if self.ws is not None:
            try:
                self.ws.close()
            finally:
                self.ws = None

    # ------------------------------------------------------------------ receiving

    def drain(self, seconds: float = 1.5) -> list[Any]:
        """Collect what PhotonVision sends right after connecting (and after changes) for a moment."""
        end = time.monotonic() + seconds
        got = []
        while True:
            left = end - time.monotonic()
            if left <= 0:
                break
            try:
                raw = self.ws.recv(timeout=left)
            except TimeoutError:
                break
            except Exception as e:  # noqa: BLE001
                raise PvError(f"PhotonVision closed the connection: {e}") from None
            if isinstance(raw, bytes):
                try:
                    got.append(self._msgpack.unpackb(raw, raw=False, strict_map_key=False))
                except Exception:  # noqa: BLE001 - not msgpack; keep it visible in pv-dump
                    got.append({"_undecoded_bytes": len(raw)})
            else:
                got.append({"_text": raw})
        self.messages.extend(got)
        return got

    # ------------------------------------------------------------------ sending

    def _send(self, message: dict[str, Any]) -> None:
        self.ws.send(self._msgpack.packb(message, use_bin_type=True))

    def change(self, camera_unique_name: str, **pv_fields: Any) -> None:
        """Set PhotonVision fields (its own JSON names, e.g. decimate=2, cameraVideoModeIndex=4) on a camera."""
        self._send({"changePipelineSetting": {"cameraUniqueName": camera_unique_name, **pv_fields}})

    def apply(self, camera_unique_name: str, settings: dict[str, Any], mode_index: int | None = None) -> None:
        """Send every wanted setting (friendly names). The camera mode needs its index in the camera's list."""
        for key, value in settings.items():
            if key == MODE_KEY:
                if mode_index is None:
                    raise PvError("no index for the camera mode; see mode_index()")
                self.change(camera_unique_name, cameraVideoModeIndex=int(mode_index))
            else:
                f = FIELDS[key]
                self.change(camera_unique_name, **{f.pv: f.kind(value)})

    # ------------------------------------------------------------------ the camera mode list

    def mode_index(self, camera_unique_name: str, wanted: str) -> int:
        """Index in this camera's video-mode list of the mode named like '1280x800 MJPG @100'."""
        if not self.messages:
            self.drain()
        w, h, fmt, fps = parse_mode(wanted)
        modes = find_modes(self.messages, camera_unique_name)
        if not modes:
            raise PvError(f"couldn't find {camera_unique_name}'s mode list in what PhotonVision sent "
                          f"(run `pv-dump` to see its messages)")
        matches = [i for i, m in modes.items()
                   if m.get("width") == w and m.get("height") == h and abs(float(m.get("fps", 0)) - fps) < 1.0
                   and (not m.get("format") or _format_key(m["format"]) == _format_key(fmt))]
        if not matches:
            have = ", ".join(f"{i}: {m.get('width')}x{m.get('height')} @{m.get('fps')}" for i, m in sorted(modes.items()))
            raise PvError(f"{camera_unique_name} has no mode {wanted!r}. It has: {have}")
        return min(matches)


def _format_key(text) -> str:
    """'kMJPEG', 'MJPEG', 'MJPG' are all one format; others compare as written."""
    t = str(text).upper().lstrip("K")
    if "JPG" in t or "JPEG" in t:
        return "MJPG"
    if t in ("YUYV", "YUY2", "YUYV422"):
        return "YUYV"
    return t


def find_modes(messages: list[Any], camera_unique_name: str) -> dict[int, dict]:
    """{index: {width, height, fps, format}} for one camera, wherever PhotonVision put its mode list.

    The list is a ``videoFormatList`` (index -> mode) on the camera's settings. The settings can be nested
    anywhere in a message, so walk every message and take the first camera entry with that unique name."""

    def walk(node):
        if isinstance(node, dict):
            yield node
            for v in node.values():
                yield from walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                yield from walk(v)

    for msg in messages:
        for d in walk(msg):
            if d.get("uniqueName") == camera_unique_name and "videoFormatList" in d:
                return _modes(d["videoFormatList"])
    # some versions send the list on its own, keyed by camera
    for msg in messages:
        for d in walk(msg):
            lst = d.get("videoFormatList")
            if lst is not None and d.get("cameraUniqueName") == camera_unique_name:
                return _modes(lst)
    return {}


def _modes(lst) -> dict[int, dict]:
    out: dict[int, dict] = {}
    items = lst.items() if isinstance(lst, dict) else enumerate(lst)
    for k, v in items:
        if not isinstance(v, dict):
            continue
        try:
            idx = int(k)
        except (TypeError, ValueError):
            continue
        out[idx] = {"width": v.get("width"), "height": v.get("height"), "fps": v.get("fps"),
                    "format": v.get("pixelFormat") or v.get("format") or ""}
    return out


def settings_error_hint() -> str:
    return "PhotonVision UI: set it by hand, the runner will see it from the Pi publisher and carry on."


__all__ = ["PvClient", "PvError", "find_modes", "SettingsError"]
