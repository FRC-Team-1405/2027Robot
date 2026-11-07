"""Metrics for the roboRIO loop-overrun experiment (see README.md).

Run from the repo root:  python docs/experiments/roborio/2026-11-03-loop-overruns/analyze.py
Reads WPILog Janitor-trimmed logs and writes results.json next to this file. Window = every
enabled span longer than 5 s.

A slow cycle is one where LoggedRobot/FullCycleMS > 20 ms. For each section timed by
LOG_SUBSYSTEM_TIMINGS (RealOutputs/Timing/*) plus AdvantageKit's own GC and logging times, it
compares the mean on slow cycles with the mean on normal ones: one section jumping points at that
section; everything stretching by the same factor points at the CPU being taken away (another
process, GC, the kernel).
"""
import sys, json, statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "wpilog-utils"))
from wpilog_utils.decode import parse_wpilog

LOGS = REPO / "logs" / "offseason"
# (ID, what it was, log). Baseline data from the two vision experiments; add this experiment's runs below.
RUNS = [
    ("B-10-27-T1", "10-27 T1, CircleFacingTag", "10-27/akit_26-10-27_22-13-27"),
    ("B-10-27-T2", "10-27 T2, CircleFacingTag", "10-27/akit_26-10-27_22-37-33"),
    ("B-10-27-T3", "10-27 T3, CircleFacingTag", "10-27/akit_26-10-27_22-42-57"),
    ("B-10-27-T7", "10-27 T7, driven heat soak", "10-27/akit_26-10-27_23-42-41"),
    ("B-11-03-R1", "11-03 R1, CircleFacingTag", "11-3/akit_26-11-03_23-38-42"),
    ("B-11-03-R2", "11-03 R2, CircleFacingTag", "11-3/akit_26-11-03_23-58-01"),
    ("B-11-03-R3", "11-03 R3, CircleFacingTag", "11-3/akit_26-11-04_00-18-32"),
    # 11-7. L1-L3 ran the OLD robot code (338bcfa, built 10-27: no RIO/* stats, extended vision
    # logging ON); L5 ran branch vision-throughput-10-27 + local edits; the rest ran beta d0b8b2c +
    # local edits with VISION_EXTENDED_NT_LOGGING=false (all read from RealMetadata in the logs).
    ("L1", "AdvantageScope + Elastic, auto (old code, ext. vision logging on)", "11-7/akit_26-11-07_18-04-56"),
    ("L2", "Driver Station only, auto (old code, ext. vision logging on)", "11-7/akit_26-11-07_18-13-22"),
    ("L3", "Driver Station only, teleop sticks idle (old code, ext. vision logging on)", "11-7/akit_26-11-07_18-16-38"),
    ("L5", "AdvantageScope + Elastic, auto, ext. vision logging off", "11-7/akit_26-11-07_18-22-17"),
    ("L4'", "AdvantageScope + Elastic, auto (beta; vision 800x600@120)", "11-7/akit_26-11-07_19-03-35"),
    ("L4''", "AdvantageScope + Elastic + LogBench Fetch Bundle page, auto (beta)", "11-7/akit_26-11-07_19-10-49"),
    ("L2'", "Driver Station only, auto (beta)", "11-7/akit_26-11-07_19-13-10"),
    ("R6", "AS + Elastic + LogBench, auto, vision dec 1 (frame-pacing R6)", "11-7/akit_26-11-07_19-19-16"),
    ("R13", "AS + Elastic + LogBench, auto, vision 1280x800 (frame-pacing R13)", "11-7/akit_26-11-07_19-23-31"),
]
SECTIONS = ["LoggedRobot/UserCodeMS", "LoggedRobot/LogPeriodicMS", "LoggedRobot/GCTimeMS",
            "Timing/RobotPeriodicMs", "Timing/CommandSchedulerMs", "Timing/VisionMs",
            "Timing/CorrectOdometryMs", "Timing/ShooterMs", "Timing/DrivetrainMs", "Timing/PublishingMs"]


def spans(sig):
    out, s0 = [], None
    for t, v in sig.get("DriverStation/Enabled", []):
        if v and s0 is None:
            s0 = t
        elif not v and s0 is not None:
            out.append((s0, t)); s0 = None
    if s0 is not None:
        out.append((s0, max(s[-1][0] for s in sig.values() if s)))
    return [s for s in out if s[1] - s[0] > 5]


def analyze(path):
    sig = parse_wpilog(str(path))
    sp = spans(sig)
    inside = lambda t: any(a <= t <= b for a, b in sp)
    full = {t: v for t, v in sig.get("RealOutputs/LoggedRobot/FullCycleMS", []) if inside(t)}
    slow = {t for t, v in full.items() if v > 20}
    r = {"enabled_s": round(sum(b - a for a, b in sp), 1), "cycles": len(full),
         "slow_cycles_pct": round(100 * len(slow) / len(full), 1) if full else None,
         "full_cycle_ms_median": round(st.median(full.values()), 2) if full else None,
         "full_cycle_ms_max": round(max(full.values()), 1) if full else None,
         "sections": {}}
    for key in SECTIONS:
        d = dict(sig.get("RealOutputs/" + key, []))
        s = [d[t] for t in slow if t in d]
        n = [d[t] for t in full if t not in slow and t in d]
        if s and n:
            r["sections"][key] = {"normal_ms": round(st.mean(n), 2), "slow_ms": round(st.mean(s), 2),
                                  "ratio": round(st.mean(s) / st.mean(n), 2) if st.mean(n) else None}
    gc = [v for t, v in sig.get("RealOutputs/LoggedRobot/GCCounts", []) if inside(t)]
    r["gc_per_cycle_mean"] = round(st.mean(gc), 2) if gc else None
    # Clients listed in the log, and which were connected when the window started (a trimmed log
    # keeps every client that ever connected, so the list alone over-counts).
    clients = {k.split("/")[2] for k in sig if k.startswith("SystemStats/NTClients/")}
    r["nt_clients"] = sorted(clients)
    conn = lambda c: [v for t, v in sig.get(f"SystemStats/NTClients/{c}/Connected", []) if t <= sp[0][0]] if sp else []
    r["nt_clients_connected"] = sorted(c for c in clients if (conn(c) or [False])[-1])
    rio = [v for t, v in sig.get("RealOutputs/RIO/CpuPct", []) if inside(t)]
    r["rio_cpu_pct_median"] = round(st.median(rio), 1) if rio else None
    r["rio_cpu_pct_max"] = round(max(rio), 1) if rio else None
    # How often a GC ran in the loop: slow vs normal loops.
    gcc = dict(sig.get("RealOutputs/LoggedRobot/GCCounts", []))
    gct = dict(sig.get("RealOutputs/LoggedRobot/GCTimeMS", []))
    nslow, nnorm = len(slow), len(full) - len(slow)
    r["gc_in_slow_pct"] = round(100 * sum(1 for t in slow if gcc.get(t, 0) > 0) / nslow) if nslow else None
    r["gc_in_normal_pct"] = round(100 * sum(1 for t in full if t not in slow and gcc.get(t, 0) > 0) / nnorm) if nnorm else None
    # Slow loops that would still be over 20 ms with their GC time removed.
    r["slow_without_gc_pct"] = round(100 * sum(1 for t in slow if full[t] - gct.get(t, 0) > 20) / nslow) if nslow else None
    md = sig.get("RealMetadata/GitSHA", [])
    r["git_sha"] = md[-1][1][:7] if md else None
    fs = sig.get("RealMetadata/FeatureSwitches", [])
    r["vision_extended_nt_logging"] = ("VISION_EXTENDED_NT_LOGGING=true" in fs[-1][1]) if fs else None
    return r


if __name__ == "__main__":
    out = []
    for run_id, what, stem in RUNS:
        name = Path(stem).name
        path = LOGS / Path(stem).parent / f"{name}-bundle" / f"{name}.trimmed.wpilog"
        r = analyze(path); r.update(id=run_id, what=what, log=name)
        out.append(r)
        s = r["sections"]
        print(f"{run_id:12s} slow {r['slow_cycles_pct']:5}%  user code {s['LoggedRobot/UserCodeMS']['normal_ms']:5} -> "
              f"{s['LoggedRobot/UserCodeMS']['slow_ms']:5} ms  GC {s['LoggedRobot/GCTimeMS']['normal_ms']} -> "
              f"{s['LoggedRobot/GCTimeMS']['slow_ms']} ms  vision {s['Timing/VisionMs']['normal_ms']} -> {s['Timing/VisionMs']['slow_ms']} ms"
              f"  dashboards {[c for c in r['nt_clients_connected'] if not c.startswith(('OrangePi', 'leftpi', 'RightPi'))]}"
              f"  rio cpu {r['rio_cpu_pct_median']}/{r['rio_cpu_pct_max']}  GC in slow/normal {r['gc_in_slow_pct']}/{r['gc_in_normal_pct']}%")
    json.dump(out, open(HERE / "results.json", "w"), indent=1)
