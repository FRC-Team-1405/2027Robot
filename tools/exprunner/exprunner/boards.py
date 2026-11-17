"""Orange Pi boards from coprocessor/robots.json (the same file Bootstrap-OrangePi.ps1 reads)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ROBOTS_JSON = REPO / "coprocessor" / "robots.json"


@dataclass(frozen=True)
class Board:
    name: str
    hosts: tuple[str, ...]
    cameras: tuple[str, ...]


def load(robot: str | None = None, path: Path = ROBOTS_JSON) -> dict[str, Board]:
    data = json.loads(path.read_text(encoding="utf-8"))
    name = robot or data.get("defaultRobot")
    robots = data.get("robots", {})
    if name not in robots:
        raise ValueError(f"robot {name!r} isn't in {path.name} (robots: {', '.join(robots)})")
    out = {}
    for b in robots[name].get("boards", []):
        out[b["name"]] = Board(b["name"], tuple(b.get("hosts", [])),
                               tuple(c["name"] for c in b.get("cameras", [])))
    return out
