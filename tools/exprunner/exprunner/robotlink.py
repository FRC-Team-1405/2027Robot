"""The robot's NetworkTables, as the runner needs them: what the Pis report, and whether the robot is enabled.

Two things are read, nothing is written:

  * ``/OrangePi/<Pi>/PhotonVision/<camera>/*`` and ``/OrangePi/<Pi>/Video/video0/Mode``: the Pi publisher's
    copy of each camera's saved PhotonVision settings and its real capture mode (so a setting
    PhotonVision ignored, or a camera mode that didn't switch, shows up). The publisher refreshes about
    every 5 s and PhotonVision saves 1-2 s after a change.
  * ``/FMSInfo/FMSControlData``: the Driver Station control word. Bit 0 = enabled, bit 1 = autonomous.

Anything with the same four methods can stand in for ``NtLink`` (the tests use one that is scripted).
"""
from __future__ import annotations

import time
from typing import Any

from .settings import FIELDS, MODE_KEY, MODE_TOPIC

ENABLED_BIT, AUTO_BIT = 0x01, 0x02


class LinkError(RuntimeError):
    pass


class NtLink:
    def __init__(self, host: str | None = None, team: int = 1405, connect_timeout: float = 10.0, port: int = 0):
        try:
            import ntcore
        except ImportError:  # pragma: no cover - environment
            raise LinkError("ntcore isn't installed: python -m pip install pyntcore") from None
        self._nt = ntcore
        self.inst = ntcore.NetworkTableInstance.create()
        self.inst.startClient4("exprunner")
        if host:
            self.inst.setServer(host, port)
            self.target = host
        else:
            self.inst.setServerTeam(team)
            self.target = f"team {team}"
        end = time.monotonic() + connect_timeout
        while not self.inst.isConnected():
            if time.monotonic() > end:
                self.inst.stopClient()
                raise LinkError(
                    f"can't reach the robot's NetworkTables ({self.target}). Is the laptop on the robot network, "
                    "and the robot code running? (--nt HOST to name a host, e.g. localhost for the simulator; "
                    "--no-robot to run without it)")
            time.sleep(0.05)
        # Subscribe to everything we read up front: a value only arrives once something subscribes, so
        # reading on demand would return nothing the first time (and record an empty baseline).
        self._sub = ntcore.MultiSubscriber(self.inst, ["/OrangePi/", "/FMSInfo/"])
        end = time.monotonic() + 3.0
        while time.monotonic() < end and not self.inst.getTopics("/OrangePi/"):
            time.sleep(0.05)
        time.sleep(0.3)        # the values follow the topic announcements

    def close(self) -> None:
        self.inst.stopClient()

    # ------------------------------------------------------------------ reading

    def _value(self, path: str) -> Any:
        v = self.inst.getEntry(path).getValue()
        return v.value() if v.isValid() else None

    def readback(self, pi: str, camera: str) -> dict[str, Any]:
        """The camera's settings as the Pi publisher last reported them, with our friendly names."""
        base = f"/OrangePi/{pi}/"
        out: dict[str, Any] = {}
        for key, f in FIELDS.items():
            v = self._value(f"{base}PhotonVision/{camera}/{f.topic}")
            if v is not None:
                out[key] = f.kind(v)
        mode = self._value(base + MODE_TOPIC)
        if mode is not None:
            out[MODE_KEY] = str(mode)
        unique = self._value(f"{base}PhotonVision/{camera}/UniqueName")
        if unique:
            out["_unique_name"] = str(unique)
        ok = self._value(f"{base}PvSettingsOk")
        if ok is not None:
            out["_settings_ok"] = bool(ok)
        return out

    def robot_state(self) -> tuple[bool, bool] | None:
        """(enabled, autonomous), or None if the Driver Station hasn't published a control word."""
        word = self._value("/FMSInfo/FMSControlData")
        if word is None:
            return None
        word = int(word)
        return bool(word & ENABLED_BIT), bool(word & AUTO_BIT)

    def now(self) -> float:
        """Robot (FPGA) time in seconds: ntcore's clock plus the offset to the server's, which is the
        roboRIO's clock, the one the robot log uses. Falls back to this laptop's clock if not synced."""
        off = self.inst.getServerTimeOffset()
        if off is None:
            return time.time()
        return (self._nt._now() + off) / 1e6
