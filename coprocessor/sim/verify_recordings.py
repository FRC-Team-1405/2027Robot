#!/usr/bin/env python3
"""Checks a simulated match's vision recordings against what the fake robot actually did.

Inputs (all pulled back from the Pi by Run-SimulatedMatch.ps1):
  --events      fake_robot.py --event-log JSONL (the ground-truth timeline)
  --recordings  the recorder's camera folder, holding boot####-<timestamp>/ session dirs
  --tap         optional frame_tap.py JSONL (ground-truth arrival time of every stream frame)

Every check prints PASS / FAIL / WARN / INFO. Exit status is 1 if anything FAILed.
Stdlib only; runs on the laptop.

    python verify_recordings.py --events ev.jsonl --recordings rec/bench --tap tap.jsonl --sample-hz 3
"""
import argparse
import hashlib
import json
import os
import re
import statistics
import sys

SESSION_RE = re.compile(r"^boot(\d{4})-(\d{8})-(\d{6})$")
ENABLED_BIT = 1
AUTO_BIT = 2


def load_jsonl(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def enabled_windows(events):
    """[(start, end, label, match)] in server-time seconds from the fake robot's event log."""
    wins, cur = [], None
    transitions = [e for e in events if "control_word" in e and e.get("phase") not in ("clients_connected",)]
    last_t = events[-1]["server_time_sec"] if events else 0.0
    for e in transitions:
        en = bool(e["control_word"] & ENABLED_BIT)
        if en and cur is None:
            cur = {"start": e["server_time_sec"], "label": "auto" if e["control_word"] & AUTO_BIT else "teleop",
                   "match": e.get("match", 0), "phase": e.get("phase", "")}
        elif cur is not None and (not en or (e["control_word"] & AUTO_BIT) != (AUTO_BIT if cur["label"] == "auto" else 0)):
            wins.append((cur["start"], e["server_time_sec"], cur["label"], cur["match"]))
            cur = None
            if en:
                cur = {"start": e["server_time_sec"], "label": "auto" if e["control_word"] & AUTO_BIT else "teleop",
                       "match": e.get("match", 0), "phase": e.get("phase", "")}
    if cur is not None:
        wins.append((cur["start"], last_t, cur["label"], cur["match"]))
    return wins


def read_session(path):
    manifest = []
    mpath = os.path.join(path, "manifest.jsonl")
    if os.path.isfile(mpath):
        manifest = load_jsonl(mpath)
    jpgs = sorted(n for n in os.listdir(path) if n.endswith(".jpg"))
    return manifest, jpgs


class Report:
    def __init__(self):
        self.lines, self.failed = [], 0

    def add(self, status, text):
        if status == "FAIL":
            self.failed += 1
        self.lines.append((status, text))
        print(f"  [{status}] {text}")


def pct(values, p):
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, int(round(p / 100.0 * (len(s) - 1))))]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--events", required=True)
    ap.add_argument("--recordings", required=True)
    ap.add_argument("--tap")
    ap.add_argument("--sample-hz", type=float, default=3.0)
    ap.add_argument("--boundary-tol-sec", type=float, default=1.5,
                    help="how far a frame may fall outside an enabled window (recorder polls at 1/SAMPLE_HZ)")
    ap.add_argument("--count-tol", type=float, default=0.25, help="allowed fractional deviation from SAMPLE_HZ * duration")
    ap.add_argument("--max-age-sec", type=float, default=0.5, help="p95 frame age above this FAILs the freshness check")
    ap.add_argument("--json-out")
    args = ap.parse_args()

    rep = Report()
    events = load_jsonl(args.events)
    wins = enabled_windows(events)
    print(f"Ground truth: {len(wins)} enabled window(s) from {args.events}")
    for s, e, lab, m in wins:
        print(f"  match {m} {lab:6s} {e - s:7.2f}s")

    sessions = sorted(d for d in os.listdir(args.recordings) if os.path.isdir(os.path.join(args.recordings, d))) \
        if os.path.isdir(args.recordings) else []
    # Chronological order comes from the data, not the folder name.
    data = []
    for d in sessions:
        manifest, jpgs = read_session(os.path.join(args.recordings, d))
        data.append({"dir": d, "manifest": manifest, "jpgs": jpgs,
                     "t0": manifest[0]["t_sec"] if manifest else None, "t1": manifest[-1]["t_sec"] if manifest else None})
    data.sort(key=lambda x: (x["t0"] is None, x["t0"]))

    print("\nSessions")
    rep.add("PASS" if len(data) == len(wins) else "FAIL",
            f"session count {len(data)} == enabled windows {len(wins)} (auto and teleop are separate sessions across the pause)")

    # Folder names + boot id
    bad = [x["dir"] for x in data if not SESSION_RE.match(x["dir"])]
    rep.add("PASS" if not bad else "FAIL", "session folder names match boot####-YYYYMMDD-HHMMSS" + (f" (bad: {bad})" if bad else ""))
    boots = {SESSION_RE.match(x["dir"]).group(1) for x in data if SESSION_RE.match(x["dir"])}
    rep.add("PASS" if len(boots) <= 1 else "WARN", f"boot id(s) seen: {sorted(boots)}")

    # Per-window matching
    ages_all, per_session = [], []
    tap = {}
    if args.tap and os.path.isfile(args.tap):
        for r in load_jsonl(args.tap):
            tap.setdefault(r["sha1"], r["t"])
        print(f"\nTap: {len(tap)} unique stream frames logged")
    for i, (s, e, lab, m) in enumerate(wins):
        print(f"\nWindow {i + 1}: match {m} {lab} {e - s:.1f}s")
        sess = None
        for x in data:
            if x["t0"] is not None and s - args.boundary_tol_sec <= x["t0"] <= e:
                sess = x
                break
        if sess is None:
            rep.add("FAIL", "no session started inside this window")
            continue
        man, jpgs = sess["manifest"], sess["jpgs"]
        names = [r["frame"] for r in man]
        rep.add("PASS" if sorted(names) == jpgs else "FAIL",
                f"manifest lists exactly the JPEGs on disk ({len(names)} manifest lines, {len(jpgs)} files)")
        ts = [r["t_sec"] for r in man]
        rep.add("PASS" if all(b > a for a, b in zip(ts, ts[1:])) else "FAIL", "t_sec strictly increasing")
        lo, hi = s - args.boundary_tol_sec, e + args.boundary_tol_sec
        outside = [t for t in ts if t < lo or t > hi]
        rep.add("PASS" if not outside else "FAIL",
                f"all frames inside the enabled window (+/-{args.boundary_tol_sec}s); {len(outside)} outside")
        expected = args.sample_hz * (e - s)
        dev = abs(len(ts) - expected) / expected if expected else 0.0
        rep.add("PASS" if dev <= args.count_tol else "FAIL",
                f"frame count {len(ts)} vs ~{expected:.0f} expected at {args.sample_hz:g} Hz ({dev * 100:.0f}% off)")
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        if gaps:
            rep.add("INFO", f"frame spacing median {statistics.median(gaps) * 1000:.0f} ms, p95 {pct(gaps, 95) * 1000:.0f} ms, max {max(gaps) * 1000:.0f} ms")
        bad_jpg = []
        for n in jpgs:
            with open(os.path.join(args.recordings, sess["dir"], n), "rb") as f:
                b = f.read()
            if not (b[:2] == b"\xff\xd8" and b[-2:] == b"\xff\xd9" and len(b) > 200):
                bad_jpg.append(n)
        rep.add("PASS" if not bad_jpg else "FAIL", f"all JPEGs have valid start/end markers and a plausible size ({len(bad_jpg)} bad)")
        first_lag = ts[0] - s if ts else None
        if first_lag is not None:
            rep.add("INFO", f"first frame {first_lag:+.2f}s after enable; last frame {e - ts[-1]:+.2f}s before disable")
        if tap:
            ages = []
            for r in man:
                with open(os.path.join(args.recordings, sess["dir"], r["frame"]), "rb") as f:
                    h = hashlib.sha1(f.read()).hexdigest()
                if h in tap:
                    ages.append(r["t_sec"] - tap[h])
            unmatched = len(man) - len(ages)
            if ages:
                first_age = ages[0]
                ages_all.extend(ages)
                per_session.append({"label": f"match{m}-{lab}", "n": len(ages), "first": first_age,
                                    "median": statistics.median(ages), "p95": pct(ages, 95), "max": max(ages)})
                before_enable = sum(1 for r in man if tap.get(_h(args.recordings, sess["dir"], r["frame"]), 1e18) < s)
                rep.add("PASS" if pct(ages, 95) <= args.max_age_sec else "FAIL",
                        f"frame freshness: age (recorded t_sec minus when PhotonVision sent it) first {first_age:.2f}s, "
                        f"median {statistics.median(ages):.2f}s, p95 {pct(ages, 95):.2f}s, max {max(ages):.2f}s "
                        f"(limit p95 <= {args.max_age_sec}s; {unmatched} unmatched)")
                if before_enable:
                    rep.add("FAIL", f"{before_enable} frame(s) in this session were captured BEFORE the robot was enabled")
            else:
                rep.add("WARN", f"none of the {len(man)} recorded frames matched the tap log (hash mismatch?)")

    # Nothing outside the windows
    print("\nGlobal")
    all_t = [t for x in data for t in [r["t_sec"] for r in x["manifest"]]]
    stray = [t for t in all_t if not any(s - args.boundary_tol_sec <= t <= e + args.boundary_tol_sec for s, e, _, _ in wins)]
    rep.add("PASS" if not stray else "FAIL", f"no frames recorded while disabled (pre-match, pause, post-match): {len(stray)} stray")
    rep.add("INFO", "recordings do not record whether a session was auto or teleop; it is inferred from order and time only")

    print()
    print(f"RESULT: {'PASS' if rep.failed == 0 else 'FAIL'} ({rep.failed} failing check(s))")
    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump({"result": "FAIL" if rep.failed else "PASS", "checks": [{"status": a, "text": b} for a, b in rep.lines],
                       "sessions": per_session}, f, indent=2)
    return 1 if rep.failed else 0


def _h(base, d, name):
    with open(os.path.join(base, d, name), "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


if __name__ == "__main__":
    sys.exit(main())
