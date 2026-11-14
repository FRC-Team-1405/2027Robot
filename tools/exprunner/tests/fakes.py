"""Stand-ins for the robot, PhotonVision and LogBench, so a whole robot experiment runs in a test."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from exprunner.pv import PvError
from exprunner.settings import MODE_KEY

MODES = {0: "640x480 MJPG @30", 4: "800x600 MJPG @100", 7: "1280x800 MJPG @100", 8: "1280x800 MJPG @120"}

BASE = {"camera_mode": "800x600 MJPG @100", "decimate": 2, "threads": 8, "low_latency": False,
        "multitag": True, "exposure": 80.0, "gain": 25}


class World:
    """The cameras as the Pis publish them. A change shows up only after `lag` readbacks, like the real
    publisher (it refreshes every few seconds)."""

    def __init__(self, cameras=(("LeftPi", "LeftCam"), ("RightPi", "RightCam")), lag: int = 1, base=None):
        self.cams = {cam: {"pi": pi, "state": dict(base or BASE), "pending": []} for pi, cam in cameras}
        for cam, c in self.cams.items():
            c["state"]["_unique_name"] = f"uid-{cam}"
        self.lag = lag
        self.readbacks = 0
        self.sent: list[tuple[str, dict]] = []

    def by_unique(self, unique):
        for cam, c in self.cams.items():
            if c["state"]["_unique_name"] == unique:
                return cam, c
        raise KeyError(unique)

    def change(self, unique, friendly: dict):
        cam, c = self.by_unique(unique)
        self.sent.append((cam, dict(friendly)))
        c["pending"].append([self.lag, dict(friendly)])

    def readback(self, pi, cam):
        self.readbacks += 1
        c = self.cams[cam]
        for item in list(c["pending"]):
            item[0] -= 1
            if item[0] < 0:
                c["state"].update(item[1])
                c["pending"].remove(item)
        return dict(c["state"])

    def set_now(self, cam, **settings):
        self.cams[cam]["state"].update(settings)


class FakeLink:
    """NtLink-like: readback from a World; the robot's enabled state follows a script."""

    def __init__(self, world: World, states=None):
        self.world = world
        self.states = list(states if states is not None else [(False, False), (True, True), (True, True), (False, True)])
        self.i = 0
        self.t = 100.0
        self.target = "fake"

    def readback(self, pi, cam):
        return self.world.readback(pi, cam)

    def robot_state(self):
        if not self.states:
            return None
        st = self.states[min(self.i, len(self.states) - 1)]
        self.i += 1
        return st

    def now(self):
        self.t += 5.0
        return self.t


class FakePv:
    """PvClient-like, writing into the World. `fail` makes it behave like a PhotonVision we can't talk to."""

    def __init__(self, world: World, fail: str = "", ignore: set | None = None):
        self.world, self.fail, self.ignore = world, fail, ignore or set()

    def __call__(self, host):
        if self.fail:
            raise PvError(self.fail)
        self.host = host
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def drain(self, seconds=1.5):
        return []

    def mode_index(self, unique, wanted):
        for i, m in MODES.items():
            if m.split()[0] == wanted.split()[0] and m.split()[-1] == wanted.split()[-1]:
                return i
        raise PvError(f"no mode {wanted!r}")

    def apply(self, unique, settings, mode_index=None):
        friendly = {k: v for k, v in settings.items() if k not in self.ignore}
        if MODE_KEY in friendly:
            friendly[MODE_KEY] = MODES[mode_index]
        self.world.change(unique, friendly)


class FakeLogBench:
    """The three LogBench endpoints the runner uses, on a real local port."""

    def __init__(self, logs=None, fail_bundle: str = ""):
        self.logs = logs if logs is not None else [
            {"name": "akit_26-11-14_19-00-00.wpilog", "size": 100, "mtime": 1.0},
            {"name": "akit_26-11-14_19-11-27.wpilog", "size": 2000, "mtime": 5.0},
        ]
        self.fail_bundle = fail_bundle
        self.jobs: dict[str, dict] = {}
        self.requests: list[tuple[str, str]] = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body):
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                outer.requests.append(("GET", self.path))
                if self.path == "/":
                    return self._send(200, {"ok": True})
                if self.path.startswith("/api/remote/jobs/"):
                    job = outer.jobs[self.path.rsplit("/", 1)[1]]
                    return self._send(200, job)
                self._send(404, {"detail": "no"})

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"null")
                outer.requests.append(("POST", self.path))
                if self.path == "/api/remote/sessions/jobs":
                    outer.jobs["j1"] = {"status": "complete", "phase": "done", "error": None, "result": {
                        "configured": True, "rio_logs": outer.logs,
                        "pairings": [{"rio_log": outer.logs[-1]["name"], "pi_sessions": [
                            {"camera": "LeftCam", "name": "s1", "pi": "LeftPi"}], "confidence": "high"}]}}
                    return self._send(202, {"configured": True, "job_id": "j1"})
                if self.path == "/api/remote/bundle/jobs":
                    outer.bundle_body = body
                    if outer.fail_bundle:
                        outer.jobs["j2"] = {"status": "error", "phase": "x", "error": outer.fail_bundle, "result": None}
                    else:
                        outer.jobs["j2"] = {"status": "complete", "phase": "Ready", "error": None, "result": {
                            "log": body["rio_log"], "pi_sessions": body["pi_sessions"], "manual": False}}
                    return self._send(202, {"job_id": "j2"})
                self._send(404, {"detail": "no"})

        self.server = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
