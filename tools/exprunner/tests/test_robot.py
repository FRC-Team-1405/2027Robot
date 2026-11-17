"""A robot experiment, end to end, against fakes of the robot, PhotonVision and LogBench."""
import json
import textwrap

import pytest

from exprunner import cli, robot
from exprunner.logbench import LogBenchClient, LogBenchError
from exprunner.manifest import Manifest
from exprunner.plan import PlanError, load
from exprunner.pv import PvError
from tests.fakes import BASE, FakeLink, FakeLogBench, FakePv, World

PLAN = textwrap.dedent('''
    experiment = "TEST-crossover"
    kind = "robot"
    routine = "CircleFacingTag_Tag10"
    cameras = ["LeftPi/LeftCam", "RightPi/RightCam"]

    [defaults]
    decimate = 2
    threads = 8
    low_latency = false

    [settings.A]
    camera_mode = "800x600 MJPG @100"
    [settings.B]
    camera_mode = "1280x800 MJPG @100"

    [[runs]]
    id = "X1"
    what = "Left on A, Right on B"
    use = { LeftCam = "A", RightCam = "B" }

    [[runs]]
    id = "X2"
    use = { LeftCam = "B", RightCam = "A" }

    [[runs]]
    id = "AA"
    use = { all = "A" }
''')


@pytest.fixture
def plan(tmp_path):
    f = tmp_path / "runs.toml"
    f.write_text(PLAN)
    return load(f)


@pytest.fixture
def lb():
    s = FakeLogBench()
    yield s
    s.close()


def session(plan, world=None, link=None, pv=None, lb=None, **kw):
    world = world or World()
    s = robot.Session(plan=plan, link=link or FakeLink(world), pi_hosts={"LeftPi": ["LeftPi.local"], "RightPi": ["RightPi.local"]},
                      logbench=LogBenchClient(lb.url, sleep=lambda x: None) if lb else None,
                      pv=pv or FakePv(world), say=lambda t: None, sleep=lambda x: None, **kw)
    s.world = world
    s.fetch = "each"                    # most tests look at one run's log; the end-of-session fetch has its own
    return s


# ---------------------------------------------------------------- the plan

def test_plan_resolves_settings_per_camera(plan):
    s = plan.settings_for(plan.run("X1"))
    assert s["LeftCam"] == {"decimate": 2, "threads": 8, "low_latency": False, "camera_mode": "800x600 MJPG @100"}
    assert s["RightCam"]["camera_mode"] == "1280x800 MJPG @100"
    assert plan.settings_for(plan.run("AA"))["RightCam"]["camera_mode"] == "800x600 MJPG @100"


def test_plan_errors(tmp_path):
    cases = {
        "unknown setting": PLAN.replace("threads = 8", "thread_count = 8", 1),
        "unknown setting name": PLAN.replace('RightCam = "B"', 'RightCam = "Z"', 1),
        "bad camera": PLAN.replace('use = { LeftCam = "A", RightCam = "B" }', 'use = { LeftCam = "A", Nope = "B" }', 1),
        "bad mode": PLAN.replace("800x600 MJPG @100", "800 by 600", 1),
        "bad type": PLAN.replace("decimate = 2", 'decimate = "two"', 1),
        "no runs": PLAN[:PLAN.index("[[runs]]")],
    }
    for name, text in cases.items():
        f = tmp_path / f"{name.replace(' ', '_')}.toml"
        f.write_text(text)
        with pytest.raises(PlanError):
            load(f)


# ---------------------------------------------------------------- one run

def test_run_applies_checks_waits_fetches_and_records(plan, lb):
    s = session(plan, lb=lb)
    m = Manifest.open(plan.folder, plan.experiment)
    assert robot.run_one(s, plan.run("X1"), m, {"sha": "abc"})
    e = m.entry("X1", robot.BOARD)
    assert e["status"] == "ok" and e["git"] == {"sha": "abc"}
    # only the differing setting was sent: the Right camera's mode
    assert s.world.sent == [("RightCam", {"camera_mode": "1280x800 MJPG @100"})]
    assert e["read_back"]["RightCam"]["camera_mode"] == "1280x800 MJPG @100"
    assert e["read_back"]["LeftCam"]["camera_mode"] == "800x600 MJPG @100"
    # the enable window is in robot time, from the link
    w = e["enable_window"]
    assert w["t_disable"] > w["t_enable"] and w["autonomous"] is True
    # the newest log was fetched (the later mtime), with its suggested Pi session
    assert e["log"]["name"] == "akit_26-11-14_19-11-27.wpilog"
    assert e["log"]["pi_sessions"] == []                  # the Pis' recordings aren't downloaded unless asked
    assert lb.bundle_body["rio_log"] == "akit_26-11-14_19-11-27.wpilog"
    # and the baseline (what the cameras were before) was recorded once, for `finish`
    assert m.data["baseline"]["RightCam"]["camera_mode"] == "800x600 MJPG @100"
    assert (plan.folder / "manifest.json").exists()


def test_a_run_whose_settings_already_match_sends_nothing(plan, lb):
    s = session(plan, lb=lb)
    m = Manifest.open(plan.folder, plan.experiment)
    assert robot.run_one(s, plan.run("AA"), m)
    assert s.world.sent == []


def test_refuses_while_enabled(plan, lb):
    world = World()
    s = session(plan, world, link=FakeLink(world, states=[(True, True)]), lb=lb)
    m = Manifest.open(plan.folder, plan.experiment)
    assert not robot.run_one(s, plan.run("X1"), m)
    e = m.entry("X1", robot.BOARD)
    assert e["status"] == "failed" and "enabled" in e["error"]
    assert world.sent == []


def test_websocket_failure_falls_back_to_the_person(plan, lb):
    """PhotonVision can't be reached: the runner says what to set, waits, and carries on once the Pi shows it."""
    world = World()
    said: list[str] = []
    s = session(plan, world, pv=FakePv(world, fail="can't reach PhotonVision at ws://x"), lb=lb)
    s.say = said.append
    s.settle_timeout = 0          # go straight to asking the person

    ticks = {"n": 0}

    def person_fixes_it(_):
        ticks["n"] += 1
        if ticks["n"] == 3:       # the person changes the mode in the PhotonVision UI
            world.set_now("RightCam", camera_mode="1280x800 MJPG @100")

    s.sleep = person_fixes_it
    m = Manifest.open(plan.folder, plan.experiment)
    assert robot.run_one(s, plan.run("X1"), m)
    text = "\n".join(said)
    assert "couldn't set it automatically" in text and "Set them by hand" in text
    assert "RightCam: camera_mode -> 1280x800 MJPG @100" in text


def test_a_setting_photonvision_ignores_is_caught(plan, lb):
    """The mode 'switched' on the websocket but the Pi never reports it: fail, don't run on the wrong setting."""
    world = World()
    s = session(plan, world, pv=FakePv(world, ignore={"camera_mode"}), lb=lb, wait_for_person=False)
    s.settle_timeout = 3
    t = {"now": 0.0}
    s.clock = lambda: t["now"]
    s.sleep = lambda x: t.__setitem__("now", t["now"] + 1.0)
    m = Manifest.open(plan.folder, plan.experiment)
    assert not robot.run_one(s, plan.run("X1"), m)
    e = m.entry("X1", robot.BOARD)
    assert e["status"] == "failed" and "didn't take" in e["error"] and "camera_mode" in e["error"]
    assert "log" not in e                    # never handed over


def test_settings_that_drift_during_the_run_fail_it(plan, lb):
    world = World()
    link = FakeLink(world)
    s = session(plan, world, link=link, lb=lb)
    real_now = link.now

    def now_and_drift():
        world.set_now("LeftCam", threads=1)     # someone touched the PhotonVision UI during the run
        return real_now()

    link.now = now_and_drift
    m = Manifest.open(plan.folder, plan.experiment)
    assert not robot.run_one(s, plan.run("AA"), m)
    e = m.entry("AA", robot.BOARD)
    assert "LeftCam" in e["drifted_during_run"] and "threads" in e["drifted_during_run"]["LeftCam"]


def test_logbench_not_running_is_recorded_not_fatal(plan):
    dead = FakeLogBench()
    url = dead.url
    dead.close()
    world = World()
    s = robot.Session(plan=plan, link=FakeLink(world), pi_hosts={}, logbench=LogBenchClient(url, sleep=lambda x: None),
                      pv=FakePv(world), say=lambda t: None, sleep=lambda x: None, fetch="each")
    m = Manifest.open(plan.folder, plan.experiment)
    assert not robot.run_one(s, plan.run("AA"), m)
    e = m.entry("AA", robot.BOARD)
    assert "LogBench" in e["fetch_error"] and e["enable_window"]["t_enable"] is not None


def test_without_a_robot_link_you_mark_the_run_with_enter(plan):
    answers = []
    world = World()
    s = robot.Session(plan=plan, link=None, pi_hosts={}, logbench=None, pv=FakePv(world), say=lambda t: None,
                      sleep=lambda x: None, ask=lambda p: answers.append(p) or "")
    # no link: nothing can be read back, so settings can't be confirmed; use only what already matches
    s.link = FakeLink(world, states=[])          # a link that has no control word (e.g. simulator DS off)
    m = Manifest.open(plan.folder, plan.experiment)
    assert robot.run_one(s, plan.run("AA"), m)
    assert len(answers) == 2                      # started, finished
    assert m.entry("AA", robot.BOARD)["enable_window"] == {"t_enable": None, "t_disable": None, "autonomous": None}


# ---------------------------------------------------------------- finish / apply

def test_finish_restores_the_baseline_and_a_new_session_records_a_fresh_one(plan, lb):
    world = World()
    s = session(plan, world, lb=lb)
    m = Manifest.open(plan.folder, plan.experiment)
    assert robot.run_one(s, plan.run("X1"), m)
    assert world.cams["RightCam"]["state"]["camera_mode"] == "1280x800 MJPG @100"
    assert robot.finish(s, m)
    assert world.cams["RightCam"]["state"]["camera_mode"] == "800x600 MJPG @100"
    assert world.cams["LeftCam"]["state"]["decimate"] == BASE["decimate"]


def test_apply_only_sets_a_runs_settings(plan):
    world = World()
    s = session(plan, world)
    robot.apply_only(s, plan.run("X2"))
    assert world.cams["LeftCam"]["state"]["camera_mode"] == "1280x800 MJPG @100"
    assert world.cams["RightCam"]["state"]["camera_mode"] == "800x600 MJPG @100"


# ---------------------------------------------------------------- LogBench client

def test_logbench_picks_the_newest_log(lb):
    res = LogBenchClient(lb.url, sleep=lambda x: None).fetch_newest()
    assert res["name"] == "akit_26-11-14_19-11-27.wpilog" and res["log"] == res["name"]


def test_logbench_error_is_explained(lb):
    lb.fail_bundle = "SFTP: roboRIO unreachable"
    with pytest.raises(LogBenchError, match="roboRIO unreachable"):
        LogBenchClient(lb.url, sleep=lambda x: None).fetch_newest()


def test_logbench_ping_says_how_to_start_it():
    with pytest.raises(LogBenchError, match="LogBench"):
        LogBenchClient("http://127.0.0.1:9").ping()


# ---------------------------------------------------------------- the CLI

def test_cli_check_and_status_for_a_robot_plan(plan, capsys):
    assert cli.main(["check", str(plan.path)]) == 0
    out = capsys.readouterr().out
    assert "routine CircleFacingTag_Tag10" in out and "RightCam: decimate=2, threads=8, low_latency=False, camera_mode=1280x800" in out
    assert cli.main(["status", str(plan.path)]) == 0
    assert "X1" in capsys.readouterr().out


# ---------------------------------------------------------------- doctor

def test_doctor_passes_when_everything_is_ready(plan, lb):
    said = []
    s = session(plan, lb=lb)
    s.say = said.append
    assert robot.doctor(s)
    text = "\n".join(said)
    assert "ok   LeftPi/LeftCam: reports 800x600 MJPG @100" in text and "all good" in text
    assert "camera modes: 1280x800 MJPG @100 = #7; 800x600 MJPG @100 = #4" in text
    assert "LogBench: running" in text


def test_doctor_names_what_is_missing(plan):
    said = []
    world = World()
    del world.cams["RightCam"]["state"]["_unique_name"]          # the Pi publisher isn't running on RightPi
    dead = FakeLogBench()
    url = dead.url
    dead.close()
    s = session(plan, world, pv=FakePv(world, fail="can't reach PhotonVision at ws://x"),
                link=FakeLink(world, states=[(True, False)]))
    s.logbench = LogBenchClient(url)
    s.say = said.append
    assert not robot.doctor(s)
    text = "\n".join(said)
    assert "FAIL RightPi/RightCam: the Pi publisher isn't reporting" in text
    assert "the robot is ENABLED" in text
    assert "FAIL LeftPi: can't reach PhotonVision" in text and "--manual still works" in text
    assert "FAIL LogBench isn't running" in text


def test_no_robot_mode_tells_you_what_to_set_and_waits_for_enter(plan):
    said, answers = [], []
    world = World()
    s = robot.Session(plan=plan, link=None, pi_hosts={}, logbench=None, pv=FakePv(world), say=said.append,
                      sleep=lambda x: None, ask=lambda p: answers.append(p) or "")
    m = Manifest.open(plan.folder, plan.experiment)
    assert robot.run_one(s, plan.run("X1"), m)
    text = "\n".join(said)
    assert "no robot link" in text and "RightCam: decimate = 2" in text and "camera_mode = 1280x800 MJPG @100" in text
    assert len(answers) == 3          # settings done, run started, run finished
    assert world.sent == []           # nothing is sent without a way to confirm it
    assert m.entry("X1", robot.BOARD)["status"] == "ok" and not m.data.get("baseline")


# ---------------------------------------------------------------- fetching once, and what gets fetched

def test_logbench_prefers_the_akit_log_and_skips_pi_recordings_by_default():
    server = FakeLogBench(logs=[
        {"name": "akit_26-11-14_20-26-00.wpilog", "size": 5000, "mtime": 5.0},
        {"name": "FRC_20261114_202608.wpilog", "size": 9000, "mtime": 9.0},      # flushed last, but not the one we need
    ])
    try:
        res = LogBenchClient(server.url, sleep=lambda x: None).fetch_newest()
        assert res["name"] == "akit_26-11-14_20-26-00.wpilog"
        assert server.bundle_body["pi_sessions"] == []
        assert res["seconds"] >= 0
        server.logs[:] = [{"name": "FRC_only.wpilog", "size": 1, "mtime": 1.0}]
        assert LogBenchClient(server.url, sleep=lambda x: None).fetch_newest()["name"] == "FRC_only.wpilog"
        LogBenchClient(server.url, sleep=lambda x: None).fetch_newest(with_pi=True)
        assert server.bundle_body["pi_sessions"] == [{"camera": "LeftCam", "name": "s1", "pi": "LeftPi"}]
    finally:
        server.close()


def test_default_fetches_the_log_once_after_the_last_run(plan, lb):
    world = World()
    s = session(plan, world, lb=lb)
    s.fetch = "end"
    m = Manifest.open(plan.folder, plan.experiment)
    for rid in ("X1", "X2", "AA"):
        s.link.i = 0                                       # the scripted robot enables and disables again
        assert robot.run_one(s, plan.run(rid), m)
        assert m.entry(rid, robot.BOARD)["log_pending"] is True and "log" not in m.entry(rid, robot.BOARD)
    assert [p for p in lb.requests if p == ("POST", "/api/remote/bundle/jobs")] == []      # nothing downloaded yet
    assert robot.fetch_pending(s, m)
    assert len([p for p in lb.requests if p == ("POST", "/api/remote/bundle/jobs")]) == 1  # one download for all three
    for rid in ("X1", "X2", "AA"):
        e = m.entry(rid, robot.BOARD)
        assert e["log"]["name"] == "akit_26-11-14_19-11-27.wpilog" or e["log"]["name"].endswith(".wpilog")
        assert "log_pending" not in e and e["log"]["fetch_seconds"] is not None
    assert robot.fetch_pending(s, m)                       # nothing pending now: no second download
    assert len([p for p in lb.requests if p == ("POST", "/api/remote/bundle/jobs")]) == 1


def test_a_failed_end_fetch_is_retried_by_fetch(plan):
    dead = FakeLogBench()
    url = dead.url
    dead.close()
    world = World()
    s = robot.Session(plan=plan, link=FakeLink(world), pi_hosts={}, logbench=LogBenchClient(url, sleep=lambda x: None),
                      pv=FakePv(world), say=lambda t: None, sleep=lambda x: None, fetch="end")
    m = Manifest.open(plan.folder, plan.experiment)
    assert robot.run_one(s, plan.run("AA"), m)
    assert not robot.fetch_pending(s, m)
    e = m.entry("AA", robot.BOARD)
    assert e["log_pending"] and "LogBench" in e["fetch_error"] and e["status"] == "ok"
    live = FakeLogBench()
    try:
        s.logbench = LogBenchClient(live.url, sleep=lambda x: None)
        assert robot.fetch_pending(s, m)
        assert "log_pending" not in m.entry("AA", robot.BOARD) and "fetch_error" not in m.entry("AA", robot.BOARD)
    finally:
        live.close()
