"""Summarizes the frame-cost bench test (README.md) from what the experiment runner fetched.

Run from the repo root:  python docs/experiments/vision/2026-11-11-pv-frame-cost/analyze.py
Reads data/<run>/<board>/result.json (written by coprocessor/bench/java/FrameCost.java on each Pi)
and manifest.json, prints the tables the README uses, and writes results.json next to this file.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

# Robot measurements the PhotonVision-like baselines are checked against (time per frame, ms).
ROBOT_FRAME_MS = {"F0a": ("11-10 B1, 800x600 dec 1, 8 threads", 14.6),
                  "F0b": ("11-07 R13, 1280x800 dec 2, 8 threads", 15.9)}


def load():
    out = {}
    if not DATA.is_dir():
        return out
    for run_dir in sorted(DATA.iterdir()):
        for board_dir in sorted(p for p in run_dir.iterdir() if p.is_dir()):
            f = board_dir / "result.json"
            if f.exists():
                out.setdefault(run_dir.name, {})[board_dir.name] = json.loads(f.read_text(encoding="utf-8"))
    return out


def med(step):
    return step.get("median") if step else None


def steps_table(res, run_id):
    """Per-step median ms for one steps run, both boards side by side."""
    boards = res.get(run_id, {})
    if not boards:
        return None
    names = []
    for r in boards.values():
        for k in r.get("steps_ms", {}):
            if k not in names:
                names.append(k)
    rows = []
    for k in names:
        row = {"step": k}
        for b, r in boards.items():
            s = r.get("steps_ms", {}).get(k, {})
            row[b] = {"median_ms": s.get("median"), "p95_ms": s.get("p95"), "tags_per_frame": s.get("tags_per_frame")}
        rows.append(row)
    jpeg = {b: r.get("jpeg") for b, r in boards.items()}
    return {"jpeg": jpeg, "rows": rows}


def inflight_table(res, run_id):
    boards = res.get(run_id, {})
    if not boards:
        return None
    out = {}
    for b, r in boards.items():
        out[b] = [{"workers": w["workers"], "frames_per_s": w["frames_per_s"],
                   "per_frame_median_ms": w["per_frame_ms"].get("median"),
                   "per_frame_p95_ms": w["per_frame_ms"].get("p95")} for w in r.get("by_workers", [])]
    return out


def main():
    res = load()
    if not res:
        print(f"no results yet under {DATA}; run the plan with tools/exprunner first")
        return
    summary = {"steps": {}, "inflight": {}, "baseline_check": {}}

    for run_id in ("T1", "T2"):
        t = steps_table(res, run_id)
        if not t:
            continue
        summary["steps"][run_id] = t
        boards = [b for b in res[run_id]]
        print(f"\n{run_id}: median ms per frame (p95)   JPEG: {t['jpeg']}")
        print(f"  {'step':34s}" + "".join(f"{b:>22s}" for b in boards))
        for row in t["rows"]:
            cells = []
            for b in boards:
                c = row[b]
                tags = f" {c['tags_per_frame']}t" if c.get("tags_per_frame") is not None else ""
                cells.append(f"{c['median_ms']} ({c['p95_ms']}){tags}" if c["median_ms"] is not None else "-")
            print(f"  {row['step']:34s}" + "".join(f"{c:>22s}" for c in cells))

    for run_id in ("F0a", "F0b", "F1", "F2", "F3", "F4"):
        t = inflight_table(res, run_id)
        if not t:
            continue
        summary["inflight"][run_id] = t
        print(f"\n{run_id}: frames/s by workers (per-frame median ms)")
        for b, rows in t.items():
            print(f"  {b:8s} " + "   ".join(f"{r['workers']}w: {r['frames_per_s']}/s ({r['per_frame_median_ms']} ms)" for r in rows))
        if run_id in ROBOT_FRAME_MS:
            label, robot_ms = ROBOT_FRAME_MS[run_id]
            checks = {}
            for b, rows in t.items():
                if rows:
                    bench_ms = round(1000 / rows[0]["frames_per_s"], 2)
                    checks[b] = {"bench_frame_ms": bench_ms, "robot_frame_ms": robot_ms,
                                 "ratio": round(bench_ms / robot_ms, 2)}
            summary["baseline_check"][run_id] = {"robot": label, **checks}
            print(f"  vs robot ({label}, {robot_ms} ms): " +
                  ", ".join(f"{b} {c['bench_frame_ms']} ms (x{c['ratio']})" for b, c in checks.items()))

    (HERE / "results.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    print(f"\nwrote {HERE / 'results.json'}")


if __name__ == "__main__":
    main()
