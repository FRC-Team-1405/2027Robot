#!/usr/bin/env python3
"""Put everything under logs/ into one folder per day: logs/<MM-DD>/.

logs/ is local only (git-ignored: it is gigabytes), so this changes nothing in git. Run it from anywhere:

    python tools/organize_logs.py            # dry run: prints what it would move
    python tools/organize_logs.py --apply    # moves it

What moves:
  logs/offseason/<d>/...            -> logs/<MM-DD>/...     (the session day folder you already had, zero-padded;
                                       "11-3" -> "11-03", "6-13-26" -> "06-13")
  logs/FRC_YYYYMMDD_HHMMSS*.wpilog  -> logs/<MM-DD>/        (the date in the file name, which is UTC)
  logs/akit_YY-MM-DD_*.wpilog       -> logs/<MM-DD>/        (same)
  logs/YYYY-MM-DD_HH-MM-SS/ (sim)   -> logs/<MM-DD>/sim/
File names are never changed (the time of day in them tells sessions apart, and experiment manifests refer to them).
Nothing is overwritten: a clash is reported and skipped. Safe to run twice.
"""
import argparse
import os
import re
import shutil
import sys
from pathlib import Path

LOGS = Path(__file__).resolve().parents[1] / "logs"


def day_folder(name: str):
    """'11-3' -> '11-03', '6-13-26' -> '06-13', '10-27' -> '10-27'; None if not a day folder."""
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})(?:-\d{2})?", name)
    return f"{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else None


def plan():
    moves = []                         # (source, destination)
    if not LOGS.is_dir():
        return moves
    off = LOGS / "offseason"
    if off.is_dir():
        for d in sorted(off.iterdir()):
            day = day_folder(d.name)
            if day and d.is_dir():
                for item in sorted(d.iterdir()):
                    moves.append((item, LOGS / day / item.name))
            else:
                moves.append((d, LOGS / "other" / d.name))
    for item in sorted(LOGS.iterdir()):
        n = item.name
        m = re.match(r"FRC_(\d{4})(\d{2})(\d{2})_\d{6}", n)
        if m and item.is_file():
            moves.append((item, LOGS / f"{m.group(2)}-{m.group(3)}" / n))
            continue
        m = re.match(r"akit_(\d{2})-(\d{2})-(\d{2})_", n)
        if m and item.is_file():
            moves.append((item, LOGS / f"{m.group(2)}-{m.group(3)}" / n))
            continue
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})_\d{2}-\d{2}-\d{2}$", n)
        if m and item.is_dir():
            moves.append((item, LOGS / f"{m.group(2)}-{m.group(3)}" / "sim" / n))
    return moves


def cleanup():
    """Remove the emptied logs/offseason/<d>/ folders, then logs/offseason itself."""
    off = LOGS / "offseason"
    if off.is_dir():
        for d in off.iterdir():
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        if not any(off.iterdir()):
            off.rmdir()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="really move things (default: dry run)")
    args = ap.parse_args()
    moves = plan()
    if not moves:
        if args.apply:
            cleanup()
        print("nothing to move: logs/ is already organized by day")
        return 0
    clashes = [(s, d) for s, d in moves if d.exists()]
    per_day = {}
    for s, d in moves:
        per_day.setdefault(d.relative_to(LOGS).parts[0], []).append(s)
    for day in sorted(per_day):
        print(f"logs/{day}/  <- {len(per_day[day])} item(s)")
    if clashes:
        print(f"\n{len(clashes)} clash(es) will be skipped (destination exists):")
        for s, d in clashes[:10]:
            print(f"  {s.relative_to(LOGS)} -> {d.relative_to(LOGS)}")
    if not args.apply:
        print("\ndry run: nothing moved. Run again with --apply.")
        return 0
    done = 0
    for s, d in moves:
        if d.exists():
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(s), str(d))
        done += 1
    off = LOGS / "offseason"
    if off.is_dir() and not any(off.iterdir()):
        off.rmdir()
    print(f"\nmoved {done} item(s)." + (" logs/offseason is now empty and was removed." if not off.exists() else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
