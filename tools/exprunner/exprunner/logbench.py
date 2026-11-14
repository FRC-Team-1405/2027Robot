"""Fetch the newest robot log (and the Pis' matching recordings) through LogBench's HTTP API.

Does what the Fetch Bundle page does, so there is one implementation of fetching: list what is on the
roboRIO and Pis, pick the newest log, download it. LogBench has to be running (the VS Code task
`LogBench`, http://127.0.0.1:8765) and configured for remote fetching (remote_config.json).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable

DEFAULT_URL = "http://127.0.0.1:8765"


class LogBenchError(RuntimeError):
    pass


class LogBenchClient:
    def __init__(self, base: str = DEFAULT_URL, poll: float = 0.5, timeout: float = 300.0,
                 sleep: Callable[[float], None] = time.sleep):
        self.base = base.rstrip("/")
        self.poll, self.timeout, self.sleep = poll, timeout, sleep

    # ------------------------------------------------------------------ plumbing

    def _call(self, method: str, path: str, body: dict | None = None) -> Any:
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode() or "null")
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            raise LogBenchError(f"LogBench {method} {path} -> {e.code}: {detail}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise LogBenchError(
                f"can't reach LogBench at {self.base} ({e}). Start it (VS Code task `LogBench`), "
                "or run with --no-fetch and fetch the log yourself.") from None

    def ping(self) -> None:
        """Raise LogBenchError if LogBench isn't running (any HTTP answer counts as running)."""
        try:
            urllib.request.urlopen(self.base + "/", timeout=5).close()
        except urllib.error.HTTPError:
            return
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise LogBenchError(
                f"LogBench isn't running at {self.base} ({e}). Start it (VS Code task `LogBench`), "
                "or run with --no-fetch and fetch the log yourself.") from None

    def _wait(self, job_id: str, what: str, on_phase: Callable[[str], None] | None = None) -> dict:
        end = time.monotonic() + self.timeout
        last = None
        while True:
            job = self._call("GET", f"/api/remote/jobs/{job_id}")
            if on_phase and job.get("phase") != last:
                last = job.get("phase")
                on_phase(f"{what}: {last}")
            if job["status"] == "complete":
                return job["result"] or {}
            if job["status"] in ("error", "cancelled"):
                raise LogBenchError(f"{what} failed: {job.get('error') or job['status']}")
            if time.monotonic() > end:
                raise LogBenchError(f"{what} timed out after {self.timeout:.0f} s")
            self.sleep(self.poll)

    # ------------------------------------------------------------------ the one thing we need

    def fetch_newest(self, on_phase: Callable[[str], None] | None = None, with_pi: bool = False,
                     prefer: str = "akit_") -> dict:
        """Download the newest roboRIO log. Returns LogBench's result: {'log': path relative to its log
        root, 'pi_sessions': [...], 'warnings': [...]}, plus 'name', 'rio_size_bytes' and 'seconds'.

        `prefer`: the roboRIO also writes WPILib's own FRC_*.wpilog (NetworkTables mirrored, written out
        of time order); the AdvantageKit log (akit_*) is the one the analysis needs, and whichever was
        flushed last is not a reliable way to tell them apart. Logs starting with `prefer` win if any
        exist; otherwise the newest of anything.

        `with_pi`: also download the Pis' vision recordings paired with the log. Off by default: they are
        many MB of camera frames, and every extra session since the last log rotation comes along, so
        each fetch is bigger than the last. Experiments that score the robot log don't need them."""
        t0 = time.monotonic()
        start = self._call("POST", "/api/remote/sessions/jobs")
        if not start.get("configured", True):
            raise LogBenchError("LogBench has no remote_config.json, so it can't fetch from the robot "
                                "(see tools/logbench/remote_config.json.example)")
        listing = self._wait(start["job_id"], "listing the robot's logs", on_phase)
        logs = listing.get("rio_logs") or []
        if not logs:
            raise LogBenchError("the roboRIO has no logs to fetch")
        candidates = [r for r in logs if str(r.get("name", "")).startswith(prefer)] if prefer else []
        newest = max(candidates or logs, key=lambda r: r.get("mtime") or 0)
        pi_sessions: list[dict] = []
        if with_pi:
            for p in listing.get("pairings") or []:
                if p.get("rio_log") == newest["name"]:
                    pi_sessions = list(p.get("pi_sessions") or [])
        job = self._call("POST", "/api/remote/bundle/jobs",
                         {"rio_log": newest["name"], "pi_sessions": pi_sessions, "manual": False})
        result = self._wait(job["job_id"], f"downloading {newest['name']}", on_phase)
        result["name"] = newest["name"]
        result["rio_size_bytes"] = newest.get("size")
        result["seconds"] = round(time.monotonic() - t0, 1)
        return result
