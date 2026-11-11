"""exprunner: run an experiment's plan, run by run, and record what ran.

    python -m exprunner check  PLAN            validate the plan, show each run's command
    python -m exprunner sync   PLAN            build the bench bundle and copy it to the plan's Pis
    python -m exprunner run    PLAN [IDS...]   run the runs not done yet (or just IDS)
    python -m exprunner status PLAN            what's done, failed or still to run

Run from tools/exprunner. PLAN is a runs.toml next to an experiment's README.
"""
from __future__ import annotations

import argparse
import sys

from . import bench, boards, build
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="exprunner", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, helptext in (("check", "validate the plan and show each run's command"),
                           ("sync", "build the bench bundle and copy it to the Pis"),
                           ("status", "show what's done"),
                           ("run", "run the runs")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("plan", help="path to runs.toml")
        if name in ("sync", "run"):
            p.add_argument("--board", action="append", help="only this board (repeatable)")
        if name == "run":
            p.add_argument("ids", nargs="*", help="run only these run IDs (runs them again if done)")
            p.add_argument("--redo", action="store_true", help="run again even if done")
            p.add_argument("--yes", action="store_true", help="don't wait at prompts")
            p.add_argument("--no-sync", action="store_true", help="don't copy the bench bundle first")
            p.add_argument("--keep-going", action="store_true", help="carry on after a failed run")
    args = ap.parse_args(argv)
    try:
        plan = load(args.plan)
        return {"check": cmd_check, "sync": cmd_sync, "status": cmd_status, "run": cmd_run}[args.cmd](plan, args)
    except (PlanError, RemoteError, build.BuildError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nstopped; `status` shows what's done", file=sys.stderr)
        return 130
