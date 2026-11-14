from pathlib import Path

import pytest

from exprunner import plan as P

REPO = Path(__file__).resolve().parents[3]
FRAME_COST = REPO / "docs" / "experiments" / "vision" / "2026-11-11-pv-frame-cost" / "runs.toml"


def write(tmp_path, text):
    f = tmp_path / "runs.toml"
    f.write_text(text, encoding="utf-8")
    return f


BASIC = """
experiment = "X-1"
kind = "bench"
boards = ["LeftPi", "RightPi"]

[defaults.steps]
cores = "4-7"
threads = [1, 4]

[[runs]]
id = "T1"
step = "steps"
args = { frames = "800x600", threads = [8] }

[[runs]]
id = "C1"
step = "capture"
prompt = "point it at tags"
boards = ["LeftPi"]
args = { name = "a", width = 800, height = 600, fps = 100, verbose = true }
"""


def test_defaults_merge_and_run_overrides(tmp_path):
    p = P.load(write(tmp_path, BASIC))
    t1 = p.run("T1")
    assert t1.args == {"cores": "4-7", "threads": [8], "frames": "800x600"}
    assert t1.cli_args() == ["--cores", "4-7", "--frames", "800x600", "--threads", "8"]
    c1 = p.run("C1")
    assert "cores" not in c1.args  # defaults are per step
    assert "--verbose" in c1.cli_args() and c1.cli_args()[c1.cli_args().index("--verbose") + 1] == "yes"
    assert p.boards_for(c1) == ["LeftPi"] and p.boards_for(t1) == ["LeftPi", "RightPi"]


def test_list_values_join_with_commas():
    assert P.format_value([1, 2, 3]) == "1,2,3"
    assert P.format_value(False) == "no"


@pytest.mark.parametrize("bad, message", [
    ('kind = "nope"', "kind must be"),
    ('boards = []', "non-empty"),
    ('bogus = 1', "unknown keys"),
])
def test_top_level_errors(tmp_path, bad, message):
    key = bad.split(" = ")[0]
    lines = [ln for ln in BASIC.splitlines() if not ln.startswith(key + " =")]
    # put the replacement before the first table so it stays top-level
    text = "\n".join([bad] + lines)
    with pytest.raises(P.PlanError, match=message):
        P.load(write(tmp_path, text))


@pytest.mark.parametrize("run, message", [
    ('id = "T1"\nstep = "steps"', "duplicate id"),
    ('id = "bad id"\nstep = "steps"', "'id' must be"),
    ('id = "Z"\nstep = "launch"', "'step' must be"),
    ('id = "Z"\nstep = "steps"\nargs = { results = "x" }', "set by the runner"),
    ('id = "Z"\nstep = "steps"\nargs = { Frames = "x" }', "lower-case"),
    ('id = "Z"\nstep = "steps"\nboards = ["MiddlePi"]', "aren't in the plan"),
    ('id = "Z"\nstep = "steps"\ncolour = "red"', "unknown keys"),
])
def test_run_errors(tmp_path, run, message):
    with pytest.raises(P.PlanError, match=message):
        P.load(write(tmp_path, BASIC + "\n[[runs]]\n" + run + "\n"))


def test_unknown_defaults_step(tmp_path):
    with pytest.raises(P.PlanError, match="unknown step"):
        P.load(write(tmp_path, BASIC.replace("[defaults.steps]", "[defaults.launch]")))


def test_missing_plan_and_bad_toml(tmp_path):
    with pytest.raises(P.PlanError, match="not found"):
        P.load(tmp_path / "missing.toml")
    with pytest.raises(P.PlanError):
        P.load(write(tmp_path, "experiment = "))


def test_frame_cost_plan_loads():
    p = P.load(FRAME_COST)
    assert p.experiment == "VIS-2026-11-11-pv-frame-cost"
    assert [r.id for r in p.runs][:3] == ["S0", "C1", "C2"]
    assert p.run("F1").args["workers"] == [1, 2, 3, 4]
    assert p.run("F0a").args["workers"] == [1]  # run args beat defaults
