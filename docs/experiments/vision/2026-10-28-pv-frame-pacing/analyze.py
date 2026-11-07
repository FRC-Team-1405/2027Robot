"""Metrics for the PhotonVision frame-pacing experiment (see README.md).

Run from the repo root:  python docs/experiments/vision/2026-10-28-pv-frame-pacing/analyze.py
Reads the WPILog Janitor-trimmed logs in logs/offseason/11-3/ and 11-7/ and writes results.json
next to this file. The per-run metrics are the 10-27 ones (imported from that folder's analyze.py, so the two
experiments are measured identically), plus:

- frame-interval histogram, in multiples of the camera period (10 ms at 100 fps): with Low Latency
  Mode on, intervals snap to 1x / 2x / 3x; with it off they should spread toward 1 / loop time
- Pi network traffic (NetTxMbps / NetRxMbps) and the radio's own bandwidthUsedMbps
- recorder state during the enabled window (it starts recording a second or so after enable)
"""
import sys, json, statistics as st, importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
spec = importlib.util.spec_from_file_location("pv1027", HERE.parent / "2026-10-27-pv-throughput" / "analyze.py")
pv1027 = importlib.util.module_from_spec(spec); spec.loader.exec_module(pv1027)
from wpilog_utils.decode import parse_wpilog  # put on sys.path by the 10-27 module

LOGS = REPO / "logs" / "offseason"
CAM_PERIOD_MS = 10.0  # set per run below (1000 / camera fps)
# (ID, setting, log under logs/offseason/, camera fps). From 11-7 on, the settings are also in the
# log (OrangePi/<Pi>/PhotonVision/<cam>/* and Video/video0/Mode); the column here was checked
# against them. The 11-7 L-runs belong to the loop-overrun experiment but used R3's settings, so
# they count as repeats of R3 (= R5).
RUNS = [
    ("R1", "800x600 @100, dec 3, Low Latency on, threads 8", "11-3/akit_26-11-03_23-38-42", 100),
    ("R2", "800x600 @100, dec 2, Low Latency on, threads 8", "11-3/akit_26-11-03_23-58-01", 100),
    ("R3", "800x600 @100, dec 2, Low Latency off, threads 8", "11-3/akit_26-11-04_00-18-32", 100),
    ("R5a", "R3 repeat (11-7 L1)", "11-7/akit_26-11-07_18-04-56", 100),
    ("R5b", "R3 repeat (11-7 L2)", "11-7/akit_26-11-07_18-13-22", 100),
    ("R5c", "R3 repeat (11-7 L3, teleop, standing still)", "11-7/akit_26-11-07_18-16-38", 100),
    ("R5d", "R3 repeat (11-7 L5)", "11-7/akit_26-11-07_18-22-17", 100),
    ("R12a", "800x600 @120, dec 2, Low Latency off, threads 8", "11-7/akit_26-11-07_19-03-35", 120),
    ("R12b", "R12 repeat", "11-7/akit_26-11-07_19-10-49", 120),
    ("R12c", "R12 repeat", "11-7/akit_26-11-07_19-13-10", 120),
    ("R6", "800x600 @120, dec 1, Low Latency off, threads 8", "11-7/akit_26-11-07_19-19-16", 120),
    ("R13", "1280x800 @100, dec 2, Low Latency off, threads 8", "11-7/akit_26-11-07_19-23-31", 100),
]


def pv_settings(sig):
    """What the Pi publisher read from PhotonVision (11-7 on), to check the RUNS column."""
    out = {}
    for pi, cam in (("LeftPi", "LeftCam"), ("RightPi", "RightCam")):
        b = f"RealOutputs/OrangePi/{pi}/"
        g = lambda k: (sig.get(b + k) or [(None, None)])[-1][1]
        out[pi] = {"mode": g("Video/video0/Mode"), "decimate": g(f"PhotonVision/{cam}/Decimate"),
                   "low_latency": g(f"PhotonVision/{cam}/LowLatencyMode"), "threads": g(f"PhotonVision/{cam}/Threads"),
                   "settings_ok": g("PvSettingsOk")}
    return out


def interval_hist(sig, cam, sp):
    ts = []
    for t, v in pv1027.win(sig.get(f"Vision/{cam}/RawTimestampsSec", []), sp):
        ts += list(v)
    ts = sorted(set(ts))
    d = [(b - a) * 1000 for a, b in zip(ts, ts[1:])]
    if not d:
        return {}
    # bins: <0.75T, 0.75-1.25T (1x), 1.25-1.75T, 1.75-2.25T (2x), 2.25-2.75T, 2.75-3.25T (3x), >3.25T
    edges = [0, 0.75, 1.25, 1.75, 2.25, 2.75, 3.25, 1e9]
    names = ["<0.75T", "1T", "1.5T", "2T", "2.5T", "3T", ">3.25T"]
    h = {n: 0 for n in names}
    for x in d:
        r = x / CAM_PERIOD_MS
        for n, lo, hi in zip(names, edges, edges[1:]):
            if lo <= r < hi:
                h[n] += 1; break
    pct = {n: round(100 * c / len(d), 1) for n, c in h.items()}
    fine = {}
    for x in d:  # 1 ms histogram up to 40 ms
        if x < 40:
            k = int(x); fine[k] = fine.get(k, 0) + 1
    return {"pct": pct, "n": len(d), "fine_1ms": dict(sorted(fine.items())),
            "p10_ms": round(pv1027.pct(d, 10), 2), "p50_ms": round(pv1027.pct(d, 50), 2),
            "p90_ms": round(pv1027.pct(d, 90), 2), "mean_ms": round(st.mean(d), 2)}


def net_stats(sig, sp):
    out = {}
    for pi in ("LeftPi", "RightPi"):
        for k in ("NetTxMbps", "NetRxMbps"):
            v = [x for t, x in pv1027.win(sig.get(f"RealOutputs/OrangePi/{pi}/{k}", []), sp)]
            if v:
                out[f"{pi}_{k}"] = (round(st.median(v), 2), round(max(v), 2))
        for k in ("NetSpeedMbps", "NetRxErrors", "NetTxErrors", "NetRxDropped"):
            v = sig.get(f"RealOutputs/OrangePi/{pi}/{k}", [])
            if v:
                out[f"{pi}_{k}"] = v[-1][1]
    bw = []
    for t, s in sig.get("RadioStatus/Status", []):
        try:
            bw.append((t, json.loads(s)["networkStatus6"]["bandwidthUsedMbps"]))
        except (ValueError, KeyError, TypeError):
            pass
    # the radio status is sampled every few seconds, so take every sample from the enabled window's padding too
    inw = [v for t, v in bw if sp[0][0] - 5 <= t <= sp[-1][1] + 5]
    out["radio_bw_mbps"] = (round(st.median(inw), 2), round(max(inw), 2), len(inw)) if inw else None
    rio = [k for k in sig if k.startswith("RealOutputs/RIO/") or k.startswith("RIO/")]
    out["rio_stats_logged"] = bool(rio)
    return out


BIG_CORES = (4, 5, 6, 7)  # RK3588: cores 4-7 are the fast A76s; PhotonVision ran only there on 11-07


def frame_budget(sig, pi, sp, results_per_s):
    """Where one frame's time goes, from the publisher's top-8 PhotonVision threads (~1 Hz).

    PhotonVision handles one frame per camera at a time: the main VisionRunner thread decodes,
    converts, runs the serial parts of the detector, PnP, draws and publishes; the detector's
    worker threads (also named "VisionRunner - ...") run in parallel in the middle. So
    frame time ~ main-thread ms + worker CPU ms / (fast cores). A thread missing from a sample
    (below the top 8) counts as 0, so worker CPU is a slight underestimate."""
    b = f"RealOutputs/OrangePi/{pi}/"
    names = {t: v for t, v in pv1027.win(sig.get(b + "PvTopThreads", []), sp)}
    pcts = {t: v for t, v in pv1027.win(sig.get(b + "PvTopThreadPct", []), sp)}
    ts = [t for t in names if t in pcts]
    if not ts or not results_per_s:
        return None
    per = {}
    for t in ts:
        for n, p in zip(names[t], pcts[t]):
            per.setdefault(n, {})[t] = p
    mean = {n: sum(d.values()) / len(ts) for n, d in per.items()}
    runners = {n: m for n, m in mean.items() if n.startswith("VisionRunner")}
    main = max(runners, key=runners.get) if runners else None
    worker_pct = sum(m for n, m in runners.items() if n != main)
    other_pct = sum(m for n, m in mean.items() if not n.startswith("VisionRunner"))
    ms = lambda pct: round(pct / 100 * 1000 / results_per_s, 2)
    cores = [v for t, v in pv1027.win(sig.get(b + "CpuCorePct", []), sp)]
    core_med = [round(st.median(c), 1) for c in zip(*cores)] if cores else []
    nbig = len(BIG_CORES)
    out = {"samples": len(ts), "main_thread": main, "main_thread_pct": round(runners.get(main, 0), 1),
           "main_ms_per_frame": ms(runners.get(main, 0)), "worker_threads": len(runners) - 1,
           "worker_cpu_pct": round(worker_pct, 1), "worker_cpu_ms_per_frame": ms(worker_pct),
           "worker_wall_ms_est": round(ms(worker_pct) / nbig, 2), "other_pv_pct": round(other_pct, 1),
           "frame_ms_measured": round(1000 / results_per_s, 2), "core_pct_median": core_med}
    out["frame_ms_model"] = round(out["main_ms_per_frame"] + out["worker_wall_ms_est"], 2)
    if core_med:
        out["fast_cores_pct"] = round(st.mean(core_med[i] for i in BIG_CORES if i < len(core_med)), 1)
        out["slow_cores_pct"] = round(st.mean(core_med[i] for i in range(len(core_med)) if i not in BIG_CORES), 1)
    return out


def recorder(sig, pi, cam, sp):
    s = sig.get(f"RealOutputs/OrangePi/{pi}/Recorders/{cam}/State", [])
    rec = 0.0
    for (t0, v), (t1, _) in zip(s, s[1:] + [(sp[-1][1], None)]):
        if v == "recording":
            a, b = max(t0, sp[0][0]), min(t1, sp[-1][1])
            rec += max(0, b - a)
    dur = sum(b - a for a, b in sp)
    return round(100 * rec / dur, 1) if dur else None


if __name__ == "__main__":
    out = []
    for run_id, setting, rel, fps in RUNS:
        CAM_PERIOD_MS = 1000.0 / fps
        stem = Path(rel).name
        path = str(LOGS / Path(rel).parent / f"{stem}-bundle" / f"{stem}.trimmed.wpilog")
        r = pv1027.analyze(path); r["id"] = run_id; r["setting"] = setting; r["camera_fps"] = fps
        sig = parse_wpilog(path)
        r["pv_settings"] = pv_settings(sig)
        sp = [s for s in pv1027.spans(sig) if s[1] - s[0] > 5]
        r["net"] = net_stats(sig, sp)
        for cam, pi in (("LeftCam", "LeftPi"), ("RightCam", "RightPi")):
            r[cam]["interval_hist"] = interval_hist(sig, cam, sp)
            r[cam]["recorder_pct_of_window"] = recorder(sig, pi, cam, sp)
            r[pi]["frame_budget"] = frame_budget(sig, pi, sp, r[cam]["results_per_s"])
        out.append(r)
        c = (r["LeftCam"], r["RightCam"])
        print(f"{run_id:5s} {setting:48s} results/s {c[0]['results_per_s']:6.1f} / {c[1]['results_per_s']:6.1f}"
              f"  drop% {c[0].get('dropped_pct')} / {c[1].get('dropped_pct')}"
              f"  PV ms {c[0].get('pv_ms_med')} / {c[1].get('pv_ms_med')}"
              f"  1T/2T% {c[0]['interval_hist']['pct']['1T']}/{c[0]['interval_hist']['pct']['2T']}"
              f" | {c[1]['interval_hist']['pct']['1T']}/{c[1]['interval_hist']['pct']['2T']}")
        for pi in ("LeftPi", "RightPi"):
            fb = r[pi]["frame_budget"]
            if fb:
                print(f"        {pi:7s} frame {fb['frame_ms_measured']:5.1f} ms = main {fb['main_ms_per_frame']:5.1f}"
                      f" + workers {fb['worker_wall_ms_est']:4.1f} ({fb['worker_threads']} thr, {fb['worker_cpu_ms_per_frame']:5.1f} ms CPU)"
                      f" -> model {fb['frame_ms_model']:5.1f}   fast/slow cores {fb.get('fast_cores_pct')}/{fb.get('slow_cores_pct')}%")
    json.dump(out, open(HERE / "results.json", "w"), indent=1, default=str)
