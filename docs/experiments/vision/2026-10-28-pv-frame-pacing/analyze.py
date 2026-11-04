"""Metrics for the PhotonVision frame-pacing experiment (see README.md).

Run from the repo root:  python docs/experiments/vision/2026-10-28-pv-frame-pacing/analyze.py
Reads the WPILog Janitor-trimmed logs in logs/offseason/11-3/ and writes results.json next to this
file. The per-run metrics are the 10-27 ones (imported from that folder's analyze.py, so the two
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

LOG_DIR = REPO / "logs" / "offseason" / "11-3"
CAM_PERIOD_MS = 10.0  # 800x600 @100 fps
RUNS = [
    ("R1", "800x600 @100, dec 3, Low Latency on, threads 8", "akit_26-11-03_23-38-42"),
    ("R2", "800x600 @100, dec 2, Low Latency on, threads 8", "akit_26-11-03_23-58-01"),
    ("R3", "800x600 @100, dec 2, Low Latency off, threads 8", "akit_26-11-04_00-18-32"),
]


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
    for run_id, setting, stem in RUNS:
        path = str(LOG_DIR / f"{stem}-bundle" / f"{stem}.trimmed.wpilog")
        r = pv1027.analyze(path); r["id"] = run_id; r["setting"] = setting
        sig = parse_wpilog(path)
        sp = [s for s in pv1027.spans(sig) if s[1] - s[0] > 5]
        r["net"] = net_stats(sig, sp)
        for cam, pi in (("LeftCam", "LeftPi"), ("RightCam", "RightPi")):
            r[cam]["interval_hist"] = interval_hist(sig, cam, sp)
            r[cam]["recorder_pct_of_window"] = recorder(sig, pi, cam, sp)
        out.append(r)
        c = (r["LeftCam"], r["RightCam"])
        print(f"{run_id:3s} {setting:48s} results/s {c[0]['results_per_s']:6.1f} / {c[1]['results_per_s']:6.1f}"
              f"  drop% {c[0].get('dropped_pct')} / {c[1].get('dropped_pct')}"
              f"  PV ms {c[0].get('pv_ms_med')} / {c[1].get('pv_ms_med')}"
              f"  1T/2T% {c[0]['interval_hist']['pct']['1T']}/{c[0]['interval_hist']['pct']['2T']}"
              f" | {c[1]['interval_hist']['pct']['1T']}/{c[1]['interval_hist']['pct']['2T']}")
    json.dump(out, open(HERE / "results.json", "w"), indent=1, default=str)
