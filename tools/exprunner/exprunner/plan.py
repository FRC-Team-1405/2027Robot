"""Run plan files (``runs.toml``): what an experiment runs, one entry per run.

A plan lives next to its experiment's README. Example (bench kind)::

    experiment = "VIS-2026-11-11-pv-frame-cost"
    kind = "bench"                 # runs on the Pis over SSH; no robot, no auto
    robot = "2027"                 # block in coprocessor/robots.json (optional: its default)
    boards = ["LeftPi"]            # which Pis, by robots.json name

    [defaults.steps]               # options every run of step "steps" gets, unless the run overrides
    max = 200

    [[runs]]
    id = "C1"
    what = "Capture 800x600 @100 frames"
    step = "capture"
    prompt = "Point the camera at two or more tags."   # shown before the run; waits for Enter
    args = { name = "800x600", width = 800, height = 600, fps = 100 }

A ``robot`` plan sets PhotonVision on the Pis, hands over for an auto, and fetches the log::

    experiment = "VIS-2026-11-14-pv-crossover-odometry"
    kind = "robot"
    routine = "CircleFacingTag_Tag10"              # the auto the person enables (shown in the prompt)
    cameras = ["LeftPi/LeftCam", "RightPi/RightCam"]   # Pi/camera, as in coprocessor/robots.json

    [defaults]                                      # every setting below starts from these
    decimate = 2
    threads = 8
    low_latency = false

    [settings.A]
    camera_mode = "800x600 MJPG @100"
    [settings.B]
    camera_mode = "1280x800 MJPG @100"

    [[runs]]
    id = "X1a"
    what = "Left on A, Right on B"
    use = { LeftCam = "A", RightCam = "B" }         # camera -> setting name ("all = "A"" sets every camera)

The settings a plan can name are in ``settings.py``. See docs/experiment-runner-plan.md.
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BENCH_STEPS = ("env", "capture", "selftest", "inspect", "steps", "inflight")
KINDS = ("bench", "robot")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
# Handled by run.sh itself rather than passed on to the step.
RUNNER_OPTIONS = ("stop-pv", "cores")


class PlanError(ValueError):
    """The plan file is wrong; the message says where."""


@dataclass
class Run:
    id: str
    step: str = ""
    what: str = ""
    prompt: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    boards: list[str] | None = None  # None = the plan's boards
    use: dict[str, str] = field(default_factory=dict)  # robot runs: camera -> setting name

    def cli_args(self) -> list[str]:
        """The run's options as ``--key value`` pairs, in a stable order."""
        out: list[str] = []
        for key in sorted(self.args):
            out += [f"--{key}", format_value(self.args[key])]
        return out


@dataclass
class Plan:
    path: Path
    experiment: str
    kind: str
    boards: list[str]
    robot: str | None = None
    runs: list[Run] = field(default_factory=list)
    # robot plans only
    routine: str = ""
    cameras: list[tuple[str, str]] = field(default_factory=list)   # (Pi, camera)
    defaults: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, dict[str, Any]] = field(default_factory=dict)

    def settings_for(self, run: "Run") -> dict[str, dict[str, Any]]:
        """{camera: full settings} for a robot run: the plan's defaults, then the named setting on top."""
        out: dict[str, dict[str, Any]] = {}
        for _pi, cam in self.cameras:
            name = run.use.get(cam)
            if name is None:
                continue
            out[cam] = {**self.defaults, **self.settings[name]}
        return out

    @property
    def folder(self) -> Path:
        return self.path.parent

    def run(self, run_id: str) -> Run:
        for r in self.runs:
            if r.id == run_id:
                return r
        raise PlanError(f"no run {run_id!r} in {self.path.name} (runs: {', '.join(r.id for r in self.runs)})")

    def boards_for(self, run: Run) -> list[str]:
        return run.boards if run.boards is not None else self.boards


def format_value(v: Any) -> str:
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (list, tuple)):
        return ",".join(format_value(x) for x in v)
    return str(v)


def load(path: str | Path) -> Plan:
    path = Path(path).resolve()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise PlanError(f"plan not found: {path}") from None
    except tomllib.TOMLDecodeError as e:
        raise PlanError(f"{path.name}: {e}") from None
    return parse(data, path)


def parse(data: dict[str, Any], path: Path) -> Plan:
    if data.get("kind") == "robot":
        return parse_robot(data, path)

    def need(key: str, kind: type) -> Any:
        if key not in data:
            raise PlanError(f"{path.name}: missing {key!r}")
        if not isinstance(data[key], kind):
            raise PlanError(f"{path.name}: {key!r} must be a {kind.__name__}")
        return data[key]

    known_top = {"experiment", "kind", "robot", "boards", "defaults", "runs"}
    extra = set(data) - known_top
    if extra:
        raise PlanError(f"{path.name}: unknown keys {sorted(extra)}")

    experiment = need("experiment", str)
    kind = need("kind", str)
    if kind not in KINDS:
        raise PlanError(f"{path.name}: kind must be one of {KINDS}, not {kind!r}")
    boards = need("boards", list)
    if not boards or not all(isinstance(b, str) for b in boards):
        raise PlanError(f"{path.name}: 'boards' must be a non-empty list of board names")
    robot = data.get("robot")
    if robot is not None and not isinstance(robot, str):
        raise PlanError(f"{path.name}: 'robot' must be a string")

    defaults = data.get("defaults", {})
    if not isinstance(defaults, dict) or not all(isinstance(v, dict) for v in defaults.values()):
        raise PlanError(f"{path.name}: [defaults] holds one table per step, e.g. [defaults.steps]")
    for step in defaults:
        if step not in BENCH_STEPS:
            raise PlanError(f"{path.name}: [defaults.{step}]: unknown step (steps: {', '.join(BENCH_STEPS)})")

    raw_runs = need("runs", list)
    if not raw_runs:
        raise PlanError(f"{path.name}: no [[runs]]")
    runs: list[Run] = []
    seen: set[str] = set()
    for i, r in enumerate(raw_runs, 1):
        where = f"{path.name}: run #{i}"
        if not isinstance(r, dict):
            raise PlanError(f"{where}: must be a table")
        extra = set(r) - {"id", "what", "step", "prompt", "args", "boards"}
        if extra:
            raise PlanError(f"{where}: unknown keys {sorted(extra)}")
        rid = r.get("id")
        if not isinstance(rid, str) or not _ID.match(rid):
            raise PlanError(f"{where}: 'id' must be letters, digits, '-', '_' or '.'")
        where = f"{path.name}: run {rid}"
        if rid in seen:
            raise PlanError(f"{where}: duplicate id")
        seen.add(rid)
        step = r.get("step")
        if step not in BENCH_STEPS:
            raise PlanError(f"{where}: 'step' must be one of {', '.join(BENCH_STEPS)}")
        args = dict(defaults.get(step, {}))
        run_args = r.get("args", {})
        if not isinstance(run_args, dict):
            raise PlanError(f"{where}: 'args' must be a table")
        args.update(run_args)
        for k, v in args.items():
            if not re.match(r"^[a-z][a-z0-9-]*$", k):
                raise PlanError(f"{where}: option {k!r}: use lower-case words joined by '-'")
            if k in ("results", "out"):
                raise PlanError(f"{where}: {k!r} is set by the runner")
            if isinstance(v, dict) or (isinstance(v, list) and any(isinstance(x, (dict, list)) for x in v)):
                raise PlanError(f"{where}: option {k!r} must be a number, string, boolean or flat list")
        run_boards = r.get("boards")
        if run_boards is not None:
            if not isinstance(run_boards, list) or not all(isinstance(b, str) for b in run_boards):
                raise PlanError(f"{where}: 'boards' must be a list of board names")
            unknown = set(run_boards) - set(boards)
            if unknown:
                raise PlanError(f"{where}: boards {sorted(unknown)} aren't in the plan's boards")
        for text_key in ("what", "prompt"):
            if text_key in r and not isinstance(r[text_key], str):
                raise PlanError(f"{where}: {text_key!r} must be a string")
        runs.append(Run(id=rid, step=step, what=r.get("what", ""), prompt=r.get("prompt", ""),
                        args=args, boards=run_boards))
    return Plan(path=path, experiment=experiment, kind=kind, boards=list(boards), robot=robot, runs=runs)


def parse_robot(data: dict[str, Any], path: Path) -> Plan:
    from .settings import SettingsError, validate

    where = path.name
    extra = set(data) - {"experiment", "kind", "robot", "routine", "cameras", "defaults", "settings", "runs"}
    if extra:
        raise PlanError(f"{where}: unknown keys {sorted(extra)}")
    for key, kind in (("experiment", str), ("routine", str), ("cameras", list), ("settings", dict), ("runs", list)):
        if key not in data:
            raise PlanError(f"{where}: missing {key!r}")
        if not isinstance(data[key], kind):
            raise PlanError(f"{where}: {key!r} must be a {kind.__name__}")
    cameras: list[tuple[str, str]] = []
    for c in data["cameras"]:
        if not isinstance(c, str) or c.count("/") != 1 or not all(c.split("/")):
            raise PlanError(f"{where}: cameras are written Pi/camera, e.g. \"LeftPi/LeftCam\" (got {c!r})")
        cameras.append((c.split("/")[0], c.split("/")[1]))
    if not cameras:
        raise PlanError(f"{where}: 'cameras' is empty")
    if len({cam for _pi, cam in cameras}) != len(cameras):
        raise PlanError(f"{where}: two cameras share a name; camera names must be unique")
    try:
        defaults = validate(data.get("defaults", {}), f"{where}: [defaults]")
        settings = {name: validate(tbl, f"{where}: [settings.{name}]") for name, tbl in data["settings"].items()}
    except SettingsError as e:
        raise PlanError(str(e)) from None
    if not settings:
        raise PlanError(f"{where}: no [settings.X] tables")
    camera_names = [cam for _pi, cam in cameras]
    runs: list[Run] = []
    seen: set[str] = set()
    for i, r in enumerate(data["runs"], 1):
        here = f"{where}: run #{i}"
        if not isinstance(r, dict):
            raise PlanError(f"{here}: must be a table")
        extra = set(r) - {"id", "what", "prompt", "use"}
        if extra:
            raise PlanError(f"{here}: unknown keys {sorted(extra)}")
        rid = r.get("id")
        if not isinstance(rid, str) or not _ID.match(rid):
            raise PlanError(f"{here}: 'id' must be letters, digits, '-', '_' or '.'")
        here = f"{where}: run {rid}"
        if rid in seen:
            raise PlanError(f"{here}: duplicate id")
        seen.add(rid)
        use = r.get("use")
        if not isinstance(use, dict) or not use:
            raise PlanError(f"{here}: 'use' must name a setting per camera, e.g. use = {{ LeftCam = \"A\", RightCam = \"B\" }}")
        if "all" in use:
            if set(use) != {"all"}:
                raise PlanError(f"{here}: use 'all' on its own, or name each camera")
            use = {cam: use["all"] for cam in camera_names}
        unknown = set(use) - set(camera_names)
        if unknown:
            raise PlanError(f"{here}: cameras {sorted(unknown)} aren't in the plan's cameras ({', '.join(camera_names)})")
        for cam, name in use.items():
            if name not in settings:
                raise PlanError(f"{here}: {cam} uses setting {name!r}, which isn't defined (have: {', '.join(settings)})")
        for text_key in ("what", "prompt"):
            if text_key in r and not isinstance(r[text_key], str):
                raise PlanError(f"{here}: {text_key!r} must be a string")
        runs.append(Run(id=rid, what=r.get("what", ""), prompt=r.get("prompt", ""), use=dict(use)))
    if not runs:
        raise PlanError(f"{where}: no [[runs]]")
    robot = data.get("robot")
    if robot is not None and not isinstance(robot, str):
        raise PlanError(f"{where}: 'robot' must be a string")
    return Plan(path=path, experiment=data["experiment"], kind="robot", boards=["robot"], robot=robot, runs=runs,
                routine=data["routine"], cameras=cameras, defaults=defaults, settings=settings)
