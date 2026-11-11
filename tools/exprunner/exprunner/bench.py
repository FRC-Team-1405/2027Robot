"""Bench runs: copy the bench bundle to each Pi, run a step there over SSH, fetch its results.

Layout on the Pi (relative to the pi user's home):
    bench/code/                    the bundle (replaced on every sync)
    bench/frames/<name>.mjpg       captured frames (kept between runs; big)
    bench/results/<experiment>/<run>/   one run's result.json, env.json, ...

Layout on the laptop, next to the plan:
    data/<run>/<board>/            the run's results folder from that Pi, plus step.log
    manifest.json                  what ran, when, from which commit, and whether it worked
"""
from __future__ import annotations

import re
import shlex
import time
from pathlib import Path
from typing import Callable, Iterable

from . import build
from .manifest import Manifest, now_utc
from .plan import Plan, Run
from .remote import Pi, RemoteError

CODE_DIR = "bench/code"


def safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)


def remote_results(plan: Plan, run: Run) -> str:
    return f"bench/results/{safe(plan.experiment)}/{safe(run.id)}"


def command(plan: Plan, run: Run) -> str:
    """The shell command run on the Pi for this run."""
    parts = ["bash", f"{CODE_DIR}/run.sh", run.step, "--results", remote_results(plan, run), *run.cli_args()]
    return " ".join(shlex.quote(p) for p in parts)


def sync(pis: Iterable[Pi], log: Callable[[str], None] = print, stage_dir: Path | None = None) -> Path:
    """Builds the bundle once and copies it to every Pi (copy only; nothing is installed)."""
    staged = build.stage(stage_dir or build.BUILD_DIR, log=log)
    for pi in pis:
        log(f"copying bench bundle to {pi.name} ({pi.connect()}:~/{CODE_DIR})")
        pi.put_dir(staged, CODE_DIR)
    return staged


def run_on(plan: Plan, run: Run, pi: Pi, manifest: Manifest, git: dict,
           log: Callable[[str], None] = print) -> bool:
    """Runs one run on one Pi and records it. Returns True if the step succeeded."""
    local = plan.folder / "data" / safe(run.id) / pi.name
    cmd = command(plan, run)
    log(f"{run.id} on {pi.name}: {cmd}")
    lines: list[str] = []
    started = now_utc()
    t0 = time.monotonic()
    entry = {"status": "failed", "step": run.step, "args": run.args, "command": cmd, "started": started,
             "git": git, "board": pi.name}
    try:
        pi.check(f"rm -rf {shlex.quote(remote_results(plan, run))}")
        code = pi.stream(cmd, echo=lambda line: (lines.append(line), print(f"  [{pi.name}] {line}", flush=True)))
        entry.update(exit_code=code, host=pi.host)
        try:
            pi.get_dir(remote_results(plan, run), local)
        except RemoteError as e:
            entry["fetch_error"] = str(e)
            local.mkdir(parents=True, exist_ok=True)
        produced = (local / ("env.json" if run.step == "env" else "result.json")).exists()
        entry["status"] = "ok" if code == 0 and produced else "failed"
    except RemoteError as e:
        entry["error"] = str(e)
        local.mkdir(parents=True, exist_ok=True)
    finally:
        local.mkdir(parents=True, exist_ok=True)
        (local / "step.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
        entry.update(finished=now_utc(), seconds=round(time.monotonic() - t0, 1),
                     results=local.relative_to(plan.folder).as_posix())
        manifest.record(run.id, pi.name, entry)
    log(f"{run.id} on {pi.name}: {entry['status']}" + (f" ({entry.get('error') or entry.get('fetch_error')})"
                                                     if entry['status'] != 'ok' else ""))
    return entry["status"] == "ok"
