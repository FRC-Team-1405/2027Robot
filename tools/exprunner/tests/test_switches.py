"""Robot-code experiment switches: the runner flips them, checks the robot reports them, records them, restores them."""
import textwrap

import pytest

from exprunner import cli, robot
from exprunner.manifest import Manifest
from exprunner.plan import PlanError, load
from tests.fakes import FakeLink, FakeLogBench, FakePv, World

PLAN = textwrap.dedent('''
    experiment = "TEST-switch"
    kind = "robot"
    routine = "Teleop, sticks untouched, 2 minutes"

    [[runs]]
    id = "off1"
    switches = { RIO_PROCESS_CPU_LOGGING = false }

    [[runs]]
    id = "on1"
    what = "Switch on"
    switches = { RIO_PROCESS_CPU_LOGGING = true }
    prompt = "Enable teleop for 2 minutes, sticks untouched."

    [[runs]]
    id = "off2"
    switches = { RIO_PROCESS_CPU_LOGGING = false }
''')


@pytest.fixture
def plan(tmp_path):
    f = tmp_path / "runs.toml"
    f.write_text(PLAN)
    return load(f)


def session(plan, world=None, link=None, lb=None):
    world = world or World(cameras=())
    s = robot.Session(plan=plan, link=link or FakeLink(world), pi_hosts={}, logbench=lb, pv=FakePv(world),
                      say=lambda t: None, sleep=lambda x: None, fetch="each")
    return s


def test_a_plan_can_be_switches_only(plan):
    assert plan.cameras == [] and plan.run("on1").switches == {"RIO_PROCESS_CPU_LOGGING": True}
    assert plan.settings_for(plan.run("on1")) == {}
    assert robot.plan_switch_names(plan) == ["RIO_PROCESS_CPU_LOGGING"]


@pytest.mark.parametrize("edit", [
    ('switches = { RIO_PROCESS_CPU_LOGGING = true }', 'switches = { rio_process = true }'),     # not UPPER_SNAKE_CASE
    ('switches = { RIO_PROCESS_CPU_LOGGING = true }', 'switches = { RIO_PROCESS_CPU_LOGGING = "yes" }'),
    ('switches = { RIO_PROCESS_CPU_LOGGING = true }', 'use = { LeftCam = "A" }'),                # names a camera, plan has none
])
def test_switch_plan_errors(tmp_path, edit):
    f = tmp_path / "bad.toml"
    f.write_text(PLAN.replace(*edit, 1))
    with pytest.raises(PlanError):
        load(f)


def test_a_run_flips_the_switch_confirms_it_and_records_it(plan):
    s = session(plan)
    m = Manifest.open(plan.folder, plan.experiment)
    s.link.i = 0
    assert robot.run_one(s, plan.run("on1"), m)
    assert s.link.switch_writes == [("RIO_PROCESS_CPU_LOGGING", True)]
    e = m.entry("on1", robot.BOARD)
    assert e["switches_asked"] == {"RIO_PROCESS_CPU_LOGGING": True}
    assert e["switches_read_back"] == {"RIO_PROCESS_CPU_LOGGING": True}
    assert e["enable_window"]["t_disable"] > e["enable_window"]["t_enable"]
    # the state before the session is remembered, to put back at the end
    assert m.data["baseline_switches"] == {"RIO_PROCESS_CPU_LOGGING": False}


def test_a_switch_already_as_asked_is_not_written_again(plan):
    s = session(plan)
    m = Manifest.open(plan.folder, plan.experiment)
    assert robot.run_one(s, plan.run("off1"), m)
    assert s.link.switch_writes == []


def test_an_on_off_on_session_toggles_and_finish_restores(plan):
    s = session(plan)
    m = Manifest.open(plan.folder, plan.experiment)
    for rid in ("on1", "off1", "on1"):
        s.link.i = 0
        assert robot.run_one(s, plan.run(rid), m)
    assert [v for _n, v in s.link.switch_writes] == [True, False, True]
    assert s.link.switch("RIO_PROCESS_CPU_LOGGING") is True
    assert robot.finish(s, m)
    assert s.link.switch("RIO_PROCESS_CPU_LOGGING") is False       # what it was before the first run


def test_robot_code_without_the_switch_is_explained(plan):
    s = session(plan)
    s.link.switches.clear()                                         # the deployed code doesn't have it
    m = Manifest.open(plan.folder, plan.experiment)
    assert not robot.run_one(s, plan.run("on1"), m)
    e = m.entry("on1", robot.BOARD)
    assert "isn't publishing /Tuning/ExperimentSwitches/RIO_PROCESS_CPU_LOGGING" in e["error"] and "deploy" in e["error"]


def test_a_switch_the_robot_ignores_fails_the_run(plan):
    s = session(plan)
    s.link.set_switch = lambda n, v: None                            # written, but the robot never changes it
    t = {"now": 0.0}
    s.clock = lambda: t["now"]
    s.sleep = lambda x: t.__setitem__("now", t["now"] + 1.0)
    m = Manifest.open(plan.folder, plan.experiment)
    assert not robot.run_one(s, plan.run("on1"), m)
    assert "switches didn't take" in m.entry("on1", robot.BOARD)["error"]


def test_a_switch_changing_during_the_run_fails_it(plan):
    s = session(plan)
    s.link.i = 0
    real_now = s.link.now

    def now_and_flip():
        s.link.switches["RIO_PROCESS_CPU_LOGGING"] = False           # someone flipped it back mid-run
        return real_now()

    s.link.now = now_and_flip
    m = Manifest.open(plan.folder, plan.experiment)
    assert not robot.run_one(s, plan.run("on1"), m)
    assert "switch RIO_PROCESS_CPU_LOGGING" in m.entry("on1", robot.BOARD)["drifted_during_run"]


def test_without_a_robot_link_switch_runs_are_refused(plan):
    s = session(plan)
    s.link = None
    s.ask = lambda p: ""
    m = Manifest.open(plan.folder, plan.experiment)
    assert not robot.run_one(s, plan.run("on1"), m)
    assert "needs the robot link" in m.entry("on1", robot.BOARD)["error"]


def test_doctor_reports_switches(plan):
    said = []
    s = session(plan)
    s.say = said.append
    assert robot.doctor(s) in (True, False)
    assert any("switch RIO_PROCESS_CPU_LOGGING: the robot reports False" in t for t in said)
    s.link.switches.clear()
    said.clear()
    assert not robot.doctor(s)
    assert any("FAIL switch RIO_PROCESS_CPU_LOGGING" in t for t in said)


def test_cli_check_and_status_show_switches(plan, capsys):
    assert cli.main(["check", str(plan.path)]) == 0
    out = capsys.readouterr().out
    assert "switches: RIO_PROCESS_CPU_LOGGING=True" in out
    assert cli.main(["status", str(plan.path)]) == 0
    assert "RIO_PROCESS_CPU_LOGGING=True" in capsys.readouterr().out
