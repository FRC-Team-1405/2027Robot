"""Attempts: each time an experiment is run is its own dated folder, ``<experiment>/attempts/<date>/``.

An experiment (a question, a method, a plan) stays put; what was *run* goes in an attempt: its ``manifest.json`` (what ran, which
log, the settings read back), ``data/`` (results fetched from the Pis, extracts) and ``results.json`` (the analysis). Running it
again is a new attempt, so nothing from an earlier session is overwritten or mixed in, and no flag is needed to start clean.

Which attempt does a command use?
  * ``--attempt NAME`` names it (a date like ``2026-11-21``, optionally with a label: ``2026-11-21-redo``);
  * otherwise ``run`` **continues the latest attempt if it still has unfinished runs and was touched in the last 18 hours** (so a
    session that runs past midnight stays together, and a stopped one resumes), and **starts a new one, named for today,** if not;
  * the other commands (status, fetch, apply, finish) use the latest attempt.
"""
from __future__ import annotations

import json
import re
import time
from datetime import date
from pathlib import Path

RESUME_WINDOW_S = 18 * 3600
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class AttemptError(ValueError):
    pass


def root(experiment_dir: Path) -> Path:
    return Path(experiment_dir) / "attempts"


def list_attempts(experiment_dir: Path) -> list[Path]:
    """Attempt folders, oldest first (names start with the date, so the name sort is the date sort)."""
    r = root(experiment_dir)
    return sorted(p for p in r.iterdir() if p.is_dir()) if r.is_dir() else []


def latest(experiment_dir: Path) -> Path | None:
    found = list_attempts(experiment_dir)
    return found[-1] if found else None


def _unfinished(attempt: Path, expected: dict[str, list[str]] | None) -> bool:
    """True if the attempt's manifest doesn't show every run ok on every board it should run on. `expected` is {run id: boards}."""
    f = attempt / "manifest.json"
    if not f.exists():
        return False
    try:
        runs = json.loads(f.read_text(encoding="utf-8")).get("runs", {})
    except ValueError:
        return False
    if expected is None:
        return False
    return any((runs.get(rid) or {}).get(b, {}).get("status") != "ok" for rid, boards in expected.items() for b in boards)


def resolve(experiment_dir: Path, requested: str | None = None, create: bool = False,
            expected: dict[str, list[str]] | None = None, today: str | None = None, now: float | None = None,
            force_new: bool = False) -> Path | None:
    """The attempt folder to use. With create=False, returns the requested/latest one or None. With create=True (for `run`),
    continues the latest unfinished attempt or makes a new one."""
    base = root(experiment_dir)
    if requested:
        if not _NAME.match(requested):
            raise AttemptError(f"attempt name {requested!r}: use a date like 2026-11-21, optionally with a label (2026-11-21-redo)")
        path = base / requested
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path if (path.exists() or create) else None
    last = latest(experiment_dir)
    if not create:
        return last
    now = time.time() if now is None else now
    if (last is not None and not force_new and _unfinished(last, expected)
            and now - (last / "manifest.json").stat().st_mtime < RESUME_WINDOW_S):
        return last
    stem = today or date.today().isoformat()
    name, n = stem, 1
    while (base / name).exists():
        n += 1
        name = f"{stem}-{n}"
    path = base / name
    path.mkdir(parents=True)
    return path
