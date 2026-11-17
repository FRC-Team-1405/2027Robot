import json
import os
import time

import pytest

from exprunner import attempts

RUNS = {"A": ["robot"], "B": ["robot"]}


def make(exp, name, statuses):
    d = exp / "attempts" / name
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({"experiment": "X", "runs": {
        r: {"robot": {"status": s}} for r, s in statuses.items()}}))
    return d


def test_first_run_starts_a_dated_attempt(tmp_path):
    a = attempts.resolve(tmp_path, create=True, expected=RUNS, today="2026-11-21")
    assert a == tmp_path / "attempts" / "2026-11-21" and a.is_dir()


def test_an_unfinished_attempt_is_continued(tmp_path):
    first = make(tmp_path, "2026-11-21", {"A": "ok"})
    assert attempts.resolve(tmp_path, create=True, expected=RUNS, today="2026-11-22") == first       # past midnight: same session


def test_a_finished_attempt_is_not_reopened_a_new_one_starts(tmp_path):
    make(tmp_path, "2026-11-21", {"A": "ok", "B": "ok"})
    new = attempts.resolve(tmp_path, create=True, expected=RUNS, today="2026-11-28")
    assert new.name == "2026-11-28"


def test_two_attempts_the_same_day_get_a_suffix(tmp_path):
    make(tmp_path, "2026-11-21", {"A": "ok", "B": "ok"})
    assert attempts.resolve(tmp_path, create=True, expected=RUNS, today="2026-11-21").name == "2026-11-21-2"


def test_an_old_unfinished_attempt_is_not_resumed(tmp_path):
    old = make(tmp_path, "2026-11-01", {"A": "ok"})
    t = time.time() - 3 * 24 * 3600
    os.utime(old / "manifest.json", (t, t))
    assert attempts.resolve(tmp_path, create=True, expected=RUNS, today="2026-11-21").name == "2026-11-21"


def test_force_new_and_named_attempts(tmp_path):
    make(tmp_path, "2026-11-21", {"A": "ok"})
    assert attempts.resolve(tmp_path, create=True, expected=RUNS, today="2026-11-21", force_new=True).name == "2026-11-21-2"
    assert attempts.resolve(tmp_path, "2026-12-01-redo", create=True).name == "2026-12-01-redo"
    assert attempts.resolve(tmp_path, "nope") is None
    with pytest.raises(attempts.AttemptError):
        attempts.resolve(tmp_path, "../escape")


def test_other_commands_use_the_latest(tmp_path):
    assert attempts.resolve(tmp_path) is None
    make(tmp_path, "2026-11-14", {"A": "ok"})
    last = make(tmp_path, "2026-11-21", {"A": "ok"})
    assert attempts.resolve(tmp_path) == last and attempts.latest(tmp_path) == last
