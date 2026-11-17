"""The run loop against a fake Pi: commands, fetched results, manifest, resume."""
import json
import shlex
import subprocess
from pathlib import Path

import pytest

from exprunner import bench, cli
from exprunner import plan as P
from exprunner.manifest import Manifest
from exprunner.remote import Pi, RemoteError

PLAN = """
experiment = "X-1"
kind = "bench"
boards = ["LeftPi", "RightPi"]

[[runs]]
id = "S0"
step = "selftest"

[[runs]]
id = "C1"
step = "capture"
prompt = "tags please"
args = { name = "800x600", width = 800, height = 600, fps = 100 }
"""


class FakePi(Pi):
    """Pretends to be a Pi: runs nothing, 'produces' result.json for every step except failing ones."""

    def __init__(self, name, fail_steps=(), unreachable=False):
        super().__init__(name, [f"{name}.local"])
        self.fail_steps, self.unreachable = set(fail_steps), unreachable
        self.commands, self.put = [], []
        self.host = None if unreachable else f"{name}.local"

    def connect(self):
        if self.unreachable:
            raise RemoteError(f"{self.name}: can't reach it")
        return self.host

    def check(self, command, timeout=60):
        self.commands.append(("check", command))
        return ""

    def stream(self, command, log_path=None, echo=None):
        self.commands.append(("stream", command))
        step = shlex.split(command)[2]
        (echo or print)(f"pretend {step}")
        self._last_step = step
        return 1 if step in self.fail_steps else 0

    def put_dir(self, local, remote):
        self.put.append((Path(local), remote))

    def get_dir(self, remote, local):
        local.mkdir(parents=True, exist_ok=True)
        if self._last_step not in self.fail_steps:
            (local / "result.json").write_text(json.dumps({"mode": self._last_step}), encoding="utf-8")


@pytest.fixture
def plan(tmp_path):
    f = tmp_path / "runs.toml"
    f.write_text(PLAN, encoding="utf-8")
    return P.load(f)


def test_command_quotes_and_paths(plan):
    cmd = bench.command(plan, plan.run("C1"))
    assert cmd.startswith("bash bench/code/run.sh capture --results bench/results/X-1/C1 ")
    assert "--name 800x600" in cmd
    weird = P.Run(id="R1", step="steps", args={"frames": "my frames; rm -rf ~"})
    assert "'my frames; rm -rf ~'" in bench.command(plan, weird)


def test_run_records_ok_and_fetches(plan):
    pi = FakePi("LeftPi")
    m = Manifest.open(plan.folder, plan.experiment)
    assert bench.run_on(plan, plan.run("S0"), pi, m, {"sha": "abc"})
    e = m.entry("S0", "LeftPi")
    assert e["status"] == "ok" and e["exit_code"] == 0 and e["git"] == {"sha": "abc"}
    assert (plan.folder / "data" / "S0" / "LeftPi" / "result.json").exists()
    assert (plan.folder / "data" / "S0" / "LeftPi" / "step.log").read_text().startswith("pretend selftest")
    assert pi.commands[0] == ("check", "rm -rf bench/results/X-1/S0")  # old results cleared first
    # the manifest on disk matches
    on_disk = json.loads((plan.folder / "manifest.json").read_text())
    assert on_disk["runs"]["S0"]["LeftPi"]["status"] == "ok"


def test_failed_step_is_recorded_and_redo_keeps_history(plan):
    m = Manifest.open(plan.folder, plan.experiment)
    assert not bench.run_on(plan, plan.run("C1"), FakePi("LeftPi", fail_steps={"capture"}), m, {})
    assert m.entry("C1", "LeftPi")["status"] == "failed" and not m.done("C1", "LeftPi")
    assert bench.run_on(plan, plan.run("C1"), FakePi("LeftPi"), m, {})
    assert m.done("C1", "LeftPi")
    assert m.data["history"][0]["status"] == "failed"


def test_manifest_refuses_another_experiment(plan):
    Manifest.open(plan.folder, plan.experiment).save()
    with pytest.raises(ValueError, match="belongs to"):
        Manifest.open(plan.folder, "Y-2")


def run_cli(monkeypatch, plan, fakes, argv, answers=()):
    monkeypatch.setattr(cli, "_pis", lambda p, only=None: {n: fakes[n] for n in (only or p.boards)})
    monkeypatch.setattr(bench, "sync", lambda pis, **kw: None)
    prompts = []
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda msg="": prompts.append(msg) or next(it, ""))
    code = cli.main(argv + [str(plan.path)] if argv[0] != "run" else argv[:1] + [str(plan.path)] + argv[1:])
    return code, prompts


def test_cli_run_resumes_and_prompts(monkeypatch, plan, capsys):
    fakes = {"LeftPi": FakePi("LeftPi"), "RightPi": FakePi("RightPi", fail_steps={"capture"})}
    code, prompts = run_cli(monkeypatch, plan, fakes, ["run"])
    assert code == 1  # stopped at RightPi's failed capture
    assert len(prompts) == 1 and "tags please" in prompts[0]
    m = Manifest.open(plan.folder, plan.experiment)
    assert m.done("S0", "LeftPi") and m.done("S0", "RightPi") and m.done("C1", "LeftPi")
    assert not m.done("C1", "RightPi")

    # Second go: only RightPi's C1 is left.
    fakes = {"LeftPi": FakePi("LeftPi"), "RightPi": FakePi("RightPi")}
    code, prompts = run_cli(monkeypatch, plan, fakes, ["run"])
    assert code == 0
    assert [c for c in fakes["LeftPi"].commands if c[0] == "stream"] == []
    assert len([c for c in fakes["RightPi"].commands if c[0] == "stream"]) == 1

    # Everything done: nothing to run.
    code, _ = run_cli(monkeypatch, plan, fakes, ["run"])
    assert code == 0 and "nothing to run" in capsys.readouterr().out


def test_cli_run_named_ids_and_yes(monkeypatch, plan):
    fakes = {"LeftPi": FakePi("LeftPi"), "RightPi": FakePi("RightPi")}
    code, prompts = run_cli(monkeypatch, plan, fakes, ["run", "C1", "--yes", "--board", "LeftPi"])
    assert code == 0 and prompts == []
    assert len([c for c in fakes["LeftPi"].commands if c[0] == "stream"]) == 1
    assert fakes["RightPi"].commands == []


def test_cli_unreachable_board_is_a_clear_error(monkeypatch, plan, capsys):
    fakes = {"LeftPi": FakePi("LeftPi"), "RightPi": FakePi("RightPi", unreachable=True)}
    code, _ = run_cli(monkeypatch, plan, fakes, ["run", "--yes"])
    assert code == 2 and "can't reach" in capsys.readouterr().err


def test_cli_check_and_status(monkeypatch, plan, capsys):
    monkeypatch.setattr(cli.boards, "load", lambda robot=None: {
        "LeftPi": cli.boards.Board("LeftPi", ("LeftPi.local",), ()),
        "RightPi": cli.boards.Board("RightPi", ("RightPi.local",), ())})
    assert cli.main(["check", str(plan.path)]) == 0
    out = capsys.readouterr().out
    assert "bash bench/code/run.sh capture" in out and "prompt: tags please" in out
    assert cli.main(["status", str(plan.path)]) == 0
    assert "LeftPi: to do" in capsys.readouterr().out


def test_pi_connect_tries_hosts_in_order(tmp_path):
    key = tmp_path / "key"
    key.write_text("k")
    calls = []

    def fake_run(argv, **kw):
        calls.append(argv[-2])
        ok = argv[-2].endswith("@10.0.0.2")
        return subprocess.CompletedProcess(argv, 0 if ok else 255, "", "" if ok else "ssh: connect: timed out")

    pi = Pi("LeftPi", ["LeftPi.local", "10.0.0.2"], key=key, run=fake_run)
    import shutil
    if not (shutil.which("ssh") and shutil.which("scp")):
        pytest.skip("no OpenSSH client on this machine")
    assert pi.connect() == "10.0.0.2"
    assert calls == ["pi@LeftPi.local", "pi@10.0.0.2"]


def test_pi_without_key_says_how_to_get_it(tmp_path):
    pi = Pi("LeftPi", ["LeftPi.local"], key=tmp_path / "missing")
    with pytest.raises(RemoteError, match="Bootstrap-OrangePi"):
        pi.connect()
