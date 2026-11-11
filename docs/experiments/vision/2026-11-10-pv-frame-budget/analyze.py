"""Metrics for the PhotonVision frame-budget experiment (see README.md).

Run from the repo root:  python docs/experiments/vision/2026-11-10-pv-frame-budget/analyze.py
Reads WPILog Janitor-trimmed logs and writes results.json next to this file. Uses the frame-pacing
experiment's code (results/s, dropped frames, latency, cross-camera agreement, frame budget), so
the numbers are directly comparable with it.

For each run it reads the PhotonVision settings from the log (camera mode, decimate, threads, and
from the pipeline JSON whether output drawing / the output stream were on) and prints time per
frame split into main thread and detector workers.
"""
import json, importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
spec = importlib.util.spec_from_file_location("fp", HERE.parent / "2026-10-28-pv-frame-pacing" / "analyze.py")
fp = importlib.util.module_from_spec(spec); spec.loader.exec_module(fp)
pv1027 = fp.pv1027
from wpilog_utils.decode import parse_wpilog  # put on sys.path by the 10-27 module

LOGS = REPO / "logs" / "offseason"
# (ID, what changed, log under logs/offseason/, camera fps). References from 11-07 first.
RUNS = [
    ("ref-R5", "11-07: 800x600 @100, dec 2, threads 8, drawing on", "11-7/akit_26-11-07_18-13-22", 100),
    ("ref-R6", "11-07: 800x600 @120, dec 1, threads 8, drawing on", "11-7/akit_26-11-07_19-19-16", 120),
    ("B1", "dec 1, threads 8, drawing on (baseline)", "11-10/akit_26-11-10_23-14-41", 100),
    ("B2", "dec 1, threads 4", "11-10/akit_26-11-10_23-27-02", 100),
    ("B3", "dec 1, threads 3", "11-10/akit_26-11-10_23-30-18", 100),
    ("B4", "dec 1, threads 1", "11-10/akit_26-11-10_23-32-43", 100),
    ("B5", "dec 1, dashboard Processed -> Raw (drawing off)", "11-10/akit_26-11-10_23-38-26", 100),
    ("reset", "dec 2, threads 8, drawing on (main setting)", "11-10/akit_26-11-10_23-43-08", 100),
]


def settings(sig, pi, cam):
    b = f"RealOutputs/OrangePi/{pi}/"
    g = lambda k: (sig.get(b + k) or [(None, None)])[-1][1]
    out = {"mode": g("Video/video0/Mode"), "decimate": g(f"PhotonVision/{cam}/Decimate"),
           "threads": g(f"PhotonVision/{cam}/Threads"), "low_latency": g(f"PhotonVision/{cam}/LowLatencyMode")}
    try:
        pj = json.loads(g(f"PhotonVision/{cam}/PipelineJson") or "{}")
    except ValueError:
        pj = {}
    out["output_draw"] = pj.get("outputShouldDraw")
    out["output_stream"] = pj.get("outputShouldShow")
    return out


def run(run_id, what, rel, fps):
    fp.CAM_PERIOD_MS = 1000.0 / fps
    stem = Path(rel).name
    path = str(LOGS / Path(rel).parent / f"{stem}-bundle" / f"{stem}.trimmed.wpilog")
    r = pv1027.analyze(path)
    sig = parse_wpilog(path)
    sp = [s for s in pv1027.spans(sig) if s[1] - s[0] > 5]
    out = {"id": run_id, "what": what, "log": stem, "camera_fps": fps,
           "xcam_trans_m_median": (r["rio"].get("xcam_trans_m") or [None])[0]}
    for cam, pi in (("LeftCam", "LeftPi"), ("RightCam", "RightPi")):
        c = r[cam]
        out[pi] = {"settings": settings(sig, pi, cam), "results_per_s": c.get("results_per_s"),
                   "dropped_pct": c.get("dropped_pct"), "latency_ms_median": c.get("total_lat_med"),
                   "interval_hist": fp.interval_hist(sig, cam, sp).get("pct"),
                   "frame_budget": fp.frame_budget(sig, pi, sp, c.get("results_per_s"))}
    return out


if __name__ == "__main__":
    out = []
    print(f"{'run':7s} {'Pi':7s} {'mode':18s} dec thr draw  res/s  frame = main + workers (model)  lat   xcam")
    for args in RUNS:
        r = run(*args)
        out.append(r)
        for pi in ("LeftPi", "RightPi"):
            p = r[pi]; s = p["settings"]; fb = p["frame_budget"] or {}
            print(f"{r['id']:7s} {pi:7s} {str(s['mode']):18s} {str(s['decimate']):3s} {str(s['threads']):3s} "
                  f"{str(s['output_draw']):5s} {p['results_per_s']:6.1f}  {fb.get('frame_ms_measured', 0):5.1f} = "
                  f"{fb.get('main_ms_per_frame', 0):4.1f} + {fb.get('worker_wall_ms_est', 0):4.1f} ({fb.get('frame_ms_model', 0):4.1f})"
                  f"  {p['latency_ms_median']}  {r['xcam_trans_m_median']}")
    json.dump(out, open(HERE / "results.json", "w"), indent=1, default=str)
