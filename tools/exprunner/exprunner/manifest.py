"""The manifest: what actually ran, written next to the plan as ``manifest.json``.

One entry per (run, board). Re-running a run replaces its entry; the previous one is kept under
``history`` so a redo never silently loses a result.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FILE = "manifest.json"


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Manifest:
    path: Path
    data: dict[str, Any]

    @classmethod
    def open(cls, folder: Path, experiment: str) -> "Manifest":
        path = folder / FILE
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("experiment") != experiment:
                raise ValueError(f"{path} belongs to {data.get('experiment')!r}, not {experiment!r}")
        else:
            data = {"experiment": experiment, "runs": {}, "history": []}
        return cls(path, data)

    def entry(self, run_id: str, board: str) -> dict[str, Any] | None:
        return self.data["runs"].get(run_id, {}).get(board)

    def done(self, run_id: str, board: str) -> bool:
        e = self.entry(run_id, board)
        return bool(e and e.get("status") == "ok")

    def record(self, run_id: str, board: str, entry: dict[str, Any]) -> None:
        old = self.entry(run_id, board)
        if old is not None:
            self.data["history"].append({"run": run_id, "board": board, **old})
        self.data["runs"].setdefault(run_id, {})[board] = entry
        self.save()

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1) + "\n", encoding="utf-8")
        tmp.replace(self.path)
