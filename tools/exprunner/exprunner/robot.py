"""Robot experiments: set PhotonVision on the Pis, check it took, hand over for an auto, fetch the log.

Per run, in order:
  1. refuse to touch anything while the robot is enabled;
  2. work out each camera's full settings (the plan's defaults + the named setting);
  3. read what each camera is set to now (the Pi publisher, over NetworkTables) and send only the
     differences to PhotonVision's web socket;
  4. read them back until every value matches (or tell the person exactly what to set by hand and wait);
  5. tell the person to close PhotonVision tabs and enable the auto; notice enable -> disable;
  6. fetch the newest log through LogBench;
  7. write the run into manifest.json: what was asked, what was read back, the enable window (robot time),
     the log, and anything that didn't match.

Everything outside the runner (NetworkTables, PhotonVision, LogBench, the keyboard, the clock) is passed
in, so the whole flow is tested end to end without a robot.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from . import settings as S
from .logbench import LogBenchClient, LogBenchError
from .manifest import Manifest, now_utc
from .plan import Plan, Run
from .pv import PvClient, PvError

BOARD = "robot"            # the manifest "board" for robot plans (one entry per run)


class RobotRunError(RuntimeError):
    pass


@dataclass
class Session:
    plan: Plan
    link: Any                                      # NtLink-like: readback(), robot_state(), now()
    pi_hosts: dict[str, list[str]]                 # Pi name -> hostnames to try for PhotonVision
    logbench: LogBenchClient | None = None
    pv: Callable[[str], PvClient] = PvClient       # host -> client (a context manager)
    ask: Callable[[str], str] = input
    say: Callable[[str], None] = print
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    settle_timeout: float = 20.0                   # how long a setting may take to show up in the readback
    poll: float = 1.0
    apply_settings: bool = True                    # False: don't send; just verify (and wait for the person)
    wait_for_person: bool = True                   # keep waiting for hand changes instead of failing
    enable_timeout: float = 300.0                  # say so if no enable is seen for this long
    log: list[str] = field(default_factory=list)

    def out(self, text: str) -> None:
        self.log.append(text)
        self.say(text)


# ---------------------------------------------------------------------------- reading the cameras

def readback_all(s: Session) -> dict[str, dict[str, Any]]:
    """{camera: settings} as the Pis report them now (friendly names, plus _unique_name)."""
    return {cam: s.link.readback(pi, cam) for pi, cam in s.plan.cameras}


def public(settings: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in settings.items() if not k.startswith("_")}


def require_disabled(s: Session) -> None:
    if s.link is None:
        return
    st = s.link.robot_state()
    if st and st[0]:
        raise RobotRunError("the robot is enabled. Disable it first: the runner doesn't change cameras while it's enabled.")


# ---------------------------------------------------------------------------- applying settings

def _pending(wanted: dict[str, dict[str, Any]], now: dict[str, dict[str, Any]]) -> dict[str, list]:
    return {cam: d for cam, want in wanted.items() if (d := S.differences(want, now.get(cam, {})))}


def _hosts(s: Session, pi: str) -> list[str]:
    return s.pi_hosts.get(pi) or [pi + ".local"]


def send(s: Session, wanted: dict[str, dict[str, Any]], pending: dict[str, list]) -> list[str]:
    """Send the differing settings over PhotonVision's web socket. Returns problems (empty = sent)."""
    problems: list[str] = []
    now = readback_all(s)
    by_pi: dict[str, list[str]] = {}
    for pi, cam in s.plan.cameras:
        if cam in pending:
            by_pi.setdefault(pi, []).append(cam)
    for pi, cams in by_pi.items():
        last_err = ""
        for host in _hosts(s, pi):
            try:
                with s.pv(host) as pv:
                    pv.drain()
                    for cam in cams:
                        unique = now.get(cam, {}).get("_unique_name")
                        if not unique:
                            problems.append(f"{cam}: the Pi publisher hasn't reported its PhotonVision name "
                                            f"(is the publisher running on {pi}?)")
                            continue
                        change = {k: wanted[cam][k] for k, _w, _g in pending[cam]}
                        idx = pv.mode_index(unique, change[S.MODE_KEY]) if S.MODE_KEY in change else None
                        pv.apply(unique, change, idx)
                        s.out(f"  sent to {pi}/{cam}: " + ", ".join(f"{k}={v}" for k, v in change.items()))
                    pv.drain(0.5)
                last_err = ""
                break
            except PvError as e:
                last_err = str(e)
        if last_err:
            problems.append(f"{pi}: {last_err}")
    return problems


def apply_and_verify(s: Session, wanted: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Make every camera match `wanted`, confirmed by the readback. Returns the final readback.
    Raises RobotRunError if it can't (and the person isn't being waited for)."""
    if s.link is None:
        s.out("  no robot link, so nothing can be confirmed from the Pis. Set these in the PhotonVision UI:")
        for cam, want in wanted.items():
            s.out(f"      {cam}: " + ", ".join(f"{k} = {v}" for k, v in want.items()))
        s.ask("  Press Enter when both cameras are set ")
        return {}
    now = readback_all(s)
    pending = _pending(wanted, now)
    if not pending:
        s.out("  settings already match")
        return now
    for cam, diffs in pending.items():
        s.out(f"  {cam}: change " + S.describe(diffs))
    manual_note = ""
    if s.apply_settings:
        problems = send(s, wanted, pending)
        if problems:
            manual_note = "; ".join(problems)
            s.out(f"  couldn't set it automatically ({manual_note})")
    shown_manual = False
    start = s.clock()
    last_shown: dict[str, str] = {}
    while True:
        now = readback_all(s)
        pending = _pending(wanted, now)
        if not pending:
            s.out("  settings confirmed from the Pi publisher: " + ", ".join(
                f"{cam}: " + ", ".join(f"{k}={v}" for k, v in want.items()) for cam, want in wanted.items()))
            return now
        waited = s.clock() - start
        if waited > s.settle_timeout:
            if not s.wait_for_person:
                raise RobotRunError("settings didn't take: " + "; ".join(
                    f"{cam}: {S.describe(d)}" for cam, d in pending.items()))
            if not shown_manual:
                shown_manual = True
                s.out("  ► These didn't take. Set them by hand in the PhotonVision UI; the runner will see it "
                      "from the Pi publisher and carry on (Ctrl+C to stop):")
                for cam, d in pending.items():
                    for k, w, g in d:
                        s.out(f"      {cam}: {k} -> {w}   (now {g})")
        text = {cam: S.describe(d) for cam, d in pending.items()}
        if text != last_shown and waited > 3:
            last_shown = text
            s.out("  waiting for: " + "; ".join(f"{cam}: {t}" for cam, t in text.items()))
        s.sleep(s.poll)


# ---------------------------------------------------------------------------- handing over

def wait_for_enable_window(s: Session) -> tuple[float | None, float | None, bool | None]:
    """Block until the robot enables and then disables. Returns (t_enable, t_disable, was_auto) in robot time.
    Without a robot link, press Enter when the run starts and again when it ends (times are None)."""
    if s.link is None or s.link.robot_state() is None:
        s.ask("  Press Enter when the run starts ")
        s.ask("  Press Enter when it's finished ")
        return None, None, None
    start = s.clock()
    warned = False
    while True:
        st = s.link.robot_state()
        if st and st[0]:
            t0, was_auto = s.link.now(), st[1]
            s.out(f"  enabled ({'auto' if was_auto else 'teleop/test'}) ...")
            break
        if not warned and s.clock() - start > s.enable_timeout:
            warned = True
            s.out("  (still waiting for the robot to enable. Ctrl+C to stop, or rerun with --no-robot "
                  "to mark the run with Enter instead)")
        s.sleep(0.1)
    while True:
        st = s.link.robot_state()
        if st and not st[0]:
            t1 = s.link.now()
            break
        s.sleep(0.1)
    s.out(f"  disabled ({t1 - t0:.1f} s)")
    return t0, t1, was_auto


def fetch_log(s: Session) -> tuple[dict | None, str | None]:
    if s.logbench is None:
        return None, None
    try:
        res = s.logbench.fetch_newest(on_phase=lambda t: s.out(f"  {t}"))
        return res, None
    except LogBenchError as e:
        return None, str(e)


# ---------------------------------------------------------------------------- one run

def run_one(s: Session, run: Run, manifest: Manifest, git: dict | None = None) -> bool:
    plan = s.plan
    wanted = plan.settings_for(run)
    s.out(f"\n=== {run.id}: {run.what or ', '.join(f'{c}={n}' for c, n in run.use.items())}")
    entry: dict[str, Any] = {"status": "failed", "kind": "robot", "routine": plan.routine, "use": run.use,
                             "asked": wanted, "started": now_utc(), "git": git or {}}
    try:
        require_disabled(s)
        if s.link is not None and not manifest.data.get("baseline"):
            manifest.data["baseline"] = {c: public(v) for c, v in readback_all(s).items()}
            manifest.save()
        final = apply_and_verify(s, wanted)
        entry["read_back"] = {c: public(v) for c, v in final.items()}
        if run.prompt:
            s.out(f"  {run.prompt}")
        s.out(f"  ► Close any PhotonVision tabs. Enable {plan.routine} now; disable when it's done.")
        t0, t1, was_auto = wait_for_enable_window(s)
        entry["enable_window"] = {"t_enable": t0, "t_disable": t1, "autonomous": was_auto}
        # the readback again: the settings must still be what we asked for after the run
        after = readback_all(s) if s.link is not None else {}
        drift = {c: S.describe(d) for c, d in _pending(wanted, after).items()} if after else {}
        if drift:
            entry["drifted_during_run"] = drift
            s.out("  !! settings changed during the run: " + "; ".join(f"{c}: {t}" for c, t in drift.items()))
        res, err = fetch_log(s)
        if res:
            entry["log"] = {"name": res.get("name"), "path": res.get("log"), "pi_sessions": res.get("pi_sessions"),
                            "warnings": res.get("warnings")}
            s.out(f"  fetched {res.get('log')}")
        elif err:
            entry["fetch_error"] = err
            s.out(f"  !! couldn't fetch the log: {err}")
        entry["status"] = "ok" if (res or s.logbench is None) and not drift else "failed"
    except (RobotRunError, PvError) as e:
        entry["error"] = str(e)
        s.out(f"  !! {e}")
    finally:
        entry["finished"] = now_utc()
        manifest.record(run.id, BOARD, entry)
    s.out(f"{run.id}: {entry['status']}")
    return entry["status"] == "ok"


# ---------------------------------------------------------------------------- the other commands

def apply_only(s: Session, run: Run) -> None:
    require_disabled(s)
    apply_and_verify(s, s.plan.settings_for(run))


def finish(s: Session, manifest: Manifest) -> bool:
    """Put every camera back to what it was when the first run started."""
    base = manifest.data.get("baseline")
    if not base:
        s.out("no baseline recorded (no run has started a session yet); nothing to restore")
        return True
    require_disabled(s)
    wanted = {cam: {k: v for k, v in b.items() if k in S.SETTING_KEYS} for cam, b in base.items()}
    s.out("restoring the settings the cameras had before the first run:")
    apply_and_verify(s, wanted)
    return True


# ---------------------------------------------------------------------------- doctor

def doctor(s: Session) -> bool:
    """Check everything a session needs before the robot is involved. Prints one line per check and
    returns True if all passed. Run it first: it is the quickest way to find what is not set up."""
    ok_all = True

    def line(ok: bool, text: str) -> None:
        nonlocal ok_all
        ok_all = ok_all and ok
        s.out(("  ok   " if ok else "  FAIL ") + text)

    s.out("checking what a session needs:")
    if s.link is None:
        line(False, "robot NetworkTables: not connected (--no-robot), so settings can't be confirmed from the Pis")
    else:
        line(True, f"robot NetworkTables: connected ({getattr(s.link, 'target', '')})")
        st = s.link.robot_state()
        line(st is not None, "Driver Station control word (/FMSInfo): " +
             (f"enabled={st[0]}" if st else "not published; the runner can't see enable/disable (use --no-robot)"))
        if st and st[0]:
            line(False, "the robot is ENABLED; disable it before a session")
    try:
        from .pv import _modules
        _modules()
    except PvError as e:
        line(False, str(e))
        s.apply_settings = False          # can't talk to PhotonVision from here; the Pis are checked below
    modes = sorted({v["camera_mode"] for v in list(s.plan.settings.values()) + [s.plan.defaults] if "camera_mode" in v})
    now = readback_all(s) if s.link else {}
    for pi, cam in s.plan.cameras:
        rb = now.get(cam, {})
        if not rb.get("_unique_name"):
            line(False, f"{pi}/{cam}: the Pi publisher isn't reporting this camera (is orangepi-nt-publisher running on {pi}?)")
            continue
        line(True, f"{pi}/{cam}: reports {rb.get('camera_mode')}, decimate {rb.get('decimate')}, threads {rb.get('threads')}")
        if rb.get("_settings_ok") is False:
            line(False, f"{pi}: the publisher couldn't read PhotonVision's settings (PvSettingsOk is false)")
        if s.apply_settings:
            for host in _hosts(s, pi):
                try:
                    with s.pv(host) as pv:
                        pv.drain()
                        found = []
                        for mode in modes:
                            found.append(f"{mode} = #{pv.mode_index(rb['_unique_name'], mode)}")
                    line(True, f"{pi}: PhotonVision reachable at {host}; camera modes: " + "; ".join(found))
                    break
                except PvError as e:
                    last = str(e)
            else:
                line(False, f"{pi}: {last}   (--manual still works: you change settings in the UI, the runner checks)")
    if s.logbench is None:
        line(False, "LogBench: not checked (--no-fetch)")
    else:
        try:
            s.logbench.ping()
            line(True, f"LogBench: running at {s.logbench.base}")
        except LogBenchError as e:
            line(False, str(e))
    s.out("all good" if ok_all else "fix the FAIL lines above, then run again")
    return ok_all
