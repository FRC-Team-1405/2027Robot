"""exprunner: run an experiment's plan, run by run, and record what ran.

    python -m exprunner check  PLAN            validate the plan, show each run's command
    python -m exprunner sync   PLAN            build the bench bundle and copy it to the plan's Pis
    python -m exprunner run    PLAN [IDS...]   run the runs not done yet (or just IDS)
    python -m exprunner status PLAN            what's done, failed or still to run

Robot experiments (kind = "robot") also have:
    python -m exprunner doctor PLAN            check the robot, Pis, PhotonVision and LogBench are ready
    python -m exprunner apply  PLAN ID         set PhotonVision to a run's settings, without running it
    python -m exprunner fetch  PLAN            download the robot log for runs that don't have it (run does this once, at the end)
    python -m exprunner finish PLAN            put the cameras back to what they were before the session
    python -m exprunner pv-dump HOST           print what PhotonVision's web socket sends (to debug)

Run from tools/exprunner. PLAN is a runs.toml next to an experiment's README.
"""
from __future__ import annotations

import argparse
import sys

from . import bench, boards, build, robot
from .logbench import DEFAULT_URL, LogBenchClient, LogBenchError
from .manifest import Manifest
from .plan import Plan, PlanError, load
from .remote import Pi, RemoteError


def _pis(plan: Plan, only: list[str] | None = None) -> dict[str, Pi]:
    known = boards.load(plan.robot)
    names = only or plan.boards
    missing = [n for n in names if n not in known]
    if missing:
        raise PlanError(f"boards {missing} aren't in coprocessor/robots.json for robot {plan.robot or '(default)'}")
    return {n: Pi(n, known[n].hosts) for n in names}


def cmd_check(plan: Plan, args) -> int:
    if plan.kind == "robot":
        return _check_robot(plan)
    known = boards.load(plan.robot)
    print(f"{plan.experiment}  ({plan.kind}, boards: {', '.join(plan.boards)})")
    for b in plan.boards:
        if b not in known:
            print(f"  ! board {b} isn't in robots.json")
    for r in plan.runs:
        print(f"\n{r.id}  {r.what}")
        if r.prompt:
            print(f"  prompt: {r.prompt}")
        print(f"  on: {', '.join(plan.boards_for(r))}")
        print(f"  $ {bench.command(plan, r)}")
    return 0


def cmd_sync(plan: Plan, args) -> int:
    pis = _pis(plan, args.board)
    bench.sync(pis.values())
    print("synced: " + ", ".join(pis))
    return 0


def cmd_status(plan: Plan, args) -> int:
    if plan.kind == "robot":
        return _status_robot(plan, args)
    m = Manifest.open(plan.folder, plan.experiment)
    width = max(len(r.id) for r in plan.runs)
    for r in plan.runs:
        cells = []
        for b in plan.boards_for(r):
            e = m.entry(r.id, b)
            cells.append(f"{b}: {e['status'] + ' ' + e['finished'] if e else 'to do'}")
        print(f"{r.id:<{width}}  {' | '.join(cells)}   {r.what}")
    return 0


def cmd_run(plan: Plan, args) -> int:
    if plan.kind == "robot":
        return _run_robot(plan, args)
    runs = [plan.run(i) for i in args.ids] if args.ids else plan.runs
    m = Manifest.open(plan.folder, plan.experiment)
    pis = _pis(plan, args.board)
    todo = []
    for r in runs:
        targets = [b for b in plan.boards_for(r) if b in pis and (args.ids or args.redo or not m.done(r.id, b))]
        if targets:
            todo.append((r, targets))
    if not todo:
        print("nothing to run: every run is done (use `run PLAN ID` or --redo to run again)")
        return 0
    for p in pis.values():
        p.connect()
    if not args.no_sync:
        bench.sync(pis.values())
    git = build.git_describe()
    failed = 0
    for r, targets in todo:
        print(f"\n=== {r.id}: {r.what or r.step}")
        if r.prompt and not args.yes:
            input(f"► {r.prompt}\n  Press Enter when ready (Ctrl+C to stop) ")
        for b in targets:
            if not bench.run_on(plan, r, pis[b], m, git):
                failed += 1
                if not args.keep_going:
                    print("\nstopped after a failure (use --keep-going to carry on); `status` shows what's left")
                    return 1
    print(f"\ndone: {len(todo)} run(s), {failed} failed. Results under {plan.folder / 'data'}")
    return 1 if failed else 0


# ------------------------------------------------------------------------------ robot plans

def _check_robot(plan: Plan) -> int:
    known = boards.load(plan.robot)
    print(f"{plan.experiment}  (robot, routine {plan.routine})")
    for pi, cam in plan.cameras:
        flag = "" if pi in known else "   ! not in coprocessor/robots.json"
        print(f"  camera {pi}/{cam}{flag}")
    print("  defaults: " + (", ".join(f"{k}={v}" for k, v in plan.defaults.items()) or "(none)"))
    for name, st in plan.settings.items():
        print(f"  setting {name}: " + ", ".join(f"{k}={v}" for k, v in st.items()))
    for r in plan.runs:
        print(f"\n{r.id}  {r.what}")
        for cam, full in plan.settings_for(r).items():
            print(f"  {cam}: " + ", ".join(f"{k}={v}" for k, v in full.items()))
    return 0


def _status_robot(plan: Plan, args) -> int:
    m = Manifest.open(plan.folder, plan.experiment)
    width = max(len(r.id) for r in plan.runs)
    for r in plan.runs:
        e = m.entry(r.id, robot.BOARD)
        state = f"{e['status']} {e.get('finished', '')}" if e else "to do"
        if e and e.get("log_pending"):
            state += " (log not fetched)"
        log = (e or {}).get("log") or {}
        extra = f"  {log.get('name', '')}" if log else ""
        use = ", ".join(f"{c}={n}" for c, n in r.use.items())
        print(f"{r.id:<{width}}  {state:<28}{use}{extra}")
    base = m.data.get("baseline")
    if base:
        print("\nCameras were changed from their baseline; `finish` puts them back:")
        for cam, b in base.items():
            print(f"  {cam}: " + ", ".join(f"{k}={v}" for k, v in b.items() if k in ("camera_mode", "decimate", "threads")))
    return 0


def _robot_session(plan: Plan, args, need_logbench: bool = False) -> robot.Session:
    from .robotlink import LinkError, NtLink

    known = boards.load(plan.robot)
    missing = [pi for pi, _c in plan.cameras if pi not in known]
    if missing:
        raise PlanError(f"boards {missing} aren't in coprocessor/robots.json for robot {plan.robot or '(default)'}")
    link = None
    if not args.no_robot:
        try:
            host, _, port = (args.nt or "").partition(":")      # --nt HOST or HOST:PORT
            link = NtLink(host=host or None, team=args.team, port=int(port) if port else 0)
        except LinkError as e:
            raise PlanError(str(e)) from None
        print(f"connected to the robot's NetworkTables ({link.target})")
    lb = None
    if need_logbench and not args.no_fetch and getattr(args, "fetch", "end") != "none":
        lb = LogBenchClient(args.logbench)
        try:
            lb.ping()
        except LogBenchError as e:
            raise PlanError(str(e)) from None
    s = robot.Session(plan=plan, link=link, pi_hosts={n: list(b.hosts) for n, b in known.items()}, logbench=lb)
    s.apply_settings = not getattr(args, "manual", False)
    s.fetch = getattr(args, "fetch", "end")
    s.with_pi = getattr(args, "with_pi", False)
    return s


def _run_robot(plan: Plan, args) -> int:
    runs = [plan.run(i) for i in args.ids] if args.ids else plan.runs
    m = Manifest.open(plan.folder, plan.experiment)
    todo = [r for r in runs if args.ids or args.redo or not m.done(r.id, robot.BOARD)]
    if not todo:
        print("nothing to run: every run is done (use `run PLAN ID` or --redo to run again)")
        return 0
    s = _robot_session(plan, args, need_logbench=True)
    if s.link is None:
        print("(no robot link: settings can't be checked from the Pis; you mark each run with Enter)")
    git = build.git_describe()
    failed = 0
    for r in todo:
        if not robot.run_one(s, r, m, git):
            failed += 1
            if not args.keep_going:
                print("\nstopped after a failure (use --keep-going to carry on); `status` shows what's left")
                return 1
    if s.fetch == "end":
        robot.fetch_pending(s, m)
    print(f"\ndone: {len(todo)} run(s), {failed} failed. `finish` puts the cameras back to their baseline.")
    return 1 if failed else 0


def cmd_fetch(plan: Plan, args) -> int:
    if plan.kind != "robot":
        raise PlanError("`fetch` is for robot plans")
    m = Manifest.open(plan.folder, plan.experiment)
    args.no_robot = True                  # fetching needs LogBench, not the robot link
    s = _robot_session(plan, args, need_logbench=True)
    if s.logbench is None:
        raise PlanError("fetching is switched off (--no-fetch / --fetch none)")
    return 0 if robot.fetch_pending(s, m) else 1


def cmd_doctor(plan: Plan, args) -> int:
    if plan.kind != "robot":
        raise PlanError("`doctor` is for robot plans")
    s = _robot_session(plan, args, need_logbench=True)
    return 0 if robot.doctor(s) else 1


def cmd_apply(plan: Plan, args) -> int:
    if plan.kind != "robot":
        raise PlanError("`apply` is for robot plans")
    s = _robot_session(plan, args)
    robot.apply_only(s, plan.run(args.id))
    return 0


def cmd_finish(plan: Plan, args) -> int:
    if plan.kind != "robot":
        raise PlanError("`finish` is for robot plans")
    m = Manifest.open(plan.folder, plan.experiment)
    s = _robot_session(plan, args)
    ok = robot.finish(s, m)
    if ok and m.data.get("baseline"):
        m.data["baseline"] = None
        m.save()
    return 0 if ok else 1


def cmd_pv_dump(args) -> int:
    import json

    from .pv import PvClient, PvError, find_modes

    try:
        with PvClient(args.host) as pv:
            msgs = pv.drain(args.seconds)
    except PvError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"{len(msgs)} message(s) from ws://{args.host}:5800/websocket_data")
    for i, m in enumerate(msgs, 1):
        text = json.dumps(m, default=repr)
        keys = list(m)[:8] if isinstance(m, dict) else type(m).__name__
        print(f"\n[{i}] keys: {keys}\n{text[:args.chars]}{' ...' if len(text) > args.chars else ''}")
    uniques = sorted({d.get("uniqueName") for m in msgs for d in _walk(m) if isinstance(d, dict) and d.get("uniqueName")})
    for u in uniques:
        modes = find_modes(msgs, u)
        print(f"\ncamera {u}: " + (", ".join(f"{i}: {v['width']}x{v['height']} @{v['fps']}" for i, v in sorted(modes.items()))
                                   or "no mode list found"))
    return 0


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, (list, tuple)):
        for v in node:
            yield from _walk(v)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="exprunner", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, helptext in (("check", "validate the plan and show each run's command or settings"),
                           ("sync", "build the bench bundle and copy it to the Pis"),
                           ("status", "show what's done"),
                           ("run", "run the runs"),
                           ("doctor", "robot plans: check everything a session needs is ready"),
                           ("fetch", "robot plans: download the robot log for runs that don't have it yet"),
                           ("apply", "robot plans: set PhotonVision to a run's settings"),
                           ("finish", "robot plans: put the cameras back to their baseline")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("plan", help="path to runs.toml")
        if name in ("sync", "run"):
            p.add_argument("--board", action="append", help="bench plans: only this board (repeatable)")
        if name == "apply":
            p.add_argument("id", help="the run whose settings to apply")
        if name == "run":
            p.add_argument("ids", nargs="*", help="run only these run IDs (runs them again if done)")
            p.add_argument("--redo", action="store_true", help="run again even if done")
            p.add_argument("--yes", action="store_true", help="bench plans: don't wait at prompts")
            p.add_argument("--no-sync", action="store_true", help="bench plans: don't copy the bench bundle first")
            p.add_argument("--keep-going", action="store_true", help="carry on after a failed run")
        if name in ("run", "apply", "finish", "doctor", "fetch"):
            g = p.add_argument_group("robot plans")
            g.add_argument("--nt", metavar="HOST", help="the robot's NetworkTables host (default: team 1405; "
                                                       "localhost for the simulator)")
            g.add_argument("--team", type=int, default=1405)
            g.add_argument("--no-robot", action="store_true",
                           help="don't connect to the robot: nothing is checked from the Pis, you press Enter per run")
            g.add_argument("--manual", action="store_true",
                           help="don't send settings to PhotonVision; say what to change and wait for the Pi to show it")
            g.add_argument("--no-fetch", action="store_true", help="don't fetch the log through LogBench (same as --fetch none)")
            g.add_argument("--fetch", choices=("end", "each", "none"), default="end",
                           help="when to download the robot log: once after the last run (default; all runs share "
                                "one log), after every run, or never")
            g.add_argument("--with-pi", action="store_true",
                           help="also download the Pis' vision recordings (large; the odometry experiments don't need them)")
            g.add_argument("--logbench", default=DEFAULT_URL, metavar="URL", help=f"LogBench address ({DEFAULT_URL})")
    d = sub.add_parser("pv-dump", help="print what PhotonVision's web socket sends (to debug the runner)")
    d.add_argument("host", help="the Pi, e.g. LeftPi.local")
    d.add_argument("--seconds", type=float, default=2.0)
    d.add_argument("--chars", type=int, default=1500, help="how much of each message to print")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "pv-dump":
            return cmd_pv_dump(args)
        plan = load(args.plan)
        return {"check": cmd_check, "sync": cmd_sync, "status": cmd_status, "run": cmd_run,
                "apply": cmd_apply, "finish": cmd_finish, "doctor": cmd_doctor, "fetch": cmd_fetch}[args.cmd](plan, args)
    except (PlanError, RemoteError, build.BuildError, robot.RobotRunError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nstopped; `status` shows what's done", file=sys.stderr)
        return 130
