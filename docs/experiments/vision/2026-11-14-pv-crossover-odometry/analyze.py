"""Metrics for the camera-setting crossover experiment (see README.md).

Run from the repo root:
    python docs/experiments/vision/2026-11-14-pv-crossover-odometry/analyze.py [--config runs.toml]

For every run it reads, from the log itself (never from notes): each camera's PhotonVision settings
(camera mode, decimate, threads, exposure, gain), the git SHA and feature switches, and checks them
against what the run table says was running. Then, from each camera's RAW per-camera robot-pose estimates
(logged before any filtering, so the robot's filter and trust settings do not matter), it computes:

  * results/s, the longest gap, the share of the run in gaps longer than 50 ms
  * PhotonVision's processing latency per result
  * jitter: how far each estimate wanders from a smooth curve through its neighbours (a quadratic over
    +-0.12 s, leave-one-out). It needs no ground truth and works while the robot moves.
  * noise_per_sqrt_s: jitter divided by sqrt(results/s): the noise left after one second of averaging,
    which is how more precise results and fewer results are weighed against each other
  * Left-minus-Right: the mean difference (bias) and scatter between the two cameras' estimates.

Then it compares setting B with setting A on the same camera across the crossover runs.
Writes results.json next to this file.
"""
import argparse
import bisect
import json
import math
import statistics
import sys
import tomllib
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "wpilog-utils"))
from wpilog_utils.decode import parse_wpilog  # noqa: E402
from wpilog_utils.modes import compute_mode_spans  # noqa: E402

LOGS = REPO / "logs" / "offseason"
WINDOW_S = 0.12          # half-width of the local quadratic used for jitter
MIN_POINTS = 8           # points needed in a window to score a sample
GAP_S = 0.05             # a gap longer than this counts as a dropout


# --------------------------------------------------------------------------- reading a log

def find(sig, key):
    for prefix in ("RealOutputs/", ""):
        if prefix + key in sig:
            return sig[prefix + key]
    low = key.lower()
    for k, v in sig.items():
        kl = k.lower()
        if kl == low or kl == "realoutputs/" + low:
            return v
    return None


def last(sig, key):
    s = find(sig, key)
    return s[-1][1] if s else None


def auto_window(sig):
    """(t0, t1) of the longest autonomous span, in the log's own time."""
    start = min(s[0][0] for s in sig.values() if s)
    end = max(s[-1][0] for s in sig.values() if s)
    spans = [(a + start, b + start) for a, b, m in compute_mode_spans(sig, start, end) if m == "auto"]
    if not spans:
        return None
    return max(spans, key=lambda s: s[1] - s[0])


def pv_settings(sig, pi, cam):
    b = f"OrangePi/{pi}/"
    return {
        "mode": last(sig, b + "Video/video0/Mode"),
        "decimate": last(sig, b + f"PhotonVision/{cam}/Decimate"),
        "threads": last(sig, b + f"PhotonVision/{cam}/Threads"),
        "exposure": last(sig, b + f"PhotonVision/{cam}/Exposure"),
        "gain": last(sig, b + f"PhotonVision/{cam}/Gain"),
        "multitag": last(sig, b + f"PhotonVision/{cam}/MultiTag"),
        "low_latency": last(sig, b + f"PhotonVision/{cam}/LowLatencyMode"),
        "pipeline": last(sig, b + f"PhotonVision/{cam}/PipelineName"),
    }


def camera_series(sig, cam, window):
    """Flatten one camera's raw per-result estimates inside the window."""
    poses = find(sig, f"Vision/{cam}/rawEstimatedPoses") or []
    stamps = dict(find(sig, f"Vision/{cam}/rawTimestampsSec") or [])
    lats = find(sig, f"Vision/{cam}/PipelineLatenciesMs") or []
    counts = dict(find(sig, f"Vision/{cam}/rawTagCountsPerResult") or [])
    dists = dict(find(sig, f"Vision/{cam}/rawAvgDistancesMeters") or [])
    t, x, y, yaw, z, ntag, dist = [], [], [], [], [], [], []
    for rec_t, ps in poses:
        if window and not (window[0] <= rec_t <= window[1]):
            continue
        ts = stamps.get(rec_t) or []
        cs = counts.get(rec_t) or []
        ds = dists.get(rec_t) or []
        for j, p in enumerate(ps):
            if j >= len(ts):
                continue
            t.append(float(ts[j]))
            x.append(p["x"])
            y.append(p["y"])
            z.append(p["z"])
            yaw.append(2.0 * math.atan2(p["qz"], p["qw"]))
            ntag.append(cs[j] if j < len(cs) else float("nan"))
            dist.append(ds[j] if j < len(ds) else float("nan"))
    order = np.argsort(t)
    arr = lambda v: np.array(v, float)[order]  # noqa: E731
    out = {"t": arr(t), "x": arr(x), "y": arr(y), "z": arr(z), "yaw": np.unwrap(arr(yaw)),
           "ntag": arr(ntag), "dist": arr(dist)}
    out["latency_ms"] = [v for rec_t, vs in lats if (not window or window[0] <= rec_t <= window[1]) for v in vs]
    return out


# --------------------------------------------------------------------------- metrics

def local_jitter(t, v):
    """Leave-one-out residual of a local quadratic (+-WINDOW_S). Returns residuals (NaN where not scored)."""
    n = len(t)
    res = np.full(n, np.nan)
    for i in range(n):
        lo = bisect.bisect_left(t, t[i] - WINDOW_S)
        hi = bisect.bisect_right(t, t[i] + WINDOW_S)
        idx = [k for k in range(lo, hi) if k != i]
        if len(idx) < MIN_POINTS:
            continue
        tt = t[idx] - t[i]
        A = np.vander(tt, 3)                      # [t^2, t, 1]
        coef, *_ = np.linalg.lstsq(A, v[idx], rcond=None)
        pred = coef[2]                            # value at t[i] (tt = 0)
        # leave-one-out prediction variance is sigma^2 * (1 + h), h = leverage of the prediction point
        h = float(np.linalg.inv(A.T @ A)[2, 2])
        res[i] = (v[i] - pred) / math.sqrt(1.0 + h)
    return res


def camera_metrics(s, window):
    t = s["t"]
    out = {"n": int(len(t))}
    if len(t) < 5 or not window:
        return out
    dur = window[1] - window[0]
    iv = np.diff(t)
    gaps = iv[iv > GAP_S]
    out.update({
        "results_per_s": len(t) / dur,
        "median_interval_ms": float(np.median(iv) * 1000),
        "max_gap_ms": float(iv.max() * 1000),
        "gap_share_pct": float(gaps.sum() / dur * 100),
        "dropouts": int(len(gaps)),
        "latency_ms_mean": float(np.mean(s["latency_ms"])) if s["latency_ms"] else None,
        "tags_mean": float(np.nanmean(s["ntag"])) if np.isfinite(s["ntag"]).any() else None,
        "distance_m_mean": float(np.nanmean(s["dist"])) if np.isfinite(s["dist"]).any() else None,
    })
    rx, ry, ryaw = local_jitter(t, s["x"]), local_jitter(t, s["y"]), local_jitter(t, s["yaw"])
    m = np.isfinite(rx) & np.isfinite(ry)
    if m.sum() >= 10:
        out["jitter_xy_mm"] = float(np.sqrt(np.mean(rx[m] ** 2 + ry[m] ** 2)) * 1000)
        out["jitter_yaw_deg"] = float(np.degrees(np.sqrt(np.mean(ryaw[m] ** 2))))
        out["jitter_scored"] = int(m.sum())
        # Averaging N independent results per second cuts noise by sqrt(N), so this is the noise left after one
        # second of averaging. It is the number that says whether more precise results are worth fewer of them.
        # Frame-to-frame errors that are NOT independent (a bias that depends on where the robot is) do not average.
        out["noise_per_sqrt_s_mm"] = out["jitter_xy_mm"] / math.sqrt(out["results_per_s"])
    return out


def left_minus_right(a, b, max_dt=0.006):
    """Mean and scatter of the Left-minus-Right pose difference at matched capture times."""
    ta, tb = a["t"], b["t"]
    if len(ta) < 5 or len(tb) < 5:
        return {}
    j = np.clip(np.searchsorted(tb, ta), 1, len(tb) - 1)
    j = np.where(np.abs(tb[j - 1] - ta) < np.abs(tb[j] - ta), j - 1, j)
    ok = np.abs(tb[j] - ta) <= max_dt
    if ok.sum() < 20:
        return {"pairs": int(ok.sum())}
    dx = a["x"][ok] - b["x"][j[ok]]
    dy = a["y"][ok] - b["y"][j[ok]]
    dyaw = np.degrees(np.angle(np.exp(1j * (a["yaw"][ok] - b["yaw"][j[ok]]))))
    return {"pairs": int(ok.sum()), "bias_xy_mm": float(np.hypot(dx.mean(), dy.mean()) * 1000),
            "scatter_xy_mm": float(np.sqrt(dx.var() + dy.var()) * 1000),
            "bias_yaw_deg": float(dyaw.mean()), "scatter_yaw_deg": float(dyaw.std())}


# --------------------------------------------------------------------------- a run

def analyze_run(run, cfg):
    path = LOGS / (run["log"] + ".wpilog")
    if not path.exists():
        alt = list(LOGS.glob(f"**/{Path(run['log']).name}.wpilog"))
        if not alt:
            raise FileNotFoundError(path)
        path = alt[0]
    sig = parse_wpilog(str(path))
    window = auto_window(sig)
    cams = cfg["cameras"]
    res = {"id": run["id"], "kind": run["kind"], "log": run["log"], "window_s": None if not window else window[1] - window[0],
           "git_sha": last(sig, "RealMetadata/GitSHA"), "git_dirty": last(sig, "RealMetadata/GitDirty"),
           "feature_switches": last(sig, "RealMetadata/FeatureSwitches"), "cameras": {}, "problems": []}
    series = {}
    for side in ("left", "right"):
        cam, pi = cams[side]["camera"], cams[side]["pi"]
        want_name = run[side]
        want = cfg["settings"][want_name]
        got = pv_settings(sig, pi, cam)
        for k, v in want.items():
            if str(got.get(k)).split(" ")[0] != str(v).split(" ")[0]:
                res["problems"].append(f"{side} ({cam}) {k}: run table says {v}, log says {got.get(k)}")
        s = camera_series(sig, cam, window)
        series[side] = s
        res["cameras"][side] = {"camera": cam, "setting": want_name, "log_settings": got, **camera_metrics(s, window)}
    res["left_minus_right"] = left_minus_right(series["left"], series["right"])
    if window is None:
        res["problems"].append("no autonomous span found in the log")
    return res


# --------------------------------------------------------------------------- comparing settings

def summarize(results, cfg):
    """B vs A on the same camera, averaged over the runs where each camera had each setting."""
    out = {}
    keys = ("results_per_s", "latency_ms_mean", "jitter_xy_mm", "jitter_yaw_deg", "noise_per_sqrt_s_mm", "max_gap_ms",
            "gap_share_pct")
    for side in ("left", "right"):
        by = {"A": [], "B": []}
        for r in results:
            c = r["cameras"][side]
            if c.get("setting") in by and "jitter_xy_mm" in c and not r["problems"]:
                by[c["setting"]].append(c)
        row = {}
        for k in keys:
            a = [c[k] for c in by["A"] if c.get(k) is not None]
            b = [c[k] for c in by["B"] if c.get(k) is not None]
            if a and b:
                ma, mb = statistics.mean(a), statistics.mean(b)
                row[k] = {"A": ma, "B": mb, "change_pct": (mb - ma) / ma * 100 if ma else None,
                          "n_A": len(a), "n_B": len(b)}
        out[side] = row
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(HERE / "runs.toml"))
    args = ap.parse_args()
    cfg = tomllib.loads(Path(args.config).read_text(encoding="utf-8"))
    results = []
    for run in cfg["runs"]:
        if not run.get("log"):
            print(f"{run['id']}: no log yet; skipped")
            continue
        try:
            results.append(analyze_run(run, cfg))
        except FileNotFoundError as e:
            print(f"{run['id']}: log not found ({e}); skipped")
    print("\nPer run (jitter = scatter around a smooth curve; smaller is better)")
    print(f"{'run':<7}{'cam':<6}{'set':<4}{'res/s':>7}{'lat ms':>8}{'jit xy mm':>10}{'jit yaw°':>9}{'max gap ms':>11}{'gap %':>7}"
          f"{'tags':>6}{'dist m':>7}")
    for r in results:
        for side in ("left", "right"):
            c = r["cameras"][side]
            f = lambda k, fmt: format(c[k], fmt) if c.get(k) is not None else "-"  # noqa: E731
            print(f"{r['id']:<7}{side:<6}{c['setting']:<4}{f('results_per_s', '7.1f')}{f('latency_ms_mean', '8.1f')}"
                  f"{f('jitter_xy_mm', '10.1f')}{f('jitter_yaw_deg', '9.2f')}{f('max_gap_ms', '11.0f')}"
                  f"{f('gap_share_pct', '7.1f')}{f('tags_mean', '6.2f')}{f('distance_m_mean', '7.2f')}")
        lr = r["left_minus_right"]
        if lr.get("bias_xy_mm") is not None:
            print(f"{'':<7}L-R: bias {lr['bias_xy_mm']:.1f} mm / {lr['bias_yaw_deg']:+.2f}°, scatter {lr['scatter_xy_mm']:.1f} mm "
                  f"/ {lr['scatter_yaw_deg']:.2f}° over {lr['pairs']} pairs")
        for p in r["problems"]:
            print(f"{'':<7}!! {p}")
    summ = summarize(results, cfg)
    print("\nSetting B vs A, same camera (needs crossover runs; runs with problems are excluded)")
    for side, row in summ.items():
        for k, v in row.items():
            ch = "-" if v["change_pct"] is None else f"{v['change_pct']:+.0f}%"
            print(f"  {side:<6}{k:<22}A {v['A']:8.2f} (n={v['n_A']})  B {v['B']:8.2f} (n={v['n_B']})  change {ch}")
    out = {"config": args.config, "runs": results, "summary": summ}
    (HERE / "results.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(f"\nwrote {HERE / 'results.json'}")


if __name__ == "__main__":
    main()
